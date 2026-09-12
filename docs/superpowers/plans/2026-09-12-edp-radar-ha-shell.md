# EDP Radar Home Assistant Shell Implementation Plan (Plan 2 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the tested core library (Plan 1) into an installable Home Assistant custom integration: manifest, coordinator with background bootstrap and incremental refresh, UI config/options flow with buyer resolution, devices and sensors, event entities, diagnostics, translations, a Docker dev container with F5 debugging, and README/HACS packaging.

**Architecture:** `__init__.py` builds `RadarStore`, `TedApiClient`, `EcbFxClient` and an `EdpRadarCoordinator` (`DataUpdateCoordinator[RadarSnapshot]`) and stores it in `entry.runtime_data`. The coordinator owns ingestion (bootstrap task, 4-hourly incremental refresh, FX refresh, pruning, event emission via the dispatcher) and computes `RadarSnapshot` in the executor. Entities are thin readers of the snapshot, declared as `EntityDescription`s with `value_fn`/`attributes_fn`, grouped into service devices. Everything user-tunable lives in `ConfigEntry.options`; changing options reloads the entry.

**Tech Stack:** Home Assistant 2026.9.2 (`DataUpdateCoordinator`, `ConfigFlow`/`OptionsFlow`, selectors, `EventEntity`, `SensorEntity`, diagnostics), `pytest-homeassistant-custom-component` (`hass`, `hass_storage`, `aioclient_mock`, `MockConfigEntry`, `freezer`), Docker (`ghcr.io/home-assistant/home-assistant:stable`), debugpy.

**Spec:** `docs/ha-edp-radar_PROJECT.md` §21–29, §33, §42–46, §50 (phases 4–9), §51; `docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md` (D2, D5, D8, D9, D11, D12, D13, D15–D19, D23); reference conventions from `../ha-battaxi` (manifest, entity/sensor patterns, tests, dev container, README).

## Global Constraints

- Same tooling and commit rules as Plan 1 (ruff, `mypy --strict` on the package, conventional commits with the attribution line, commit per task). Run `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components/edp_radar` before each commit.
- No GitHub workflows, no issue templates.
- Entities never make HTTP calls and read only `coordinator.data` (a `RadarSnapshot`).
- `_attr_has_entity_name = True`; unique ids `<entry_id>_<key>`; category entities `<entry_id>_cat_<category_id>_<key>`.
- Devices (D16): manufacturer `TED / Publications Office of the European Union`, model `EDP Radar Analytics`, `DeviceEntryType.SERVICE`, identifiers `(DOMAIN, f"{entry_id}_{device_key}")`.
- Bootstrap runs in a background task (D8); entities report `unknown` until `snapshot.bootstrap_complete` is true; no events for bootstrap notices (plan §42).
- Request pacing/backoff is the client's job (D9); the coordinator never retries inside one refresh.
- Attribute payloads: rankings and recent-item lists capped at 10 entries (plan §49); Decimals converted to `float`, dates to ISO strings.
- Strings: `strings.json` (English source), `translations/en.json` (identical), `translations/sv.json` (Swedish, same keys; tested).
- Country selection uses `CountrySelector` with alpha-2 codes (D2).
- Dev container ports default to `8125`/`5679` (D19).

---

## File structure (this plan)

| File | Responsibility |
| --- | --- |
| `custom_components/edp_radar/manifest.json`, `hacs.json` | Integration metadata (HACS) |
| `custom_components/edp_radar/__init__.py` | `async_setup_entry`, `async_unload_entry`, `async_remove_entry`, options listener, `PLATFORMS` |
| `custom_components/edp_radar/config.py` | `RadarConfig`: parse `ConfigEntry.options` → `MetricsConfig` + query inputs (pure, no HA imports) |
| `custom_components/edp_radar/coordinator.py` | `EdpRadarCoordinator`, bootstrap task, incremental refresh, event dispatch |
| `custom_components/edp_radar/config_flow.py` | `EdpRadarConfigFlow` (7 steps) and `EdpRadarOptionsFlow` (menu) |
| `custom_components/edp_radar/entity.py` | `EdpRadarEntity`, `DeviceKind`, device info |
| `custom_components/edp_radar/sensor.py` | Sensor descriptions and platform setup |
| `custom_components/edp_radar/event.py` | `event.procurement_activity`, `event.watchlist_activity` |
| `custom_components/edp_radar/diagnostics.py` | Config entry diagnostics |
| `custom_components/edp_radar/strings.json`, `translations/en.json`, `translations/sv.json`, `icons.json` | UI text and icons |
| `docker-compose.yml`, `dev/ha.sh`, `dev/config/configuration.yaml`, `.vscode/*`, `.env.example` | Live HA dev container (D19) |
| `README.md`, `LICENSE`, `docs/dashboard-example.yaml` | Documentation and packaging |
| `tests/test_config.py`, `test_init.py`, `test_coordinator.py`, `test_config_flow.py`, `test_sensor.py`, `test_event.py`, `test_diagnostics.py`, `test_translations.py` | Tests |

---

### Task 1: Config parsing, manifest and entry lifecycle

**Files:**
- Create: `custom_components/edp_radar/manifest.json`, `hacs.json`, `custom_components/edp_radar/config.py`, `tests/test_config.py`, `tests/test_init.py`
- Modify: `custom_components/edp_radar/__init__.py`, `tests/conftest.py`
- Create (skeleton, completed in Task 2): `custom_components/edp_radar/coordinator.py`

**Interfaces:**
- `manifest.json`: `{"domain": "edp_radar", "name": "European Defence Procurement Radar", "codeowners": ["@mattahr"], "config_flow": true, "documentation": "https://github.com/mattahr/ha-edp-radar", "integration_type": "service", "iot_class": "cloud_polling", "issue_tracker": "https://github.com/mattahr/ha-edp-radar/issues", "requirements": [], "single_config_entry": true, "version": "0.1.0"}`.
- `hacs.json`: `{"name": "European Defence Procurement Radar", "render_readme": true, "homeassistant": "2026.9.0"}`.
- `config.py`:
  - `@dataclass(frozen=True) class RadarConfig(metrics: MetricsConfig, relevance_mode: RelevanceMode, market_countries: frozenset[str], bootstrap_days: int, retention_days: int)`
  - `RadarConfig.from_options(options: Mapping[str, Any]) -> RadarConfig` — reads the `CONF_*` keys (Task 1 of Plan 1); `market_preset` resolves to `MARKET_PRESET_COUNTRIES` unless `custom`; own organisation dict → `OwnOrganisation.from_options`; watchlist keys → `WatchlistConfig` (min values as `Decimal`); peer preset `nordic|eu|custom|none`.
  - `RadarConfig.universe_query(self, taxonomy: Taxonomy, since: date) -> str` — `TedQueryBuilder.combine_and(publication_range(since), defence_universe(mode, taxonomy.defence_cpv_prefixes), countries(query_countries))` where `query_countries` = market ∪ peer ∪ own-org country ∪ watchlist countries (so peers outside the market are still fetched), or empty when market preset is `ted`.
- `__init__.py`: `PLATFORMS = [Platform.SENSOR, Platform.EVENT]`; `async_setup_entry` creates store/clients/coordinator, `await coordinator.async_setup()`, `await coordinator.async_config_entry_first_refresh()`, sets `entry.runtime_data`, registers `entry.add_update_listener(_async_update_listener)` (reloads), forwards platforms; `async_unload_entry` unloads platforms and `await coordinator.async_shutdown()` (cancels bootstrap, saves store immediately); `async_remove_entry` removes the store.
- `coordinator.py` skeleton exposes `type EdpRadarConfigEntry = ConfigEntry[EdpRadarCoordinator]` and the class with `async_setup`, `async_shutdown`, `_async_update_data` returning a snapshot from the store (full logic in Task 2).

- [ ] **Step 1: Write `tests/test_config.py`**

```python
from datetime import date
from decimal import Decimal

from custom_components.edp_radar.config import RadarConfig
from custom_components.edp_radar.const import (
    CONF_MARKET_COUNTRIES, CONF_MARKET_PRESET, CONF_OWN_ALIASES, CONF_OWN_COUNTRY,
    CONF_OWN_IDENTIFIERS, CONF_OWN_NAME, CONF_OWN_ORGANISATION, CONF_PEER_COUNTRIES,
    CONF_PEER_PRESET, CONF_PINNED_CATEGORIES, CONF_RELEVANCE_MODE, CONF_SELECTED_COUNTRY,
    CONF_WATCHLIST_COUNTRIES, CONF_WATCHLIST_MIN_ESTIMATED_EUR, EU_COUNTRIES,
    NORDIC_COUNTRIES, RelevanceMode,
)
from custom_components.edp_radar.taxonomy import Taxonomy


def test_defaults() -> None:
    config = RadarConfig.from_options({})
    assert config.relevance_mode is RelevanceMode.STRICT
    assert config.market_countries == EU_COUNTRIES
    assert config.metrics.own_organisation is None
    assert config.metrics.peer_countries == frozenset()
    assert config.metrics.watchlist.is_empty
    assert config.bootstrap_days == 400 and config.retention_days == 400


def test_full_options() -> None:
    config = RadarConfig.from_options(
        {
            CONF_RELEVANCE_MODE: "broad",
            CONF_MARKET_PRESET: "custom",
            CONF_MARKET_COUNTRIES: ["SE", "FI"],
            CONF_OWN_ORGANISATION: {
                CONF_OWN_IDENTIFIERS: ["202100-0340"], CONF_OWN_COUNTRY: "SE",
                CONF_OWN_NAME: "FMV", CONF_OWN_ALIASES: ["Försvarets materielverk"],
            },
            CONF_PEER_PRESET: "nordic",
            CONF_SELECTED_COUNTRY: "SE",
            CONF_PINNED_CATEGORIES: ["land_systems"],
            CONF_WATCHLIST_COUNTRIES: ["PL"],
            CONF_WATCHLIST_MIN_ESTIMATED_EUR: 500000000,
        }
    )
    assert config.relevance_mode is RelevanceMode.BROAD
    assert config.market_countries == frozenset({"SE", "FI"})
    assert config.metrics.own_organisation is not None
    assert config.metrics.own_organisation.identifiers == frozenset({"202100-0340"})
    assert config.metrics.peer_countries == NORDIC_COUNTRIES
    assert config.metrics.selected_country == "SE"
    assert config.metrics.pinned_categories == ("land_systems",)
    assert config.metrics.watchlist.countries == frozenset({"PL"})
    assert config.metrics.watchlist.min_estimated_value_eur == Decimal("500000000")


def test_custom_peers_and_query() -> None:
    config = RadarConfig.from_options(
        {CONF_MARKET_PRESET: "nordic", CONF_PEER_PRESET: "custom", CONF_PEER_COUNTRIES: ["PL"]}
    )
    query = config.universe_query(Taxonomy.load(), date(2025, 8, 9))
    assert query.startswith("PD>=20250809 AND (authority-main-activity=defence")
    assert query.endswith("AND (buyer-country IN (DNK FIN ISL NOR POL SWE))")


def test_ted_preset_has_no_country_filter() -> None:
    config = RadarConfig.from_options({CONF_MARKET_PRESET: "ted"})
    assert "buyer-country" not in config.universe_query(Taxonomy.load(), date(2025, 8, 9))
```

- [ ] **Step 2: Implement `config.py`**

```python
"""Translate ConfigEntry options into typed configuration (plan §27–28, §46)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from .const import (
    CONF_MARKET_COUNTRIES, CONF_MARKET_PRESET, CONF_OWN_ALIASES, CONF_OWN_COUNTRY,
    CONF_OWN_IDENTIFIERS, CONF_OWN_NAME, CONF_OWN_ORGANISATION, CONF_PEER_COUNTRIES,
    CONF_PEER_ORGANISATIONS, CONF_PEER_PRESET, CONF_PINNED_CATEGORIES, CONF_RELEVANCE_MODE,
    CONF_SELECTED_COUNTRY, CONF_WATCHLIST_BUYERS, CONF_WATCHLIST_CATEGORIES,
    CONF_WATCHLIST_COUNTRIES, CONF_WATCHLIST_MIN_AWARD_EUR, CONF_WATCHLIST_MIN_ESTIMATED_EUR,
    DEFAULT_BOOTSTRAP_DAYS, DEFAULT_RETENTION_DAYS, MARKET_PRESET_COUNTRIES, MarketPreset,
    RelevanceMode,
)
from .metrics import MetricsConfig, OwnOrganisation, WatchlistConfig
from .query import TedQueryBuilder
from .taxonomy import Taxonomy


def _countries(value: Any) -> frozenset[str]:
    return frozenset(str(c).upper() for c in (value or []))


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", 0):
        return None
    return Decimal(str(value))


@dataclass(frozen=True)
class RadarConfig:
    metrics: MetricsConfig
    relevance_mode: RelevanceMode
    market_countries: frozenset[str]
    market_preset: MarketPreset
    bootstrap_days: int = DEFAULT_BOOTSTRAP_DAYS
    retention_days: int = DEFAULT_RETENTION_DAYS

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> RadarConfig:
        mode = RelevanceMode(options.get(CONF_RELEVANCE_MODE, RelevanceMode.STRICT))
        preset = MarketPreset(options.get(CONF_MARKET_PRESET, MarketPreset.EU))
        market = (
            _countries(options.get(CONF_MARKET_COUNTRIES))
            if preset is MarketPreset.CUSTOM
            else MARKET_PRESET_COUNTRIES[preset]
        )
        own_raw = options.get(CONF_OWN_ORGANISATION) or None
        own = (
            OwnOrganisation.from_options(
                own_raw.get(CONF_OWN_IDENTIFIERS) or [],
                own_raw.get(CONF_OWN_COUNTRY),
                own_raw.get(CONF_OWN_NAME),
                own_raw.get(CONF_OWN_ALIASES) or [],
            )
            if own_raw
            else None
        )
        peer_preset = options.get(CONF_PEER_PRESET, "none")
        if peer_preset == "custom":
            peers = _countries(options.get(CONF_PEER_COUNTRIES))
        elif peer_preset in ("nordic", "eu"):
            peers = MARKET_PRESET_COUNTRIES[MarketPreset(peer_preset)]
        else:
            peers = frozenset()
        watchlist = WatchlistConfig(
            countries=_countries(options.get(CONF_WATCHLIST_COUNTRIES)),
            buyer_identifiers=frozenset(options.get(CONF_WATCHLIST_BUYERS) or []),
            categories=frozenset(options.get(CONF_WATCHLIST_CATEGORIES) or []),
            min_estimated_value_eur=_decimal(options.get(CONF_WATCHLIST_MIN_ESTIMATED_EUR)),
            min_award_value_eur=_decimal(options.get(CONF_WATCHLIST_MIN_AWARD_EUR)),
        )
        metrics = MetricsConfig(
            relevance_mode=mode,
            market_countries=market,
            own_organisation=own,
            peer_countries=peers,
            peer_organisation_identifiers=frozenset(options.get(CONF_PEER_ORGANISATIONS) or []),
            selected_country=options.get(CONF_SELECTED_COUNTRY) or None,
            pinned_categories=tuple(options.get(CONF_PINNED_CATEGORIES) or []),
            watchlist=watchlist,
        )
        return cls(metrics, mode, market, preset)

    @property
    def query_countries(self) -> frozenset[str]:
        """Countries to fetch: market plus peers, own organisation and watchlist."""
        if self.market_preset is MarketPreset.TED:
            return frozenset()
        extra: set[str] = set(self.metrics.peer_countries) | set(self.metrics.watchlist.countries)
        own = self.metrics.own_organisation
        if own is not None and own.country:
            extra.add(own.country)
        return self.market_countries | extra

    def universe_query(self, taxonomy: Taxonomy, since: date) -> str:
        return TedQueryBuilder.combine_and(
            TedQueryBuilder.publication_range(since),
            TedQueryBuilder.defence_universe(self.relevance_mode, taxonomy.defence_cpv_prefixes),
            TedQueryBuilder.countries(self.query_countries),
        )
```

- [ ] **Step 3: Write `manifest.json`, `hacs.json`, the coordinator skeleton, `__init__.py`**

`coordinator.py` (skeleton; Task 2 fills the ingestion):

```python
"""DataUpdateCoordinator: ingestion, storage, metrics (plan §33, D8, D9, D11)."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import TedApiClient
from .config import RadarConfig
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .fx import EcbFxClient
from .metrics import RadarSnapshot, compute_snapshot
from .storage import RadarStore
from .taxonomy import Taxonomy

_LOGGER = logging.getLogger(__name__)

type EdpRadarConfigEntry = ConfigEntry[EdpRadarCoordinator]


class EdpRadarCoordinator(DataUpdateCoordinator[RadarSnapshot]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: EdpRadarConfigEntry,
        *,
        client: TedApiClient,
        fx_client: EcbFxClient,
        store: RadarStore,
        taxonomy: Taxonomy,
    ) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=DEFAULT_UPDATE_INTERVAL
        )
        self.entry = entry
        self.client = client
        self.fx_client = fx_client
        self.store = store
        self.taxonomy = taxonomy
        self.config = RadarConfig.from_options(entry.options)
        self.last_ted_error: str | None = None
        self.last_fx_error: str | None = None

    async def async_setup(self) -> None:
        await self.store.async_load()

    async def async_shutdown(self) -> None:
        await self.store.async_save(immediate=True)
        await super().async_shutdown()

    async def _async_compute(self, *, bootstrap_complete: bool) -> RadarSnapshot:
        today = dt_util.now().date()
        return await self.hass.async_add_executor_job(
            lambda: compute_snapshot(
                list(self.store.notices.values()),
                self.store.fx,
                self.config.metrics,
                today,
                taxonomy=self.taxonomy,
                parse_errors=self.store.index.parse_errors,
                bootstrap_complete=bootstrap_complete,
                computed_at=datetime.now(tz=dt_util.UTC),
            )
        )

    async def _async_update_data(self) -> RadarSnapshot:
        return await self._async_compute(bootstrap_complete=self.store.index.bootstrap_complete)
```

`__init__.py`:

```python
"""European Defence Procurement Radar for Home Assistant."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TedApiClient
from .config import RadarConfig
from .coordinator import EdpRadarConfigEntry, EdpRadarCoordinator
from .fx import EcbFxClient
from .storage import RadarStore
from .taxonomy import Taxonomy

PLATFORMS = [Platform.SENSOR, Platform.EVENT]


async def async_setup_entry(hass: HomeAssistant, entry: EdpRadarConfigEntry) -> bool:
    """Set up the radar from a config entry."""
    session = async_get_clientsession(hass)
    config = RadarConfig.from_options(entry.options)
    coordinator = EdpRadarCoordinator(
        hass,
        entry,
        client=TedApiClient(session),
        fx_client=EcbFxClient(session),
        store=RadarStore(hass, entry.entry_id, retention_days=config.retention_days),
        taxonomy=Taxonomy.load(),
    )
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: EdpRadarConfigEntry) -> None:
    """Options changed: reload so devices and entities follow the new configuration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: EdpRadarConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: EdpRadarConfigEntry) -> None:
    """Delete stored notices when the integration is removed."""
    store = RadarStore(hass, entry.entry_id)
    await store.async_load()
    await store.async_remove()
```

- [ ] **Step 4: Extend `tests/conftest.py` with a config entry fixture and a mocked TED/ECB backend**

```python
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.edp_radar.const import DOMAIN, ECB_90D_URL, ECB_HISTORY_URL

@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, entry_id="test-entry", title="European Defence Procurement Radar", unique_id=DOMAIN, data={}, options={})


@pytest.fixture
def mock_backend(aioclient_mock: AiohttpClientMocker, real_notices: list[dict[str, Any]]) -> AiohttpClientMocker:
    """TED answers every search with the 18 real notices (one page); ECB with fixtures."""
    async def handler(method: str, url: Any, data: dict[str, Any]) -> AiohttpClientMockResponse:
        if data.get("checkQuerySyntax"):
            return AiohttpClientMockResponse(method, url, json={"notices": [], "totalNoticeCount": None})
        if data.get("iterationNextToken") or data.get("page", 1) > 1:
            return AiohttpClientMockResponse(method, url, json={"notices": [], "totalNoticeCount": 18})
        return AiohttpClientMockResponse(method, url, json={"notices": real_notices, "totalNoticeCount": 18, "iterationNextToken": "t"})
    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    aioclient_mock.get(ECB_90D_URL, text=(FIXTURES / "ecb" / "hist-90d.xml").read_text())
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("eurofxref-hist.csv", (FIXTURES / "ecb" / "hist.csv").read_text())
    aioclient_mock.get(ECB_HISTORY_URL, content=buffer.getvalue())
    return aioclient_mock
```

- [ ] **Step 5: Write `tests/test_init.py`**

```python
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.edp_radar.const import DOMAIN


async def test_setup_and_unload(hass: HomeAssistant, mock_backend: AiohttpClientMocker, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.data is not None
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_remove_entry_deletes_storage(hass: HomeAssistant, mock_backend: AiohttpClientMocker, config_entry: MockConfigEntry, hass_storage: dict) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert not [k for k in hass_storage if k.startswith(f"{DOMAIN}.{config_entry.entry_id}")]
```

- [ ] **Step 6: Run, lint, commit**

Run: `uv run pytest tests/test_config.py tests/test_init.py -v` — expected: all pass (setup completes even though bootstrap is not finished; the snapshot has `bootstrap_complete=False`).

```bash
git add custom_components hacs.json tests
git commit -m "feat: add manifest, config parsing and config entry lifecycle

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Coordinator — bootstrap, incremental refresh, FX, events

**Files:**
- Modify: `custom_components/edp_radar/coordinator.py`
- Create: `tests/test_coordinator.py`

**Interfaces:**
- `SIGNAL_ACTIVITY = f"{DOMAIN}_activity_{{entry_id}}"`, `SIGNAL_WATCHLIST = f"{DOMAIN}_watchlist_{{entry_id}}"` (formatted with the entry id); payload `(event_type: str, attributes: dict[str, Any])`.
- `EdpRadarCoordinator`:
  - `bootstrap_progress: tuple[int, int | None] | None` (fetched, total) while bootstrapping.
  - `async_setup()` loads the store and, when `bootstrap_complete` is false, starts `self._bootstrap_task = self.entry.async_create_background_task(hass, self._async_bootstrap(), "edp_radar bootstrap")`.
  - `_async_bootstrap()`: FX history (errors logged, non-fatal) → iterate `config.universe_query(taxonomy, today - bootstrap_days)` with `progress` callback → `normalize_many` per page → `store.upsert_many` → every 10 pages `store.async_save()` (delayed) → on completion: `index.bootstrap_complete = True`, `index.last_publication_date = max`, `index.taxonomy_version`, `store.mark_events_emitted(all version keys)`, `await store.async_save(immediate=True)`, `self.async_set_updated_data(await self._async_compute(bootstrap_complete=True))`. On `TedApiError`: log warning, keep `bootstrap_complete=False`, and reschedule via `async_call_later(hass, 900, ...)`.
  - `_async_update_data()`: if not bootstrapped → ensure task running and return the (partial) snapshot. Else `_async_incremental_refresh()`: `since = (index.last_publication_date or today - bootstrap_days) - INCREMENTAL_OVERLAP_DAYS` → fetch/normalize/upsert collecting new version keys → FX `async_fetch_recent()` (errors logged into `last_fx_error`) → `store.prune(today)` → update index → `store.async_save()` → compute snapshot → emit events for new keys not `was_event_emitted` (post-bootstrap only), mark emitted. On `TedApiTemporaryError`/`TedApiError`: record `last_ted_error`; if the store has notices, log and return the snapshot from stored data (D25 — entities stay available); if the store is empty raise `UpdateFailed`.
  - `_emit(notice)`: `event_type_for(notice)`; if not None → `async_dispatcher_send(hass, SIGNAL_ACTIVITY..., event_type, notice_event_attributes(notice, store.fx))`; if `watchlist_matches(notice, config.metrics.watchlist, store.fx)` → `async_dispatcher_send(... SIGNAL_WATCHLIST ...)`.
  - `async_shutdown()` cancels the bootstrap task, saves immediately.

- [ ] **Step 1: Write the tests** (`tests/test_coordinator.py`)

Cover: (a) fresh entry → bootstrap task runs → `data.bootstrap_complete` becomes True, store index saved with `bootstrap_complete`, no events dispatched (assert a dispatcher listener saw nothing); (b) second setup with stored data → no bootstrap fetch (count TED calls == 1 incremental), incremental query starts from `last_publication_date - 2 days`; (c) a new notice in the incremental page dispatches exactly one activity event and is not re-emitted on the next refresh; (d) TED 503 during refresh → `last_ted_error` set, `data` still a snapshot, `last_update_success` True; (e) TED 503 during refresh with empty store → `UpdateFailed`; (f) ECB failure → `last_fx_error` set, refresh succeeds; (g) watchlist event when options include a matching country. Use `freezer` to fix today; use `async_fire_time_changed` to trigger scheduled refreshes; use `hass.async_block_till_done()` after setup to let the background bootstrap finish.

Write each test with concrete assertions against `aioclient_mock.mock_calls` (query strings contain `PD>=...`) and `hass_storage`.

- [ ] **Step 2: Implement**

```python
SIGNAL_ACTIVITY = f"{DOMAIN}_activity_{{}}"
SIGNAL_WATCHLIST = f"{DOMAIN}_watchlist_{{}}"
BOOTSTRAP_RETRY_SECONDS = 900
SAVE_EVERY_PAGES = 10


class EdpRadarCoordinator(DataUpdateCoordinator[RadarSnapshot]):
    ...
    @property
    def signal_activity(self) -> str:
        return SIGNAL_ACTIVITY.format(self.entry.entry_id)

    @property
    def signal_watchlist(self) -> str:
        return SIGNAL_WATCHLIST.format(self.entry.entry_id)

    async def async_setup(self) -> None:
        await self.store.async_load()
        self.store.index.retention_days = self.config.retention_days
        self._ensure_bootstrap()

    def _ensure_bootstrap(self) -> None:
        if self.store.index.bootstrap_complete or self._bootstrap_task is not None:
            return
        self._bootstrap_task = self.entry.async_create_background_task(
            self.hass, self._async_bootstrap(), f"{DOMAIN} bootstrap"
        )

    async def _async_ingest(self, query: str, *, progress=None) -> list[ProcurementNotice]:
        """Fetch, normalize and store; return the notice versions that were new."""
        new: list[ProcurementNotice] = []
        pages = 0
        page: list[dict[str, Any]] = []
        async for raw in self.client.async_search_notices(query, REQUESTED_FIELDS, progress=progress):
            page.append(raw)
            if len(page) >= 200:
                new.extend(self._store_page(page)); page = []; pages += 1
                if pages % SAVE_EVERY_PAGES == 0:
                    await self.store.async_save()
        new.extend(self._store_page(page))
        return new

    def _store_page(self, page: list[dict[str, Any]]) -> list[ProcurementNotice]:
        notices, errors = normalize_many(page, self.taxonomy)
        self.store.index.parse_errors += errors
        return [n for n in notices if self.store.upsert(n)]

    async def _async_bootstrap(self) -> None:
        today = dt_util.now().date()
        try:
            await self._async_refresh_fx(history=True)
            since = today - timedelta(days=self.config.bootstrap_days)
            self.bootstrap_progress = (0, None)
            new = await self._async_ingest(self.config.universe_query(self.taxonomy, since), progress=self._on_progress)
        except TedApiError as err:
            _LOGGER.warning("Bootstrap failed (%s); retrying in %s s", err, BOOTSTRAP_RETRY_SECONDS)
            self.last_ted_error = str(err)
            self._bootstrap_task = None
            self.bootstrap_progress = None
            async_call_later(self.hass, BOOTSTRAP_RETRY_SECONDS, lambda _: self._ensure_bootstrap())
            return
        self.store.mark_events_emitted(n.version_key for n in self.store.notices.values())
        self._finish_refresh(today, new)
        self.store.index.bootstrap_complete = True
        await self.store.async_save(immediate=True)
        self.bootstrap_progress = None
        self._bootstrap_task = None
        self.async_set_updated_data(await self._async_compute(bootstrap_complete=True))
```

(Continue with `_async_incremental_refresh`, `_async_refresh_fx`, `_finish_refresh` (prune, `last_successful_update`, `last_publication_date`, `taxonomy_version`), `_emit_events`, `_async_update_data` as specified in the Interfaces block; catch `TedApiError` around the incremental fetch and apply D25.)

- [ ] **Step 3: Run tests, lint, type-check, commit**

```bash
git commit -m "feat(coordinator): background bootstrap, incremental refresh, FX refresh and event dispatch"
```

---

### Task 3: Config flow and options flow

**Files:**
- Create: `custom_components/edp_radar/config_flow.py`, `custom_components/edp_radar/strings.json`, `translations/en.json`, `translations/sv.json`, `tests/test_config_flow.py`, `tests/test_translations.py`

**Interfaces:**
- Config flow steps (plan §27): `user` (relevance mode radio, market preset) → `countries` (only for `custom`; `CountrySelector(multiple=True)`) → `organisation` (boolean "track a selected organisation") → `organisation_search` (country + search term; queries TED `buyer-name ~ (...)` over `today-400d` with fields `buyer-name, buyer-identifier, buyer-country`, groups hits by identifier tuple, shows up to 25 candidates as `SelectSelector` options labelled `"<name> · <identifiers>"`; errors `cannot_connect`, `no_matches`) → `organisation_select` (pick candidate; stores `{identifiers, country, canonical_name, aliases: [all names seen]}`) → `peers` (peer preset `none|nordic|eu|custom`, selected country `CountrySelector`) → `peer_countries` (custom only) → `categories` (multi-select of `Taxonomy.category_ids` with labels) → `watchlist` (countries multi, min estimated EUR number, min award EUR number; all optional) → `async_create_entry(title=NAME, data={}, options=...)`. `single_config_entry` in the manifest prevents duplicates.
- Options flow: `init` shows a menu with the same six sections; each section step pre-fills current values and, on submit, `async_create_entry(data={**current_options, **changes})` (the update listener reloads the entry). Organisation section re-runs the search/select sub-steps and offers a "clear" toggle.
- Buyer resolution helper (pure, tested): `group_buyer_candidates(raws: Iterable[Mapping]) -> list[BuyerCandidate(identifiers: tuple[str, ...], country: str | None, names: tuple[str, ...], notices: int)]` sorted by notice count desc.

- [ ] **Step 1: Write `strings.json`** with `config.step.*` (titles, descriptions, data labels, `data_description`), `config.error` (`cannot_connect`, `no_matches`, `invalid_selection`), `config.abort` (`single_instance_allowed`), `options.step.*` mirroring the config steps, `options.step.init.menu_options`, `selector.*` option labels for relevance mode/presets, and `entity.sensor.*.name` + `entity.event.*.name` for every entity key defined in Tasks 4–5. Copy to `translations/en.json`; write `translations/sv.json` with Swedish text (entity names e.g. `Nya upphandlingar 30 d`, `Uppskattat värde 90 d`, `Största externa upphandling 7 d`, `Egen organisation: offentliga upphandlingar 30 d`, …).
- [ ] **Step 2: Write the tests** — full user flow without organisation; with organisation (mock TED buyer search returning two candidate buyers from `real_notices`); `no_matches`; `cannot_connect` (TED 503); custom countries; options flow changing relevance mode reloads the entry and updates `runtime_data.config`; translations key-equality test (copied from ha-battaxi) plus a Swedish entity-name spot check.
- [ ] **Step 3: Implement** the flow (use `SelectSelector`, `CountrySelector`, `BooleanSelector`, `NumberSelector(mode=BOX, unit "EUR")`; keep step methods small; put schema builders in module functions). Validate the final universe query with `client.async_validate_query` before creating the entry (error `cannot_connect` on failure).
- [ ] **Step 4: Run tests, lint, commit** — `feat(config_flow): UI setup with buyer resolution and options menu`.

---

### Task 4: Devices and sensors

**Files:**
- Create: `custom_components/edp_radar/entity.py`, `custom_components/edp_radar/sensor.py`, `custom_components/edp_radar/icons.json`, `tests/test_sensor.py`

**Interfaces:**
- `entity.py`: `class DeviceKind(StrEnum)`: `MARKET="market"`, `EXTERNAL="external"`, `ORGANISATION="organisation"`, `PEERS="peers"`, `SUPPLIERS="suppliers"`, `CATEGORY="category"`; `device_info(entry_id, kind, *, category_label=None) -> DeviceInfo` (names: "European Defence Market", "External Radar", "Selected Organisation", "Peer Comparison", "Supplier Landscape", "Pinned Category: <label>"); `class EdpRadarEntity(CoordinatorEntity[EdpRadarCoordinator])` with `_attr_has_entity_name = True`, unique id, device info, `snapshot` property, and `available` = coordinator success **and** `snapshot.bootstrap_complete` (so entities read `unavailable`→ no: plan says `unknown` during bootstrap — implement as: `available` follows the coordinator; `native_value` returns `None` until bootstrap completes).
- `sensor.py`: `@dataclass(frozen=True, kw_only=True) class EdpRadarSensorEntityDescription(SensorEntityDescription)`: `device: DeviceKind`, `value_fn: Callable[[RadarSnapshot], StateType | datetime]`, `attributes_fn: Callable[[RadarSnapshot], dict[str, Any]] | None = None`, `exists_fn: Callable[[RadarConfig], bool] = lambda c: True`. Category sensors use a separate description class with `category_id` bound at setup.
- Helper converters: `_eur(value: Decimal | None) -> float | None`, `_ranking_attrs(ranking) -> dict` (`population`, `population_size`, `ranking: [{rank, key, label, value_eur, procedures, previous_value_eur, change_pct}]`), `_count_attrs(metric)`, `_value_attrs(metric)`, `_highlight_attrs(h)`, `_median_attrs`, `_share_attrs`.

Sensor table (state → unit/class; attributes):

| key | device | state | attributes |
| --- | --- | --- | --- |
| `market_new_competitions_30d` / `_90d` | market | count (`state_class=measurement`) | `previous_period`, `change`, `change_pct`, `period_days` |
| `market_estimated_value_30d` / `_90d` | market | EUR float (`device_class=monetary`, unit `EUR`) | `previous_period_eur`, `change_pct`, `sample_size`, `covered_records`, `coverage_pct`, `period_days` |
| `market_award_value_30d` / `_90d` | market | EUR | same as above |
| `top_country_by_value_90d` | market | alpha-2 | `_ranking_attrs` |
| `fastest_growing_country_90d` | market | alpha-2 | growth ranking attrs |
| `top_category_by_value_90d`, `fastest_growing_category_90d` | market | category label | ranking attrs (keys are category ids, labels included) |
| `largest_country_change_90d`, `largest_category_change_90d` | market | key/label | `current_value_eur`, `previous_value_eur`, `change_eur`, `change_pct`, `current_procedures`, `previous_procedures` |
| `market_snapshot_text`, `country_ranking_text` | market | text | – |
| `market_median_tenders_365d` | market | float | `sample_size`, `coverage_pct`, `population` |
| `market_single_bid_share_365d` | market | % | `single_bid_lot_results`, `lot_results_with_bid_count`, `coverage_pct` |
| `market_median_public_time_to_result_365d` | market | days | `sample_size`, `procedure_link_coverage_pct` |
| `market_non_award_share_365d` (disabled by default) | market | % | `non_awarded_lot_results`, `decided_lot_results`, `coverage_pct` |
| `ted_data_last_updated` (diagnostic, disabled by default, `device_class=timestamp`) | market | last successful update | `latest_publication_date`, `stored_notices`, `stored_procedures`, `bootstrap_complete`, `bootstrap_progress`, `last_ted_error`, `last_fx_error`, `fx_latest_date` |
| `external_new_competitions_7d` | external | count | `recent: [highlight × ≤10]` |
| `largest_external_competition_7d`, `largest_external_award_7d` | external | EUR or None | `title`, `buyer`, `country`, `publication_date`, `original_value`, `original_currency`, `value_eur`, `categories`, `ted_url` |
| `external_latest_text` | external | text | – |
| `own_public_competitions_30d`, `own_public_awards_30d`, `own_public_changes_30d`, `own_public_modifications_365d` | organisation (exists when own configured) | count | count attrs |
| `own_public_estimated_value_30d`, `own_public_award_value_30d` | organisation | EUR | value attrs |
| `own_median_tenders_365d`, `own_single_bid_share_365d`, `own_median_public_time_to_result_365d`, `own_non_award_share_365d` (last disabled) | organisation | as market | as market |
| `peer_median_tenders_365d`, `peer_single_bid_share_365d`, `peer_median_public_time_to_result_365d` | peers (exists when peers/selected country configured) | as market | + `population`, `population_size` |
| `selected_country_value_rank_90d`, `selected_country_activity_rank_90d`, `selected_country_value_percentile_90d` | peers | int / % | `population`, `population_size`, `country` |
| `own_vs_peer_single_bid_delta_pp`, `own_vs_peer_median_tenders_delta`, `own_vs_peer_public_time_to_result_delta_days` | peers (exists when own **and** peers) | float | `own_value`, `peer_value` |
| `top_supplier_by_award_value_365d` (disabled) | suppliers | name | `ranking` top 10, `coverage_pct`, `total_award_value_eur`, `groups` |
| `supplier_top5_share_365d` (disabled) | suppliers | % | same |
| `competitions_30d`, `competitions_change_pct`, `estimated_value_90d`, `estimated_value_change_pct`, `award_value_90d` | category (one device per pinned category) | count / % / EUR | count/value attrs |

- [ ] **Step 1: Tests** — set up the entry with `mock_backend`, wait for bootstrap, then assert a representative set of states/attributes computed from the 18 fixture notices (e.g. `sensor.european_defence_market_new_competitions_30d` after freezing time to 2026-09-12 = number of unique procedures with an original competition published in (Aug 13, Sep 12]), `top_country_by_value_90d` state and `ranking` length, `largest_external_competition_7d` attributes, entities absent when own org is not configured and present when it is, disabled-by-default entities registered but disabled, category devices created for pinned categories.
- [ ] **Step 2: Implement** `entity.py`, `sensor.py`, `icons.json` (mdi icons: `mdi:radar`, `mdi:gavel`, `mdi:cash-multiple`, `mdi:flag`, `mdi:trending-up`, `mdi:office-building`, `mdi:account-group`, `mdi:factory`, `mdi:text`).
- [ ] **Step 3: Run tests, lint, commit** — `feat(sensor): devices and sensors reading RadarSnapshot`.

---

### Task 5: Event entities

**Files:**
- Create: `custom_components/edp_radar/event.py`, `tests/test_event.py`

**Interfaces:**
- `EdpRadarActivityEvent(EdpRadarEntity, EventEntity)`: key `procurement_activity`, device market, `_attr_event_types = ["new_competition", "change", "result", "contract_modification"]`; subscribes to `coordinator.signal_activity` in `async_added_to_hass` (`async_dispatcher_connect`, unsubscribed via `async_on_remove`) and calls `_trigger_event(event_type, attributes)` + `async_write_ha_state()`.
- `EdpRadarWatchlistEvent`: key `watchlist_activity`, same event types, subscribes to `coordinator.signal_watchlist`; created only when the watchlist is not empty.

- [ ] **Step 1: Tests** — after setup, dispatch a signal and assert `event.european_defence_market_procurement_activity` state changes and attributes contain the facts; watchlist entity absent by default and present with a watchlist option.
- [ ] **Step 2: Implement; Step 3: commit** — `feat(event): procurement activity and watchlist event entities`.

---

### Task 6: Diagnostics

**Files:**
- Create: `custom_components/edp_radar/diagnostics.py`, `tests/test_diagnostics.py`

**Interfaces:** `async_get_config_entry_diagnostics(hass, entry) -> dict` with: `integration_version` (from the manifest via `async_get_integration`), `options` (verbatim; nothing sensitive), `config` summary (mode, market countries, peers, pinned categories, own organisation identifiers), `taxonomy_version`, `store` (`schema_version`, `partitions`, `bootstrap_complete`, `bootstrap_progress`, `last_successful_update`, `last_publication_date`, `stored_versions`, `stored_notices`, `stored_procedures`, `parse_errors`, `emitted_event_keys`), `quality` (all `DataQualityMetrics` fields; `Coverage` as `{covered, population, pct}`), `errors` (`last_ted_error`, `last_fx_error`), `fx` (`latest_date`, `dates`, `currencies`). No notices are dumped (plan §44).

- [ ] **Step 1: Test** the diagnostics dict shape after setup; **Step 2: Implement; Step 3: commit** — `feat: add config entry diagnostics`.

---

### Task 7: Docker dev container with F5 debugging (D19)

**Files:**
- Create: `docker-compose.yml`, `dev/ha.sh` (executable), `dev/config/configuration.yaml`, `.vscode/launch.json`, `.vscode/tasks.json`, `.vscode/settings.json`, `.vscode/extensions.json`, `.env.example`

- [ ] **Step 1:** Copy the files from `../ha-battaxi` verbatim, then change: container/project name `ha-edp-radar`; default ports `HA_PORT=8125`, `DEBUGPY_PORT=5679` in `docker-compose.yml` (`"${HA_PORT:-8125}:8123"`, `"${DEBUGPY_PORT:-5679}:5678"`), `dev/ha.sh` (`HA_PORT="${HA_PORT:-8125}"`, `DEBUGPY_PORT="${DEBUGPY_PORT:-5679}"`, `CONTAINER="ha-edp-radar"`) and `.vscode/launch.json` (`"port": 5679`); logger target `custom_components.edp_radar: debug`; `.env.example` documents 8125/5679.
- [ ] **Step 2: Smoke test** — `dev/ha.sh up`; open http://localhost:8125, complete onboarding, add the integration, watch `dev/ha.sh logs` for the bootstrap (≈150 requests, several minutes) and confirm the market sensors leave `unknown`. Record the observed bootstrap duration and store sizes in `docs/data-profile.md` under a new "Live bootstrap" heading. `dev/ha.sh down` afterwards.
- [ ] **Step 3: commit** — `feat: add Docker dev environment with F5 debugpy attach`.

---

### Task 8: README, LICENSE, example dashboard, final verification

**Files:**
- Create: `README.md`, `LICENSE` (MIT, copyright Mattias Ahrens 2026 — confirm the name/licence with the owner before writing), `docs/dashboard-example.yaml`

- [ ] **Step 1:** README in English following the ha-battaxi structure: purpose ("factual radar, no interpretation"), data sources and update cadence (4 h; TED publishes Mon–Fri), installation (HACS custom repository, manual), configuration steps, devices/entities table with definitions and coverage attributes (copy definitions from the plan §16–19 wording), currency normalization note (ECB reference rate at event date, backwards fallback; unconvertible amounts reduce coverage), framework agreements note (D21), central purchasing note (D5), limitations (public-data only, TED publication timing ≠ lead time, CPV-only categories leave ~56 % unclassified), dashboard examples (tile cards, markdown template card iterating `ranking` attributes), development section (uv, pytest, F5 flow, `scripts/data_profile.py`).
- [ ] **Step 2:** `docs/dashboard-example.yaml` with a snapshot tile grid, a history graph for the 30-day sensors, a markdown card for the country ranking and an entities card for the peer comparison.
- [ ] **Step 3:** Final verification: `uv run pytest`, ruff, mypy, `uv run python -m json.tool custom_components/edp_radar/manifest.json`, HACS validation by inspection (`hacs.json`, `manifest.json` keys), and one more container smoke test.
- [ ] **Step 4: commit** — `docs: README, HACS packaging and example dashboard`.

---

## Self-review notes

- **Spec coverage:** §21 devices → Task 4; §22 MVP entities → Task 4 table (every listed sensor present; competition metrics enabled since Phase 0 showed 88 % bid-count coverage); §23 events → Task 5; §24 watchlist → Tasks 1 (config), 2 (dispatch), 5 (entity); §25 texts → Task 4; §27–28 flows → Task 3; §29–30 update strategy/bootstrap → Task 2; §33 coordinator → Tasks 1–2; §42 dedup → Task 2 (`was_event_emitted`); §43 failure handling → Task 2 (D25 refinement: stale snapshot instead of `UpdateFailed` when stored data exists); §44 diagnostics → Task 6; §45 freshness sensor → Task 4; §46 conventions → all; §47 config-flow/sensor tests → Tasks 3–6; §50 Phase 9 minus workflows → Task 8; D19 → Task 7.
- **Decision recorded here:** D25 — on a failed incremental refresh the coordinator keeps serving the snapshot computed from stored data and exposes `last_ted_error` (diagnostics + freshness sensor); `UpdateFailed` is raised only when there is nothing stored yet. Add to the addendum when Task 2 lands.
- **Open items for the owner:** LICENSE holder name; whether to add an "Infrastructure & facilities" category (addendum §4).

# Phase 3 Spending Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Sweden-centred defence-spending data layer (Statskontoret, Eurostat `gov_ev`, NATO, EDA, SIPRI) with automatic discovery, provenance-carrying datapoints, per-source storage, an isolated coordinator, diagnostics and the generated source profile — no entities yet.

**Architecture:** A new package `custom_components/edp_radar/spending/` holds frozen models, a source/metric registry, one provider module per source (pure synchronous parsers + thin async discovery/fetch), `SpendingStore` (one HA `Store` per source), `SpendingCoordinator` (6 h tick, per-source check cadence, failures isolated) and pure freshness/calculation helpers. `entry.runtime_data` becomes `RuntimeData(radar, spending)`. Scripts regenerate fixtures and `docs/phase3-source-profile.md` from cached downloads.

**Tech Stack:** Python 3.14, Home Assistant 2026.9.2, aiohttp (HA session), `openpyxl==3.1.5` (first third-party requirement), stdlib `csv`/`zipfile`/`html.parser`/`json`, pytest-homeassistant-custom-component, ruff, mypy --strict.

**Spec:** `docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md` §7 (decisions S1–S20, verified source facts §7.1) implementing `docs/ha-edp-radar_PHASE3_SWEDEN_DEFENCE_SPENDING.md` (plan steps 1–7). Earlier decisions D1–D26 and P1–P12 in the same addendum still apply (D2 alpha-2 country codes, D12 storage style, D13 tooling, D14 script pattern, D15 language).

## Global Constraints

- Python `>=3.14.2`; Home Assistant `2026.9.2`; `pytest-homeassistant-custom-component==0.13.365`; `uv` with the `dev` dependency group (D13).
- Quality gate before every commit: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components/edp_radar` — all green, 200 existing tests keep passing.
- Code, docstrings, `strings.json`, README and docs in English; conversation with the owner in Swedish (D15). No `strings.json`/translation changes in this plan (S20).
- Country codes are ISO 3166-1 alpha-2 everywhere (`SE`, `GR`, `GB`) (D2, S7).
- The focus country is hard-coded `"SE"` (S2).
- No third-party dependency other than `openpyxl==3.1.5` (S3); no PDF parsing, no browser automation (plan §63, §88).
- A missing expected column/sheet/table/dimension raises `SchemaChangedError`; never emit zero/empty values instead (S12, plan §65).
- Values are `Decimal` in the source unit; no FX, no rounding in the data layer (S6).
- Rankings never mix sources (S8, plan §48). No synthetic totals across sources (plan §60).
- Commits: conventional messages, direct on `main` (owner decision), each ending with `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`. Never push unless the owner says so.
- Scripts run with `PYTHONPATH=. uv run python scripts/<name>.py` (D14); downloads cache under `.cache/spending/` (git-ignored); the profile document contains aggregates and provenance only.
- Fixtures under `tests/fixtures/spending/<source>/` are trimmed **real** files captured 2026-09-12, produced by `scripts/fetch_spending_fixtures.py` (S18). Never hand-edit numbers in a fixture.

---

## File structure

| Path | Responsibility |
| --- | --- |
| `custom_components/edp_radar/manifest.json`, `pyproject.toml` | add `openpyxl==3.1.5` (runtime requirement + dev group, `types-openpyxl` for mypy) |
| `custom_components/edp_radar/spending/__init__.py` | package docstring only |
| `custom_components/edp_radar/spending/models.py` | `DatapointStatus`, `Cadence`, `ReferencePeriod`, `SourceRelease`, `SpendingDataPoint`, `DatapointKey`, `Revision`, `ProviderState`, `ProviderHealth`, `SourceSeries`, `MetricSpec`, `SourceSpec` + `to_dict`/`from_dict` (S4, S5) |
| `custom_components/edp_radar/spending/countries.py` | label → alpha-2 tables for NATO/EDA/SIPRI labels, Eurostat code fixes, skip sets, `resolve_country()` (S7) |
| `custom_components/edp_radar/spending/registry.py` | `SOURCES`, `METRICS`, `source_spec()`, `metric_spec()`, `FOCUS_COUNTRY = "SE"` (S8, S2) |
| `custom_components/edp_radar/spending/providers/__init__.py` | `all_providers()` factory in registry order |
| `custom_components/edp_radar/spending/providers/base.py` | `SpendingProvider` protocol, `ParseResult`, `FetchResult`, errors, `async_fetch_bytes()` with conditional headers, `sha256_hex()` (S12) |
| `custom_components/edp_radar/spending/providers/statskontoret.py` | discovery-page parser (`html.parser`), Zip→CSV parser, monthly datapoints (S9) |
| `custom_components/edp_radar/spending/providers/eurostat.py` | fixed API request, JSON-stat decoding by dimension codes (S10) |
| `custom_components/edp_radar/spending/xlsx.py` | openpyxl helpers: load bytes read-only, header/row scanning, numeric coercion, year headers, font colour index (S11) |
| `custom_components/edp_radar/spending/providers/nato.py` | topic-page discovery, `Table 1/2/3/8a` parser, derived equipment value (S11) |
| `custom_components/edp_radar/spending/providers/eda.py` | portal discovery of every `Defence Data YYYY` workbook ≥ 2022, `Member States` + `Billions` parsers (S11) |
| `custom_components/edp_radar/spending/providers/sipri.py` | landing-page discovery (xlsx link + revision date), three sheets, blue-font estimates, note markers (S11) |
| `custom_components/edp_radar/spending/freshness.py` | ages and `freshness_state()` (S15) |
| `custom_components/edp_radar/spending/calculations.py` | `ytd`, `latest_month`, `nominal_change_pct`, `rank`, `nordic_subset` (S16) |
| `custom_components/edp_radar/spending/store.py` | `SpendingStore`: one `Store` per source, `apply_release()` diff + revisions (S13) |
| `custom_components/edp_radar/spending/coordinator.py` | `SpendingCoordinator`, `SpendingSnapshot`, cadence gating, isolation (S14) |
| `custom_components/edp_radar/__init__.py` | `RuntimeData`, second coordinator, unload/remove (S1) |
| `custom_components/edp_radar/diagnostics.py`, `event.py`, `services.py`, `sensor.py` | `.radar` readers; `spending` diagnostics section (S1, S17) |
| `scripts/fetch_spending_fixtures.py` | download + trim real fixtures (S18) |
| `scripts/spending_profile.py` | cache every source, run providers, write `docs/phase3-source-profile.md` (S18) |
| `docs/providers/{statskontoret,eurostat,nato,eda,sipri}.md` | provider documents (plan §68) |
| `tests/spending/` | unit tests (`test_models.py`, `test_countries.py`, `test_registry.py`, `test_base.py`, `test_statskontoret.py`, `test_eurostat.py`, `test_xlsx.py`, `test_nato.py`, `test_eda.py`, `test_sipri.py`, `test_freshness.py`, `test_calculations.py`, `test_store.py`, `test_coordinator.py`) |
| `tests/test_init.py`, `tests/test_diagnostics.py` | wiring and diagnostics assertions |

Interfaces used across tasks (defined in Task 1–3, consumed later):

```python
# models.py
class DatapointStatus(StrEnum): ACTUAL, PRELIMINARY, PROVISIONAL, ESTIMATE, PROJECTION, BUDGET
class Cadence(StrEnum): MONTHLY, TWICE_YEARLY, ANNUAL
class ProviderState(StrEnum): NEVER_LOADED, AVAILABLE, STALE_BUT_CACHED, TEMPORARILY_UNAVAILABLE, PARSER_ERROR, SCHEMA_CHANGED
ReferencePeriod(start: date, end: date, label: str)            .year(y) / .month(y, m) / .to_dict() / .from_dict()
SourceRelease(source_id, release_id, published_at: date | None, download_url, canonical_url, format, etag=None, last_modified=None, checksum=None)
SpendingDataPoint(source_id, metric_id, country, reference, value: Decimal, unit, status, release_id, published_at: date | None, source_url, flags=())   .key -> DatapointKey
DatapointKey = tuple[str, str, str, str, str, str]              # source_id, metric_id, country, start iso, end iso, unit
Revision(key, previous_value, previous_release_id, new_value, release_id, detected_at: datetime)
ProviderHealth(state, last_check_at, next_check_at, last_success_at, last_error, warnings: tuple[str, ...], skip_reason)
SourceSeries(source_id, release, health, datapoints, revisions, retrieved_at)
MetricSpec(metric_id, source_id, display_name, definition, unit, comparison_group)
SourceSpec(source_id, display_name, publisher, official, canonical_url, cadence, expected_lag_days, check_interval: timedelta, formats)

# providers/base.py
class SpendingProviderError(Exception); class SourceUnavailableError(SpendingProviderError); class SchemaChangedError(SpendingProviderError)
ParseResult(datapoints: tuple[SpendingDataPoint, ...], warnings: tuple[str, ...], layout_fingerprint: str)
FetchResult(payload: bytes, etag, last_modified, checksum, not_modified: bool = False)
Payload = bytes | Mapping[str, bytes]
class SpendingProvider(Protocol):
    spec: SourceSpec
    async def async_discover_latest(self, session: ClientSession) -> SourceRelease
    async def async_fetch_release(self, session: ClientSession, release: SourceRelease) -> tuple[SourceRelease, Payload]
    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult
async def async_fetch_bytes(session, url, *, previous: SourceRelease | None = None, timeout: float = 120.0) -> FetchResult
def sha256_hex(data: bytes) -> str
```

---

### Task 1: openpyxl dependency and the spending models

**Files:**
- Modify: `custom_components/edp_radar/manifest.json` (`requirements`)
- Modify: `pyproject.toml` (dev group, mypy override)
- Create: `custom_components/edp_radar/spending/__init__.py`
- Create: `custom_components/edp_radar/spending/models.py`
- Create: `tests/spending/__init__.py`
- Test: `tests/spending/test_models.py`

**Interfaces:**
- Produces: every type listed under "Interfaces used across tasks" in `models.py`.

- [ ] **Step 1: Add the dependency**

In `custom_components/edp_radar/manifest.json` change `"requirements": []` to `"requirements": ["openpyxl==3.1.5"]`.

In `pyproject.toml` add to the `dev` group after `"mypy>=1.14",`:

```toml
    "openpyxl==3.1.5",
    "types-openpyxl>=3.1",
```

Run: `uv sync --group dev` and `uv run python -c "import openpyxl; print(openpyxl.__version__)"`
Expected: `3.1.5`

- [ ] **Step 2: Write the failing model tests**

Create `tests/spending/__init__.py` (empty) and `tests/spending/test_models.py`:

```python
"""Spending models: construction, keys and JSON round-trips (S4, S5)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from custom_components.edp_radar.spending.models import (
    DatapointStatus,
    ProviderHealth,
    ProviderState,
    ReferencePeriod,
    Revision,
    SourceRelease,
    SourceSeries,
    SpendingDataPoint,
)


def test_reference_period_year_and_month_labels() -> None:
    year = ReferencePeriod.year(2025)
    assert (year.start, year.end, year.label) == (date(2025, 1, 1), date(2025, 12, 31), "2025")
    month = ReferencePeriod.month(2026, 7)
    assert (month.start, month.end, month.label) == (date(2026, 7, 1), date(2026, 7, 31), "Jul 2026")
    assert ReferencePeriod.month(2024, 2).end == date(2024, 2, 29)
    assert ReferencePeriod.from_dict(month.to_dict()) == month


def _point(**overrides: object) -> SpendingDataPoint:
    base: dict[str, object] = {
        "source_id": "statskontoret",
        "metric_id": "materiel_outturn",
        "country": "SE",
        "reference": ReferencePeriod.month(2026, 7),
        "value": Decimal("3753.54717975"),
        "unit": "SEK_MILLION",
        "status": DatapointStatus.ACTUAL,
        "release_id": "2026-07-definitiv-2026-08-24",
        "published_at": date(2026, 8, 24),
        "source_url": "https://www.statskontoret.se/analys-och-statistik/oppna-data/manadsutfall/?year=2026",
        "flags": ("agency:2021000340",),
    }
    base.update(overrides)
    return SpendingDataPoint(**base)  # type: ignore[arg-type]


def test_datapoint_key_and_round_trip() -> None:
    point = _point()
    assert point.key == (
        "statskontoret",
        "materiel_outturn",
        "SE",
        "2026-07-01",
        "2026-07-31",
        "SEK_MILLION",
    )
    data = point.to_dict()
    assert data["value"] == "3753.54717975"
    assert data["status"] == "actual"
    assert SpendingDataPoint.from_dict(data) == point
    assert SpendingDataPoint.from_dict(_point(published_at=None, flags=()).to_dict()).published_at is None


def test_release_round_trip_keeps_optional_fields() -> None:
    release = SourceRelease(
        source_id="nato",
        release_id="2026:0x8DEDE695735E099",
        published_at=date(2026, 7, 10),
        download_url="https://www.nato.int/content/dam/nato/webready/documents/finance/def-exp-2026-en.xlsx",
        canonical_url="https://www.nato.int/en/what-we-do/introduction-to-nato/defence-expenditures-and-natos-5-commitment",
        format="xlsx",
        etag='"0x8DEDE695735E099"',
        last_modified="Fri, 10 Jul 2026 09:55:14 GMT",
        checksum="abc",
    )
    assert SourceRelease.from_dict(release.to_dict()) == release
    minimal = SourceRelease("sipri", "v1.2", None, "u", "c", "xlsx")
    assert SourceRelease.from_dict(minimal.to_dict()) == minimal


def test_series_round_trip_with_health_and_revisions() -> None:
    now = datetime(2026, 9, 12, 21, 0, tzinfo=UTC)
    point = _point()
    revision = Revision(
        key=point.key,
        previous_value=Decimal("3700"),
        previous_release_id="2026-07-preliminar-2026-08-20",
        new_value=point.value,
        release_id=point.release_id,
        detected_at=now,
    )
    health = ProviderHealth(
        state=ProviderState.AVAILABLE,
        last_check_at=now,
        next_check_at=now,
        last_success_at=now,
        last_error=None,
        warnings=("unknown country label 'Kosovo'",),
        skip_reason=None,
    )
    series = SourceSeries(
        source_id="statskontoret",
        release=None,
        health=health,
        datapoints=(point,),
        revisions=(revision,),
        retrieved_at=now,
    )
    restored = SourceSeries.from_dict(series.to_dict())
    assert restored == series
    assert restored.health.state is ProviderState.AVAILABLE
    assert restored.revisions[0].detected_at == now


def test_empty_series_default() -> None:
    series = SourceSeries.empty("eda")
    assert series.health.state is ProviderState.NEVER_LOADED
    assert series.datapoints == ()
    assert series.release is None
    assert SourceSeries.from_dict(series.to_dict()) == series
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_models.py -q`
Expected: `ModuleNotFoundError: No module named 'custom_components.edp_radar.spending'`

- [ ] **Step 4: Implement the models**

Create `custom_components/edp_radar/spending/__init__.py`:

```python
"""Phase 3 defence-spending data layer (addendum §7, decisions S1–S20)."""
```

Create `custom_components/edp_radar/spending/models.py`:

```python
"""Frozen, Home-Assistant-independent spending models (S4, S5).

Every datapoint carries its own provenance: source, metric, country, reference
period, unit, status, release and publication date (plan §6). Retrieval time
lives on the ``SourceSeries`` because a whole release is retrieved at once.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

type DatapointKey = tuple[str, str, str, str, str, str]

_MONTH_ABBREVIATIONS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


class DatapointStatus(StrEnum):
    """Controlled vocabulary of plan §8."""

    ACTUAL = "actual"
    PRELIMINARY = "preliminary"
    PROVISIONAL = "provisional"
    ESTIMATE = "estimate"
    PROJECTION = "projection"
    BUDGET = "budget"


class Cadence(StrEnum):
    MONTHLY = "monthly"
    TWICE_YEARLY = "twice_yearly"
    ANNUAL = "annual"


class ProviderState(StrEnum):
    """Per-provider health (plan §64)."""

    NEVER_LOADED = "never_loaded"
    AVAILABLE = "available"
    STALE_BUT_CACHED = "stale_but_cached"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    PARSER_ERROR = "parser_error"
    SCHEMA_CHANGED = "schema_changed"


def _opt_date(value: str | None) -> date | None:
    return None if value is None else date.fromisoformat(value)


def _opt_datetime(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


@dataclass(frozen=True, slots=True)
class ReferencePeriod:
    """The period a value describes; ``label`` is for display only."""

    start: date
    end: date
    label: str

    @classmethod
    def year(cls, year: int) -> ReferencePeriod:
        return cls(date(year, 1, 1), date(year, 12, 31), str(year))

    @classmethod
    def month(cls, year: int, month: int) -> ReferencePeriod:
        last_day = calendar.monthrange(year, month)[1]
        return cls(
            date(year, month, 1),
            date(year, month, last_day),
            f"{_MONTH_ABBREVIATIONS[month - 1]} {year}",
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReferencePeriod:
        return cls(
            date.fromisoformat(data["start"]),
            date.fromisoformat(data["end"]),
            str(data["label"]),
        )


@dataclass(frozen=True, slots=True)
class SourceRelease:
    """One discovered publication of a source (plan §10, §67)."""

    source_id: str
    release_id: str
    published_at: date | None
    download_url: str
    canonical_url: str
    format: str
    etag: str | None = None
    last_modified: str | None = None
    checksum: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "release_id": self.release_id,
            "published_at": None
            if self.published_at is None
            else self.published_at.isoformat(),
            "download_url": self.download_url,
            "canonical_url": self.canonical_url,
            "format": self.format,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceRelease:
        return cls(
            source_id=str(data["source_id"]),
            release_id=str(data["release_id"]),
            published_at=_opt_date(data.get("published_at")),
            download_url=str(data["download_url"]),
            canonical_url=str(data["canonical_url"]),
            format=str(data["format"]),
            etag=data.get("etag"),
            last_modified=data.get("last_modified"),
            checksum=data.get("checksum"),
        )


@dataclass(frozen=True, slots=True)
class SpendingDataPoint:
    """One value with full provenance (plan §6). ``flags`` keeps source markers."""

    source_id: str
    metric_id: str
    country: str
    reference: ReferencePeriod
    value: Decimal
    unit: str
    status: DatapointStatus
    release_id: str
    published_at: date | None
    source_url: str
    flags: tuple[str, ...] = ()

    @property
    def key(self) -> DatapointKey:
        """Logical identity (S5)."""
        return (
            self.source_id,
            self.metric_id,
            self.country,
            self.reference.start.isoformat(),
            self.reference.end.isoformat(),
            self.unit,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "metric_id": self.metric_id,
            "country": self.country,
            "reference": self.reference.to_dict(),
            "value": str(self.value),
            "unit": self.unit,
            "status": self.status.value,
            "release_id": self.release_id,
            "published_at": None
            if self.published_at is None
            else self.published_at.isoformat(),
            "source_url": self.source_url,
            "flags": list(self.flags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpendingDataPoint:
        return cls(
            source_id=str(data["source_id"]),
            metric_id=str(data["metric_id"]),
            country=str(data["country"]),
            reference=ReferencePeriod.from_dict(data["reference"]),
            value=Decimal(str(data["value"])),
            unit=str(data["unit"]),
            status=DatapointStatus(data["status"]),
            release_id=str(data["release_id"]),
            published_at=_opt_date(data.get("published_at")),
            source_url=str(data["source_url"]),
            flags=tuple(str(flag) for flag in data.get("flags", [])),
        )


@dataclass(frozen=True, slots=True)
class Revision:
    """A changed value on an existing key (plan §62)."""

    key: DatapointKey
    previous_value: Decimal
    previous_release_id: str
    new_value: Decimal
    release_id: str
    detected_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": list(self.key),
            "previous_value": str(self.previous_value),
            "previous_release_id": self.previous_release_id,
            "new_value": str(self.new_value),
            "release_id": self.release_id,
            "detected_at": self.detected_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Revision:
        key = tuple(str(part) for part in data["key"])
        if len(key) != 6:
            raise ValueError(f"datapoint key must have 6 parts, got {key!r}")
        return cls(
            key=(key[0], key[1], key[2], key[3], key[4], key[5]),
            previous_value=Decimal(str(data["previous_value"])),
            previous_release_id=str(data["previous_release_id"]),
            new_value=Decimal(str(data["new_value"])),
            release_id=str(data["release_id"]),
            detected_at=datetime.fromisoformat(data["detected_at"]),
        )


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Per-provider state exposed by diagnostics (plan §64, §80)."""

    state: ProviderState = ProviderState.NEVER_LOADED
    last_check_at: datetime | None = None
    next_check_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    warnings: tuple[str, ...] = ()
    skip_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "last_check_at": _iso(self.last_check_at),
            "next_check_at": _iso(self.next_check_at),
            "last_success_at": _iso(self.last_success_at),
            "last_error": self.last_error,
            "warnings": list(self.warnings),
            "skip_reason": self.skip_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderHealth:
        return cls(
            state=ProviderState(data.get("state", ProviderState.NEVER_LOADED.value)),
            last_check_at=_opt_datetime(data.get("last_check_at")),
            next_check_at=_opt_datetime(data.get("next_check_at")),
            last_success_at=_opt_datetime(data.get("last_success_at")),
            last_error=data.get("last_error"),
            warnings=tuple(str(w) for w in data.get("warnings", [])),
            skip_reason=data.get("skip_reason"),
        )


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


@dataclass(frozen=True, slots=True)
class SourceSeries:
    """Everything stored for one source: current release, health, all datapoints."""

    source_id: str
    release: SourceRelease | None
    health: ProviderHealth
    datapoints: tuple[SpendingDataPoint, ...]
    revisions: tuple[Revision, ...]
    retrieved_at: datetime | None

    @classmethod
    def empty(cls, source_id: str) -> SourceSeries:
        return cls(source_id, None, ProviderHealth(), (), (), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "release": None if self.release is None else self.release.to_dict(),
            "health": self.health.to_dict(),
            "datapoints": [point.to_dict() for point in self.datapoints],
            "revisions": [revision.to_dict() for revision in self.revisions],
            "retrieved_at": _iso(self.retrieved_at),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceSeries:
        release = data.get("release")
        return cls(
            source_id=str(data["source_id"]),
            release=None if release is None else SourceRelease.from_dict(release),
            health=ProviderHealth.from_dict(data.get("health", {})),
            datapoints=tuple(
                SpendingDataPoint.from_dict(item) for item in data.get("datapoints", [])
            ),
            revisions=tuple(
                Revision.from_dict(item) for item in data.get("revisions", [])
            ),
            retrieved_at=_opt_datetime(data.get("retrieved_at")),
        )


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """Definition of one metric of one source (plan §47)."""

    metric_id: str
    source_id: str
    display_name: str
    definition: str
    unit: str
    comparison_group: str


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Source registry entry (plan §9, §57, §86)."""

    source_id: str
    display_name: str
    publisher: str
    official: bool
    canonical_url: str
    cadence: Cadence
    expected_lag_days: int
    check_interval: timedelta
    formats: tuple[str, ...] = field(default_factory=tuple)
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/spending/test_models.py -q`
Expected: 5 passed

- [ ] **Step 6: Quality gate and commit**

Run: `uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q`
Expected: all green (ruff format may reformat the long tuple in `_MONTH_ABBREVIATIONS`; that is fine).

```bash
git add custom_components/edp_radar/manifest.json pyproject.toml uv.lock custom_components/edp_radar/spending tests/spending
git commit -m "feat(spending): models with provenance and openpyxl requirement (S3, S4, S5)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Country label tables and the source/metric registry

**Files:**
- Create: `custom_components/edp_radar/spending/countries.py`
- Create: `custom_components/edp_radar/spending/registry.py`
- Test: `tests/spending/test_countries.py`, `tests/spending/test_registry.py`

**Interfaces:**
- Consumes: `models.MetricSpec`, `models.SourceSpec`, `models.Cadence`.
- Produces: `countries.resolve_country(label) -> str | None`, `countries.normalise_label(label) -> str`, `countries.SKIP_LABELS`, `countries.EUROSTAT_GEO_FIXES`, `countries.EUROSTAT_AGGREGATES`, `countries.NORDIC`; `registry.FOCUS_COUNTRY`, `registry.SOURCES: dict[str, SourceSpec]`, `registry.METRICS: dict[tuple[str, str], MetricSpec]`, `registry.source_spec(source_id)`, `registry.metric_spec(source_id, metric_id)`, `registry.SOURCE_ORDER`, and the source ids `"statskontoret"`, `"eurostat"`, `"nato"`, `"eda"`, `"sipri"`.

- [ ] **Step 1: Write the failing tests**

`tests/spending/test_countries.py`:

```python
"""Label → alpha-2 resolution shared by the XLSX providers (S7)."""

from __future__ import annotations

from custom_components.edp_radar.spending.countries import (
    EUROSTAT_AGGREGATES,
    EUROSTAT_GEO_FIXES,
    NORDIC,
    SKIP_LABELS,
    normalise_label,
    resolve_country,
)


def test_plain_labels_resolve() -> None:
    assert resolve_country("Sweden") == "SE"
    assert resolve_country("Türkiye") == "TR"
    assert resolve_country("Slovak Republic") == "SK"
    assert resolve_country("Czech Republic") == "CZ"
    assert resolve_country("United States of America") == "US"
    assert resolve_country("Korea, South") == "KR"


def test_decorated_labels_are_normalised_first() -> None:
    assert normalise_label("Sweden* (Kronor)") == "Sweden"
    assert normalise_label("Slovenia*** ") == "Slovenia"
    assert normalise_label("Croatia ") == "Croatia"
    assert resolve_country("Sweden* (Kronor)") == "SE"
    assert resolve_country("Luxembourg**") == "LU"


def test_unknown_and_skipped_labels() -> None:
    assert resolve_country("Atlantis") is None
    assert "NATO Total" in SKIP_LABELS
    assert "USSR" in SKIP_LABELS
    assert resolve_country("USSR") is None


def test_eurostat_helpers() -> None:
    assert EUROSTAT_GEO_FIXES == {"EL": "GR", "UK": "GB"}
    assert "EU27_2020" in EUROSTAT_AGGREGATES
    assert NORDIC == ("SE", "FI", "DK", "NO", "IS")
```

`tests/spending/test_registry.py`:

```python
"""Source and metric registry invariants (S8, plan §9, §47)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from custom_components.edp_radar.spending.models import Cadence
from custom_components.edp_radar.spending.registry import (
    FOCUS_COUNTRY,
    METRICS,
    SOURCE_ORDER,
    SOURCES,
    metric_spec,
    source_spec,
)


def test_focus_country_is_sweden() -> None:
    assert FOCUS_COUNTRY == "SE"


def test_five_sources_in_plan_order() -> None:
    assert SOURCE_ORDER == ("statskontoret", "eurostat", "nato", "eda", "sipri")
    assert set(SOURCES) == set(SOURCE_ORDER)
    assert source_spec("statskontoret").cadence is Cadence.MONTHLY
    assert source_spec("statskontoret").check_interval == timedelta(days=1)
    assert source_spec("eurostat").cadence is Cadence.TWICE_YEARLY
    assert source_spec("nato").check_interval == timedelta(days=7)
    assert all(spec.official for spec in SOURCES.values() if spec.source_id != "sipri")
    assert source_spec("sipri").official is False


def test_every_metric_belongs_to_its_source_and_group() -> None:
    for (source_id, metric_id), spec in METRICS.items():
        assert spec.source_id == source_id
        assert spec.metric_id == metric_id
        assert spec.comparison_group == source_id
        assert spec.unit
        assert spec.definition
    assert metric_spec("statskontoret", "materiel_outturn").unit == "SEK_MILLION"
    assert metric_spec("eurostat", "defence_investment_pct_gdp").unit == "PCT_GDP"
    assert metric_spec("nato", "equipment_expenditure_usd_current").definition.startswith(
        "Derived"
    )
    with pytest.raises(KeyError):
        metric_spec("nato", "nope")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_countries.py tests/spending/test_registry.py -q`
Expected: `ModuleNotFoundError` for `countries` / `registry`.

- [ ] **Step 3: Implement `countries.py`**

```python
"""Country label resolution for XLSX sources and Eurostat code fixes (S7, D2).

Every label observed in the NATO 2025/2026 workbooks, the EDA 2022–2025
workbooks and the SIPRI 1949–2025 v1.2 workbook is listed. Anything else
resolves to ``None`` and the caller records a parse warning; historical
entities and aggregates are listed in ``SKIP_LABELS`` so they produce no
warning.
"""

from __future__ import annotations

import re

_DECORATION = re.compile(r"\*+|\s*\([^)]*\)\s*$")

NORDIC: tuple[str, ...] = ("SE", "FI", "DK", "NO", "IS")

EUROSTAT_GEO_FIXES: dict[str, str] = {"EL": "GR", "UK": "GB"}
EUROSTAT_AGGREGATES: frozenset[str] = frozenset({"EU27_2020", "EU28", "EA", "EA20", "EA19"})

SKIP_LABELS: frozenset[str] = frozenset(
    {
        "Czechoslovakia",
        "German Democratic Republic",
        "Yugoslavia",
        "USSR",
        "Yemen, North",
        "European Union",
        "NATO Total",
        "NATO Europe and Canada",
        "EU27",
        "EU 27",
        "EDA 26",
    }
)

COUNTRY_LABELS: dict[str, str] = {
    # Europe (NATO, EDA and SIPRI spellings)
    "Albania": "AL", "Austria": "AT", "Belgium": "BE", "Bosnia and Herzegovina": "BA",
    "Bulgaria": "BG", "Croatia": "HR", "Cyprus": "CY", "Czechia": "CZ",
    "Czech Republic": "CZ", "Denmark": "DK", "Estonia": "EE", "Finland": "FI",
    "France": "FR", "Germany": "DE", "Greece": "GR", "Hungary": "HU", "Iceland": "IS",
    "Ireland": "IE", "Italy": "IT", "Kosovo": "XK", "Latvia": "LV", "Lithuania": "LT",
    "Luxembourg": "LU", "Malta": "MT", "Moldova": "MD", "Montenegro": "ME",
    "Netherlands": "NL", "North Macedonia": "MK", "Norway": "NO", "Poland": "PL",
    "Portugal": "PT", "Romania": "RO", "Serbia": "RS", "Slovakia": "SK",
    "Slovak Republic": "SK", "Slovenia": "SI", "Spain": "ES", "Sweden": "SE",
    "Switzerland": "CH", "Türkiye": "TR", "Turkey": "TR", "Ukraine": "UA",
    "United Kingdom": "GB", "Belarus": "BY", "Russia": "RU", "Armenia": "AM",
    "Azerbaijan": "AZ", "Georgia": "GE",
    # Americas
    "Canada": "CA", "United States": "US", "United States of America": "US",
    "Mexico": "MX", "Belize": "BZ", "Costa Rica": "CR", "Cuba": "CU",
    "Dominican Republic": "DO", "El Salvador": "SV", "Guatemala": "GT", "Haiti": "HT",
    "Honduras": "HN", "Jamaica": "JM", "Nicaragua": "NI", "Panama": "PA",
    "Trinidad and Tobago": "TT", "Argentina": "AR", "Bolivia": "BO", "Brazil": "BR",
    "Chile": "CL", "Colombia": "CO", "Ecuador": "EC", "Guyana": "GY", "Paraguay": "PY",
    "Peru": "PE", "Uruguay": "UY", "Venezuela": "VE",
    # Africa
    "Algeria": "DZ", "Libya": "LY", "Morocco": "MA", "Tunisia": "TN", "Angola": "AO",
    "Benin": "BJ", "Botswana": "BW", "Burkina Faso": "BF", "Burundi": "BI",
    "Cameroon": "CM", "Cape Verde": "CV", "Central African Republic": "CF", "Chad": "TD",
    "Congo, DR": "CD", "Congo, Republic": "CG", "Cote d'Ivoire": "CI", "Djibouti": "DJ",
    "Equatorial Guinea": "GQ", "Eritrea": "ER", "Ethiopia": "ET", "Gabon": "GA",
    "Gambia, The": "GM", "Ghana": "GH", "Guinea": "GN", "Guinea-Bissau": "GW",
    "Kenya": "KE", "Lesotho": "LS", "Liberia": "LR", "Madagascar": "MG", "Malawi": "MW",
    "Mali": "ML", "Mauritania": "MR", "Mauritius": "MU", "Mozambique": "MZ",
    "Namibia": "NA", "Niger": "NE", "Nigeria": "NG", "Rwanda": "RW", "Senegal": "SN",
    "Seychelles": "SC", "Sierra Leone": "SL", "Somalia": "SO", "South Africa": "ZA",
    "South Sudan": "SS", "Sudan": "SD", "Eswatini": "SZ", "Tanzania": "TZ", "Togo": "TG",
    "Uganda": "UG", "Zambia": "ZM", "Zimbabwe": "ZW",
    # Asia and Oceania
    "Australia": "AU", "Fiji": "FJ", "New Zealand": "NZ", "Papua New Guinea": "PG",
    "Afghanistan": "AF", "Bangladesh": "BD", "India": "IN", "Nepal": "NP",
    "Pakistan": "PK", "Sri Lanka": "LK", "China": "CN", "Japan": "JP",
    "Korea, North": "KP", "Korea, South": "KR", "Mongolia": "MN", "Taiwan": "TW",
    "Brunei": "BN", "Cambodia": "KH", "Indonesia": "ID", "Laos": "LA", "Malaysia": "MY",
    "Myanmar": "MM", "Philippines": "PH", "Singapore": "SG", "Thailand": "TH",
    "Timor Leste": "TL", "Viet Nam": "VN", "Kazakhstan": "KZ", "Kyrgyz Republic": "KG",
    "Tajikistan": "TJ", "Turkmenistan": "TM", "Uzbekistan": "UZ",
    # Middle East
    "Bahrain": "BH", "Egypt": "EG", "Iran": "IR", "Iraq": "IQ", "Israel": "IL",
    "Jordan": "JO", "Kuwait": "KW", "Lebanon": "LB", "Oman": "OM", "Qatar": "QA",
    "Saudi Arabia": "SA", "Syria": "SY", "United Arab Emirates": "AE", "Yemen": "YE",
}


def normalise_label(label: str) -> str:
    """Strip footnote asterisks, a trailing ``(currency)`` and whitespace."""
    return _DECORATION.sub("", label).strip()


def resolve_country(label: str) -> str | None:
    """Alpha-2 code for a source label, ``None`` when unknown or skipped."""
    plain = normalise_label(label)
    if plain in SKIP_LABELS:
        return None
    return COUNTRY_LABELS.get(plain)
```

(`ruff format` will reflow the dictionary; keep one entry per line if it does.)

- [ ] **Step 4: Implement `registry.py`**

```python
"""Source registry and metric definitions (S8; plan §9, §24, §30, §37, §42, §47).

``comparison_group`` equals the source id: rankings and medians only ever
combine datapoints of one source, one metric, one reference period and one
unit (plan §48).
"""

from __future__ import annotations

from datetime import timedelta

from .models import Cadence, MetricSpec, SourceSpec

FOCUS_COUNTRY = "SE"

STATSKONTORET = "statskontoret"
EUROSTAT = "eurostat"
NATO = "nato"
EDA = "eda"
SIPRI = "sipri"

SOURCE_ORDER: tuple[str, ...] = (STATSKONTORET, EUROSTAT, NATO, EDA, SIPRI)

SOURCES: dict[str, SourceSpec] = {
    STATSKONTORET: SourceSpec(
        source_id=STATSKONTORET,
        display_name="Statskontoret monthly budget outturn",
        publisher="Statskontoret",
        official=True,
        canonical_url="https://www.statskontoret.se/analys-och-statistik/oppna-data/manadsutfall/",
        cadence=Cadence.MONTHLY,
        expected_lag_days=31,
        check_interval=timedelta(days=1),
        formats=("csv",),
    ),
    EUROSTAT: SourceSpec(
        source_id=EUROSTAT,
        display_name="Eurostat gov_ev defence expenditure and investment",
        publisher="Eurostat",
        official=True,
        canonical_url="https://ec.europa.eu/eurostat/cache/metadata/en/gov_ev_esms.htm",
        cadence=Cadence.TWICE_YEARLY,
        expected_lag_days=120,
        check_interval=timedelta(days=1),
        formats=("json-stat",),
    ),
    NATO: SourceSpec(
        source_id=NATO,
        display_name="NATO defence expenditure of NATO countries",
        publisher="NATO",
        official=True,
        canonical_url="https://www.nato.int/en/what-we-do/introduction-to-nato/defence-expenditures-and-natos-5-commitment",
        cadence=Cadence.ANNUAL,
        expected_lag_days=200,
        check_interval=timedelta(days=7),
        formats=("xlsx",),
    ),
    EDA: SourceSpec(
        source_id=EDA,
        display_name="EDA defence data",
        publisher="European Defence Agency",
        official=True,
        canonical_url="https://www.eda.europa.eu/publications-and-data/defence-data",
        cadence=Cadence.ANNUAL,
        expected_lag_days=250,
        check_interval=timedelta(days=7),
        formats=("xlsx",),
    ),
    SIPRI: SourceSpec(
        source_id=SIPRI,
        display_name="SIPRI military expenditure database",
        publisher="SIPRI",
        official=False,
        canonical_url="https://www.sipri.org/databases/milex",
        cadence=Cadence.ANNUAL,
        expected_lag_days=120,
        check_interval=timedelta(days=7),
        formats=("xlsx",),
    ),
}


def _metric(source_id: str, metric_id: str, name: str, definition: str, unit: str) -> MetricSpec:
    return MetricSpec(metric_id, source_id, name, definition, unit, source_id)


_METRIC_LIST: tuple[MetricSpec, ...] = (
    # Statskontoret (S9)
    _metric(STATSKONTORET, "uo6_total_outturn", "Expenditure area 6 outturn",
            "Monthly outturn of all appropriations in utgiftsområde 6 (Försvar och samhällets krisberedskap).", "SEK_MILLION"),
    _metric(STATSKONTORET, "uo6_defence_outturn", "Defence appropriations outturn",
            "Monthly outturn of appropriations 6:1:1–6:1:14 (Anslag 0601001–0601014).", "SEK_MILLION"),
    _metric(STATSKONTORET, "materiel_outturn", "Materiel acquisition outturn",
            "Monthly outturn of appropriation 6:1:3 Anskaffning av materiel och anläggningar (Anslag 0601003).", "SEK_MILLION"),
    # Eurostat gov_ev (S10)
    _metric(EUROSTAT, "defence_expenditure", "Government defence expenditure",
            "gov_ev: total general government expenditure on defence (expend=DEF, na_item=TE), ESA 2010.", "EUR_MILLION"),
    _metric(EUROSTAT, "defence_expenditure_nac", "Government defence expenditure (national currency)",
            "gov_ev DEF/TE in million units of national currency.", "NAC_MILLION"),
    _metric(EUROSTAT, "defence_expenditure_pct_gdp", "Government defence expenditure, % of GDP",
            "gov_ev DEF/TE as a percentage of GDP.", "PCT_GDP"),
    _metric(EUROSTAT, "defence_investment", "Government defence investment",
            "gov_ev: gross fixed capital formation on defence (expend=DEF, na_item=P51G).", "EUR_MILLION"),
    _metric(EUROSTAT, "defence_investment_nac", "Government defence investment (national currency)",
            "gov_ev DEF/P51G in million units of national currency.", "NAC_MILLION"),
    _metric(EUROSTAT, "defence_investment_pct_gdp", "Government defence investment, % of GDP",
            "gov_ev DEF/P51G as a percentage of GDP.", "PCT_GDP"),
    # NATO (S11)
    _metric(NATO, "defence_expenditure_nac", "Defence expenditure (national currency)",
            "Table 1, current prices, million national currency units (NATO definition).", "NAC_MILLION"),
    _metric(NATO, "defence_expenditure_usd_current", "Defence expenditure (USD, current)",
            "Table 2, current prices and exchange rates, million US dollars.", "USD_MILLION"),
    _metric(NATO, "defence_expenditure_usd_constant", "Defence expenditure (USD, constant 2021)",
            "Table 2, constant 2021 prices and exchange rates, million US dollars.", "USD_MILLION_CONSTANT_2021"),
    _metric(NATO, "defence_expenditure_pct_gdp", "Defence expenditure, % of real GDP",
            "Table 3, share of real GDP based on 2021 prices.", "PCT_GDP"),
    _metric(NATO, "equipment_share_pct", "Equipment share of defence expenditure",
            "Table 8a, equipment (a) as a percentage of total defence expenditure.", "PCT"),
    _metric(NATO, "equipment_expenditure_usd_current", "Equipment expenditure (USD, current)",
            "Derived: Table 2 current-price USD expenditure × Table 8a equipment share / 100 (plan §30).", "USD_MILLION"),
    # EDA (S11)
    _metric(EDA, "defence_expenditure", "Total defence expenditure",
            "Member States sheet: Total Defence Expenditure, million EUR, current prices.", "EUR_MILLION"),
    _metric(EDA, "defence_investment", "Defence investment",
            "Member States sheet: Defence Investment (equipment procurement + R&D), million EUR.", "EUR_MILLION"),
    _metric(EDA, "defence_expenditure_pct_gdp", "Total defence expenditure, % of GDP",
            "Member States sheet share of GDP × 100.", "PCT_GDP"),
    _metric(EDA, "defence_expenditure_pct_government", "Total defence expenditure, % of government expenditure",
            "Member States sheet share of general government expenditure × 100.", "PCT"),
    _metric(EDA, "defence_expenditure_per_capita", "Total defence expenditure per capita",
            "Member States sheet, EUR per capita.", "EUR"),
    _metric(EDA, "equipment_procurement", "Defence equipment procurement",
            "Billions sheet: Defence Equipment Procurement Expenditure, million EUR (2005–2021 only).", "EUR_MILLION"),
    _metric(EDA, "defence_rnd", "Defence R&D expenditure",
            "Billions sheet: Defence R&D Expenditure, million EUR (2005–2021 only).", "EUR_MILLION"),
    # SIPRI (S11)
    _metric(SIPRI, "military_expenditure_usd_constant", "Military expenditure (USD, constant 2024)",
            "Sheet 'Constant (2024) US$', million US dollars at constant 2024 prices and exchange rates.", "USD_MILLION_CONSTANT_2024"),
    _metric(SIPRI, "military_expenditure_usd_current", "Military expenditure (USD, current)",
            "Sheet 'Current US$', million US dollars at current prices and exchange rates.", "USD_MILLION"),
    _metric(SIPRI, "military_expenditure_pct_gdp", "Military expenditure, % of GDP",
            "Sheet 'Share of GDP' ratio × 100.", "PCT_GDP"),
)

METRICS: dict[tuple[str, str], MetricSpec] = {
    (spec.source_id, spec.metric_id): spec for spec in _METRIC_LIST
}


def source_spec(source_id: str) -> SourceSpec:
    return SOURCES[source_id]


def metric_spec(source_id: str, metric_id: str) -> MetricSpec:
    return METRICS[(source_id, metric_id)]


def metrics_for(source_id: str) -> tuple[MetricSpec, ...]:
    return tuple(spec for spec in _METRIC_LIST if spec.source_id == source_id)
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/spending -q`
Expected: all pass (5 + 4 + 3).

- [ ] **Step 6: Quality gate and commit**

Run: `uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q`

```bash
git add custom_components/edp_radar/spending tests/spending
git commit -m "feat(spending): country label tables and source/metric registry (S7, S8)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Provider contract, errors and the conditional HTTP fetch helper

**Files:**
- Create: `custom_components/edp_radar/spending/providers/__init__.py`
- Create: `custom_components/edp_radar/spending/providers/base.py`
- Test: `tests/spending/test_base.py`

**Interfaces:**
- Consumes: `models.SourceRelease`, `models.SourceSpec`, `models.SpendingDataPoint`.
- Produces: `SpendingProviderError`, `SourceUnavailableError`, `SchemaChangedError`, `ParseResult`, `FetchResult`, `Payload`, `SpendingProvider` protocol, `async_fetch_bytes()`, `async_head_metadata()`, `sha256_hex()`, `http_date_to_date()`.

- [ ] **Step 1: Write the failing tests**

`tests/spending/test_base.py`:

```python
"""HTTP helper: conditional requests, 304, errors, checksums (S12, plan §87)."""

from __future__ import annotations

from datetime import date

import pytest
from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.spending.models import SourceRelease
from custom_components.edp_radar.spending.providers.base import (
    SourceUnavailableError,
    async_fetch_bytes,
    async_head_metadata,
    http_date_to_date,
    sha256_hex,
)

URL = "https://example.org/data.xlsx"


def _release(**overrides: object) -> SourceRelease:
    base: dict[str, object] = {
        "source_id": "nato",
        "release_id": "2026",
        "published_at": None,
        "download_url": URL,
        "canonical_url": "https://example.org/",
        "format": "xlsx",
        "etag": '"abc"',
        "last_modified": "Fri, 10 Jul 2026 09:55:14 GMT",
    }
    base.update(overrides)
    return SourceRelease(**base)  # type: ignore[arg-type]


async def test_fetch_returns_payload_headers_and_checksum(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        URL,
        content=b"hello",
        headers={"ETag": '"xyz"', "Last-Modified": "Mon, 27 Apr 2026 15:20:25 GMT"},
    )
    result = await async_fetch_bytes(async_get_clientsession(hass), URL)
    assert result.payload == b"hello"
    assert result.etag == '"xyz"'
    assert result.last_modified == "Mon, 27 Apr 2026 15:20:25 GMT"
    assert result.checksum == sha256_hex(b"hello")
    assert result.not_modified is False
    assert "If-None-Match" not in aioclient_mock.mock_calls[0][3]


async def test_fetch_sends_conditional_headers_and_handles_304(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(URL, status=304)
    result = await async_fetch_bytes(
        async_get_clientsession(hass), URL, previous=_release()
    )
    assert result.not_modified is True
    assert result.payload == b""
    headers = aioclient_mock.mock_calls[0][3]
    assert headers["If-None-Match"] == '"abc"'
    assert headers["If-Modified-Since"] == "Fri, 10 Jul 2026 09:55:14 GMT"


async def test_conditional_headers_only_for_the_same_url(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(URL, content=b"x")
    await async_fetch_bytes(
        async_get_clientsession(hass),
        URL,
        previous=_release(download_url="https://example.org/other.xlsx"),
    )
    assert "If-None-Match" not in aioclient_mock.mock_calls[0][3]


async def test_fetch_errors_are_wrapped(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(URL, status=503)
    with pytest.raises(SourceUnavailableError, match="HTTP 503"):
        await async_fetch_bytes(async_get_clientsession(hass), URL)
    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, exc=ClientError("boom"))
    with pytest.raises(SourceUnavailableError, match="boom"):
        await async_fetch_bytes(async_get_clientsession(hass), URL)


async def test_head_metadata_tolerates_failures(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.head(URL, headers={"ETag": '"e"', "Last-Modified": "x"})
    assert await async_head_metadata(async_get_clientsession(hass), URL) == ('"e"', "x")
    aioclient_mock.clear_requests()
    aioclient_mock.head(URL, status=405)
    assert await async_head_metadata(async_get_clientsession(hass), URL) == (None, None)


def test_http_date_parsing() -> None:
    assert http_date_to_date("Fri, 10 Jul 2026 09:55:14 GMT") == date(2026, 7, 10)
    assert http_date_to_date("garbage") is None
    assert http_date_to_date(None) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_base.py -q`
Expected: `ModuleNotFoundError: ... spending.providers`

- [ ] **Step 3: Implement the base module**

`custom_components/edp_radar/spending/providers/__init__.py`:

```python
"""Spending providers; ``all_providers`` is filled in as providers land."""

from __future__ import annotations

from .base import SpendingProvider


def all_providers() -> tuple[SpendingProvider, ...]:
    """Providers in plan order (Statskontoret, Eurostat, NATO, EDA, SIPRI)."""
    return ()
```

`custom_components/edp_radar/spending/providers/base.py`:

```python
"""Provider contract and shared HTTP helpers (S12; plan §10, §65, §87).

Parsing is synchronous and pure so it can run in an executor and in scripts
without Home Assistant; discovery and fetching take the aiohttp session.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Protocol

from aiohttp import ClientError, ClientSession

from ..models import SourceRelease, SourceSpec, SpendingDataPoint

type Payload = bytes | Mapping[str, bytes]

USER_AGENT = "ha-edp-radar (Home Assistant integration; +https://github.com/mattahr/ha-edp-radar)"
DEFAULT_TIMEOUT = 120.0


class SpendingProviderError(Exception):
    """Base class for provider failures."""


class SourceUnavailableError(SpendingProviderError):
    """HTTP error, timeout or connection problem: try again later."""


class SchemaChangedError(SpendingProviderError):
    """The source layout no longer matches the parser (plan §65)."""


@dataclass(frozen=True, slots=True)
class ParseResult:
    datapoints: tuple[SpendingDataPoint, ...]
    warnings: tuple[str, ...]
    layout_fingerprint: str


@dataclass(frozen=True, slots=True)
class FetchResult:
    payload: bytes
    etag: str | None
    last_modified: str | None
    checksum: str
    not_modified: bool = False


class SpendingProvider(Protocol):
    """What the coordinator needs from every source (plan §10)."""

    spec: SourceSpec

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease: ...

    async def async_fetch_release(
        self, session: ClientSession, release: SourceRelease
    ) -> tuple[SourceRelease, Payload]: ...

    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult: ...


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def http_date_to_date(value: str | None) -> date | None:
    """``Last-Modified`` header → date, ``None`` when absent or unparsable."""
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError):
        return None


def _conditional_headers(url: str, previous: SourceRelease | None) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if previous is None or previous.download_url != url:
        return headers
    if previous.etag:
        headers["If-None-Match"] = previous.etag
    if previous.last_modified:
        headers["If-Modified-Since"] = previous.last_modified
    return headers


async def async_fetch_bytes(
    session: ClientSession,
    url: str,
    *,
    previous: SourceRelease | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> FetchResult:
    """GET ``url``; conditional when ``previous`` has validators for the same URL."""
    try:
        async with asyncio.timeout(timeout):
            response = await session.get(
                url, headers=_conditional_headers(url, previous), allow_redirects=True
            )
            if response.status == 304:
                return FetchResult(b"", previous.etag if previous else None,
                                   previous.last_modified if previous else None,
                                   previous.checksum or "" if previous else "", True)
            if response.status != 200:
                raise SourceUnavailableError(f"HTTP {response.status} for {url}")
            payload = await response.read()
    except TimeoutError as err:
        raise SourceUnavailableError(f"Timeout fetching {url}") from err
    except ClientError as err:
        raise SourceUnavailableError(f"Error fetching {url}: {err}") from err
    return FetchResult(
        payload=payload,
        etag=response.headers.get("ETag"),
        last_modified=response.headers.get("Last-Modified"),
        checksum=sha256_hex(payload),
    )


async def async_head_metadata(
    session: ClientSession, url: str, *, timeout: float = 30.0
) -> tuple[str | None, str | None]:
    """``(ETag, Last-Modified)`` from a HEAD request; ``(None, None)`` on any failure."""
    try:
        async with asyncio.timeout(timeout):
            response = await session.head(
                url, headers={"User-Agent": USER_AGENT}, allow_redirects=True
            )
            if response.status != 200:
                return (None, None)
            return (response.headers.get("ETag"), response.headers.get("Last-Modified"))
    except (TimeoutError, ClientError):
        return (None, None)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending/test_base.py -q`
Expected: 6 passed

- [ ] **Step 5: Quality gate and commit**

Run: `uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q`

```bash
git add custom_components/edp_radar/spending/providers tests/spending/test_base.py
git commit -m "feat(spending): provider contract and conditional fetch helper (S12)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Statskontoret provider (discovery page → Zip/CSV → monthly datapoints)

**Files:**
- Create: `scripts/fetch_spending_fixtures.py` (Statskontoret part; later tasks extend it)
- Create: `tests/fixtures/spending/statskontoret/discovery-2026.html`, `discovery-2025.html`, `utgifter-2026-07.csv`, `utgifter-2025-12-preliminar.csv`, `utgifter-2025-12-definitiv.csv`
- Create: `custom_components/edp_radar/spending/providers/statskontoret.py`
- Create: `docs/providers/statskontoret.md`
- Modify: `custom_components/edp_radar/spending/providers/__init__.py`
- Test: `tests/spending/test_statskontoret.py`

**Interfaces:**
- Consumes: Task 1–3 types, `registry.STATSKONTORET`, `registry.FOCUS_COUNTRY`, `registry.source_spec`.
- Produces: `StatskontoretProvider` (implements `SpendingProvider`), pure helpers `parse_discovery_page(html_text, page_url) -> list[DiscoveredRelease]`, `select_latest(releases) -> DiscoveredRelease`, `release_from(discovered, page_url) -> SourceRelease`, `parse_outturn_csv(payload, release) -> ParseResult`, constants `DISCOVERY_URL`, `MATERIEL_APPROPRIATION = "0601003"`.

- [ ] **Step 1: Write the fixture script and capture the fixtures**

Create `scripts/fetch_spending_fixtures.py`:

```python
"""Download and trim the real spending fixtures (S18).

Usage:
    PYTHONPATH=. uv run python scripts/fetch_spending_fixtures.py statskontoret
    PYTHONPATH=. uv run python scripts/fetch_spending_fixtures.py all

Downloads are cached under --cache (default .cache/spending/fixtures). Trimming
keeps the rows/sheets the parsers and tests need; numbers are never edited.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

FIXTURES = Path("tests/fixtures/spending")
USER_AGENT = "ha-edp-radar fixture fetcher"


def download(url: str, cache: Path, name: str) -> bytes:
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / name
    if target.exists():
        return target.read_bytes()
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT})) as response:  # noqa: S310
        data: bytes = response.read()
    target.write_bytes(data)
    print(f"downloaded {url} -> {target} ({len(data)} bytes)")
    return data


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"wrote {path} ({len(data)} bytes)")


# ----------------------------------------------------------------- Statskontoret

SK_BASE = "https://www.statskontoret.se"
SK_PAGE = SK_BASE + "/analys-och-statistik/oppna-data/manadsutfall/?year={year}"
SK_FILE = (
    SK_BASE
    + "/OpenDataManadsUtfallPage/GetFile?documentType=Utgift&fileType=Zip"
    + "&fileName=x.zip&Year={year}&month={month}&status={status}"
)
_LI_DATA = re.compile(r'<li class="data[^"]*">.*?</li>', re.S)


def trim_statskontoret_page(html: str) -> str:
    """Keep only the ``<li class="data">`` blocks for Utgifter releases."""
    blocks = [b for b in _LI_DATA.findall(html) if "documentType=Utgift" in b]
    body = "\n".join(blocks)
    return f'<!DOCTYPE html>\n<html lang="sv"><body><ul class="fixture">\n{body}\n</ul></body></html>\n'


def trim_statskontoret_csv(zip_bytes: bytes, years: set[str]) -> bytes:
    """Header + every utgiftsområde 06 row of ``years`` + three non-06 rows."""
    archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    text = archive.read(archive.namelist()[0]).decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    kept = [rows[0]]
    others = 0
    for row in rows[1:]:
        if row[0] == "06" and row[10] in years:
            kept.append(row)
        elif others < 3 and row[10] in years:
            kept.append(row)
            others += 1
    out = io.StringIO()
    csv.writer(out, delimiter=";", lineterminator="\n").writerows(kept)
    return ("﻿" + out.getvalue()).encode("utf-8")


def fetch_statskontoret(cache: Path) -> None:
    folder = FIXTURES / "statskontoret"
    for year in (2026, 2025):
        page = download(SK_PAGE.format(year=year), cache, f"statskontoret-{year}.html")
        write(folder / f"discovery-{year}.html", trim_statskontoret_page(page.decode("utf-8")).encode("utf-8"))
    july = download(SK_FILE.format(year=2026, month=7, status="Definitiv"), cache, "statskontoret-2026-07.zip")
    write(folder / "utgifter-2026-07.csv", trim_statskontoret_csv(july, {"2025", "2026"}))
    prelim = download(SK_FILE.format(year=2025, month=12, status=quote("Preliminär 1")), cache, "statskontoret-2025-12-preliminar.zip")
    write(folder / "utgifter-2025-12-preliminar.csv", trim_statskontoret_csv(prelim, {"2025"}))
    definitive = download(SK_FILE.format(year=2025, month=12, status="Definitiv"), cache, "statskontoret-2025-12-definitiv.zip")
    write(folder / "utgifter-2025-12-definitiv.csv", trim_statskontoret_csv(definitive, {"2025"}))


FETCHERS = {"statskontoret": fetch_statskontoret}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", choices=[*FETCHERS, "all"])
    parser.add_argument("--cache", default=".cache/spending/fixtures")
    args = parser.parse_args(argv)
    cache = Path(args.cache)
    for name, fetcher in FETCHERS.items():
        if args.source in (name, "all"):
            fetcher(cache)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Run: `PYTHONPATH=. uv run python scripts/fetch_spending_fixtures.py statskontoret`
Expected: five files written; `discovery-2026.html` contains seven `Utgifter` blocks (January–July 2026) and `discovery-2025.html` contains both `Utgifter december 2025 — preliminär 1` (dd `2026-01-28`) and `— definitiv` (dd `2026-03-24`); `utgifter-2026-07.csv` has ≈ 118 lines. Check `.gitignore` already ignores `.cache/` (it does for Phase 0/2; add `.cache/` if missing).

- [ ] **Step 2: Write the failing tests**

`tests/spending/test_statskontoret.py`:

```python
"""Statskontoret discovery and CSV parsing against real trimmed fixtures (S9)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.spending.models import DatapointStatus
from custom_components.edp_radar.spending.providers.base import SchemaChangedError
from custom_components.edp_radar.spending.providers.statskontoret import (
    DISCOVERY_URL,
    MATERIEL_APPROPRIATION,
    StatskontoretProvider,
    parse_discovery_page,
    parse_outturn_csv,
    release_from,
    select_latest,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spending" / "statskontoret"
PAGE_2026 = f"{DISCOVERY_URL}?year=2026"
PAGE_2025 = f"{DISCOVERY_URL}?year=2025"


def _page(year: int) -> str:
    return (FIXTURES / f"discovery-{year}.html").read_text(encoding="utf-8")


def _csv(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_discovery_lists_expenditure_releases_newest_last() -> None:
    releases = parse_discovery_page(_page(2026), PAGE_2026)
    assert [(r.year, r.month) for r in releases] == [(2026, m) for m in range(1, 8)]
    latest = select_latest(releases)
    assert (latest.year, latest.month, latest.status_raw) == (2026, 7, "Definitiv")
    assert latest.updated == date(2026, 8, 24)
    assert latest.csv_url.startswith("https://www.statskontoret.se/OpenDataManadsUtfallPage/GetFile?")
    assert "fileType=Zip" in latest.csv_url and "month=7" in latest.csv_url


def test_december_definitive_wins_over_preliminary() -> None:
    releases = parse_discovery_page(_page(2025), PAGE_2025)
    december = [r for r in releases if r.month == 12]
    assert sorted(r.status_raw for r in december) == ["Definitiv", "Preliminär 1"]
    latest = select_latest(releases)
    assert latest.status_raw == "Definitiv"
    assert latest.updated == date(2026, 3, 24)
    release = release_from(latest, PAGE_2025)
    assert release.release_id == "2025-12-definitiv-2026-03-24"
    assert release.published_at == date(2026, 3, 24)
    assert release.format == "csv"
    prelim = release_from(next(r for r in december if r.status_raw != "Definitiv"), PAGE_2025)
    assert prelim.release_id == "2025-12-preliminar-2026-01-28"


def test_parse_july_2026_file() -> None:
    release = release_from(select_latest(parse_discovery_page(_page(2026), PAGE_2026)), PAGE_2026)
    result = parse_outturn_csv(_csv("utgifter-2026-07.csv"), release)
    points = {(p.metric_id, p.reference.start.year, p.reference.start.month): p for p in result.datapoints}
    assert points[("materiel_outturn", 2026, 7)].value == Decimal("3753.54717975")
    assert points[("uo6_defence_outturn", 2026, 1)].value == Decimal("6676.43315691")
    assert points[("uo6_total_outturn", 2026, 7)].value == Decimal("11050.09591378")
    assert points[("materiel_outturn", 2025, 12)].value == Decimal("23327.02469578")
    assert ("materiel_outturn", 2026, 8) not in points
    assert {p.status for p in result.datapoints} == {DatapointStatus.ACTUAL}
    assert {p.country for p in result.datapoints} == {"SE"}
    assert {p.unit for p in result.datapoints} == {"SEK_MILLION"}
    assert points[("materiel_outturn", 2026, 7)].reference.label == "Jul 2026"
    assert points[("materiel_outturn", 2026, 7)].release_id == release.release_id
    assert points[("materiel_outturn", 2026, 7)].published_at == date(2026, 8, 24)
    assert result.layout_fingerprint.startswith("Utgiftsområde;Utgiftsområdesnamn;Anslag")
    assert result.warnings == ()
    assert len(result.datapoints) == 3 * (12 + 7)


def test_preliminary_december_marks_only_december() -> None:
    releases = parse_discovery_page(_page(2025), PAGE_2025)
    prelim = release_from(next(r for r in releases if r.month == 12 and r.status_raw != "Definitiv"), PAGE_2025)
    result = parse_outturn_csv(_csv("utgifter-2025-12-preliminar.csv"), prelim)
    by_month = {(p.metric_id, p.reference.start.month): p for p in result.datapoints}
    assert by_month[("materiel_outturn", 12)].value == Decimal("19729.43332150")
    assert by_month[("materiel_outturn", 12)].status is DatapointStatus.PRELIMINARY
    assert by_month[("materiel_outturn", 11)].status is DatapointStatus.ACTUAL
    definitive = release_from(select_latest(releases), PAGE_2025)
    final = parse_outturn_csv(_csv("utgifter-2025-12-definitiv.csv"), definitive)
    dec = next(p for p in final.datapoints if p.metric_id == "materiel_outturn" and p.reference.start.month == 12)
    assert dec.value == Decimal("23327.02469578")
    assert dec.status is DatapointStatus.ACTUAL
    assert dec.key == by_month[("materiel_outturn", 12)].key


def test_schema_changes_fail_loudly() -> None:
    release = release_from(select_latest(parse_discovery_page(_page(2026), PAGE_2026)), PAGE_2026)
    text = _csv("utgifter-2026-07.csv").decode("utf-8-sig")
    renamed = text.replace("Anslag;", "Anslagskod;", 1).encode("utf-8")
    with pytest.raises(SchemaChangedError, match="Anslag"):
        parse_outturn_csv(renamed, release)
    header_only = text.splitlines()[0].encode("utf-8")
    with pytest.raises(SchemaChangedError, match="utgiftsområde 06"):
        parse_outturn_csv(header_only, release)
    assert MATERIEL_APPROPRIATION == "0601003"


async def test_provider_discovers_and_fetches(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(PAGE_2026, text=_page(2026))
    provider = StatskontoretProvider(today=lambda: date(2026, 9, 12))
    session = async_get_clientsession(hass)
    release = await provider.async_discover_latest(session)
    assert release.release_id == "2026-07-definitiv-2026-08-24"
    aioclient_mock.get(release.download_url, content=_csv("utgifter-2026-07.csv"))
    fetched, payload = await provider.async_fetch_release(session, release)
    assert fetched.checksum is not None
    assert isinstance(payload, bytes)
    result = provider.parse_release(payload, fetched)
    assert len(result.datapoints) == 57


async def test_provider_falls_back_to_previous_year_in_january(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{DISCOVERY_URL}?year=2027", text="<html><body><ul></ul></body></html>")
    aioclient_mock.get(f"{DISCOVERY_URL}?year=2026", text=_page(2026))
    provider = StatskontoretProvider(today=lambda: date(2027, 1, 5))
    release = await provider.async_discover_latest(async_get_clientsession(hass))
    assert release.release_id == "2026-07-definitiv-2026-08-24"
    assert release.canonical_url == f"{DISCOVERY_URL}?year=2026"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_statskontoret.py -q`
Expected: `ImportError` (module missing).

- [ ] **Step 4: Implement the provider**

`custom_components/edp_radar/spending/providers/statskontoret.py`:

```python
"""Statskontoret monthly budget outturn (S9; plan §12–§19).

Discovery reads the official open-data page for the current year, picks the
newest ``Utgifter <month> <year>`` release (definitive beats preliminary for
the same month), its ``Senast uppdaterad`` date and the Zip (CSV) link. The CSV
covers January 2006 up to the release month; rows are identified by the
stable ``Anslag`` code, never by display names.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

from aiohttp import ClientSession

from ..models import (
    DatapointStatus,
    ReferencePeriod,
    SourceRelease,
    SpendingDataPoint,
)
from ..registry import FOCUS_COUNTRY, STATSKONTORET, source_spec
from .base import ParseResult, Payload, SchemaChangedError, async_fetch_bytes

BASE_URL = "https://www.statskontoret.se"
DISCOVERY_URL = f"{BASE_URL}/analys-och-statistik/oppna-data/manadsutfall/"
UNIT = "SEK_MILLION"
EXPENDITURE_AREA = "06"
DEFENCE_PREFIX = "0601"
MATERIEL_APPROPRIATION = "0601003"
MONTH_COLUMNS: tuple[str, ...] = (
    "Utfall januari", "Utfall februari", "Utfall mars", "Utfall april",
    "Utfall maj", "Utfall juni", "Utfall juli", "Utfall augusti",
    "Utfall september", "Utfall oktober", "Utfall november", "Utfall december",
)
REQUIRED_COLUMNS: tuple[str, ...] = ("Utgiftsområde", "Anslag", "År", *MONTH_COLUMNS)
METRICS: tuple[tuple[str, Callable[[str, str], bool]], ...] = (
    ("uo6_total_outturn", lambda area, _anslag: area == EXPENDITURE_AREA),
    ("uo6_defence_outturn", lambda _area, anslag: anslag.startswith(DEFENCE_PREFIX)),
    ("materiel_outturn", lambda _area, anslag: anslag == MATERIEL_APPROPRIATION),
)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True, slots=True)
class DiscoveredRelease:
    year: int
    month: int
    status_raw: str
    updated: date | None
    csv_url: str
    heading: str

    @property
    def is_definitive(self) -> bool:
        return self.status_raw.casefold().startswith("definitiv")


class _DiscoveryParser(HTMLParser):
    """Collect heading, ``Senast uppdaterad`` and links per ``<li class="data">``."""

    def __init__(self) -> None:
        super().__init__()
        self.entries: list[tuple[str, str | None, list[str]]] = []
        self._in_entry = False
        self._heading: list[str] = []
        self._updated: str | None = None
        self._links: list[str] = []
        self._capture: str | None = None
        self._await_dd = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "li" and "data" in (attributes.get("class") or "").split():
            self._in_entry, self._heading, self._updated, self._links = True, [], None, []
        elif self._in_entry and tag == "h2":
            self._capture = "h2"
        elif self._in_entry and tag == "dt":
            self._capture = "dt"
        elif self._in_entry and tag == "dd" and self._await_dd:
            self._capture = "dd"
        elif self._in_entry and tag == "a" and attributes.get("href"):
            self._links.append(attributes["href"] or "")

    def handle_data(self, data: str) -> None:
        if self._capture == "h2":
            self._heading.append(data)
        elif self._capture == "dt":
            self._await_dd = "senast uppdaterad" in data.casefold()
        elif self._capture == "dd":
            match = _DATE.search(data)
            if match:
                self._updated = match.group(0)
            self._await_dd = False

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h2", "dt", "dd"}:
            self._capture = None
        elif tag == "li" and self._in_entry:
            self.entries.append(("".join(self._heading).strip(), self._updated, self._links))
            self._in_entry = False


def parse_discovery_page(html_text: str, page_url: str) -> list[DiscoveredRelease]:
    """Expenditure (Utgifter) releases on the page, oldest first."""
    parser = _DiscoveryParser()
    parser.feed(html_text)
    releases: list[DiscoveredRelease] = []
    for heading, updated, links in parser.entries:
        for href in links:
            query = parse_qs(urlsplit(href).query)
            if query.get("documentType") != ["Utgift"] or query.get("fileType") != ["Zip"]:
                continue
            try:
                year = int(query["Year"][0])
                month = int(query["month"][0])
                status_raw = query["status"][0]
            except (KeyError, IndexError, ValueError) as err:
                raise SchemaChangedError(f"unexpected Statskontoret link {href!r}") from err
            releases.append(
                DiscoveredRelease(
                    year=year,
                    month=month,
                    status_raw=status_raw,
                    updated=date.fromisoformat(updated) if updated else None,
                    csv_url=urljoin(page_url, href),
                    heading=heading,
                )
            )
    releases.sort(key=lambda r: (r.year, r.month, r.is_definitive))
    return releases


def select_latest(releases: list[DiscoveredRelease]) -> DiscoveredRelease:
    if not releases:
        raise SchemaChangedError("no Utgifter releases found on the Statskontoret page")
    return releases[-1]


def status_of(status_raw: str) -> DatapointStatus:
    folded = status_raw.casefold()
    if folded.startswith("definitiv"):
        return DatapointStatus.ACTUAL
    if folded.startswith("prelimin"):
        return DatapointStatus.PRELIMINARY
    raise SchemaChangedError(f"unknown Statskontoret status {status_raw!r}")


def release_from(discovered: DiscoveredRelease, page_url: str) -> SourceRelease:
    slug = "definitiv" if discovered.is_definitive else "preliminar"
    updated = discovered.updated.isoformat() if discovered.updated else "unknown"
    return SourceRelease(
        source_id=STATSKONTORET,
        release_id=f"{discovered.year}-{discovered.month:02d}-{slug}-{updated}",
        published_at=discovered.updated,
        download_url=discovered.csv_url,
        canonical_url=page_url,
        format="csv",
    )


def _release_period(release: SourceRelease) -> tuple[int, int, DatapointStatus]:
    query = parse_qs(urlsplit(release.download_url).query)
    try:
        return int(query["Year"][0]), int(query["month"][0]), status_of(query["status"][0])
    except (KeyError, IndexError, ValueError) as err:
        raise SchemaChangedError(
            f"release URL lacks Year/month/status: {release.download_url}"
        ) from err


def _csv_text(payload: bytes) -> str:
    if payload[:2] == b"PK":
        archive = zipfile.ZipFile(io.BytesIO(payload))
        names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise SchemaChangedError("Statskontoret zip contains no CSV")
        payload = archive.read(names[0])
    return payload.decode("utf-8-sig")


def _decimal(text: str) -> Decimal | None:
    if not text.strip():
        return None
    try:
        return Decimal(text.strip().replace(",", "."))
    except InvalidOperation as err:
        raise SchemaChangedError(f"non-numeric outturn value {text!r}") from err


def parse_outturn_csv(payload: bytes, release: SourceRelease) -> ParseResult:
    """Sum the three metrics per (year, month) from the appropriation rows."""
    rows = list(csv.reader(io.StringIO(_csv_text(payload)), delimiter=";"))
    if not rows:
        raise SchemaChangedError("Statskontoret CSV is empty")
    header = rows[0]
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise SchemaChangedError(f"Statskontoret CSV lacks columns {missing}")
    index = {name: header.index(name) for name in REQUIRED_COLUMNS}
    sums: dict[tuple[str, int, int], Decimal] = {}
    matched_rows = 0
    for row in rows[1:]:
        if len(row) < len(header):
            continue
        area, anslag = row[index["Utgiftsområde"]], row[index["Anslag"]]
        if area != EXPENDITURE_AREA:
            continue
        matched_rows += 1
        year = int(row[index["År"]])
        for month, column in enumerate(MONTH_COLUMNS, start=1):
            value = _decimal(row[index[column]])
            if value is None:
                continue
            for metric_id, predicate in METRICS:
                if predicate(area, anslag):
                    key = (metric_id, year, month)
                    sums[key] = sums.get(key, Decimal(0)) + value
    if matched_rows == 0:
        raise SchemaChangedError("Statskontoret CSV has no rows for utgiftsområde 06")
    release_year, release_month, release_status = _release_period(release)
    datapoints = tuple(
        SpendingDataPoint(
            source_id=STATSKONTORET,
            metric_id=metric_id,
            country=FOCUS_COUNTRY,
            reference=ReferencePeriod.month(year, month),
            value=value,
            unit=UNIT,
            status=release_status
            if (year, month) == (release_year, release_month)
            else DatapointStatus.ACTUAL,
            release_id=release.release_id,
            published_at=release.published_at,
            source_url=release.canonical_url,
        )
        for (metric_id, year, month), value in sorted(sums.items())
    )
    return ParseResult(datapoints, (), ";".join(header))


class StatskontoretProvider:
    """Discovery page → newest Utgifter Zip → CSV."""

    def __init__(self, *, today: Callable[[], date] = date.today) -> None:
        self.spec = source_spec(STATSKONTORET)
        self._today = today

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease:
        year = self._today().year
        for candidate in (year, year - 1):
            page_url = f"{DISCOVERY_URL}?year={candidate}"
            page = await async_fetch_bytes(session, page_url)
            releases = parse_discovery_page(page.payload.decode("utf-8", "replace"), page_url)
            if releases:
                return release_from(select_latest(releases), page_url)
        raise SchemaChangedError("Statskontoret lists no Utgifter releases for this or last year")

    async def async_fetch_release(
        self, session: ClientSession, release: SourceRelease
    ) -> tuple[SourceRelease, Payload]:
        fetched = await async_fetch_bytes(session, release.download_url)
        return with_fetch_metadata(release, fetched), fetched.payload

    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult:
        if not isinstance(payload, bytes):
            raise SchemaChangedError("Statskontoret expects a single CSV/Zip payload")
        return parse_outturn_csv(payload, release)
```

Add `with_fetch_metadata` to `providers/base.py` (every provider uses it; add `import dataclasses` at the top of base.py):

```python
def with_fetch_metadata(release: SourceRelease, fetched: FetchResult) -> SourceRelease:
    """Copy of ``release`` carrying the validators and checksum of ``fetched``."""
    return dataclasses.replace(
        release,
        etag=fetched.etag,
        last_modified=fetched.last_modified,
        checksum=fetched.checksum,
    )
```

and import it in the provider: `from .base import ParseResult, Payload, SchemaChangedError, async_fetch_bytes, with_fetch_metadata`.

Register the provider in `providers/__init__.py`:

```python
from .statskontoret import StatskontoretProvider


def all_providers() -> tuple[SpendingProvider, ...]:
    """Providers in plan order (Statskontoret, Eurostat, NATO, EDA, SIPRI)."""
    return (StatskontoretProvider(),)
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/spending/test_statskontoret.py -q`
Expected: 7 passed. If `test_parse_july_2026_file` reports a different count, inspect the trimmed fixture (`grep -c '^06;' tests/fixtures/spending/statskontoret/utgifter-2026-07.csv`): 2025 must have 12 months and 2026 seven months for each of the three metrics (57 datapoints).

- [ ] **Step 6: Write `docs/providers/statskontoret.md`**

```markdown
# Provider: Statskontoret monthly budget outturn

| Item | Value |
| --- | --- |
| Canonical discovery URL | `https://www.statskontoret.se/analys-och-statistik/oppna-data/manadsutfall/?year=YYYY` |
| Verified example (2026-09-12) | `Utgifter juli 2026`, `Senast uppdaterad 2026-08-24`, Zip link `GetFile?documentType=Utgift&fileType=Zip&…&Year=2026&month=7&status=Definitiv` |
| Format | Zip containing one CSV: `;`-delimited, UTF-8 with BOM, decimal comma, 31 columns, one row per appropriation item × agency × year, months as columns (`Utfall januari` … `Utfall december`), values in SEK million |
| Coverage | January 2006 → release month; every release contains the full history |
| Licence | CC0 (stated on the page) |
| Cadence | Monthly, "senast sista vardagen i månaden efter aktuell utfallsmånad" |
| Publication date | `Senast uppdaterad` on the discovery page (the Zip has no `Last-Modified`) |
| Reference period | Calendar month; YTD is computed from months |

## Metric mapping (S9)

| metric_id | Rows | Unit |
| --- | --- | --- |
| `uo6_total_outturn` | `Utgiftsområde == "06"` | SEK_MILLION |
| `uo6_defence_outturn` | `Anslag` starts with `0601` (1:1–1:14) | SEK_MILLION |
| `materiel_outturn` | `Anslag == "0601003"` (1:3 Anskaffning av materiel och anläggningar; FMV and Försvarsmakten items incl. Läglighetsköp) | SEK_MILLION |

## Status semantics

`status=Definitiv` → `actual`; `status=Preliminär 1` → `preliminary` **for the release month only** (earlier months in a preliminary file equal the earlier definitive releases). December appears twice: preliminary (late January) and definitive (late March). The definitive release replaces the preliminary datapoints (same key) and records a revision when the value differs — December 2025 materiel: 19 729.43 → 23 327.02.

## Parser assumptions

- Columns are looked up by name; `Utgiftsområde`, `Anslag`, `År` and the twelve month columns are required (`SchemaChangedError` otherwise).
- Rows with `Utgiftsområde != "06"` are ignored; a file without UO6 rows fails.
- Empty month cells mean "not yet reported"; a month is emitted only when at least one row has a value.
- Release year/month/status are read from the `GetFile` query parameters.

## Known weaknesses

- No budget figure (anslagsbelopp) in the CSV: budget utilisation needs another official source (see `docs/phase3-source-profile.md`).
- The discovery page is HTML; the parser depends on `<li class="data">`, `<h2>`, `<dt>Senast uppdaterad</dt><dd>` and the `GetFile` query parameters.

## Fixtures

`tests/fixtures/spending/statskontoret/` — `discovery-2026.html`, `discovery-2025.html`, `utgifter-2026-07.csv`, `utgifter-2025-12-preliminar.csv`, `utgifter-2025-12-definitiv.csv` (trimmed to UO6 rows 2025–2026 by `scripts/fetch_spending_fixtures.py`).
```

- [ ] **Step 7: Quality gate and commit**

Run: `uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q`

```bash
git add scripts/fetch_spending_fixtures.py tests/fixtures/spending/statskontoret custom_components/edp_radar/spending/providers tests/spending/test_statskontoret.py docs/providers/statskontoret.md
git commit -m "feat(spending): Statskontoret monthly outturn provider (S9)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Eurostat `gov_ev` provider (JSON-stat by dimension codes)

**Files:**
- Modify: `scripts/fetch_spending_fixtures.py` (add `eurostat`)
- Create: `tests/fixtures/spending/eurostat/gov_ev-defence.json`
- Create: `custom_components/edp_radar/spending/providers/eurostat.py`
- Create: `docs/providers/eurostat.md`
- Modify: `custom_components/edp_radar/spending/providers/__init__.py`
- Test: `tests/spending/test_eurostat.py`

**Interfaces:**
- Consumes: Task 1–3 types, `countries.EUROSTAT_GEO_FIXES`, `countries.EUROSTAT_AGGREGATES`, `registry.EUROSTAT`.
- Produces: `EurostatProvider`, `API_URL`, `parse_jsonstat(payload, release) -> ParseResult`, `release_from_payload(payload) -> SourceRelease`.

- [ ] **Step 1: Extend the fixture script and capture the fixture**

Add to `scripts/fetch_spending_fixtures.py` (after the Statskontoret section; register `"eurostat": fetch_eurostat` in `FETCHERS`):

```python
# ---------------------------------------------------------------------- Eurostat

EUROSTAT_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_ev"
    "?lang=en&expend=DEF&na_item=TE&na_item=P51G&unit=MIO_EUR&unit=PC_GDP&unit=MIO_NAC"
)


def fetch_eurostat(cache: Path) -> None:
    payload = download(EUROSTAT_URL, cache, "eurostat-gov_ev.json")
    write(FIXTURES / "eurostat" / "gov_ev-defence.json", payload)
```

Run: `PYTHONPATH=. uv run python scripts/fetch_spending_fixtures.py eurostat`
Expected: a ≈ 13 KB JSON with `"updated": "2026-04-27T23:00:00+0200"` and `"size": [1, 1, 2, 3, 28, 5]`.

- [ ] **Step 2: Write the failing tests**

`tests/spending/test_eurostat.py`:

```python
"""Eurostat gov_ev JSON-stat decoding (S10; plan §20–§26, §82)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.spending.models import DatapointStatus
from custom_components.edp_radar.spending.providers.base import SchemaChangedError
from custom_components.edp_radar.spending.providers.eurostat import (
    API_URL,
    EurostatProvider,
    parse_jsonstat,
    release_from_payload,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "spending" / "eurostat" / "gov_ev-defence.json"


def _payload() -> bytes:
    return FIXTURE.read_bytes()


def test_release_from_updated_timestamp() -> None:
    release = release_from_payload(_payload())
    assert release.release_id == "2026-04-27T23:00:00+0200"
    assert release.published_at == date(2026, 4, 27)
    assert release.download_url == API_URL
    assert release.format == "json-stat"


def test_parse_all_countries_and_units() -> None:
    result = parse_jsonstat(_payload(), release_from_payload(_payload()))
    points = {(p.metric_id, p.country, p.reference.start.year): p for p in result.datapoints}
    assert points[("defence_expenditure", "SE", 2025)].value == Decimal("17196.9")
    assert points[("defence_expenditure_pct_gdp", "SE", 2025)].value == Decimal("2.9")
    assert points[("defence_expenditure_nac", "SE", 2025)].value == Decimal("190306.0")
    assert points[("defence_investment", "SE", 2025)].value == Decimal("4864.3")
    assert points[("defence_investment_pct_gdp", "SE", 2025)].value == Decimal("0.8")
    assert points[("defence_investment", "DE", 2025)].value == Decimal("13527.0")
    assert points[("defence_expenditure", "GR", 2025)].value == Decimal("5998.0")
    assert ("defence_expenditure", "IT", 2025) not in points
    assert not any(p.country.startswith("EU") for p in result.datapoints)
    assert len({p.country for p in result.datapoints}) == 27
    assert len(result.datapoints) == 771
    assert {p.status for p in result.datapoints} == {DatapointStatus.ACTUAL}
    assert points[("defence_expenditure", "SE", 2025)].unit == "EUR_MILLION"
    assert points[("defence_expenditure", "SE", 2025)].reference.label == "2025"
    assert result.layout_fingerprint == "freq,expend,na_item,unit,geo,time"


def test_dimension_order_independence_and_status_flags() -> None:
    data = json.loads(_payload())
    # Reorder dimensions: time first, geo last; rebuild the value map accordingly.
    ids = data["id"]
    new_ids = ["time", "freq", "expend", "na_item", "unit", "geo"]
    sizes = dict(zip(ids, data["size"], strict=True))
    index = {k: data["dimension"][k]["category"]["index"] for k in ids}

    def old_strides() -> dict[str, int]:
        strides, step = {}, 1
        for k in reversed(ids):
            strides[k], step = step, step * sizes[k]
        return strides

    def new_strides() -> dict[str, int]:
        strides, step = {}, 1
        for k in reversed(new_ids):
            strides[k], step = step, step * sizes[k]
        return strides

    old_s, new_s = old_strides(), new_strides()
    new_value: dict[str, float] = {}
    for old_flat, value in data["value"].items():
        remaining = int(old_flat)
        positions = {}
        for k in ids:
            positions[k], remaining = divmod(remaining, old_s[k])
        new_value[str(sum(positions[k] * new_s[k] for k in new_ids))] = value
    data["id"], data["size"] = new_ids, [sizes[k] for k in new_ids]
    data["value"] = new_value
    se_2025 = sum(
        index[k][code] * new_s[k]
        for k, code in (("time", "2025"), ("freq", "A"), ("expend", "DEF"), ("na_item", "TE"), ("unit", "MIO_EUR"), ("geo", "SE"))
    )
    data["status"] = {str(se_2025): "p"}
    payload = json.dumps(data).encode()
    result = parse_jsonstat(payload, release_from_payload(payload))
    point = next(p for p in result.datapoints if p.metric_id == "defence_expenditure" and p.country == "SE" and p.reference.start.year == 2025)
    assert point.value == Decimal("17196.9")
    assert point.status is DatapointStatus.PROVISIONAL
    assert point.flags == ("p",)
    assert len(result.datapoints) == 771


def test_missing_codes_fail() -> None:
    data = json.loads(_payload())
    del data["dimension"]["na_item"]["category"]["index"]["P51G"]
    data["size"][2] = 1
    with pytest.raises(SchemaChangedError, match="P51G"):
        parse_jsonstat(json.dumps(data).encode(), release_from_payload(_payload()))
    with pytest.raises(SchemaChangedError, match="updated"):
        release_from_payload(b'{"class": "dataset"}')


async def test_provider_round_trip(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(API_URL, content=_payload())
    provider = EurostatProvider()
    session = async_get_clientsession(hass)
    release = await provider.async_discover_latest(session)
    fetched, payload = await provider.async_fetch_release(session, release)
    assert len(aioclient_mock.mock_calls) == 1  # discovery payload is reused
    assert fetched.checksum
    assert len(provider.parse_release(payload, fetched).datapoints) == 771
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_eurostat.py -q`
Expected: `ImportError`.

- [ ] **Step 4: Implement the provider**

`custom_components/edp_radar/spending/providers/eurostat.py`:

```python
"""Eurostat ``gov_ev`` defence expenditure and investment (S10; plan §20–§26).

One fixed Statistics-API request; JSON-stat 2.0 is decoded through ``id``,
``size`` and the dimension category indexes, never through array positions.
"""

from __future__ import annotations

import itertools
import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from aiohttp import ClientSession

from ..countries import EUROSTAT_AGGREGATES, EUROSTAT_GEO_FIXES
from ..models import (
    DatapointStatus,
    ReferencePeriod,
    SourceRelease,
    SpendingDataPoint,
)
from ..registry import EUROSTAT, source_spec
from .base import (
    FetchResult,
    ParseResult,
    Payload,
    SchemaChangedError,
    async_fetch_bytes,
    sha256_hex,
    with_fetch_metadata,
)

API_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_ev"
    "?lang=en&expend=DEF&na_item=TE&na_item=P51G&unit=MIO_EUR&unit=PC_GDP&unit=MIO_NAC"
)
CANONICAL_URL = "https://ec.europa.eu/eurostat/cache/metadata/en/gov_ev_esms.htm"
EXPEND = "DEF"
METRICS: dict[tuple[str, str], tuple[str, str]] = {
    ("TE", "MIO_EUR"): ("defence_expenditure", "EUR_MILLION"),
    ("TE", "MIO_NAC"): ("defence_expenditure_nac", "NAC_MILLION"),
    ("TE", "PC_GDP"): ("defence_expenditure_pct_gdp", "PCT_GDP"),
    ("P51G", "MIO_EUR"): ("defence_investment", "EUR_MILLION"),
    ("P51G", "MIO_NAC"): ("defence_investment_nac", "NAC_MILLION"),
    ("P51G", "PC_GDP"): ("defence_investment_pct_gdp", "PCT_GDP"),
}
FLAG_STATUS: dict[str, DatapointStatus] = {
    "p": DatapointStatus.PROVISIONAL,
    "e": DatapointStatus.ESTIMATE,
    "f": DatapointStatus.PROJECTION,
}


def _load(payload: bytes) -> dict[str, Any]:
    try:
        data = json.loads(payload)
    except ValueError as err:
        raise SchemaChangedError(f"Eurostat response is not JSON: {err}") from err
    if not isinstance(data, dict) or data.get("class") != "dataset":
        raise SchemaChangedError("Eurostat response is not a JSON-stat dataset")
    return data


def release_from_payload(payload: bytes) -> SourceRelease:
    data = _load(payload)
    updated = data.get("updated")
    if not isinstance(updated, str):
        raise SchemaChangedError("Eurostat dataset has no 'updated' timestamp")
    return SourceRelease(
        source_id=EUROSTAT,
        release_id=updated,
        published_at=datetime.fromisoformat(updated).date(),
        download_url=API_URL,
        canonical_url=CANONICAL_URL,
        format="json-stat",
    )


def _index(data: dict[str, Any], dimension: str) -> dict[str, int]:
    try:
        index = data["dimension"][dimension]["category"]["index"]
    except (KeyError, TypeError) as err:
        raise SchemaChangedError(f"Eurostat dimension {dimension!r} missing") from err
    if isinstance(index, list):
        return {str(code): position for position, code in enumerate(index)}
    return {str(code): int(position) for code, position in index.items()}


def _status_flags(data: dict[str, Any]) -> dict[int, str]:
    status = data.get("status")
    if isinstance(status, dict):
        return {int(k): str(v) for k, v in status.items()}
    if isinstance(status, list):
        return {i: str(v) for i, v in enumerate(status) if v}
    return {}


def parse_jsonstat(payload: bytes, release: SourceRelease) -> ParseResult:
    data = _load(payload)
    ids: list[str] = [str(i) for i in data.get("id", [])]
    sizes: list[int] = [int(s) for s in data.get("size", [])]
    for required in ("expend", "na_item", "unit", "geo", "time"):
        if required not in ids:
            raise SchemaChangedError(f"Eurostat dimension {required!r} missing")
    indexes = {dim: _index(data, dim) for dim in ids}
    if EXPEND not in indexes["expend"]:
        raise SchemaChangedError("Eurostat expend code DEF missing")
    for na_item, unit in METRICS:
        if na_item not in indexes["na_item"]:
            raise SchemaChangedError(f"Eurostat na_item code {na_item} missing")
        if unit not in indexes["unit"]:
            raise SchemaChangedError(f"Eurostat unit code {unit} missing")
    strides: dict[str, int] = {}
    step = 1
    for dim, size in zip(reversed(ids), reversed(sizes), strict=True):
        strides[dim] = step
        step *= size
    values = data.get("value")
    if not isinstance(values, dict):
        raise SchemaChangedError("Eurostat value map missing")
    flags = _status_flags(data)
    fixed = {dim: indexes[dim] for dim in ids if dim not in {"na_item", "unit", "geo", "time"}}
    fixed_offset = 0
    for dim, index in fixed.items():
        code = EXPEND if dim == "expend" else next(iter(index))
        fixed_offset += index[code] * strides[dim]
    warnings: list[str] = []
    datapoints: list[SpendingDataPoint] = []
    for (na_item, unit), (metric_id, unit_id) in METRICS.items():
        base = fixed_offset + indexes["na_item"][na_item] * strides["na_item"] + indexes["unit"][unit] * strides["unit"]
        for (geo, geo_pos), (time, time_pos) in itertools.product(indexes["geo"].items(), indexes["time"].items()):
            if geo in EUROSTAT_AGGREGATES:
                continue
            flat = base + geo_pos * strides["geo"] + time_pos * strides["time"]
            raw = values.get(str(flat))
            if raw is None:
                continue
            try:
                year = int(time)
            except ValueError:
                warnings.append(f"time code {time!r} is not a year")
                continue
            flag = flags.get(flat, "")
            status = next((FLAG_STATUS[c] for c in flag if c in FLAG_STATUS), DatapointStatus.ACTUAL)
            datapoints.append(
                SpendingDataPoint(
                    source_id=EUROSTAT,
                    metric_id=metric_id,
                    country=EUROSTAT_GEO_FIXES.get(geo, geo),
                    reference=ReferencePeriod.year(year),
                    value=Decimal(str(raw)),
                    unit=unit_id,
                    status=status,
                    release_id=release.release_id,
                    published_at=release.published_at,
                    source_url=CANONICAL_URL,
                    flags=(flag,) if flag else (),
                )
            )
    return ParseResult(tuple(datapoints), tuple(warnings), ",".join(ids))


class EurostatProvider:
    """Discovery *is* the request: the response carries ``updated``."""

    def __init__(self) -> None:
        self.spec = source_spec(EUROSTAT)
        self._cached: tuple[str, FetchResult] | None = None

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease:
        fetched = await async_fetch_bytes(session, API_URL)
        release = release_from_payload(fetched.payload)
        self._cached = (release.release_id, fetched)
        return with_fetch_metadata(release, fetched)

    async def async_fetch_release(
        self, session: ClientSession, release: SourceRelease
    ) -> tuple[SourceRelease, Payload]:
        if self._cached is not None and self._cached[0] == release.release_id:
            fetched = self._cached[1]
        else:
            fetched = await async_fetch_bytes(session, API_URL)
        if fetched.checksum != sha256_hex(fetched.payload):
            raise SchemaChangedError("Eurostat payload checksum mismatch")
        return with_fetch_metadata(release, fetched), fetched.payload

    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult:
        if not isinstance(payload, bytes):
            raise SchemaChangedError("Eurostat expects a single JSON payload")
        return parse_jsonstat(payload, release)
```

Register in `providers/__init__.py`: `return (StatskontoretProvider(), EurostatProvider())`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/spending/test_eurostat.py -q`
Expected: 5 passed.

- [ ] **Step 6: Write `docs/providers/eurostat.md`**

```markdown
# Provider: Eurostat `gov_ev`

| Item | Value |
| --- | --- |
| Canonical metadata URL | `https://ec.europa.eu/eurostat/cache/metadata/en/gov_ev_esms.htm` |
| Request (fixed) | `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_ev?lang=en&expend=DEF&na_item=TE&na_item=P51G&unit=MIO_EUR&unit=PC_GDP&unit=MIO_NAC` |
| Verified (2026-09-12) | `updated 2026-04-27T23:00:00+0200`; dimensions `freq=A`, `expend=DEF`, `na_item=P51G,TE`, `unit=MIO_EUR,MIO_NAC,PC_GDP`, `geo` = EU27_2020 + 27 member states (`EL` = Greece), `time` 2021–2025; 771 country values, no `status` flags |
| Format | JSON-stat 2.0 |
| Cadence | Reported twice yearly (end of March, end of September); disseminated twice yearly |
| Publication date | `updated` in the response (also the release id) |
| Reference period | Calendar year |

## Metric mapping (S10)

| na_item | unit | metric_id | unit |
| --- | --- | --- | --- |
| TE | MIO_EUR | `defence_expenditure` | EUR_MILLION |
| TE | MIO_NAC | `defence_expenditure_nac` | NAC_MILLION |
| TE | PC_GDP | `defence_expenditure_pct_gdp` | PCT_GDP |
| P51G | MIO_EUR | `defence_investment` | EUR_MILLION |
| P51G | MIO_NAC | `defence_investment_nac` | NAC_MILLION |
| P51G | PC_GDP | `defence_investment_pct_gdp` | PCT_GDP |

## Status semantics

JSON-stat `status` flags per observation: `p` → provisional, `e` → estimate, `f` → projection, anything else → `actual` with the flag kept in `flags`. The 2026-04 dissemination carries no flags at all; April/October are never inferred as preliminary/final (plan §23).

## Parser assumptions

- `class == "dataset"`, `id`/`size`/`dimension`/`value` present; flat indexes computed from `size` (row-major, last dimension fastest).
- Codes `DEF`, `TE`, `P51G`, `MIO_EUR`, `PC_GDP`, `MIO_NAC` must exist (`SchemaChangedError` otherwise).
- `EL → GR`, `UK → GB`; `EU27_2020` and other aggregates are skipped.
- Missing observations (e.g. IT/ES/NL 2025 in the 2026-04 release) produce no datapoint.

## Known weaknesses

- Coverage starts 2021; `gov_10a_exp` (COFOG) is a separate, future series (plan §25).
- Fewer countries report the latest year: rankings must state population size.

## Fixtures

`tests/fixtures/spending/eurostat/gov_ev-defence.json` (complete real response, 13 KB).
```

- [ ] **Step 7: Quality gate and commit**

Run: `uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q`

```bash
git add scripts/fetch_spending_fixtures.py tests/fixtures/spending/eurostat custom_components/edp_radar/spending/providers tests/spending/test_eurostat.py docs/providers/eurostat.md
git commit -m "feat(spending): Eurostat gov_ev provider (S10)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: XLSX helpers and the NATO provider

**Files:**
- Create: `custom_components/edp_radar/spending/xlsx.py`
- Modify: `scripts/fetch_spending_fixtures.py` (add `nato`)
- Create: `tests/fixtures/spending/nato/def-exp-2026-en.xlsx`, `def-exp-2025-en.xlsx`, `topic-page.html`
- Create: `custom_components/edp_radar/spending/providers/nato.py`
- Create: `docs/providers/nato.md`
- Modify: `custom_components/edp_radar/spending/providers/__init__.py`
- Test: `tests/spending/test_xlsx.py`, `tests/spending/test_nato.py`

**Interfaces:**
- Consumes: Task 1–3 types, `countries.resolve_country`, `countries.normalise_label`, `countries.SKIP_LABELS`, `base.async_head_metadata`, `base.http_date_to_date`.
- Produces: `xlsx.open_workbook(payload) -> Workbook`, `xlsx.require_sheet(wb, name)`, `xlsx.rows_of(ws) -> list[tuple[Any, ...]]` (cells), `xlsx.text(cell) -> str`, `xlsx.number(value) -> Decimal | None`, `xlsx.find_row(rows, predicate, *, start=0, what) -> int`, `xlsx.year_header(row) -> dict[int, tuple[int, bool]]`, `xlsx.font_colour_index(cell) -> int | None`; `NatoProvider`, `TOPIC_URL`, `discover_workbook(html_text, base_url) -> tuple[int, str]`, `parse_nato_workbook(payload, release) -> ParseResult`.

- [ ] **Step 1: Write the failing XLSX helper tests**

`tests/spending/test_xlsx.py`:

```python
"""openpyxl helper behaviour on a generated workbook (S11)."""

from __future__ import annotations

import io
from decimal import Decimal

import pytest
from openpyxl import Workbook
from openpyxl.styles import Font

from custom_components.edp_radar.spending.providers.base import SchemaChangedError
from custom_components.edp_radar.spending.xlsx import (
    find_row,
    font_colour_index,
    number,
    open_workbook,
    require_sheet,
    rows_of,
    text,
    year_header,
)


def _workbook() -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = "Table 1"
    sheet.append(["Table 1: Core defence expenditure"])
    sheet.append([None, 2024, "2025e", "2026e"])
    sheet.append(["Sweden (Kronor)", 140549, 187790.5, "..."])
    sheet.cell(row=3, column=3).font = Font(color="FF0000FF")
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_sheet_rows_text_and_numbers() -> None:
    book = open_workbook(_workbook())
    rows = rows_of(require_sheet(book, "Table 1"))
    assert text(rows[0][0]) == "Table 1: Core defence expenditure"
    assert text(rows[1][0]) == ""
    assert number(rows[2][1].value) == Decimal("140549")
    assert number(rows[2][2].value) == Decimal("187790.5")
    assert number("...") is None
    assert number("xxx") is None
    assert number("-") is None
    assert number("1 234,5") == Decimal("1234.5")
    assert number(None) is None
    with pytest.raises(SchemaChangedError, match="Table 9"):
        require_sheet(book, "Table 9")


def test_find_row_and_year_header() -> None:
    rows = rows_of(require_sheet(open_workbook(_workbook()), "Table 1"))
    assert find_row(rows, lambda t: t.startswith("Table 1:"), what="title") == 0
    with pytest.raises(SchemaChangedError, match="subtitle"):
        find_row(rows, lambda t: t == "nope", what="subtitle")
    assert year_header(rows[1]) == {1: (2024, False), 2: (2025, True), 3: (2026, True)}
    assert year_header(rows[0]) == {}


def test_font_colour_index_reads_rgb_and_indexed() -> None:
    rows = rows_of(require_sheet(open_workbook(_workbook()), "Table 1"))
    assert font_colour_index(rows[2][2]) == 12  # blue, mapped from FF0000FF
    assert font_colour_index(rows[2][1]) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/spending/test_xlsx.py -q`
Expected: `ImportError`.

- [ ] **Step 3: Implement `xlsx.py`**

```python
"""openpyxl helpers shared by the NATO, EDA and SIPRI parsers (S11).

Workbooks are opened read-only with cached values (``data_only``). Cells keep
their font so SIPRI's blue (estimate) and red (highly uncertain) markers can be
read; the legacy indexed palette maps blue to 12 and red to 10.
"""

from __future__ import annotations

import io
import re
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any

from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook

from .providers.base import SchemaChangedError

_YEAR = re.compile(r"^(\d{4})\s*(e?)$")
_MISSING = frozenset({"", "..", "...", ". .", "xxx", "-", ":", "n/a", "na"})
_RGB_TO_INDEXED = {"0000FF": 12, "FF0000": 10, "000000": 8}


def open_workbook(payload: bytes) -> Workbook:
    try:
        return load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
    except Exception as err:  # openpyxl raises several unrelated types
        raise SchemaChangedError(f"workbook cannot be opened: {err}") from err


def require_sheet(book: Workbook, name: str) -> Any:
    if name not in book.sheetnames:
        raise SchemaChangedError(f"sheet {name!r} missing; found {book.sheetnames}")
    return book[name]


def rows_of(sheet: Any) -> list[tuple[Any, ...]]:
    return [tuple(row) for row in sheet.iter_rows()]


def text(cell: Any) -> str:
    value = getattr(cell, "value", cell)
    return "" if value is None else str(value).strip()


def number(value: Any) -> Decimal | None:
    """Numeric cell → Decimal; SIPRI/NATO/EDA missing markers → None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return Decimal(str(value))
    if isinstance(value, Decimal):
        return value
    cleaned = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if cleaned.casefold() in _MISSING:
        return None
    try:
        return Decimal(cleaned.replace(",", "."))
    except InvalidOperation:
        return None


def find_row(
    rows: list[tuple[Any, ...]],
    predicate: Callable[[str], bool],
    *,
    start: int = 0,
    what: str,
) -> int:
    for index in range(start, len(rows)):
        if rows[index] and predicate(text(rows[index][0])):
            return index
    raise SchemaChangedError(f"{what} not found from row {start + 1}")


def year_header(row: tuple[Any, ...]) -> dict[int, tuple[int, bool]]:
    """``{column: (year, is_estimate)}`` for cells like ``2024``/``"2025e"``."""
    years: dict[int, tuple[int, bool]] = {}
    for column, cell in enumerate(row):
        value = getattr(cell, "value", cell)
        if isinstance(value, int | float) and not isinstance(value, bool):
            if 1900 <= int(value) <= 2100:
                years[column] = (int(value), False)
            continue
        match = _YEAR.match(text(value))
        if match:
            years[column] = (int(match.group(1)), match.group(2) == "e")
    return years


def font_colour_index(cell: Any) -> int | None:
    font = getattr(cell, "font", None)
    colour = getattr(font, "color", None)
    if colour is None:
        return None
    if colour.type == "indexed":
        return int(colour.indexed)
    if colour.type == "rgb" and isinstance(colour.rgb, str):
        return _RGB_TO_INDEXED.get(colour.rgb[-6:].upper())
    return None
```

- [ ] **Step 4: Run the helper tests**

Run: `uv run pytest tests/spending/test_xlsx.py -q`
Expected: 3 passed. (If `number("1 234,5")` fails, the non-breaking-space replacement is missing.)

- [ ] **Step 5: Extend the fixture script and capture the NATO fixtures**

Add to `scripts/fetch_spending_fixtures.py` (register `"nato": fetch_nato`):

```python
# -------------------------------------------------------------------------- NATO

NATO_TOPIC = "https://www.nato.int/en/what-we-do/introduction-to-nato/defence-expenditures-and-natos-5-commitment"
NATO_XLSX = "https://www.nato.int/content/dam/nato/webready/documents/finance/def-exp-{year}-en.xlsx"
_NATO_ARCHIVE = re.compile(r'<a href=\\?"[^"]*def-exp-\d{4}-en\.(?:pdf|PDF)\\?"[^>]*>\d{4}</a>')


def trim_nato_topic(html: str) -> str:
    """Keep only the archive anchors (``def-exp-YYYY-en.pdf``) the discovery needs."""
    anchors = _NATO_ARCHIVE.findall(html)
    body = "\n".join(a.replace('\\"', '"') for a in anchors)
    return f"<!DOCTYPE html>\n<html lang=\"en\"><body><p>Archive of tables</p>\n{body}\n</body></html>\n"


def fetch_nato(cache: Path) -> None:
    folder = FIXTURES / "nato"
    topic = download(NATO_TOPIC, cache, "nato-topic.html")
    write(folder / "topic-page.html", trim_nato_topic(topic.decode("utf-8", "replace")).encode("utf-8"))
    for year in (2026, 2025):
        write(folder / f"def-exp-{year}-en.xlsx", download(NATO_XLSX.format(year=year), cache, f"def-exp-{year}-en.xlsx"))
```

(The workbooks are 70 KB and 108 KB and contain no formulas; they are kept whole.)

Run: `PYTHONPATH=. uv run python scripts/fetch_spending_fixtures.py nato`
Expected: `topic-page.html` lists anchors for 2026, 2025, 2024 … (the page embeds the anchors inside a JSON attribute with escaped quotes and again as plain HTML; both forms are kept as plain anchors); both workbooks written.

- [ ] **Step 6: Write the failing NATO tests**

`tests/spending/test_nato.py`:

```python
"""NATO discovery and workbook parsing (S11; plan §27–§33, §83)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.spending.models import DatapointStatus, SourceRelease
from custom_components.edp_radar.spending.providers.base import SchemaChangedError
from custom_components.edp_radar.spending.providers.nato import (
    TOPIC_URL,
    NatoProvider,
    discover_workbook,
    parse_nato_workbook,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spending" / "nato"
XLSX_2026 = "https://www.nato.int/content/dam/nato/webready/documents/finance/def-exp-2026-en.xlsx"


def _release(year: int = 2026) -> SourceRelease:
    return SourceRelease(
        source_id="nato",
        release_id=f"{year}:test",
        published_at=date(2026, 7, 10),
        download_url=XLSX_2026.replace("2026", str(year)),
        canonical_url=TOPIC_URL,
        format="xlsx",
    )


def test_discover_picks_newest_archive_year() -> None:
    html = (FIXTURES / "topic-page.html").read_text(encoding="utf-8")
    assert discover_workbook(html, TOPIC_URL) == (2026, XLSX_2026)
    with pytest.raises(SchemaChangedError, match="def-exp"):
        discover_workbook("<html></html>", TOPIC_URL)


def test_parse_2026_workbook_sweden_and_status() -> None:
    result = parse_nato_workbook((FIXTURES / "def-exp-2026-en.xlsx").read_bytes(), _release())
    points = {(p.metric_id, p.country, p.reference.start.year): p for p in result.datapoints}
    assert points[("defence_expenditure_nac", "SE", 2024)].value == Decimal("140549")
    assert points[("defence_expenditure_nac", "SE", 2024)].flags == ("currency:Kronor",)
    assert points[("defence_expenditure_usd_current", "SE", 2026)].value == Decimal("24186")
    assert points[("defence_expenditure_usd_current", "SE", 2026)].status is DatapointStatus.ESTIMATE
    assert points[("defence_expenditure_usd_current", "SE", 2024)].status is DatapointStatus.ACTUAL
    assert points[("defence_expenditure_usd_constant", "SE", 2026)].value == Decimal("21538")
    assert points[("defence_expenditure_pct_gdp", "SE", 2026)].value == Decimal("3.22")
    assert points[("equipment_share_pct", "SE", 2026)].value == Decimal("25.41")
    derived = points[("equipment_expenditure_usd_current", "SE", 2026)]
    assert derived.value == Decimal("24186") * Decimal("25.41") / Decimal(100)
    assert derived.status is DatapointStatus.ESTIMATE
    assert derived.flags == ("derived",)
    assert points[("defence_expenditure_usd_current", "SI", 2026)].flags == ("footnote_star",)
    assert points[("defence_expenditure_usd_current", "US", 2026)].value == Decimal("1032849")
    assert points[("defence_expenditure_usd_current", "TR", 2026)].country == "TR"
    countries = {p.country for p in result.datapoints if p.metric_id == "defence_expenditure_usd_current"}
    assert len(countries) == 31 and "IS" not in countries
    assert not any(p.country.startswith("NATO") for p in result.datapoints)
    assert result.warnings == ()
    assert result.layout_fingerprint.startswith("Table 1: Core defence expenditure")


def test_parse_2025_workbook_layout_variant() -> None:
    result = parse_nato_workbook((FIXTURES / "def-exp-2025-en.xlsx").read_bytes(), _release(2025))
    points = {(p.metric_id, p.country, p.reference.start.year): p for p in result.datapoints}
    assert points[("defence_expenditure_usd_current", "SE", 2025)].status is DatapointStatus.ESTIMATE
    assert points[("defence_expenditure_usd_current", "SE", 2023)].status is DatapointStatus.ACTUAL
    assert points[("defence_expenditure_nac", "SE", 2025)].flags == ("currency:Kronor", "footnote_star")
    assert points[("equipment_share_pct", "SE", 2025)].value == Decimal("35.82725060827251")
    assert result.layout_fingerprint.startswith("Table 1: Defence expenditure")


def test_layout_change_fails() -> None:
    from openpyxl import Workbook
    import io

    book = Workbook()
    book.active.title = "Table 1"
    book.active.append(["Table 1: Something else"])
    for name in ("Table 2", "Table 3", "Table 8a"):
        book.create_sheet(name).append([f"{name}: x"])
    buffer = io.BytesIO()
    book.save(buffer)
    with pytest.raises(SchemaChangedError):
        parse_nato_workbook(buffer.getvalue(), _release())


async def test_provider_discovery_uses_head_metadata(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(TOPIC_URL, text=(FIXTURES / "topic-page.html").read_text(encoding="utf-8"))
    aioclient_mock.head(
        XLSX_2026,
        headers={"ETag": '"0x8DEDE695735E099"', "Last-Modified": "Fri, 10 Jul 2026 09:55:14 GMT"},
    )
    provider = NatoProvider()
    session = async_get_clientsession(hass)
    release = await provider.async_discover_latest(session)
    assert release.release_id == '2026:"0x8DEDE695735E099"'
    assert release.published_at == date(2026, 7, 10)
    assert release.download_url == XLSX_2026
    aioclient_mock.get(XLSX_2026, content=(FIXTURES / "def-exp-2026-en.xlsx").read_bytes())
    fetched, payload = await provider.async_fetch_release(session, release)
    assert fetched.checksum
    assert len(provider.parse_release(payload, fetched).datapoints) > 1500
```

- [ ] **Step 7: Run to verify failure**

Run: `uv run pytest tests/spending/test_nato.py -q`
Expected: `ImportError`.

- [ ] **Step 8: Implement the NATO provider**

`custom_components/edp_radar/spending/providers/nato.py`:

```python
"""NATO defence expenditure workbook (S11; plan §27–§33).

Discovery reads the stable topic page's "Archive of tables" links
(``def-exp-YYYY-en.pdf``), takes the newest year and derives the XLSX on the
same path. Tables are located by sheet name, title prefix and block subtitle;
years come from the header row (``2025e`` marks estimates); countries from
label tables. The equipment value is derived (plan §30) and flagged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientSession

from ..countries import SKIP_LABELS, normalise_label, resolve_country
from ..models import (
    DatapointStatus,
    ReferencePeriod,
    SourceRelease,
    SpendingDataPoint,
)
from ..registry import NATO, source_spec
from ..xlsx import find_row, number, open_workbook, require_sheet, rows_of, text, year_header
from .base import (
    ParseResult,
    Payload,
    SchemaChangedError,
    async_fetch_bytes,
    async_head_metadata,
    http_date_to_date,
    with_fetch_metadata,
)

TOPIC_URL = "https://www.nato.int/en/what-we-do/introduction-to-nato/defence-expenditures-and-natos-5-commitment"
_ARCHIVE_LINK = re.compile(r'href=\\?"([^"\\]*def-exp-(\d{4})-en\.pdf)\\?"', re.IGNORECASE)
_CURRENCY = re.compile(r"\(([^)]*)\)\s*$")


@dataclass(frozen=True, slots=True)
class TableSpec:
    sheet: str
    block: int
    subtitle: str
    metric_id: str
    unit: str
    keep_currency: bool = False


TABLES: tuple[TableSpec, ...] = (
    TableSpec("Table 1", 0, "current prices", "defence_expenditure_nac", "NAC_MILLION", True),
    TableSpec("Table 2", 0, "current prices", "defence_expenditure_usd_current", "USD_MILLION"),
    TableSpec("Table 2", 1, "constant 2021", "defence_expenditure_usd_constant", "USD_MILLION_CONSTANT_2021"),
    TableSpec("Table 3", 0, "share of real gdp", "defence_expenditure_pct_gdp", "PCT_GDP"),
    TableSpec("Table 8a", 0, "equipment", "equipment_share_pct", "PCT"),
)


def discover_workbook(html_text: str, base_url: str) -> tuple[int, str]:
    """Newest archive year and its XLSX URL."""
    best: tuple[int, str] | None = None
    for path, year in _ARCHIVE_LINK.findall(html_text):
        candidate = (int(year), urljoin(base_url, path[:-4] + ".xlsx"))
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        raise SchemaChangedError("NATO topic page has no def-exp-YYYY-en links")
    return best


def _blocks(rows: list[tuple[Any, ...]]) -> list[tuple[int, dict[int, tuple[int, bool]]]]:
    """Header rows (empty first cell + year cells) with their year map."""
    found = []
    for index, row in enumerate(rows):
        if row and text(row[0]) == "":
            years = year_header(row)
            if years:
                found.append((index, years))
    return found


def _subtitle_before(rows: list[tuple[Any, ...]], header_index: int) -> str:
    for index in range(header_index - 1, max(-1, header_index - 4), -1):
        label = text(rows[index][0]) if rows[index] else ""
        if label:
            return label
    return ""


def _parse_table(
    rows: list[tuple[Any, ...]], spec: TableSpec, release: SourceRelease
) -> tuple[list[SpendingDataPoint], list[str]]:
    blocks = _blocks(rows)
    if len(blocks) <= spec.block:
        raise SchemaChangedError(f"{spec.sheet}: block {spec.block} missing")
    header_index, years = blocks[spec.block]
    subtitle = _subtitle_before(rows, header_index).casefold()
    if spec.subtitle not in subtitle:
        raise SchemaChangedError(f"{spec.sheet}: expected subtitle containing {spec.subtitle!r}, got {subtitle!r}")
    points: list[SpendingDataPoint] = []
    warnings: list[str] = []
    for row in rows[header_index + 1 :]:
        label = text(row[0]) if row else ""
        if not label or label.casefold().startswith("notes"):
            break
        plain = normalise_label(label)
        if plain in SKIP_LABELS:
            continue
        country = resolve_country(label)
        if country is None:
            warnings.append(f"{spec.sheet}: unknown country label {label!r}")
            continue
        flags: list[str] = []
        currency = _CURRENCY.search(label)
        if spec.keep_currency and currency:
            flags.append(f"currency:{currency.group(1).strip()}")
        if "*" in label:
            flags.append("footnote_star")
        for column, (year, is_estimate) in years.items():
            value = number(row[column].value if column < len(row) else None)
            if value is None:
                continue
            points.append(
                SpendingDataPoint(
                    source_id=NATO,
                    metric_id=spec.metric_id,
                    country=country,
                    reference=ReferencePeriod.year(year),
                    value=value,
                    unit=spec.unit,
                    status=DatapointStatus.ESTIMATE if is_estimate else DatapointStatus.ACTUAL,
                    release_id=release.release_id,
                    published_at=release.published_at,
                    source_url=release.canonical_url,
                    flags=tuple(flags),
                )
            )
    return points, warnings


def _derive_equipment(points: list[SpendingDataPoint], release: SourceRelease) -> list[SpendingDataPoint]:
    usd = {(p.country, p.reference.start.year): p for p in points if p.metric_id == "defence_expenditure_usd_current"}
    share = {(p.country, p.reference.start.year): p for p in points if p.metric_id == "equipment_share_pct"}
    derived = []
    for key, total in usd.items():
        pct = share.get(key)
        if pct is None:
            continue
        estimate = DatapointStatus.ESTIMATE in (total.status, pct.status)
        derived.append(
            SpendingDataPoint(
                source_id=NATO,
                metric_id="equipment_expenditure_usd_current",
                country=total.country,
                reference=total.reference,
                value=total.value * pct.value / Decimal(100),
                unit="USD_MILLION",
                status=DatapointStatus.ESTIMATE if estimate else DatapointStatus.ACTUAL,
                release_id=release.release_id,
                published_at=release.published_at,
                source_url=release.canonical_url,
                flags=("derived",),
            )
        )
    return derived


def parse_nato_workbook(payload: bytes, release: SourceRelease) -> ParseResult:
    book = open_workbook(payload)
    points: list[SpendingDataPoint] = []
    warnings: list[str] = []
    titles: list[str] = []
    for spec in TABLES:
        rows = rows_of(require_sheet(book, spec.sheet))
        title_index = find_row(rows, lambda t, s=spec.sheet: t.startswith(f"{s}:"), what=f"{spec.sheet} title")
        if spec.block == 0:
            titles.append(text(rows[title_index][0]))
        table_points, table_warnings = _parse_table(rows, spec, release)
        if not table_points:
            raise SchemaChangedError(f"{spec.sheet}: no country rows parsed")
        points.extend(table_points)
        warnings.extend(table_warnings)
    points.extend(_derive_equipment(points, release))
    return ParseResult(tuple(points), tuple(warnings), " | ".join(titles))


class NatoProvider:
    def __init__(self) -> None:
        self.spec = source_spec(NATO)

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease:
        page = await async_fetch_bytes(session, TOPIC_URL)
        year, xlsx_url = discover_workbook(page.payload.decode("utf-8", "replace"), TOPIC_URL)
        etag, last_modified = await async_head_metadata(session, xlsx_url)
        return SourceRelease(
            source_id=NATO,
            release_id=f"{year}:{etag or last_modified or 'unknown'}",
            published_at=http_date_to_date(last_modified),
            download_url=xlsx_url,
            canonical_url=TOPIC_URL,
            format="xlsx",
            etag=etag,
            last_modified=last_modified,
        )

    async def async_fetch_release(
        self, session: ClientSession, release: SourceRelease
    ) -> tuple[SourceRelease, Payload]:
        fetched = await async_fetch_bytes(session, release.download_url)
        return with_fetch_metadata(release, fetched), fetched.payload

    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult:
        if not isinstance(payload, bytes):
            raise SchemaChangedError("NATO expects a single workbook payload")
        return parse_nato_workbook(payload, release)
```

Register in `providers/__init__.py`: `return (StatskontoretProvider(), EurostatProvider(), NatoProvider())`.

- [ ] **Step 9: Run the tests**

Run: `uv run pytest tests/spending/test_nato.py -q`
Expected: 5 passed. If `test_discover_picks_newest_archive_year` fails, print the fixture's anchors: the topic page embeds them twice (escaped inside a JSON attribute and plain); the regex accepts both `href="` and `href=\"`.

- [ ] **Step 10: Write `docs/providers/nato.md`**

```markdown
# Provider: NATO defence expenditure

| Item | Value |
| --- | --- |
| Canonical discovery URL | `https://www.nato.int/en/what-we-do/introduction-to-nato/defence-expenditures-and-natos-5-commitment` ("Archive of tables": `def-exp-YYYY-en.pdf` per year) |
| Verified (2026-09-12) | newest year 2026 → `https://www.nato.int/content/dam/nato/webready/documents/finance/def-exp-2026-en.xlsx` (69 931 bytes, `ETag "0x8DEDE695735E099"`, `Last-Modified Fri, 10 Jul 2026 09:55:14 GMT`); 2025 workbook also available (108 341 bytes) |
| Format | XLSX, sheets `Table 1` … `Table 8b`; each sheet: title in A1 (`Table N: …`), unit rows, then blocks of `<blank> ; 2014 … 2024 ; 2025e ; 2026e` header + country rows; aggregate rows `NATO Europe and Canada`, `NATO Total`; `Notes:` row at the end |
| Cadence | Annual (June/July), occasionally revised in between |
| Publication date | `Last-Modified` of the XLSX (the topic page has no date) |
| Reference period | Calendar year; `e` suffix = estimate |

## Metric mapping (S11)

| Sheet / block | Subtitle check | metric_id | unit |
| --- | --- | --- | --- |
| Table 1 / 0 | "current prices" | `defence_expenditure_nac` (flag `currency:<name>` from the label) | NAC_MILLION |
| Table 2 / 0 | "current prices" | `defence_expenditure_usd_current` | USD_MILLION |
| Table 2 / 1 | "constant 2021" | `defence_expenditure_usd_constant` | USD_MILLION_CONSTANT_2021 |
| Table 3 / 0 | "share of real gdp" | `defence_expenditure_pct_gdp` | PCT_GDP |
| Table 8a / 0 | "equipment" | `equipment_share_pct` | PCT |
| derived | — | `equipment_expenditure_usd_current` = USD current × equipment share / 100 (flag `derived`; estimate if either input is) | USD_MILLION |

## Status semantics

Header `YYYYe` → `estimate`; otherwise `actual`. The 2026 workbook marks 2025 and 2026 as estimates; the 2025 workbook 2024 and 2025. Country labels with `*` carry `footnote_star` (2026: Slovenia; 2025: eleven allies with revised figures). Aggregates are skipped.

## Parser assumptions

- Sheet names `Table 1`, `Table 2`, `Table 3`, `Table 8a` exist; A1 starts with `Table N:` (2025: "Defence expenditure", 2026: "Core defence expenditure" — the prefix is what is checked, the full titles form the layout fingerprint).
- Blocks are header rows with an empty first cell and year cells; the nearest non-empty row above must contain the expected subtitle keyword.
- Country rows end at a blank row or a `Notes` row. Iceland has no row (no armed forces).

## Known weaknesses

- Equipment value is derived, not published; the derivation is explicit and tested (plan §30).
- Discovery depends on the archive anchor pattern `def-exp-YYYY-en.pdf` and on the XLSX sharing its path.

## Fixtures

`tests/fixtures/spending/nato/def-exp-2026-en.xlsx`, `def-exp-2025-en.xlsx` (whole workbooks), `topic-page.html` (archive anchors only).
```

- [ ] **Step 11: Quality gate and commit**

Run: `uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q`

```bash
git add custom_components/edp_radar/spending scripts/fetch_spending_fixtures.py tests/fixtures/spending/nato tests/spending/test_xlsx.py tests/spending/test_nato.py docs/providers/nato.md
git commit -m "feat(spending): XLSX helpers and NATO provider (S11)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: EDA provider (portal → every `Defence Data YYYY` workbook ≥ 2022)

**Files:**
- Create: `docs/providers/eda.md` (first — plan §36 requires the profile before the parser)
- Modify: `scripts/fetch_spending_fixtures.py` (add `eda`)
- Create: `tests/fixtures/spending/eda/portal.html`, `defence-data-2025.xlsx`, `defence-data-2022.xlsx`
- Create: `custom_components/edp_radar/spending/providers/eda.py`
- Modify: `custom_components/edp_radar/spending/providers/__init__.py`
- Test: `tests/spending/test_eda.py`

**Interfaces:**
- Consumes: Task 1–3 types, `xlsx.*`, `countries.*`.
- Produces: `EdaProvider`, `PORTAL_URL`, `MIN_YEAR = 2022`, `discover_workbooks(html_text, base_url) -> dict[int, str]`, `parse_eda_workbooks(payload: Mapping[str, bytes], release) -> ParseResult`.

- [ ] **Step 1: Write `docs/providers/eda.md` from the verified profile**

```markdown
# Provider: EDA defence data

Profiled 2026-09-12 on the workbooks linked from the portal (plan §36).

| Item | Value |
| --- | --- |
| Canonical discovery URL | `https://www.eda.europa.eu/publications-and-data/defence-data` |
| Verified links | anchors `<a href='…xlsx'><span>Defence Data YYYY</span></a>` for 2020–2025: `final-defence-data-2025-1.xlsx`, `defence-data-2024.xlsx`, `defence-data-2023.xlsx`, `eda-2022-defence-data.xlsx`, `defence-data-2021.xlsx`, `data-by-pms-for-the-eda-website.xlsx` (2020); `Last-Modified` present on the files |
| Layout 2022–2025 | sheets `EU27` (aggregates only), `Billions` (26 countries × 2005–2021, long format), `Member States[ YYYY]` (27 countries, **one year per workbook**) |
| Layout 2020–2021 | one sheet per country, years 2017–2021 — subset of `Billions`; **not used** |
| Formulas | workbooks contain formulas (cached values are read with `data_only`); fixtures are therefore kept as the original bytes |
| Cadence | Annual (Defence Data report, late summer/autumn); revisions possible |
| Publication date | `Last-Modified` of the newest workbook |
| Reference period | Calendar year |

## Sheets and columns

`Member States` header (normalised): `eu ms | year | total defence expenditure | defence investment | total defence expenditure as % of gdp | total defence expenditure as % of government expenditure | total defence expenditure per capita`. Values: EUR million (current prices), ratios as fractions, EUR per capita. Footnote rows start with `*`: `*Estimated 2025 figures` (labels with one `*`), `**Luxembourg … GNI`, `***Slovenia …`. Labels may carry trailing spaces (`Croatia `) and use `Czech Republic`.

`Billions` header: `pms | year | total defence expenditure | defence equipment procurement expenditure | defence r&d expenditure | defence investment | gdp (mrd) | total defence expenditure as % of gdp`. Despite the sheet name the expenditure columns are EUR million (Sweden 2021 = 6 000 = EUR 6.0 bn); `gdp (mrd)` is EUR billion. 26 countries (no Denmark), 2005–2021, identical in the 2022–2025 workbooks (frozen history). `-` = not available.

## Metric verdicts (plan §39)

| metric_id | Source sheet | Years | Verdict |
| --- | --- | --- | --- |
| `defence_expenditure` | Member States (2022+), Billions (2005–2021) | 2005–2025 | GREEN |
| `defence_investment` | Member States, Billions | 2005–2025 | GREEN |
| `defence_expenditure_pct_gdp` | Member States, Billions (×100) | 2005–2025 | GREEN |
| `defence_expenditure_pct_government` | Member States (×100) | 2022–2025 | GREEN |
| `defence_expenditure_per_capita` | Member States | 2022–2025 | GREEN |
| `equipment_procurement` | Billions only | 2005–2021 | GREEN for history, **not available for current years** at country level |
| `defence_rnd` | Billions only | 2005–2021 | GREEN for history only |
| collaborative procurement / R&T | `EU27` aggregates only | — | not exposed (no country level) |

## Status semantics

Member States: label with exactly one `*` and a footnote row starting with `*Estimated` → `estimate`; otherwise `actual`. `**` → flag `note_2`, `***` → flag `note_3`. Billions: `actual`, flag `sheet:billions`.

## Parser assumptions

- One sheet whose name starts with `Member States` per workbook; header matched by normalised prefixes; `Year` column gives the reference year.
- `Billions` is read from the newest workbook only.
- Workbooks before 2022 are ignored (different layout, no additional data).

## Known weaknesses

- Country-level equipment procurement stops in 2021; the `EU27` sheet has newer aggregates only.
- Denmark is absent from `Billions` (joined the data set in 2021).

## Fixtures

`tests/fixtures/spending/eda/portal.html` (anchors only), `defence-data-2025.xlsx`, `defence-data-2022.xlsx` (original bytes).
```

- [ ] **Step 2: Extend the fixture script and capture the fixtures**

Add to `scripts/fetch_spending_fixtures.py` (register `"eda": fetch_eda`):

```python
# --------------------------------------------------------------------------- EDA

EDA_PORTAL = "https://www.eda.europa.eu/publications-and-data/defence-data"
_EDA_ANCHOR = re.compile(
    r"""<a[^>]*href=(?:"|')[^"']*\.xlsx(?:"|')[^>]*>\s*(?:<span>)?\s*Defence Data \d{4}\s*(?:</span>)?\s*</a>""",
    re.I | re.S,
)
_EDA_LINK = re.compile(r"""href=(["'])([^"']*\.xlsx)\1[^>]*>\s*(?:<span>)?\s*Defence Data (\d{4})""", re.I | re.S)


def trim_eda_portal(html: str) -> str:
    anchors = _EDA_ANCHOR.findall(html)
    return "<!DOCTYPE html>\n<html lang=\"en\"><body>\n" + "\n".join(anchors) + "\n</body></html>\n"


def fetch_eda(cache: Path) -> None:
    folder = FIXTURES / "eda"
    portal = download(EDA_PORTAL, cache, "eda-portal.html").decode("utf-8", "replace")
    write(folder / "portal.html", trim_eda_portal(portal).encode("utf-8"))
    links = {int(year): url for _, url, year in _EDA_LINK.findall(portal)}
    for year in (2025, 2022):
        write(folder / f"defence-data-{year}.xlsx", download(links[year], cache, f"eda-{year}.xlsx"))
```

Run: `PYTHONPATH=. uv run python scripts/fetch_spending_fixtures.py eda`
Expected: `portal.html` with six anchors (2020–2025); two workbooks (≈ 80 KB each).

- [ ] **Step 3: Write the failing tests**

`tests/spending/test_eda.py`:

```python
"""EDA discovery and multi-workbook parsing (S11; plan §34–§39, §84)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.spending.models import DatapointStatus, SourceRelease
from custom_components.edp_radar.spending.providers.base import SchemaChangedError
from custom_components.edp_radar.spending.providers.eda import (
    MIN_YEAR,
    PORTAL_URL,
    EdaProvider,
    discover_workbooks,
    parse_eda_workbooks,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spending" / "eda"
URL_2025 = "https://eda.europa.eu/docs/default-source/documents/defence-data/final-defence-data-2025-1.xlsx"
URL_2022 = "https://eda.europa.eu/docs/default-source/documents/defence-data/eda-2022-defence-data.xlsx"


def _release() -> SourceRelease:
    return SourceRelease("eda", "2025:test", date(2026, 9, 4), URL_2025, PORTAL_URL, "xlsx")


def _payload() -> dict[str, bytes]:
    return {
        "2025": (FIXTURES / "defence-data-2025.xlsx").read_bytes(),
        "2022": (FIXTURES / "defence-data-2022.xlsx").read_bytes(),
    }


def test_discover_lists_workbooks_by_year() -> None:
    links = discover_workbooks((FIXTURES / "portal.html").read_text(encoding="utf-8"), PORTAL_URL)
    assert sorted(links) == [2020, 2021, 2022, 2023, 2024, 2025]
    assert links[2025] == URL_2025
    assert links[2022] == URL_2022
    assert MIN_YEAR == 2022
    with pytest.raises(SchemaChangedError, match="Defence Data"):
        discover_workbooks("<html></html>", PORTAL_URL)


def test_member_states_sheets_and_estimates() -> None:
    result = parse_eda_workbooks(_payload(), _release())
    points = {(p.metric_id, p.country, p.reference.start.year): p for p in result.datapoints}
    se = points[("defence_expenditure", "SE", 2025)]
    assert se.value == Decimal("14788.962566848055")
    assert se.status is DatapointStatus.ACTUAL
    assert se.unit == "EUR_MILLION"
    assert points[("defence_investment", "SE", 2025)].value == Decimal("4227.901618627983")
    assert points[("defence_expenditure_pct_gdp", "SE", 2025)].value == Decimal("0.024880146027005542") * 100
    assert points[("defence_expenditure_pct_government", "SE", 2025)].value == Decimal("0.05697066959157698") * 100
    assert points[("defence_expenditure_per_capita", "SE", 2025)].value == Decimal("1386.9598218459764")
    assert points[("defence_expenditure", "DK", 2025)].status is DatapointStatus.ESTIMATE
    assert points[("defence_expenditure", "LU", 2025)].flags == ("note_2",)
    assert points[("defence_expenditure", "SI", 2025)].flags == ("note_3",)
    assert points[("defence_expenditure", "HR", 2025)].country == "HR"
    assert points[("defence_expenditure", "SE", 2022)].value == Decimal("7872")
    assert points[("defence_expenditure", "DK", 2022)].status is DatapointStatus.ACTUAL
    assert len({p.country for p in result.datapoints if p.reference.start.year == 2025}) == 27


def test_billions_history_from_newest_workbook_only() -> None:
    result = parse_eda_workbooks(_payload(), _release())
    points = {(p.metric_id, p.country, p.reference.start.year): p for p in result.datapoints}
    assert points[("equipment_procurement", "SE", 2021)].value == Decimal("1500")
    assert points[("equipment_procurement", "SE", 2020)].value == Decimal("1454.37")
    assert points[("defence_rnd", "SE", 2021)].value == Decimal("88.2")
    assert points[("defence_expenditure", "SE", 2005)].value == Decimal("4433.18031115")
    assert points[("defence_expenditure", "SE", 2021)].flags == ("sheet:billions",)
    assert ("equipment_procurement", "SE", 2025) not in points
    assert ("defence_expenditure", "DK", 2021) not in points
    assert len({p.country for p in result.datapoints if p.metric_id == "equipment_procurement"}) == 26
    assert result.warnings == ()
    assert "member states 2025" in result.layout_fingerprint.casefold()


def test_missing_sheet_or_column_fails() -> None:
    payload = _payload()
    with pytest.raises(SchemaChangedError):
        parse_eda_workbooks({"2025": b"not a workbook"}, _release())
    import io
    from openpyxl import Workbook

    book = Workbook()
    book.active.title = "Member States 2030"
    book.active.append(["EU MS", "Year", "Total Defence Expenditure"])
    book.create_sheet("Billions").append(["PMS", "Year"])
    buffer = io.BytesIO()
    book.save(buffer)
    with pytest.raises(SchemaChangedError, match="Defence Investment"):
        parse_eda_workbooks(
            {"2030": buffer.getvalue()},
            SourceRelease("eda", "2030:test", None, URL_2025, PORTAL_URL, "xlsx"),
        )
    del payload["2025"]
    with pytest.raises(SchemaChangedError, match="newest"):
        parse_eda_workbooks(payload, SourceRelease("eda", "2025:x", None, URL_2025, PORTAL_URL, "xlsx"))


async def test_provider_discovers_and_fetches_every_recent_workbook(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(PORTAL_URL, text=(FIXTURES / "portal.html").read_text(encoding="utf-8"))
    links = discover_workbooks((FIXTURES / "portal.html").read_text(encoding="utf-8"), PORTAL_URL)
    for year, url in links.items():
        aioclient_mock.head(url, headers={"Last-Modified": f"Fri, 04 Sep 2026 10:13:{year % 60:02d} GMT"})
        fixture = FIXTURES / f"defence-data-{year}.xlsx"
        aioclient_mock.get(url, content=fixture.read_bytes() if fixture.exists() else (FIXTURES / "defence-data-2022.xlsx").read_bytes())
    provider = EdaProvider()
    session = async_get_clientsession(hass)
    release = await provider.async_discover_latest(session)
    assert release.release_id.startswith("2025:")
    assert release.published_at == date(2026, 9, 4)
    assert release.download_url == URL_2025
    fetched, payload = await provider.async_fetch_release(session, release)
    assert isinstance(payload, dict) and sorted(payload) == ["2022", "2023", "2024", "2025"]
    assert fetched.checksum
    result = provider.parse_release(payload, fetched)
    assert any(p.reference.start.year == 2025 for p in result.datapoints)
```

- [ ] **Step 4: Run to verify failure**

Run: `uv run pytest tests/spending/test_eda.py -q`
Expected: `ImportError`.

- [ ] **Step 5: Implement the provider**

`custom_components/edp_radar/spending/providers/eda.py`:

```python
"""EDA defence data workbooks (S11; plan §34–§39; docs/providers/eda.md).

Country-level data lives in one ``Member States`` sheet per annual workbook
(one year each) plus the frozen ``Billions`` history (2005–2021) in every
workbook. Discovery lists every ``Defence Data YYYY`` link on the portal;
the provider fetches all workbooks from 2022 onwards and parses ``Billions``
from the newest one only.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientSession

from ..countries import resolve_country
from ..models import (
    DatapointStatus,
    ReferencePeriod,
    SourceRelease,
    SpendingDataPoint,
)
from ..registry import EDA, source_spec
from ..xlsx import number, open_workbook, require_sheet, rows_of, text
from .base import (
    ParseResult,
    Payload,
    SchemaChangedError,
    async_fetch_bytes,
    async_head_metadata,
    http_date_to_date,
    sha256_hex,
)

PORTAL_URL = "https://www.eda.europa.eu/publications-and-data/defence-data"
MIN_YEAR = 2022
_LINK = re.compile(
    r"""href=(["'])([^"']*\.xlsx)\1[^>]*>\s*(?:<span>)?\s*Defence Data (\d{4})""",
    re.IGNORECASE | re.DOTALL,
)
_STARS = re.compile(r"\*+")
PERCENT = Decimal(100)

# (normalised header, metric_id, unit, multiply by 100)
MEMBER_STATE_COLUMNS: tuple[tuple[str, str, str, bool], ...] = (
    ("total defence expenditure", "defence_expenditure", "EUR_MILLION", False),
    ("defence investment", "defence_investment", "EUR_MILLION", False),
    ("total defence expenditure as % of gdp", "defence_expenditure_pct_gdp", "PCT_GDP", True),
    ("total defence expenditure as % of government expenditure", "defence_expenditure_pct_government", "PCT", True),
    ("total defence expenditure per capita", "defence_expenditure_per_capita", "EUR", False),
)
BILLIONS_COLUMNS: tuple[tuple[str, str, str, bool], ...] = (
    ("total defence expenditure", "defence_expenditure", "EUR_MILLION", False),
    ("defence equipment procurement expenditure", "equipment_procurement", "EUR_MILLION", False),
    ("defence r&d expenditure", "defence_rnd", "EUR_MILLION", False),
    ("defence investment", "defence_investment", "EUR_MILLION", False),
    ("total defence expenditure as % of gdp", "defence_expenditure_pct_gdp", "PCT_GDP", True),
)


def discover_workbooks(html_text: str, base_url: str) -> dict[int, str]:
    links = {int(year): urljoin(base_url, url) for _, url, year in _LINK.findall(html_text)}
    if not links:
        raise SchemaChangedError("EDA portal has no 'Defence Data YYYY' workbook links")
    return links


def _normalise(header: str) -> str:
    return " ".join(header.split()).casefold()


def _columns(header_row: tuple[Any, ...], wanted: tuple[tuple[str, str, str, bool], ...], sheet: str) -> dict[str, int]:
    names = [_normalise(text(cell)) for cell in header_row]
    columns: dict[str, int] = {}
    for label in ("year",):
        if label not in names:
            raise SchemaChangedError(f"{sheet}: column {label!r} missing")
        columns[label] = names.index(label)
    for header, metric_id, _unit, _pct in wanted:
        if header not in names:
            pretty = header.title().replace("Gdp", "GDP").replace("R&D", "R&D")
            raise SchemaChangedError(f"{sheet}: column {pretty!r} missing")
        columns[metric_id] = names.index(header)
    return columns


def _member_states_sheet(book: Any) -> str:
    for name in book.sheetnames:
        if name.strip().casefold().startswith("member states"):
            return name
    raise SchemaChangedError(f"no 'Member States' sheet; found {book.sheetnames}")


def _emit(
    rows: list[tuple[Any, ...]],
    columns: dict[str, int],
    wanted: tuple[tuple[str, str, str, bool], ...],
    release: SourceRelease,
    *,
    sheet: str,
    estimates_marked: bool,
    extra_flags: tuple[str, ...],
    warnings: list[str],
) -> list[SpendingDataPoint]:
    points: list[SpendingDataPoint] = []
    for row in rows[1:]:
        label = text(row[0]) if row else ""
        if not label or label.startswith("*"):
            continue
        country = resolve_country(label)
        if country is None:
            warnings.append(f"{sheet}: unknown country label {label!r}")
            continue
        year_value = number(row[columns["year"]].value)
        if year_value is None:
            warnings.append(f"{sheet}: row {label!r} has no year")
            continue
        stars = _STARS.search(label)
        star_count = len(stars.group(0)) if stars else 0
        flags = list(extra_flags)
        status = DatapointStatus.ACTUAL
        if star_count == 1 and estimates_marked:
            status = DatapointStatus.ESTIMATE
        elif star_count > 1:
            flags.append(f"note_{star_count}")
        for _header, metric_id, unit, pct in wanted:
            value = number(row[columns[metric_id]].value)
            if value is None:
                continue
            points.append(
                SpendingDataPoint(
                    source_id=EDA,
                    metric_id=metric_id,
                    country=country,
                    reference=ReferencePeriod.year(int(year_value)),
                    value=value * PERCENT if pct else value,
                    unit=unit,
                    status=status,
                    release_id=release.release_id,
                    published_at=release.published_at,
                    source_url=release.canonical_url,
                    flags=tuple(flags),
                )
            )
    return points


def parse_eda_workbooks(payload: Mapping[str, bytes], release: SourceRelease) -> ParseResult:
    if not payload:
        raise SchemaChangedError("EDA payload has no workbooks")
    years = sorted(payload, key=int, reverse=True)
    newest = years[0]
    if release.release_id.split(":")[0] != newest:
        raise SchemaChangedError(f"EDA newest workbook {newest} does not match release {release.release_id}")
    points: list[SpendingDataPoint] = []
    warnings: list[str] = []
    fingerprints: list[str] = []
    for year in years:
        book = open_workbook(payload[year])
        sheet = _member_states_sheet(book)
        rows = rows_of(require_sheet(book, sheet))
        if not rows:
            raise SchemaChangedError(f"{sheet}: empty")
        columns = _columns(rows[0], MEMBER_STATE_COLUMNS, sheet)
        estimates_marked = any(text(r[0]).casefold().startswith("*estimated") for r in rows[1:] if r)
        sheet_points = _emit(rows, columns, MEMBER_STATE_COLUMNS, release, sheet=sheet,
                             estimates_marked=estimates_marked, extra_flags=(), warnings=warnings)
        if not sheet_points:
            raise SchemaChangedError(f"{sheet}: no country rows parsed")
        points.extend(sheet_points)
        fingerprints.append(f"{year}:{sheet.strip()}")
        if year == newest:
            billions = rows_of(require_sheet(book, "Billions"))
            if not billions:
                raise SchemaChangedError("Billions: empty")
            b_columns = _columns(billions[0], BILLIONS_COLUMNS, "Billions")
            b_points = _emit(billions, b_columns, BILLIONS_COLUMNS, release, sheet="Billions",
                             estimates_marked=False, extra_flags=("sheet:billions",), warnings=warnings)
            if not b_points:
                raise SchemaChangedError("Billions: no country rows parsed")
            points.extend(b_points)
            fingerprints.append("Billions")
    return ParseResult(tuple(points), tuple(warnings), " | ".join(fingerprints))


class EdaProvider:
    def __init__(self) -> None:
        self.spec = source_spec(EDA)
        self._links: dict[int, str] = {}
        self._validators: dict[int, tuple[str | None, str | None]] = {}

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease:
        page = await async_fetch_bytes(session, PORTAL_URL)
        links = discover_workbooks(page.payload.decode("utf-8", "replace"), PORTAL_URL)
        self._links = {year: url for year, url in links.items() if year >= MIN_YEAR}
        if not self._links:
            raise SchemaChangedError(f"EDA portal lists no workbook from {MIN_YEAR} onwards")
        newest = max(self._links)
        self._validators = {}
        for year, url in sorted(self._links.items()):
            self._validators[year] = await async_head_metadata(session, url)
        digest = hashlib.sha256(
            "|".join(f"{y}:{self._links[y]}:{e}:{m}" for y, (e, m) in sorted(self._validators.items())).encode()
        ).hexdigest()[:16]
        etag, last_modified = self._validators[newest]
        return SourceRelease(
            source_id=EDA,
            release_id=f"{newest}:{digest}",
            published_at=http_date_to_date(last_modified),
            download_url=self._links[newest],
            canonical_url=PORTAL_URL,
            format="xlsx",
            etag=etag,
            last_modified=last_modified,
        )

    async def async_fetch_release(
        self, session: ClientSession, release: SourceRelease
    ) -> tuple[SourceRelease, Payload]:
        if not self._links:
            await self.async_discover_latest(session)
        workbooks: dict[str, bytes] = {}
        for year, url in sorted(self._links.items()):
            workbooks[str(year)] = (await async_fetch_bytes(session, url)).payload
        combined = sha256_hex(b"".join(workbooks[y] for y in sorted(workbooks)))
        return dataclasses.replace(release, checksum=combined), workbooks

    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult:
        if isinstance(payload, bytes):
            raise SchemaChangedError("EDA expects one payload per workbook year")
        return parse_eda_workbooks(payload, release)
```

(`import dataclasses` at the top of the module; `with_fetch_metadata` is not needed here and should not be imported.)

Register in `providers/__init__.py`: `return (StatskontoretProvider(), EurostatProvider(), NatoProvider(), EdaProvider())`.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/spending/test_eda.py -q`
Expected: 5 passed. `test_provider_discovers_and_fetches_every_recent_workbook` serves the 2022 workbook for 2023/2024 (same layout) — the parser then sees `Member States` sheets carrying year 2022 four times; duplicate keys are tolerated by the parser (the store de-duplicates later), so only `any(... 2025 ...)` is asserted.

- [ ] **Step 7: Quality gate and commit**

Run: `uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q`

```bash
git add docs/providers/eda.md scripts/fetch_spending_fixtures.py tests/fixtures/spending/eda custom_components/edp_radar/spending/providers tests/spending/test_eda.py
git commit -m "feat(spending): EDA provider with per-metric verdicts (S11)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: SIPRI provider (landing page → workbook → three sheets, blue = estimate)

**Files:**
- Modify: `scripts/fetch_spending_fixtures.py` (add `sipri`)
- Create: `tests/fixtures/spending/sipri/landing.html`, `milex-trimmed.xlsx`
- Create: `custom_components/edp_radar/spending/providers/sipri.py`
- Create: `docs/providers/sipri.md`
- Modify: `custom_components/edp_radar/spending/providers/__init__.py`
- Test: `tests/spending/test_sipri.py`

**Interfaces:**
- Consumes: Task 1–3 types, `xlsx.*`, `countries.*`.
- Produces: `SipriProvider`, `LANDING_URL`, `MIN_YEAR = 1990`, `discover_release(html_text, base_url) -> tuple[str, date | None]`, `parse_sipri_workbook(payload, release) -> ParseResult`.

- [ ] **Step 1: Extend the fixture script and capture the fixtures**

Add to `scripts/fetch_spending_fixtures.py` (register `"sipri": fetch_sipri`; add `import openpyxl` at the top — the script runs under `uv run`, which has the dev group):

```python
# ------------------------------------------------------------------------- SIPRI

SIPRI_LANDING = "https://www.sipri.org/databases/milex"
_SIPRI_XLSX = re.compile(r'href="((?:https?:)?//www\.sipri\.org/[^"]*\.xlsx)"')
_SIPRI_REVISED = re.compile(r"revised on \d{1,2} [A-Za-z]+ \d{4}[^.<]{0,200}")
SIPRI_SHEETS = ("Constant (2024) US$", "Current US$", "Share of GDP")


def trim_sipri_landing(html: str) -> str:
    link = _SIPRI_XLSX.search(html)
    revised = _SIPRI_REVISED.search(html)
    if link is None or revised is None:
        raise SystemExit("SIPRI landing page: xlsx link or revision sentence not found")
    return (
        "<!DOCTYPE html>\n<html lang=\"en\"><body>\n"
        f'<p>The file was {revised.group(0)}.</p>\n'
        f'<a href="{link.group(1)}">Download the SIPRI Military Expenditure Database (Excel)</a>\n'
        "</body></html>\n"
    )


def trim_sipri_workbook(data: bytes) -> bytes:
    """Keep three data sheets and only the rows from 'Europe' on (colours survive)."""
    book = openpyxl.load_workbook(io.BytesIO(data))
    for name in list(book.sheetnames):
        if name not in SIPRI_SHEETS:
            book.remove(book[name])
    for name in SIPRI_SHEETS:
        sheet = book[name]
        header = next(i for i in range(1, 15) if str(sheet.cell(i, 1).value).strip() == "Country")
        europe = next(i for i in range(header + 1, sheet.max_row + 1) if str(sheet.cell(i, 1).value).strip() == "Europe")
        sheet.delete_rows(header + 2, europe - (header + 2))
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def fetch_sipri(cache: Path) -> None:
    folder = FIXTURES / "sipri"
    landing = download(SIPRI_LANDING, cache, "sipri-landing.html").decode("utf-8", "replace")
    write(folder / "landing.html", trim_sipri_landing(landing).encode("utf-8"))
    url = _SIPRI_XLSX.search(landing).group(1)  # type: ignore[union-attr]
    workbook = download("https:" + url if url.startswith("//") else url, cache, "sipri-milex.xlsx")
    write(folder / "milex-trimmed.xlsx", trim_sipri_workbook(workbook))
```

Run: `PYTHONPATH=. uv run python scripts/fetch_spending_fixtures.py sipri`
Expected: `landing.html` with the revision sentence ("revised on 27 April 2026 …") and the anchor `//www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2025_v1.2.xlsx`; `milex-trimmed.xlsx` ≈ 160 KB with 77 rows per sheet.

- [ ] **Step 2: Write the failing tests**

`tests/spending/test_sipri.py`:

```python
"""SIPRI discovery and workbook parsing (S11; plan §40–§44, §85)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.spending.models import DatapointStatus, SourceRelease
from custom_components.edp_radar.spending.providers.base import SchemaChangedError
from custom_components.edp_radar.spending.providers.sipri import (
    LANDING_URL,
    MIN_YEAR,
    SipriProvider,
    discover_release,
    parse_sipri_workbook,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spending" / "sipri"
XLSX_URL = "https://www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2025_v1.2.xlsx"


def _release() -> SourceRelease:
    return SourceRelease("sipri", "SIPRI-Milex-data-1949-2025_v1.2.xlsx:2026-04-27", date(2026, 4, 27), XLSX_URL, LANDING_URL, "xlsx")


def test_discover_link_and_revision_date() -> None:
    html = (FIXTURES / "landing.html").read_text(encoding="utf-8")
    assert discover_release(html, LANDING_URL) == (XLSX_URL, date(2026, 4, 27))
    assert discover_release('<a href="https://www.sipri.org/x/y.xlsx">x</a>', LANDING_URL) == ("https://www.sipri.org/x/y.xlsx", None)
    with pytest.raises(SchemaChangedError, match="xlsx"):
        discover_release("<html></html>", LANDING_URL)


def test_parse_sweden_estimates_and_notes() -> None:
    result = parse_sipri_workbook((FIXTURES / "milex-trimmed.xlsx").read_bytes(), _release())
    points = {(p.metric_id, p.country, p.reference.start.year): p for p in result.datapoints}
    assert points[("military_expenditure_usd_constant", "SE", 2025)].value == Decimal("14954.07135864315")
    assert points[("military_expenditure_usd_current", "SE", 2025)].value == Decimal("16473.47720649671")
    assert points[("military_expenditure_pct_gdp", "SE", 2025)].value == Decimal("0.02471184849540041") * 100
    assert points[("military_expenditure_usd_constant", "SE", 2025)].status is DatapointStatus.ACTUAL
    assert points[("military_expenditure_usd_constant", "SE", 1990)].status is DatapointStatus.ACTUAL
    assert ("military_expenditure_usd_constant", "SE", 1975) not in points  # below MIN_YEAR
    assert MIN_YEAR == 1990
    albania = points[("military_expenditure_usd_constant", "AL", 2025)]
    assert albania.status is DatapointStatus.BUDGET
    assert albania.flags == ("excludes_paramilitary", "footnote_3")
    assert points[("military_expenditure_usd_constant", "IS", 2025)].value == Decimal("0")
    assert points[("military_expenditure_usd_current", "TR", 2025)].flags == ("currency_redenominated", "footnote_105")
    assert not any(p.country in {"USSR", "European Union"} for p in result.datapoints)
    assert result.warnings == ()
    assert len({p.country for p in result.datapoints if p.metric_id == "military_expenditure_usd_current"}) == 59
    assert "blue" in result.layout_fingerprint.casefold()


def test_blue_font_is_estimate_when_present_above_min_year() -> None:
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font

    book = Workbook()
    for name in ("Constant (2024) US$", "Current US$", "Share of GDP"):
        sheet = book.create_sheet(name)
        sheet.append(["Military expenditure by country"])
        sheet.append(["x"])
        sheet.append(["Figures in blue are SIPRI estimates. Figures in red indicate highly uncertain data."])
        sheet.append(["Country", "Notes", 1990, 1991])
        sheet.append(["Europe"])
        sheet.append(["Sweden", None, 100, 200])
        sheet.cell(row=6, column=3).font = Font(color="FF0000FF")
        sheet.cell(row=6, column=4).font = Font(color="FFFF0000")
    book.remove(book["Sheet"])
    buffer = io.BytesIO()
    book.save(buffer)
    result = parse_sipri_workbook(buffer.getvalue(), _release())
    points = {(p.metric_id, p.reference.start.year): p for p in result.datapoints}
    assert points[("military_expenditure_usd_constant", 1990)].status is DatapointStatus.ESTIMATE
    assert points[("military_expenditure_usd_constant", 1991)].status is DatapointStatus.ACTUAL
    assert points[("military_expenditure_usd_constant", 1991)].flags == ("highly_uncertain",)


def test_missing_sheet_or_legend_fails() -> None:
    import io
    from openpyxl import Workbook

    book = Workbook()
    book.active.title = "Constant (2024) US$"
    book.active.append(["Country", "Notes", 2020])
    buffer = io.BytesIO()
    book.save(buffer)
    with pytest.raises(SchemaChangedError):
        parse_sipri_workbook(buffer.getvalue(), _release())


async def test_provider_round_trip(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(LANDING_URL, text=(FIXTURES / "landing.html").read_text(encoding="utf-8"))
    aioclient_mock.head(XLSX_URL, headers={"ETag": '"e13b8-65072a76c0127"', "Last-Modified": "Mon, 27 Apr 2026 15:20:25 GMT"})
    provider = SipriProvider()
    session = async_get_clientsession(hass)
    release = await provider.async_discover_latest(session)
    assert release.release_id == "SIPRI-Milex-data-1949-2025_v1.2.xlsx:2026-04-27"
    assert release.published_at == date(2026, 4, 27)
    aioclient_mock.get(XLSX_URL, content=(FIXTURES / "milex-trimmed.xlsx").read_bytes())
    fetched, payload = await provider.async_fetch_release(session, release)
    assert fetched.etag == '"e13b8-65072a76c0127"'
    assert len(provider.parse_release(payload, fetched).datapoints) > 5000
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/spending/test_sipri.py -q`
Expected: `ImportError`.

- [ ] **Step 4: Implement the provider**

`custom_components/edp_radar/spending/providers/sipri.py`:

```python
"""SIPRI Military Expenditure Database (S11; plan §40–§44).

The landing page links the current workbook and states when it was revised;
a new release id triggers a full re-import (plan §43). Three sheets are read.
SIPRI marks estimates with blue font and highly uncertain data with red font;
``§`` in the Notes column means adopted budget rather than outturn, so the
status vocabulary maps it to ``budget``. Non-marked figures are stored as
``actual`` meaning "SIPRI reported figure", not "official outturn" (plan §44).
Years before ``MIN_YEAR`` are not stored (storage size; the workbook keeps
1949 onwards).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientSession

from ..countries import SKIP_LABELS, normalise_label, resolve_country
from ..models import (
    DatapointStatus,
    ReferencePeriod,
    SourceRelease,
    SpendingDataPoint,
)
from ..registry import SIPRI, source_spec
from ..xlsx import (
    find_row,
    font_colour_index,
    number,
    open_workbook,
    require_sheet,
    rows_of,
    text,
    year_header,
)
from .base import (
    ParseResult,
    Payload,
    SchemaChangedError,
    async_fetch_bytes,
    async_head_metadata,
    http_date_to_date,
    with_fetch_metadata,
)

LANDING_URL = "https://www.sipri.org/databases/milex"
MIN_YEAR = 1990
BLUE = 12
RED = 10
PERCENT = Decimal(100)
_XLSX = re.compile(r'href="((?:https?:)?//www\.sipri\.org/[^"]*\.xlsx)"')
_REVISED = re.compile(r"revised on (\d{1,2} [A-Za-z]+ \d{4})")
_FOOTNOTE = re.compile(r"\d+")
NOTE_FLAGS: dict[str, str] = {
    "†": "excludes_pensions",
    "‡": "current_spending_only",
    "¶": "excludes_paramilitary",
    "‖": "currency_redenominated",
}
BUDGET_MARK = "§"
# (sheet, metric_id, unit, multiply by 100)
SHEETS: tuple[tuple[str, str, str, bool], ...] = (
    ("Constant (2024) US$", "military_expenditure_usd_constant", "USD_MILLION_CONSTANT_2024", False),
    ("Current US$", "military_expenditure_usd_current", "USD_MILLION", False),
    ("Share of GDP", "military_expenditure_pct_gdp", "PCT_GDP", True),
)


def discover_release(html_text: str, base_url: str) -> tuple[str, date | None]:
    """Workbook URL and the revision date from the landing page."""
    link = _XLSX.search(html_text)
    if link is None:
        raise SchemaChangedError("SIPRI landing page has no xlsx link")
    url = link.group(1)
    if url.startswith("//"):
        url = "https:" + url
    revised = _REVISED.search(html_text)
    revised_on = None
    if revised:
        try:
            revised_on = datetime.strptime(revised.group(1), "%d %B %Y").date()
        except ValueError:
            revised_on = None
    return urljoin(base_url, url), revised_on


def _note_flags(notes: str) -> tuple[list[str], bool]:
    flags = [flag for mark, flag in NOTE_FLAGS.items() if mark in notes]
    flags.extend(f"footnote_{n}" for n in _FOOTNOTE.findall(notes))
    return flags, BUDGET_MARK in notes


def _parse_sheet(
    rows: list[tuple[Any, ...]],
    sheet: str,
    metric_id: str,
    unit: str,
    pct: bool,
    release: SourceRelease,
    warnings: list[str],
) -> tuple[list[SpendingDataPoint], str]:
    legend_index = find_row(rows, lambda t: "blue" in t.casefold(), what=f"{sheet} colour legend")
    header_index = find_row(rows, lambda t: t == "Country", what=f"{sheet} header")
    header = rows[header_index]
    years = {column: year for column, (year, _) in year_header(header).items()}
    if not years:
        raise SchemaChangedError(f"{sheet}: header has no year columns")
    notes_column = next((i for i, cell in enumerate(header) if text(cell) == "Notes"), None)
    if notes_column is None:
        raise SchemaChangedError(f"{sheet}: 'Notes' column missing")
    points: list[SpendingDataPoint] = []
    for row in rows[header_index + 1 :]:
        label = text(row[0]) if row else ""
        if not label or normalise_label(label) in SKIP_LABELS:
            continue
        cells = {column: row[column] for column in years if column < len(row)}
        if not any(number(cell.value) is not None for cell in cells.values()):
            continue  # region heading or a country without data
        country = resolve_country(label)
        if country is None:
            warnings.append(f"{sheet}: unknown country label {label!r}")
            continue
        flags, is_budget = _note_flags(text(row[notes_column]))
        base_status = DatapointStatus.BUDGET if is_budget else DatapointStatus.ACTUAL
        for column, cell in cells.items():
            year = years[column]
            if year < MIN_YEAR:
                continue
            value = number(cell.value)
            if value is None:
                continue
            colour = font_colour_index(cell)
            status = DatapointStatus.ESTIMATE if colour == BLUE else base_status
            point_flags = [*flags, "highly_uncertain"] if colour == RED else list(flags)
            points.append(
                SpendingDataPoint(
                    source_id=SIPRI,
                    metric_id=metric_id,
                    country=country,
                    reference=ReferencePeriod.year(year),
                    value=value * PERCENT if pct else value,
                    unit=unit,
                    status=status,
                    release_id=release.release_id,
                    published_at=release.published_at,
                    source_url=release.canonical_url,
                    flags=tuple(point_flags),
                )
            )
    if not points:
        raise SchemaChangedError(f"{sheet}: no country rows parsed")
    return points, f"{sheet}: {text(rows[legend_index][0])}"


def parse_sipri_workbook(payload: bytes, release: SourceRelease) -> ParseResult:
    book = open_workbook(payload)
    points: list[SpendingDataPoint] = []
    warnings: list[str] = []
    fingerprints: list[str] = []
    for sheet, metric_id, unit, pct in SHEETS:
        rows = rows_of(require_sheet(book, sheet))
        sheet_points, fingerprint = _parse_sheet(rows, sheet, metric_id, unit, pct, release, warnings)
        points.extend(sheet_points)
        fingerprints.append(fingerprint)
    return ParseResult(tuple(points), tuple(warnings), " | ".join(fingerprints))


class SipriProvider:
    def __init__(self) -> None:
        self.spec = source_spec(SIPRI)

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease:
        page = await async_fetch_bytes(session, LANDING_URL)
        url, revised_on = discover_release(page.payload.decode("utf-8", "replace"), LANDING_URL)
        etag, last_modified = await async_head_metadata(session, url)
        filename = url.rsplit("/", 1)[-1]
        stamp = revised_on.isoformat() if revised_on else (last_modified or etag or "unknown")
        return SourceRelease(
            source_id=SIPRI,
            release_id=f"{filename}:{stamp}",
            published_at=revised_on or http_date_to_date(last_modified),
            download_url=url,
            canonical_url=LANDING_URL,
            format="xlsx",
            etag=etag,
            last_modified=last_modified,
        )

    async def async_fetch_release(
        self, session: ClientSession, release: SourceRelease
    ) -> tuple[SourceRelease, Payload]:
        fetched = await async_fetch_bytes(session, release.download_url)
        return with_fetch_metadata(release, fetched), fetched.payload

    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult:
        if not isinstance(payload, bytes):
            raise SchemaChangedError("SIPRI expects a single workbook payload")
        return parse_sipri_workbook(payload, release)
```

Register in `providers/__init__.py` — final form:

```python
"""Spending providers in plan order (plan §69)."""

from __future__ import annotations

from .base import SpendingProvider
from .eda import EdaProvider
from .eurostat import EurostatProvider
from .nato import NatoProvider
from .sipri import SipriProvider
from .statskontoret import StatskontoretProvider


def all_providers() -> tuple[SpendingProvider, ...]:
    """Statskontoret, Eurostat, NATO, EDA, SIPRI (registry.SOURCE_ORDER)."""
    return (
        StatskontoretProvider(),
        EurostatProvider(),
        NatoProvider(),
        EdaProvider(),
        SipriProvider(),
    )
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/spending/test_sipri.py -q`
Expected: 5 passed. Türkiye's Notes cell is `‖105` → flags `("currency_redenominated", "footnote_105")`; Albania `§¶3` → budget + `("excludes_paramilitary", "footnote_3")`. If the country count differs from 59, print the set difference against the labels listed in `docs/providers/sipri.md` before changing the assertion.

- [ ] **Step 6: Write `docs/providers/sipri.md`**

```markdown
# Provider: SIPRI Military Expenditure Database

| Item | Value |
| --- | --- |
| Canonical discovery URL | `https://www.sipri.org/databases/milex` |
| Verified (2026-09-12) | link `//www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2025_v1.2.xlsx` (922 552 bytes, `Last-Modified Mon, 27 Apr 2026 15:20:25 GMT`, ETag present); page text "revised on 27 April 2026 at 19:00 CET … replaces all previous versions" |
| Format | XLSX; sheets `Front page`, `Regional totals`, `Local currency financial years`, `Local currency calendar years`, `Constant (2024) US$`, `Current US$`, `Share of GDP`, `Per capita`, `Share of Govt. spending`, `Footnotes` |
| Cadence | Annual (late April), in-year revisions replace the file |
| Publication date | revision date from the landing page, else `Last-Modified` |
| Reference period | Calendar year (financial-year sheet not used) |
| Official | No — independent research dataset built from open sources |

## Sheet layout

Rows 1–4 title/legend ("Figures in blue are SIPRI estimates. Figures in red indicate highly uncertain data." and the missing-value legend); header row starts with `Country` (row 6; `Notes` column at B or C; year columns 1949–2025 as integers); region rows (`Africa`, `Europe`, `Western Europe`, …) have no values; `...`/`. .` = unavailable, `xxx` = country did not exist. Historical entities (`USSR`, `Yugoslavia`, `Czechoslovakia`, `German Democratic Republic`, `Yemen, North`, `European Union`) are skipped.

## Metric mapping (S11)

| Sheet | metric_id | unit |
| --- | --- | --- |
| `Constant (2024) US$` | `military_expenditure_usd_constant` | USD_MILLION_CONSTANT_2024 |
| `Current US$` | `military_expenditure_usd_current` | USD_MILLION |
| `Share of GDP` (ratio × 100) | `military_expenditure_pct_gdp` | PCT_GDP |

Only years ≥ 1990 are stored (`MIN_YEAR`, storage size); the workbook goes back to 1949.

## Status and flags

- Blue font (indexed colour 12) → `estimate`; red font (10) → flag `highly_uncertain`.
- Notes `§` (adopted budget, not actual expenditure) → `budget`; `†` → `excludes_pensions`; `‡` → `current_spending_only`; `¶` → `excludes_paramilitary`; `‖` → `currency_redenominated`; numbered footnotes → `footnote_<n>`.
- Everything else → `actual` = "SIPRI reported figure" (not an official outturn, plan §44).

## Parser assumptions

- The colour legend row (containing "blue") and the `Country` header row exist on every sheet (`SchemaChangedError` otherwise).
- Font colours are read from cell styles; the fixture preserves them.

## Known weaknesses

- Full re-import on every new release; revisions to any year are detected by the store diff.
- Sweden's 1957–1979 values are SIPRI estimates (blue); below `MIN_YEAR` anyway.

## Fixtures

`tests/fixtures/spending/sipri/landing.html` (link + revision sentence), `milex-trimmed.xlsx` (three sheets; rows from `Europe` onwards: 59 countries incl. Middle East).
```

- [ ] **Step 7: Quality gate and commit**

Run: `uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q`

```bash
git add scripts/fetch_spending_fixtures.py tests/fixtures/spending/sipri custom_components/edp_radar/spending/providers tests/spending/test_sipri.py docs/providers/sipri.md
git commit -m "feat(spending): SIPRI provider with colour-coded estimates (S11)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Freshness (ages and cadence-aware state)

**Files:**
- Create: `custom_components/edp_radar/spending/freshness.py`
- Test: `tests/spending/test_freshness.py`

**Interfaces:**
- Consumes: `models.SourceSpec`, `models.Cadence`, `registry.source_spec`.
- Produces: `FreshnessState` (StrEnum `current | expected | late | unknown`), `publication_age_days(published_at, today) -> int | None`, `reference_age_days(reference_end, today) -> int`, `retrieval_age_days(retrieved_at, now) -> int | None`, `last_business_day(year, month) -> date`, `next_release_deadline(spec, latest_reference_end, published_at) -> date | None`, `freshness_state(spec, latest_reference_end, published_at, today, *, grace_days=7) -> FreshnessState`, `GRACE_DAYS = 7`.

- [ ] **Step 1: Write the failing tests**

`tests/spending/test_freshness.py`:

```python
"""Ages and cadence-aware freshness (S15; plan §14, §56–§58)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from custom_components.edp_radar.spending.freshness import (
    FreshnessState,
    freshness_state,
    last_business_day,
    next_release_deadline,
    publication_age_days,
    reference_age_days,
    retrieval_age_days,
)
from custom_components.edp_radar.spending.registry import source_spec

TODAY = date(2026, 9, 12)


def test_ages() -> None:
    assert publication_age_days(date(2026, 8, 24), TODAY) == 19
    assert publication_age_days(None, TODAY) is None
    assert reference_age_days(date(2026, 7, 31), TODAY) == 43
    assert retrieval_age_days(datetime(2026, 9, 11, 22, 0, tzinfo=UTC), datetime(2026, 9, 12, 21, 0, tzinfo=UTC)) == 0
    assert retrieval_age_days(datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 9, 12, tzinfo=UTC)) == 11
    assert retrieval_age_days(None, datetime(2026, 9, 12, tzinfo=UTC)) is None


def test_last_business_day() -> None:
    assert last_business_day(2026, 8) == date(2026, 8, 31)  # Monday
    assert last_business_day(2026, 5) == date(2026, 5, 29)  # 31st is a Sunday
    assert last_business_day(2026, 1) == date(2026, 1, 30)


def test_monthly_deadline_and_states() -> None:
    spec = source_spec("statskontoret")
    # Latest reference month July 2026 → August is due by the last business day of September.
    assert next_release_deadline(spec, date(2026, 7, 31), date(2026, 8, 24)) == date(2026, 9, 30)
    assert freshness_state(spec, date(2026, 7, 31), date(2026, 8, 24), TODAY) is FreshnessState.CURRENT
    assert freshness_state(spec, date(2026, 7, 31), date(2026, 8, 24), date(2026, 10, 3)) is FreshnessState.EXPECTED
    assert freshness_state(spec, date(2026, 7, 31), date(2026, 8, 24), date(2026, 10, 8)) is FreshnessState.LATE
    assert freshness_state(spec, None, None, TODAY) is FreshnessState.UNKNOWN


def test_annual_and_twice_yearly_states() -> None:
    nato = source_spec("nato")
    assert next_release_deadline(nato, date(2026, 12, 31), date(2026, 7, 10)) == date(2027, 7, 10)
    assert freshness_state(nato, date(2026, 12, 31), date(2026, 7, 10), TODAY) is FreshnessState.CURRENT
    assert freshness_state(nato, date(2026, 12, 31), date(2026, 7, 10), date(2027, 7, 15)) is FreshnessState.EXPECTED
    assert freshness_state(nato, date(2026, 12, 31), date(2026, 7, 10), date(2027, 8, 1)) is FreshnessState.LATE
    assert freshness_state(nato, date(2026, 12, 31), None, TODAY) is FreshnessState.UNKNOWN
    eurostat = source_spec("eurostat")
    assert next_release_deadline(eurostat, date(2025, 12, 31), date(2026, 4, 27)) == date(2026, 10, 27)
    assert freshness_state(eurostat, date(2025, 12, 31), date(2026, 4, 27), TODAY) is FreshnessState.CURRENT
    assert freshness_state(eurostat, date(2025, 12, 31), date(2026, 4, 27), date(2026, 11, 15)) is FreshnessState.LATE
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/spending/test_freshness.py -q`
Expected: `ImportError`.

- [ ] **Step 3: Implement `freshness.py`**

```python
"""Publication, reference and retrieval ages plus a cadence-aware state (S15).

``current``  – the next release is not yet due.
``expected`` – due, but within the grace period.
``late``     – past due and grace.
``unknown``  – not enough metadata.

Statskontoret publishes "senast sista vardagen i månaden efter aktuell
utfallsmånad" (plan §14): the month after the latest reference month is due
on the last business day of the month after that. Business days ignore
Swedish public holidays (a documented simplification). Annual sources are due
365 days after their last publication, twice-yearly sources after 183 days.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from enum import StrEnum

from .models import Cadence, SourceSpec

GRACE_DAYS = 7
_ANNUAL = timedelta(days=365)
_TWICE_YEARLY = timedelta(days=183)


class FreshnessState(StrEnum):
    CURRENT = "current"
    EXPECTED = "expected"
    LATE = "late"
    UNKNOWN = "unknown"


def publication_age_days(published_at: date | None, today: date) -> int | None:
    return None if published_at is None else (today - published_at).days


def reference_age_days(reference_end: date, today: date) -> int:
    return (today - reference_end).days


def retrieval_age_days(retrieved_at: datetime | None, now: datetime) -> int | None:
    return None if retrieved_at is None else (now - retrieved_at).days


def last_business_day(year: int, month: int) -> date:
    day = date(year, month, calendar.monthrange(year, month)[1])
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _add_months(day: date, months: int) -> tuple[int, int]:
    index = day.year * 12 + (day.month - 1) + months
    return index // 12, index % 12 + 1


def next_release_deadline(
    spec: SourceSpec, latest_reference_end: date | None, published_at: date | None
) -> date | None:
    """When the next release is due, or ``None`` when it cannot be known."""
    if spec.cadence is Cadence.MONTHLY:
        if latest_reference_end is None:
            return None
        year, month = _add_months(latest_reference_end, 2)
        return last_business_day(year, month)
    if published_at is None:
        return None
    if spec.cadence is Cadence.TWICE_YEARLY:
        return published_at + _TWICE_YEARLY
    return published_at + _ANNUAL


def freshness_state(
    spec: SourceSpec,
    latest_reference_end: date | None,
    published_at: date | None,
    today: date,
    *,
    grace_days: int = GRACE_DAYS,
) -> FreshnessState:
    deadline = next_release_deadline(spec, latest_reference_end, published_at)
    if deadline is None or latest_reference_end is None:
        return FreshnessState.UNKNOWN
    if today <= deadline:
        return FreshnessState.CURRENT
    if today <= deadline + timedelta(days=grace_days):
        return FreshnessState.EXPECTED
    return FreshnessState.LATE
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending/test_freshness.py -q`
Expected: 4 passed.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q
git add custom_components/edp_radar/spending/freshness.py tests/spending/test_freshness.py
git commit -m "feat(spending): freshness ages and cadence-aware state (S15)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Calculations (YTD, YoY, rankings, Nordic subset)

**Files:**
- Create: `custom_components/edp_radar/spending/calculations.py`
- Test: `tests/spending/test_calculations.py`

**Interfaces:**
- Consumes: `models.SpendingDataPoint`, `models.ReferencePeriod`, `models.DatapointStatus`, `countries.NORDIC`, `registry.FOCUS_COUNTRY`.
- Produces: `monthly_series(points, metric_id, country) -> dict[tuple[int, int], SpendingDataPoint]`, `latest_month(points, metric_id, country) -> SpendingDataPoint | None`, `ytd(points, metric_id, country, year, through_month) -> Decimal | None`, `nominal_change_pct(current, previous) -> Decimal | None`, `RankEntry(rank, country, value, status, flags)`, `Ranking(source_id, metric_id, unit, reference, entries, focus_rank, focus_value, population, top, median, statuses)`, `rank(points, *, metric_id, unit, reference, focus=FOCUS_COUNTRY, statuses=None) -> Ranking | None`, `latest_reference(points, metric_id, *, min_countries=2) -> ReferencePeriod | None`, `nordic_subset(ranking) -> tuple[RankEntry, ...]`.

- [ ] **Step 1: Write the failing tests**

`tests/spending/test_calculations.py`:

```python
"""Pure calculations on datapoints (S16; plan §48–§55)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from custom_components.edp_radar.spending.calculations import (
    latest_month,
    latest_reference,
    monthly_series,
    nominal_change_pct,
    nordic_subset,
    rank,
    ytd,
)
from custom_components.edp_radar.spending.models import (
    DatapointStatus,
    ReferencePeriod,
    SpendingDataPoint,
)


def _monthly(metric: str, year: int, month: int, value: str) -> SpendingDataPoint:
    return SpendingDataPoint(
        "statskontoret", metric, "SE", ReferencePeriod.month(year, month), Decimal(value),
        "SEK_MILLION", DatapointStatus.ACTUAL, "r", date(2026, 8, 24), "u",
    )


def _annual(source: str, metric: str, country: str, year: int, value: str, status: DatapointStatus = DatapointStatus.ACTUAL, unit: str = "EUR_MILLION") -> SpendingDataPoint:
    return SpendingDataPoint(source, metric, country, ReferencePeriod.year(year), Decimal(value), unit, status, "r", None, "u")


MONTHLY = [
    *[_monthly("materiel_outturn", 2025, m, v) for m, v in enumerate(["1249.91904794", "1761.37533405", "3924.46838279", "1992.49195545", "3023.46969568", "5014.53463338", "2939.12460557", "1795.37738032", "5249.30849248", "4913.77616522", "3638.46181911", "23327.02469578"], start=1)],
    *[_monthly("materiel_outturn", 2026, m, v) for m, v in enumerate(["1413.08686370", "3525.41360338", "5470.01853783", "2779.98873985", "3349.14200332", "5585.76075380", "3753.54717975"], start=1)],
    _monthly("uo6_total_outturn", 2026, 7, "11050.09591378"),
]


def test_monthly_series_latest_and_ytd() -> None:
    series = monthly_series(MONTHLY, "materiel_outturn", "SE")
    assert sorted(series)[-1] == (2026, 7)
    latest = latest_month(MONTHLY, "materiel_outturn", "SE")
    assert latest is not None and latest.reference.label == "Jul 2026"
    assert ytd(MONTHLY, "materiel_outturn", "SE", 2026, 7) == Decimal("25876.95768163")
    assert ytd(MONTHLY, "materiel_outturn", "SE", 2025, 7) == Decimal("19905.38365486")
    assert ytd(MONTHLY, "materiel_outturn", "SE", 2026, 8) is None  # August missing
    assert ytd(MONTHLY, "uo6_total_outturn", "SE", 2026, 7) is None  # January–June missing
    assert latest_month(MONTHLY, "nope", "SE") is None


def test_nominal_change_pct() -> None:
    assert nominal_change_pct(Decimal("25876.95768163"), Decimal("19905.38365486")) == pytest.approx(Decimal("30.0"), abs=Decimal("0.1"))
    assert nominal_change_pct(Decimal("10"), Decimal("0")) is None
    assert nominal_change_pct(Decimal("10"), None) is None
    assert nominal_change_pct(None, Decimal("5")) is None
    assert nominal_change_pct(Decimal("90"), Decimal("100")) == Decimal("-10")


ANNUAL = [
    _annual("eurostat", "defence_expenditure", "DE", 2025, "68824.0"),
    _annual("eurostat", "defence_expenditure", "FR", 2025, "56638.0"),
    _annual("eurostat", "defence_expenditure", "PL", 2025, "31637.9"),
    _annual("eurostat", "defence_expenditure", "SE", 2025, "17196.9"),
    _annual("eurostat", "defence_expenditure", "DK", 2025, "8997.7"),
    _annual("eurostat", "defence_expenditure", "FI", 2025, "7000.0"),
    _annual("eurostat", "defence_expenditure", "SE", 2024, "11093.8"),
    _annual("eurostat", "defence_expenditure", "DE", 2024, "60000"),
    _annual("eurostat", "defence_expenditure_pct_gdp", "SE", 2025, "2.9", unit="PCT_GDP"),
    _annual("nato", "defence_expenditure_usd_current", "SE", 2025, "19122", DatapointStatus.ESTIMATE, "USD_MILLION"),
]


def test_rank_within_one_source_metric_reference_unit() -> None:
    ranking = rank(ANNUAL, metric_id="defence_expenditure", unit="EUR_MILLION", reference=ReferencePeriod.year(2025))
    assert ranking is not None
    assert ranking.source_id == "eurostat"
    assert [e.country for e in ranking.entries] == ["DE", "FR", "PL", "SE", "DK", "FI"]
    assert ranking.entries[0].rank == 1
    assert ranking.focus_rank == 4
    assert ranking.focus_value == Decimal("17196.9")
    assert ranking.population == 6
    assert ranking.top.country == "DE"
    assert ranking.median == (Decimal("31637.9") + Decimal("17196.9")) / 2
    assert ranking.statuses == ("actual",)
    assert [e.country for e in nordic_subset(ranking)] == ["SE", "DK", "FI"]


def test_rank_requires_focus_and_rejects_mixed_sources() -> None:
    without_sweden = [p for p in ANNUAL if p.country != "SE"]
    assert rank(without_sweden, metric_id="defence_expenditure", unit="EUR_MILLION", reference=ReferencePeriod.year(2025)) is None
    assert rank(ANNUAL, metric_id="defence_expenditure", unit="EUR_MILLION", reference=ReferencePeriod.year(2030)) is None
    mixed = [*ANNUAL, _annual("nato", "defence_expenditure", "NO", 2025, "1", unit="EUR_MILLION")]
    with pytest.raises(ValueError, match="one source"):
        rank(mixed, metric_id="defence_expenditure", unit="EUR_MILLION", reference=ReferencePeriod.year(2025))
    only_actual = rank(ANNUAL, metric_id="defence_expenditure", unit="EUR_MILLION", reference=ReferencePeriod.year(2025), statuses={DatapointStatus.ESTIMATE})
    assert only_actual is None


def test_latest_reference_with_enough_countries() -> None:
    assert latest_reference(ANNUAL, "defence_expenditure") == ReferencePeriod.year(2025)
    assert latest_reference(ANNUAL, "defence_expenditure", min_countries=7) is None
    assert latest_reference(ANNUAL, "defence_expenditure", min_countries=2) == ReferencePeriod.year(2025)
    assert latest_reference([], "defence_expenditure") is None
```

(2025 has six countries and 2024 two; with `min_countries=7` no year qualifies.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/spending/test_calculations.py -q`
Expected: `ImportError`.

- [ ] **Step 3: Implement `calculations.py`**

```python
"""Pure calculations over datapoints (S16; plan §48–§55).

Nothing here converts currencies or mixes sources: ``rank`` refuses more than
one ``source_id`` and works on exactly one metric, reference period and unit.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from statistics import median as _median

from .countries import NORDIC
from .models import DatapointStatus, ReferencePeriod, SpendingDataPoint
from .registry import FOCUS_COUNTRY


def monthly_series(
    points: Iterable[SpendingDataPoint], metric_id: str, country: str
) -> dict[tuple[int, int], SpendingDataPoint]:
    """``{(year, month): point}`` for one monthly metric of one country."""
    series: dict[tuple[int, int], SpendingDataPoint] = {}
    for point in points:
        if point.metric_id != metric_id or point.country != country:
            continue
        start, end = point.reference.start, point.reference.end
        if start.year == end.year and start.month == end.month and start.day == 1:
            series[(start.year, start.month)] = point
    return series


def latest_month(
    points: Iterable[SpendingDataPoint], metric_id: str, country: str
) -> SpendingDataPoint | None:
    series = monthly_series(points, metric_id, country)
    if not series:
        return None
    return series[max(series)]


def ytd(
    points: Iterable[SpendingDataPoint],
    metric_id: str,
    country: str,
    year: int,
    through_month: int,
) -> Decimal | None:
    """Sum of January..``through_month``; ``None`` when any month is missing."""
    series = monthly_series(points, metric_id, country)
    total = Decimal(0)
    for month in range(1, through_month + 1):
        point = series.get((year, month))
        if point is None:
            return None
        total += point.value
    return total


def nominal_change_pct(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    """Nominal change in percent (plan §54); ``None`` without a usable base."""
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / previous * Decimal(100)


@dataclass(frozen=True, slots=True)
class RankEntry:
    rank: int
    country: str
    value: Decimal
    status: DatapointStatus
    flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Ranking:
    source_id: str
    metric_id: str
    unit: str
    reference: ReferencePeriod
    entries: tuple[RankEntry, ...]
    focus_rank: int
    focus_value: Decimal
    population: int
    top: RankEntry
    median: Decimal
    statuses: tuple[str, ...]


def rank(
    points: Iterable[SpendingDataPoint],
    *,
    metric_id: str,
    unit: str,
    reference: ReferencePeriod,
    focus: str = FOCUS_COUNTRY,
    statuses: set[DatapointStatus] | None = None,
) -> Ranking | None:
    """Descending ranking of one source/metric/reference/unit (plan §48, §50)."""
    selected: dict[str, SpendingDataPoint] = {}
    sources: set[str] = set()
    for point in points:
        if point.metric_id != metric_id or point.unit != unit:
            continue
        if (point.reference.start, point.reference.end) != (reference.start, reference.end):
            continue
        sources.add(point.source_id)
        if statuses is not None and point.status not in statuses:
            continue
        selected[point.country] = point
    if len(sources) > 1:
        raise ValueError(f"ranking must use one source, got {sorted(sources)}")
    if focus not in selected:
        return None
    ordered = sorted(selected.values(), key=lambda p: (-p.value, p.country))
    entries = tuple(
        RankEntry(index, p.country, p.value, p.status, p.flags)
        for index, p in enumerate(ordered, start=1)
    )
    focus_entry = next(e for e in entries if e.country == focus)
    return Ranking(
        source_id=next(iter(sources)),
        metric_id=metric_id,
        unit=unit,
        reference=reference,
        entries=entries,
        focus_rank=focus_entry.rank,
        focus_value=focus_entry.value,
        population=len(entries),
        top=entries[0],
        median=Decimal(_median(e.value for e in entries)),
        statuses=tuple(sorted({e.status.value for e in entries})),
    )


def latest_reference(
    points: Iterable[SpendingDataPoint], metric_id: str, *, min_countries: int = 2
) -> ReferencePeriod | None:
    """Newest reference period of a metric with at least ``min_countries``."""
    by_period: dict[tuple[str, str], tuple[ReferencePeriod, set[str]]] = {}
    for point in points:
        if point.metric_id != metric_id:
            continue
        key = (point.reference.start.isoformat(), point.reference.end.isoformat())
        entry = by_period.setdefault(key, (point.reference, set()))
        entry[1].add(point.country)
    candidates = [ref for ref, countries in by_period.values() if len(countries) >= min_countries]
    if not candidates:
        return None
    return max(candidates, key=lambda r: (r.end, r.start))


def nordic_subset(ranking: Ranking) -> tuple[RankEntry, ...]:
    """Nordic entries in ranking order; Iceland only when present (plan §51)."""
    return tuple(e for e in ranking.entries if e.country in NORDIC)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending/test_calculations.py -q`
Expected: 5 passed. (`statistics.median` of Decimals returns a Decimal for an even count via `(a + b) / 2`; the explicit `Decimal(...)` wrap keeps the type.)

- [ ] **Step 5: Quality gate and commit**

```bash
uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q
git add custom_components/edp_radar/spending/calculations.py tests/spending/test_calculations.py
git commit -m "feat(spending): YTD, YoY and single-source ranking calculations (S16)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: `SpendingStore` — one Home Assistant `Store` per source, diff and revisions

**Files:**
- Create: `custom_components/edp_radar/spending/store.py`
- Test: `tests/spending/test_store.py`

**Interfaces:**
- Consumes: `models.*`, `registry.SOURCE_ORDER`, `const.DOMAIN`.
- Produces: `SpendingStore(hass, entry_id)` with `async_load()`, `get(source_id) -> SourceSeries`, `series: dict[str, SourceSeries]`, `apply_release(source_id, release, datapoints, *, now, warnings=()) -> ApplyResult`, `set_health(source_id, health)`, `async_save(*, immediate=False)`, `async_remove()`; `ApplyResult(added, updated, unchanged, carried_over, revisions)`; `SCHEMA_VERSION`, `STORAGE_VERSION`, `storage_key(entry_id, source_id)`.

- [ ] **Step 1: Write the failing tests**

`tests/spending/test_store.py`:

```python
"""SpendingStore: per-source Store files, diff, revisions, removal (S13, S5)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.edp_radar.const import DOMAIN
from custom_components.edp_radar.spending.models import (
    DatapointStatus,
    ProviderHealth,
    ProviderState,
    ReferencePeriod,
    SourceRelease,
    SpendingDataPoint,
)
from custom_components.edp_radar.spending.store import (
    SCHEMA_VERSION,
    SpendingStore,
    storage_key,
)

ENTRY = "entry1"
NOW = datetime(2026, 9, 12, 21, 0, tzinfo=UTC)


def _release(release_id: str, published: date) -> SourceRelease:
    return SourceRelease("statskontoret", release_id, published, "d", "c", "csv", checksum=release_id)


def _point(metric: str, year: int, month: int, value: str, release: SourceRelease, status: DatapointStatus = DatapointStatus.ACTUAL) -> SpendingDataPoint:
    return SpendingDataPoint(
        "statskontoret", metric, "SE", ReferencePeriod.month(year, month), Decimal(value),
        "SEK_MILLION", status, release.release_id, release.published_at, "u",
    )


async def test_fresh_store_has_empty_series_for_every_source(hass: HomeAssistant) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    assert sorted(store.series) == ["eda", "eurostat", "nato", "sipri", "statskontoret"]
    assert store.get("nato").health.state is ProviderState.NEVER_LOADED
    assert storage_key(ENTRY, "nato") == f"{DOMAIN}.{ENTRY}.spending.nato"


async def test_apply_release_persists_and_reloads(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    first = _release("2025-12-preliminar-2026-01-28", date(2026, 1, 28))
    result = store.apply_release(
        "statskontoret",
        first,
        [
            _point("materiel_outturn", 2025, 11, "3638.46181911", first),
            _point("materiel_outturn", 2025, 12, "19729.43332150", first, DatapointStatus.PRELIMINARY),
        ],
        now=NOW,
        warnings=("w1",),
    )
    assert (result.added, result.updated, result.unchanged, result.carried_over) == (2, 0, 0, 0)
    assert result.revisions == ()
    series = store.get("statskontoret")
    assert series.release == first
    assert series.retrieved_at == NOW
    assert series.health.state is ProviderState.AVAILABLE
    assert series.health.last_success_at == NOW
    assert series.health.warnings == ("w1",)
    await store.async_save(immediate=True)
    stored = hass_storage[storage_key(ENTRY, "statskontoret")]["data"]
    assert stored["schema_version"] == SCHEMA_VERSION
    assert len(stored["series"]["datapoints"]) == 2

    reloaded = SpendingStore(hass, ENTRY)
    await reloaded.async_load()
    assert reloaded.get("statskontoret") == series


async def test_second_release_updates_records_revision_and_carries_over(hass: HomeAssistant) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    first = _release("2025-12-preliminar-2026-01-28", date(2026, 1, 28))
    store.apply_release(
        "statskontoret",
        first,
        [
            _point("materiel_outturn", 2025, 11, "3638.46181911", first),
            _point("materiel_outturn", 2025, 12, "19729.43332150", first, DatapointStatus.PRELIMINARY),
            _point("uo6_total_outturn", 2025, 12, "34786.38436460", first, DatapointStatus.PRELIMINARY),
        ],
        now=NOW,
    )
    second = _release("2025-12-definitiv-2026-03-24", date(2026, 3, 24))
    result = store.apply_release(
        "statskontoret",
        second,
        [
            _point("materiel_outturn", 2025, 11, "3638.46181911", second),
            _point("materiel_outturn", 2025, 12, "23327.02469578", second),
        ],
        now=NOW,
    )
    assert (result.added, result.updated, result.unchanged, result.carried_over) == (0, 1, 1, 1)
    assert len(result.revisions) == 1
    revision = result.revisions[0]
    assert revision.previous_value == Decimal("19729.43332150")
    assert revision.new_value == Decimal("23327.02469578")
    assert revision.previous_release_id == first.release_id
    assert revision.release_id == second.release_id
    assert revision.detected_at == NOW
    series = store.get("statskontoret")
    by_key = {p.key: p for p in series.datapoints}
    december = by_key[("statskontoret", "materiel_outturn", "SE", "2025-12-01", "2025-12-31", "SEK_MILLION")]
    assert december.value == Decimal("23327.02469578")
    assert december.status is DatapointStatus.ACTUAL
    assert december.release_id == second.release_id
    november = by_key[("statskontoret", "materiel_outturn", "SE", "2025-11-01", "2025-11-30", "SEK_MILLION")]
    assert november.release_id == second.release_id  # unchanged value, newest provenance
    carried = by_key[("statskontoret", "uo6_total_outturn", "SE", "2025-12-01", "2025-12-31", "SEK_MILLION")]
    assert carried.release_id == first.release_id
    assert series.revisions == result.revisions
    assert [p.key for p in series.datapoints] == sorted(p.key for p in series.datapoints)


async def test_set_health_and_remove(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    store.set_health("nato", ProviderHealth(state=ProviderState.TEMPORARILY_UNAVAILABLE, last_error="HTTP 503"))
    await store.async_save(immediate=True)
    assert hass_storage[storage_key(ENTRY, "nato")]["data"]["series"]["health"]["last_error"] == "HTTP 503"
    assert storage_key(ENTRY, "eda") not in hass_storage  # untouched sources are not written
    await store.async_remove()
    assert not [k for k in hass_storage if ".spending." in k]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/spending/test_store.py -q`
Expected: `ImportError`.

- [ ] **Step 3: Implement `store.py`**

```python
"""Per-source persistence of spending series (S13; plan §62, §66, §67).

Every release replaces the series: datapoints present in the new release are
added or updated (a changed value records a ``Revision``), datapoints absent
from it are carried over with their original provenance so history survives
sources that drop old years.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..const import DOMAIN
from .models import (
    ProviderHealth,
    ProviderState,
    Revision,
    SourceRelease,
    SourceSeries,
    SpendingDataPoint,
)
from .registry import SOURCE_ORDER

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SCHEMA_VERSION = 1
SAVE_DELAY_SECONDS = 30


def storage_key(entry_id: str, source_id: str) -> str:
    return f"{DOMAIN}.{entry_id}.spending.{source_id}"


@dataclass(frozen=True, slots=True)
class ApplyResult:
    added: int
    updated: int
    unchanged: int
    carried_over: int
    revisions: tuple[Revision, ...]


class SpendingStore:
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._hass = hass
        self._entry_id = entry_id
        self._stores: dict[str, Store[dict[str, Any]]] = {
            source_id: Store(hass, STORAGE_VERSION, storage_key(entry_id, source_id))
            for source_id in SOURCE_ORDER
        }
        self.series: dict[str, SourceSeries] = {
            source_id: SourceSeries.empty(source_id) for source_id in SOURCE_ORDER
        }
        self._dirty: set[str] = set()
        self._pending: set[str] = set()

    async def async_load(self) -> None:
        for source_id, store in self._stores.items():
            data = await store.async_load()
            if not data or data.get("schema_version") != SCHEMA_VERSION:
                if data:
                    _LOGGER.warning("Discarding %s: schema %s", source_id, data.get("schema_version"))
                continue
            try:
                self.series[source_id] = SourceSeries.from_dict(data["series"])
            except (KeyError, ValueError, TypeError) as err:
                _LOGGER.warning("Discarding stored %s series: %s", source_id, err)

    def get(self, source_id: str) -> SourceSeries:
        return self.series[source_id]

    def apply_release(
        self,
        source_id: str,
        release: SourceRelease,
        datapoints: Iterable[SpendingDataPoint],
        *,
        now: datetime,
        warnings: tuple[str, ...] = (),
    ) -> ApplyResult:
        current = self.series[source_id]
        existing = {point.key: point for point in current.datapoints}
        incoming: dict[tuple[str, ...], SpendingDataPoint] = {}
        for point in datapoints:
            incoming[point.key] = point
        merged = dict(existing)
        added = updated = unchanged = 0
        revisions: list[Revision] = []
        for key, point in incoming.items():
            previous = existing.get(key)
            if previous is None:
                added += 1
            elif previous.value != point.value:
                updated += 1
                revisions.append(
                    Revision(
                        key=point.key,
                        previous_value=previous.value,
                        previous_release_id=previous.release_id,
                        new_value=point.value,
                        release_id=point.release_id,
                        detected_at=now,
                    )
                )
            else:
                unchanged += 1
            merged[key] = point
        carried_over = len(existing.keys() - incoming.keys())
        health = dataclasses.replace(
            current.health,
            state=ProviderState.AVAILABLE,
            last_check_at=now,
            last_success_at=now,
            last_error=None,
            warnings=warnings,
            skip_reason=None,
        )
        self.series[source_id] = SourceSeries(
            source_id=source_id,
            release=release,
            health=health,
            datapoints=tuple(merged[key] for key in sorted(merged)),
            revisions=(*current.revisions, *revisions),
            retrieved_at=now,
        )
        self._dirty.add(source_id)
        return ApplyResult(added, updated, unchanged, carried_over, tuple(revisions))

    def set_health(self, source_id: str, health: ProviderHealth) -> None:
        self.series[source_id] = dataclasses.replace(self.series[source_id], health=health)
        self._dirty.add(source_id)

    def _payload(self, source_id: str) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "series": self.series[source_id].to_dict()}

    async def async_save(self, *, immediate: bool = False) -> None:
        """Write changed sources (delayed by default, as D12).

        Serialisation runs in the executor. Sources with a delayed write still
        pending are rewritten by an immediate save (shutdown), so an unload
        never loses the last release.
        """
        dirty = sorted(self._dirty | (self._pending if immediate else set()))
        self._dirty.clear()
        for source_id in dirty:
            payload = await self._hass.async_add_executor_job(self._payload, source_id)
            store = self._stores[source_id]
            if immediate:
                self._pending.discard(source_id)
                await store.async_save(payload)
            else:
                self._pending.add(source_id)
                store.async_delay_save(lambda payload=payload: payload, SAVE_DELAY_SECONDS)

    async def async_remove(self) -> None:
        for store in self._stores.values():
            await store.async_remove()
        self.series = {source_id: SourceSeries.empty(source_id) for source_id in SOURCE_ORDER}
        self._dirty.clear()
        self._pending.clear()
```

(`self._pending: set[str] = set()` is initialised in `__init__` next to `self._dirty`. The lambda binds `payload` through its default argument, so ruff's B023 does not apply; if mypy complains about the lambda's type, wrap it as `def _static(payload: dict[str, Any] = payload) -> dict[str, Any]: return payload`.)

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending/test_store.py -q`
Expected: 4 passed.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q
git add custom_components/edp_radar/spending/store.py tests/spending/test_store.py
git commit -m "feat(spending): per-source store with release diff and revisions (S13)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: `SpendingCoordinator` — cadence gating, unchanged-release skip, isolated failures

**Files:**
- Create: `custom_components/edp_radar/spending/coordinator.py`
- Modify: `custom_components/edp_radar/const.py` (add `SPENDING_UPDATE_INTERVAL`, `SPENDING_RETRY_INTERVAL`)
- Test: `tests/spending/test_coordinator.py`

**Interfaces:**
- Consumes: `SpendingStore`, `SpendingProvider`, `models.*`, `registry.*`, `providers.base` errors.
- Produces: `SpendingSnapshot(series: Mapping[str, SourceSeries], refreshed_at: datetime)` with `get(source_id)`; `SpendingCoordinator(hass, entry, *, session, store, providers, clock=dt_util.utcnow)` with `async_setup()`, `async_shutdown()`, `async_refresh_source(source_id)` (forces one provider now), `store`, `providers`; constants `SPENDING_UPDATE_INTERVAL = timedelta(hours=6)`, `SPENDING_RETRY_INTERVAL = timedelta(hours=1)`.

- [ ] **Step 1: Add constants**

Append to `custom_components/edp_radar/const.py` after `DEFAULT_UPDATE_INTERVAL`:

```python
# Phase 3 spending layer (S14): coordinator tick and retry after a source error.
SPENDING_UPDATE_INTERVAL = timedelta(hours=6)
SPENDING_RETRY_INTERVAL = timedelta(hours=1)
```

- [ ] **Step 2: Write the failing tests**

`tests/spending/test_coordinator.py`:

```python
"""SpendingCoordinator: cadence, unchanged skip, isolation, revisions (S14)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edp_radar.const import (
    DOMAIN,
    SPENDING_RETRY_INTERVAL,
)
from custom_components.edp_radar.spending.coordinator import SpendingCoordinator
from custom_components.edp_radar.spending.models import (
    DatapointStatus,
    ProviderState,
    ReferencePeriod,
    SourceRelease,
    SpendingDataPoint,
)
from custom_components.edp_radar.spending.providers.base import (
    ParseResult,
    Payload,
    SchemaChangedError,
    SourceUnavailableError,
)
from custom_components.edp_radar.spending.registry import source_spec
from custom_components.edp_radar.spending.store import SpendingStore

NOW = datetime(2026, 9, 12, 21, 0, tzinfo=UTC)


class FakeProvider:
    """A provider whose behaviour is scripted per test."""

    def __init__(self, source_id: str, release_id: str = "r1", value: str = "1") -> None:
        self.spec = source_spec(source_id)
        self.release_id = release_id
        self.value = value
        self.discover_error: Exception | None = None
        self.fetch_error: Exception | None = None
        self.parse_error: Exception | None = None
        self.calls = {"discover": 0, "fetch": 0, "parse": 0}

    def _release(self) -> SourceRelease:
        return SourceRelease(self.spec.source_id, self.release_id, date(2026, 9, 1), "d", "c", "x", checksum=self.release_id)

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease:
        self.calls["discover"] += 1
        if self.discover_error:
            raise self.discover_error
        return self._release()

    async def async_fetch_release(self, session: ClientSession, release: SourceRelease) -> tuple[SourceRelease, Payload]:
        self.calls["fetch"] += 1
        if self.fetch_error:
            raise self.fetch_error
        return release, b"payload"

    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult:
        self.calls["parse"] += 1
        if self.parse_error:
            raise self.parse_error
        point = SpendingDataPoint(
            self.spec.source_id, "m", "SE", ReferencePeriod.year(2025), Decimal(self.value),
            "U", DatapointStatus.ACTUAL, release.release_id, release.published_at, "c",
        )
        return ParseResult((point,), ("note",), "fp")


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


async def _coordinator(hass: HomeAssistant, providers: list[FakeProvider], clock: Clock) -> SpendingCoordinator:
    entry = MockConfigEntry(domain=DOMAIN, entry_id="test-entry", unique_id=DOMAIN, data={}, options={}, version=2)
    entry.add_to_hass(hass)
    store = SpendingStore(hass, entry.entry_id)
    coordinator = SpendingCoordinator(
        hass, entry, session=async_get_clientsession(hass), store=store, providers=providers, clock=clock
    )
    await coordinator.async_setup()
    return coordinator


async def test_first_refresh_loads_every_provider(hass: HomeAssistant) -> None:
    clock = Clock(NOW)
    providers = [FakeProvider("statskontoret"), FakeProvider("nato")]
    coordinator = await _coordinator(hass, providers, clock)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    snapshot = coordinator.data
    assert snapshot is not None and snapshot.refreshed_at == NOW
    for provider in providers:
        series = snapshot.get(provider.spec.source_id)
        assert provider.calls == {"discover": 1, "fetch": 1, "parse": 1}
        assert len(series.datapoints) == 1
        assert series.health.state is ProviderState.AVAILABLE
        assert series.health.warnings == ("note",)
        assert series.health.next_check_at == NOW + provider.spec.check_interval
    assert snapshot.get("eurostat").health.state is ProviderState.NEVER_LOADED


async def test_not_due_providers_are_skipped_and_unchanged_releases_not_fetched(hass: HomeAssistant) -> None:
    clock = Clock(NOW)
    provider = FakeProvider("nato")
    coordinator = await _coordinator(hass, [provider], clock)
    await coordinator.async_refresh()
    clock.now = NOW + timedelta(hours=6)
    await coordinator.async_refresh()
    assert provider.calls["discover"] == 1  # weekly cadence: not due yet
    clock.now = NOW + timedelta(days=7, minutes=1)
    await coordinator.async_refresh()
    assert provider.calls == {"discover": 2, "fetch": 1, "parse": 1}
    health = coordinator.data.get("nato").health
    assert health.skip_reason == "unchanged_release"
    assert health.last_check_at == clock.now
    assert health.next_check_at == clock.now + provider.spec.check_interval
    provider.release_id, provider.value = "r2", "2"
    clock.now += timedelta(days=7, minutes=1)
    await coordinator.async_refresh()
    assert provider.calls == {"discover": 3, "fetch": 2, "parse": 2}
    series = coordinator.data.get("nato")
    assert series.datapoints[0].value == Decimal("2")
    assert len(series.revisions) == 1


async def test_failures_are_isolated_and_retry_sooner(hass: HomeAssistant) -> None:
    clock = Clock(NOW)
    broken = FakeProvider("eurostat")
    broken.discover_error = SourceUnavailableError("HTTP 503 for x")
    fine = FakeProvider("statskontoret")
    coordinator = await _coordinator(hass, [broken, fine], clock)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    eurostat = coordinator.data.get("eurostat")
    assert eurostat.health.state is ProviderState.TEMPORARILY_UNAVAILABLE
    assert eurostat.health.last_error == "HTTP 503 for x"
    assert eurostat.health.next_check_at == NOW + SPENDING_RETRY_INTERVAL
    assert len(coordinator.data.get("statskontoret").datapoints) == 1
    # Recover, then fail again: data stays, state says stale.
    broken.discover_error = None
    clock.now = NOW + SPENDING_RETRY_INTERVAL + timedelta(minutes=1)
    await coordinator.async_refresh()
    assert coordinator.data.get("eurostat").health.state is ProviderState.AVAILABLE
    broken.fetch_error = SourceUnavailableError("timeout")
    broken.release_id = "r2"
    clock.now += timedelta(days=1, minutes=1)
    await coordinator.async_refresh()
    eurostat = coordinator.data.get("eurostat")
    assert eurostat.health.state is ProviderState.STALE_BUT_CACHED
    assert len(eurostat.datapoints) == 1


async def test_schema_change_and_parser_error_keep_old_data(hass: HomeAssistant) -> None:
    clock = Clock(NOW)
    provider = FakeProvider("sipri")
    coordinator = await _coordinator(hass, [provider], clock)
    await coordinator.async_refresh()
    provider.release_id = "r2"
    provider.parse_error = SchemaChangedError("sheet missing")
    clock.now = NOW + timedelta(days=7, minutes=1)
    await coordinator.async_refresh()
    series = coordinator.data.get("sipri")
    assert series.health.state is ProviderState.SCHEMA_CHANGED
    assert series.health.last_error == "sheet missing"
    assert series.release is not None and series.release.release_id == "r1"
    assert len(series.datapoints) == 1
    provider.parse_error = ValueError("bad number")
    clock.now += timedelta(days=7, minutes=1)
    await coordinator.async_refresh()
    assert coordinator.data.get("sipri").health.state is ProviderState.PARSER_ERROR


async def test_update_failed_only_when_nothing_is_available(hass: HomeAssistant) -> None:
    clock = Clock(NOW)
    provider = FakeProvider("eda")
    provider.discover_error = SourceUnavailableError("down")
    coordinator = await _coordinator(hass, [provider], clock)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_force_refresh_one_source(hass: HomeAssistant) -> None:
    clock = Clock(NOW)
    provider = FakeProvider("nato")
    coordinator = await _coordinator(hass, [provider], clock)
    await coordinator.async_refresh()
    provider.release_id = "r2"
    await coordinator.async_refresh_source("nato")
    assert provider.calls["fetch"] == 2
    assert coordinator.data.get("nato").release.release_id == "r2"
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/spending/test_coordinator.py -q`
Expected: `ImportError`.

- [ ] **Step 4: Implement the coordinator**

`custom_components/edp_radar/spending/coordinator.py`:

```python
"""SpendingCoordinator (S14; plan §64, §65, §86, §87).

Ticks every ``SPENDING_UPDATE_INTERVAL`` and runs only the providers whose
``next_check_at`` has passed. Discovery is cheap; a download happens only when
the release id changed. Failures are recorded per provider and never affect
the others; ``UpdateFailed`` is raised only when no source has any data.
"""

from __future__ import annotations

import dataclasses
import logging
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from aiohttp import ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, SPENDING_RETRY_INTERVAL, SPENDING_UPDATE_INTERVAL
from .models import ProviderHealth, ProviderState, SourceSeries
from .providers.base import (
    SchemaChangedError,
    SourceUnavailableError,
    SpendingProvider,
    SpendingProviderError,
)
from .store import SpendingStore

_LOGGER = logging.getLogger(__name__)

_PARSE_SLIPS = (
    ValueError,
    KeyError,
    IndexError,
    TypeError,
    AttributeError,
    UnicodeDecodeError,
    zipfile.BadZipFile,
)


@dataclass(frozen=True, slots=True)
class SpendingSnapshot:
    """What entities and diagnostics read: one series per source."""

    series: Mapping[str, SourceSeries]
    refreshed_at: datetime

    def get(self, source_id: str) -> SourceSeries:
        return self.series[source_id]


class SpendingCoordinator(DataUpdateCoordinator[SpendingSnapshot]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        *,
        session: ClientSession,
        store: SpendingStore,
        providers: Sequence[SpendingProvider],
        clock: Callable[[], datetime] = dt_util.utcnow,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_spending",
            update_interval=SPENDING_UPDATE_INTERVAL,
        )
        self.entry = entry
        self.store = store
        self.providers = tuple(providers)
        self._session = session
        self._clock = clock

    async def async_setup(self) -> None:
        await self.store.async_load()

    async def async_shutdown(self) -> None:
        await self.store.async_save(immediate=True)
        await super().async_shutdown()

    def _snapshot(self, now: datetime) -> SpendingSnapshot:
        return SpendingSnapshot(dict(self.store.series), now)

    async def _async_update_data(self) -> SpendingSnapshot:
        now = self._clock()
        for provider in self.providers:
            health = self.store.get(provider.spec.source_id).health
            if health.next_check_at is not None and now < health.next_check_at:
                continue
            await self._async_refresh_provider(provider, now)
        await self.store.async_save()
        if self.providers and not any(
            series.datapoints for series in self.store.series.values()
        ):
            errors = {
                source_id: series.health.last_error
                for source_id, series in self.store.series.items()
                if series.health.last_error
            }
            raise UpdateFailed(f"No spending source available: {errors}")
        return self._snapshot(now)

    async def async_refresh_source(self, source_id: str) -> None:
        """Run one provider now regardless of its cadence (diagnostics/scripts)."""
        provider = next(p for p in self.providers if p.spec.source_id == source_id)
        now = self._clock()
        await self._async_refresh_provider(provider, now)
        await self.store.async_save()
        self.async_set_updated_data(self._snapshot(now))

    async def _async_refresh_provider(self, provider: SpendingProvider, now: datetime) -> None:
        source_id = provider.spec.source_id
        series = self.store.get(source_id)
        try:
            release = await provider.async_discover_latest(self._session)
            if (
                series.release is not None
                and series.release.release_id == release.release_id
                and series.datapoints
            ):
                self._set_health(
                    source_id,
                    now,
                    state=ProviderState.AVAILABLE,
                    next_check_at=now + provider.spec.check_interval,
                    skip_reason="unchanged_release",
                )
                return
            fetched, payload = await provider.async_fetch_release(self._session, release)
            if (
                series.release is not None
                and series.datapoints
                and fetched.checksum is not None
                and fetched.checksum == series.release.checksum
            ):
                self.store.series[source_id] = dataclasses.replace(series, release=fetched)
                self._set_health(
                    source_id,
                    now,
                    state=ProviderState.AVAILABLE,
                    next_check_at=now + provider.spec.check_interval,
                    skip_reason="unchanged_checksum",
                )
                return
            result = await self.hass.async_add_executor_job(provider.parse_release, payload, fetched)
            applied = self.store.apply_release(
                source_id, fetched, result.datapoints, now=now, warnings=result.warnings
            )
            self._set_health(
                source_id, now, state=ProviderState.AVAILABLE,
                next_check_at=now + provider.spec.check_interval, skip_reason=None,
            )
            _LOGGER.debug(
                "%s: release %s → +%d ~%d =%d (carried %d, revisions %d)",
                source_id, fetched.release_id, applied.added, applied.updated,
                applied.unchanged, applied.carried_over, len(applied.revisions),
            )
        except SourceUnavailableError as err:
            state = ProviderState.STALE_BUT_CACHED if series.datapoints else ProviderState.TEMPORARILY_UNAVAILABLE
            _LOGGER.warning("%s unavailable: %s", source_id, err)
            self._set_health(source_id, now, state=state, next_check_at=now + SPENDING_RETRY_INTERVAL, error=str(err))
        except SchemaChangedError as err:
            _LOGGER.error("%s layout changed, keeping stored data: %s", source_id, err)
            self._set_health(source_id, now, state=ProviderState.SCHEMA_CHANGED, next_check_at=now + provider.spec.check_interval, error=str(err))
        except (SpendingProviderError, *_PARSE_SLIPS) as err:
            _LOGGER.error("%s parser error, keeping stored data: %r", source_id, err)
            self._set_health(source_id, now, state=ProviderState.PARSER_ERROR, next_check_at=now + provider.spec.check_interval, error=str(err))

    def _set_health(
        self,
        source_id: str,
        now: datetime,
        *,
        state: ProviderState,
        next_check_at: datetime,
        skip_reason: str | None = None,
        error: str | None = None,
    ) -> None:
        current = self.store.get(source_id).health
        self.store.set_health(
            source_id,
            ProviderHealth(
                state=state,
                last_check_at=now,
                next_check_at=next_check_at,
                last_success_at=now if state is ProviderState.AVAILABLE else current.last_success_at,
                last_error=error,
                warnings=current.warnings,
                skip_reason=skip_reason,
            ),
        )
```

Note for the executor: after `apply_release` the store already set `AVAILABLE`/`last_success_at`; `_set_health` is still called to record `next_check_at` — it keeps `warnings` from the store.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/spending/test_coordinator.py -q`
Expected: 6 passed. In `test_update_failed_only_when_nothing_is_available` the private `_async_update_data` is called directly because `async_refresh` swallows `UpdateFailed` into `last_update_success`.

- [ ] **Step 6: Quality gate and commit**

```bash
uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q
git add custom_components/edp_radar/const.py custom_components/edp_radar/spending/coordinator.py tests/spending/test_coordinator.py
git commit -m "feat(spending): coordinator with per-source cadence and isolated failures (S14)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: Wiring — `RuntimeData`, second coordinator, unload/remove, test isolation

**Files:**
- Create: `custom_components/edp_radar/runtime.py`
- Modify: `custom_components/edp_radar/coordinator.py:53` (`EdpRadarConfigEntry` alias)
- Modify: `custom_components/edp_radar/__init__.py` (setup/unload/remove)
- Modify: `custom_components/edp_radar/diagnostics.py:82`, `event.py:39`, `services.py:85`, `sensor.py:1193` (`.radar`)
- Modify: `tests/conftest.py` (autouse provider stub), `pyproject.toml` (marker), `tests/test_config_flow.py:422,438`, `tests/test_coordinator.py:73,87`, `tests/test_init.py:27,73`
- Create: `tests/spending/mocks.py`
- Test: `tests/test_init.py` (new test)

**Interfaces:**
- Consumes: `SpendingCoordinator`, `SpendingStore`, `providers.all_providers`.
- Produces: `runtime.RuntimeData(radar: EdpRadarCoordinator, spending: SpendingCoordinator)`; `EdpRadarConfigEntry = ConfigEntry[RuntimeData]`; `tests/spending/mocks.mock_spending_sources(aioclient_mock, *, today=None)`; pytest marker `spending_live`.

- [ ] **Step 1: Write the failing wiring test**

Append to `tests/test_init.py`:

```python
@pytest.mark.spending_live
async def test_spending_layer_is_wired(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    from custom_components.edp_radar.spending.models import ProviderState
    from custom_components.edp_radar.spending.store import storage_key

    from .spending.mocks import mock_spending_sources

    mock_spending_sources(mock_backend)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    runtime = config_entry.runtime_data
    assert runtime.radar.data is not None
    snapshot = runtime.spending.data
    assert snapshot is not None
    for source_id in ("statskontoret", "eurostat", "nato", "eda", "sipri"):
        series = snapshot.get(source_id)
        assert series.health.state is ProviderState.AVAILABLE, (source_id, series.health)
        assert series.datapoints
    assert any(p.metric_id == "materiel_outturn" for p in snapshot.get("statskontoret").datapoints)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert storage_key(config_entry.entry_id, "nato") in hass_storage

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert not [k for k in hass_storage if ".spending." in k]
```

Add `import pytest` to the test module imports.

Create `tests/spending/mocks.py`:

```python
"""Register every spending source on the aiohttp mocker using the real fixtures."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.spending.providers.eda import (
    PORTAL_URL,
    discover_workbooks,
)
from custom_components.edp_radar.spending.providers.eurostat import API_URL
from custom_components.edp_radar.spending.providers.nato import (
    TOPIC_URL,
    discover_workbook,
)
from custom_components.edp_radar.spending.providers.sipri import (
    LANDING_URL,
    discover_release,
)
from custom_components.edp_radar.spending.providers.statskontoret import (
    DISCOVERY_URL,
    parse_discovery_page,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spending"


def mock_spending_sources(aioclient_mock: AiohttpClientMocker, *, today: date | None = None) -> None:
    today = today or date.today()
    page = (FIXTURES / "statskontoret" / "discovery-2026.html").read_text(encoding="utf-8")
    for year in {today.year, today.year - 1, 2026}:
        aioclient_mock.get(f"{DISCOVERY_URL}?year={year}", text=page)
    csv = (FIXTURES / "statskontoret" / "utgifter-2026-07.csv").read_bytes()
    for release in parse_discovery_page(page, f"{DISCOVERY_URL}?year=2026"):
        aioclient_mock.get(release.csv_url, content=csv)

    aioclient_mock.get(API_URL, content=(FIXTURES / "eurostat" / "gov_ev-defence.json").read_bytes())

    topic = (FIXTURES / "nato" / "topic-page.html").read_text(encoding="utf-8")
    aioclient_mock.get(TOPIC_URL, text=topic)
    _year, nato_xlsx = discover_workbook(topic, TOPIC_URL)
    aioclient_mock.head(nato_xlsx, headers={"ETag": '"nato"', "Last-Modified": "Fri, 10 Jul 2026 09:55:14 GMT"})
    aioclient_mock.get(nato_xlsx, content=(FIXTURES / "nato" / "def-exp-2026-en.xlsx").read_bytes())

    portal = (FIXTURES / "eda" / "portal.html").read_text(encoding="utf-8")
    aioclient_mock.get(PORTAL_URL, text=portal)
    for year, url in discover_workbooks(portal, PORTAL_URL).items():
        aioclient_mock.head(url, headers={"Last-Modified": "Fri, 04 Sep 2026 10:13:18 GMT"})
        name = "defence-data-2025.xlsx" if year >= 2025 else "defence-data-2022.xlsx"
        aioclient_mock.get(url, content=(FIXTURES / "eda" / name).read_bytes())

    landing = (FIXTURES / "sipri" / "landing.html").read_text(encoding="utf-8")
    aioclient_mock.get(LANDING_URL, text=landing)
    sipri_xlsx, _revised = discover_release(landing, LANDING_URL)
    aioclient_mock.head(sipri_xlsx, headers={"ETag": '"sipri"'})
    aioclient_mock.get(sipri_xlsx, content=(FIXTURES / "sipri" / "milex-trimmed.xlsx").read_bytes())
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_init.py -q`
Expected: the new test fails (`AttributeError: 'EdpRadarCoordinator' object has no attribute 'radar'` or unknown marker warning).

- [ ] **Step 3: Add the marker and the autouse stub**

`pyproject.toml`, under `[tool.pytest.ini_options]`:

```toml
markers = ["spending_live: set up the entry with the real spending providers (mocked HTTP)"]
```

`tests/conftest.py` — add:

```python
@pytest.fixture(autouse=True)
def stub_spending_providers(request: pytest.FixtureRequest) -> Generator[None]:
    """Radar tests run without spending providers; ``spending_live`` tests opt in."""
    if "spending_live" in request.keywords:
        yield
        return
    with patch("custom_components.edp_radar.all_providers", return_value=()):
        yield
```

- [ ] **Step 4: Implement the wiring**

Create `custom_components/edp_radar/runtime.py`:

```python
"""Per-entry runtime objects (S1)."""

from __future__ import annotations

from dataclasses import dataclass

from .coordinator import EdpRadarCoordinator
from .spending.coordinator import SpendingCoordinator


@dataclass(slots=True)
class RuntimeData:
    radar: EdpRadarCoordinator
    spending: SpendingCoordinator
```

In `custom_components/edp_radar/coordinator.py` replace `type EdpRadarConfigEntry = ConfigEntry[EdpRadarCoordinator]` with:

```python
if TYPE_CHECKING:
    from .runtime import RuntimeData

type EdpRadarConfigEntry = ConfigEntry[RuntimeData]
```

(add `TYPE_CHECKING` to the `typing` import; the alias is evaluated lazily so no runtime cycle).

In `custom_components/edp_radar/__init__.py`:

```python
from .runtime import RuntimeData
from .spending.coordinator import SpendingCoordinator
from .spending.providers import all_providers
from .spending.store import SpendingStore
```

and in `async_setup_entry` replace `entry.runtime_data = coordinator` with:

```python
    spending = SpendingCoordinator(
        hass,
        entry,
        session=session,
        store=SpendingStore(hass, entry.entry_id),
        providers=all_providers(),
    )
    await spending.async_setup()
    entry.runtime_data = RuntimeData(radar=coordinator, spending=spending)
    # No entities listen yet (Plan 2): a no-op listener keeps the 6 h cycle armed,
    # and the first refresh runs in the background so a slow source never delays setup.
    entry.async_on_unload(spending.async_add_listener(lambda: None))
    entry.async_create_background_task(
        hass, spending.async_refresh(), name=f"{DOMAIN} spending initial refresh"
    )
```

`async_unload_entry`:

```python
    if unloaded:
        await entry.runtime_data.spending.async_shutdown()
        await entry.runtime_data.radar.async_shutdown()
```

`async_remove_entry`:

```python
    store = RadarStore(hass, entry.entry_id)
    await store.async_load()
    await store.async_remove()
    await SpendingStore(hass, entry.entry_id).async_remove()
```

Readers: `diagnostics.py:82` → `coordinator = entry.runtime_data.radar`; `event.py:39` → `coordinator = entry.runtime_data.radar`; `sensor.py:1193` → `coordinator = entry.runtime_data.radar`; `services.py:85` → `coordinator: EdpRadarCoordinator = entry.runtime_data.radar`.

Tests: `tests/test_config_flow.py:422` → `config_entry.runtime_data.radar.config…`, `:438` → `coordinator = config_entry.runtime_data.radar`; `tests/test_coordinator.py:73` → `coordinator: EdpRadarCoordinator = entry.runtime_data.radar`, `:87` → `await entry.runtime_data.radar.async_refresh()`; `tests/test_init.py:27` → `config_entry.runtime_data.radar.data`, `:73` → `entry.runtime_data.radar.config…`.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q`
Expected: all green, including `test_spending_layer_is_wired` (it parses five real fixtures; ≈ 2–3 s). If `async_block_till_done(wait_background_tasks=True)` returns before the spending refresh completes, add `await config_entry.runtime_data.spending.async_refresh()` after it — the assertion set stays the same.

- [ ] **Step 6: Quality gate and commit**

```bash
uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q
git add custom_components/edp_radar pyproject.toml tests
git commit -m "feat(spending): wire SpendingCoordinator into the entry runtime (S1)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 14: Diagnostics `spending` section

**Files:**
- Modify: `custom_components/edp_radar/diagnostics.py`
- Test: `tests/test_diagnostics.py`

**Interfaces:**
- Consumes: `RuntimeData.spending`, `SpendingSnapshot`, `freshness.*`, `calculations.latest_reference`.
- Produces: `diagnostics["spending"]` = `{source_id: {...}}` per plan §80.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_diagnostics.py`:

```python
@pytest.mark.spending_live
async def test_spending_diagnostics(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    from .spending.mocks import mock_spending_sources

    freezer.move_to(NOW)
    mock_spending_sources(mock_backend)
    entry = MockConfigEntry(domain=DOMAIN, entry_id="test-entry", unique_id=DOMAIN, data={}, options=FULL_OPTIONS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    spending = diagnostics["spending"]
    assert sorted(spending) == ["eda", "eurostat", "nato", "sipri", "statskontoret"]
    sk = spending["statskontoret"]
    assert sk["health"]["state"] == "available"
    assert sk["release"]["release_id"] == "2026-07-definitiv-2026-08-24"
    assert sk["release"]["published_at"] == "2026-08-24"
    assert sk["datapoints"] == 57
    assert sk["countries"] == ["SE"]
    assert sk["metrics"] == ["materiel_outturn", "uo6_defence_outturn", "uo6_total_outturn"]
    assert sk["latest_reference"] == {"start": "2026-07-01", "end": "2026-07-31", "label": "Jul 2026"}
    assert sk["freshness"] == {"state": "current", "publication_age_days": 19, "reference_age_days": 43}
    assert sk["revisions"] == 0
    assert sk["schema_version"] == 1
    assert sk["parse_warnings"] == []
    nato = spending["nato"]
    assert nato["latest_reference"]["label"] == "2026"
    assert set(nato["statuses"]) == {"actual", "estimate"}
    assert set(nato["countries"]) >= {"SE", "US", "TR"}
    json.dumps(diagnostics)  # serialisable
```

(`statuses` is a count per status value.)

Add `import pytest` to the module imports if missing.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_diagnostics.py -q -k spending`
Expected: `KeyError: 'spending'`.

- [ ] **Step 3: Implement**

In `custom_components/edp_radar/diagnostics.py` add imports:

```python
from collections import Counter

from .spending.calculations import latest_reference
from .spending.freshness import (
    freshness_state,
    publication_age_days,
    reference_age_days,
)
from .spending.models import SourceSeries
from .spending.registry import source_spec
from .spending.store import SCHEMA_VERSION as SPENDING_SCHEMA_VERSION
```

and the helper:

```python
def _spending_series(series: SourceSeries, today: date) -> dict[str, Any]:
    """One diagnostics block per source (plan §80): metadata only, no values."""
    metrics = sorted({p.metric_id for p in series.datapoints})
    latest = None
    for metric_id in metrics:
        candidate = latest_reference(series.datapoints, metric_id, min_countries=1)
        if candidate and (latest is None or candidate.end > latest.end):
            latest = candidate
    published = series.release.published_at if series.release else None
    return {
        "health": series.health.to_dict(),
        "release": None if series.release is None else series.release.to_dict(),
        "retrieved_at": _plain(series.retrieved_at),
        "datapoints": len(series.datapoints),
        "countries": sorted({p.country for p in series.datapoints}),
        "metrics": metrics,
        "statuses": dict(Counter(p.status.value for p in series.datapoints)),
        "latest_reference": None if latest is None else latest.to_dict(),
        "freshness": {
            "state": freshness_state(
                source_spec(series.source_id), latest.end if latest else None, published, today
            ).value,
            "publication_age_days": publication_age_days(published, today),
            "reference_age_days": None if latest is None else reference_age_days(latest.end, today),
        },
        "parse_warnings": list(series.health.warnings),
        "revisions": len(series.revisions),
        "schema_version": SPENDING_SCHEMA_VERSION,
    }
```

In `async_get_config_entry_diagnostics` read `runtime = entry.runtime_data`, `coordinator = runtime.radar`, and add to the returned dict (after `"fx"`):

```python
        "spending": {
            source_id: _spending_series(series, dt_util.now().date())
            for source_id, series in runtime.spending.store.series.items()
        },
```

(`from homeassistant.util import dt as dt_util`; `date` from `datetime`.) Diagnostics read the store, not `coordinator.data`, so a source that never loaded still appears with `never_loaded`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_diagnostics.py -q`
Expected: all pass. `publication_age_days` is 19 because `NOW` is 2026-09-12 and the Statskontoret release date is 2026-08-24.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar && uv run pytest -q
git add custom_components/edp_radar/diagnostics.py tests/test_diagnostics.py
git commit -m "feat(spending): per-source diagnostics with freshness (S17)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 15: `scripts/spending_profile.py` and the generated `docs/phase3-source-profile.md`

**Files:**
- Create: `scripts/spending_profile.py`
- Create (generated): `docs/phase3-source-profile.md`
- Modify: `.gitignore` (ensure `.cache/` is ignored)

**Interfaces:**
- Consumes: `providers.all_providers()`, `calculations.*`, `freshness.*`, `registry.*`, `countries.NORDIC`.
- Produces: the plan-§70 profile and plan-§71 validation report in one Markdown file; a cache under `.cache/spending/profile/<source>/<release>/`.

- [ ] **Step 1: Write the script**

`scripts/spending_profile.py`:

```python
"""Phase 3A/3B harness: profile every spending source and validate the facts.

Usage:
    PYTHONPATH=. uv run python scripts/spending_profile.py \
        --out docs/phase3-source-profile.md
    PYTHONPATH=. uv run python scripts/spending_profile.py --no-fetch

Every provider's latest release is discovered, downloaded and cached under
--cache (default .cache/spending/profile); --no-fetch re-parses the newest
cached release. The report holds aggregates, provenance and the Sweden
answers of plan §71 — never raw workbooks.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import aiohttp

from custom_components.edp_radar.spending.calculations import (
    latest_month,
    latest_reference,
    nominal_change_pct,
    nordic_subset,
    rank,
    ytd,
)
from custom_components.edp_radar.spending.freshness import (
    freshness_state,
    publication_age_days,
    reference_age_days,
)
from custom_components.edp_radar.spending.models import (
    DatapointStatus,
    SourceRelease,
    SpendingDataPoint,
)
from custom_components.edp_radar.spending.providers import all_providers
from custom_components.edp_radar.spending.providers.base import (
    ParseResult,
    Payload,
    SpendingProvider,
    SpendingProviderError,
)
from custom_components.edp_radar.spending.registry import (
    FOCUS_COUNTRY,
    SOURCE_ORDER,
    metrics_for,
    source_spec,
)

BUDGET_PAGE = "https://www.statskontoret.se/analys-och-statistik/utfall/utfall-for-statens-budget/?year={year}&month={month}"
UO6_NAME = "Försvar och samhällets krisberedskap"

REVISION_BEHAVIOUR = {
    "statskontoret": "Every monthly file carries the full history; December is published as preliminär then definitiv. The store diff records changed values as revisions.",
    "eurostat": "Twice-yearly dissemination may revise earlier years; `updated` changes the release id and the store diff records revisions.",
    "nato": "Each annual workbook restates 2014 onwards and re-marks the last two years as estimates; revisions detected by the store diff.",
    "eda": "Occasional in-year revisions (EDA statement); every workbook ≥ 2022 is re-fetched and compared.",
    "sipri": "Annual release plus in-year revisions replacing the file; full re-import and store diff.",
}
PARSER_RISK = {
    "statskontoret": "HTML discovery markup (`li.data`, `Senast uppdaterad`, GetFile query) and CSV column names.",
    "eurostat": "Dimension/unit codes; a renamed code fails discovery of the metric (SchemaChangedError).",
    "nato": "Sheet names, `Table N:` titles, block subtitles, `YYYYe` headers, label spellings; XLSX must share the PDF path.",
    "eda": "Portal anchor text `Defence Data YYYY`, `Member States` sheet header wording, footnote conventions.",
    "sipri": "Landing-page anchor and revision sentence; header row `Country`; colour semantics (blue/red).",
}


def _table(rows: list[tuple[Any, ...]], header: tuple[str, ...]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def _fmt(value: Decimal | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:,.{digits}f}"


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text)[:120]


async def fetch_release(
    provider: SpendingProvider, session: aiohttp.ClientSession, cache: Path
) -> tuple[SourceRelease, Payload]:
    release = await provider.async_discover_latest(session)
    fetched, payload = await provider.async_fetch_release(session, release)
    folder = cache / provider.spec.source_id / _slug(fetched.release_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "release.json").write_text(json.dumps(fetched.to_dict(), indent=2))
    if isinstance(payload, bytes):
        (folder / "payload.bin").write_bytes(payload)
    else:
        for key, blob in payload.items():
            (folder / f"payload.{key}.bin").write_bytes(blob)
    return fetched, payload


def cached_release(provider: SpendingProvider, cache: Path) -> tuple[SourceRelease, Payload]:
    folders = sorted((cache / provider.spec.source_id).glob("*/release.json"), key=lambda p: p.stat().st_mtime)
    if not folders:
        raise SystemExit(f"no cached release for {provider.spec.source_id}; run without --no-fetch")
    folder = folders[-1].parent
    release = SourceRelease.from_dict(json.loads((folder / "release.json").read_text()))
    single = folder / "payload.bin"
    if single.exists():
        return release, single.read_bytes()
    parts = {p.name.split(".")[1]: p.read_bytes() for p in folder.glob("payload.*.bin")}
    return release, parts


async def check_budget_page(session: aiohttp.ClientSession | None, cache: Path, today: date) -> dict[str, Any]:
    """Plan §53: does the human-readable outturn page expose a UO6 budget (SB + ÄB)?"""
    month = today.month - 2 if today.month > 2 else 12
    year = today.year if today.month > 2 else today.year - 1
    url = BUDGET_PAGE.format(year=year, month=month)
    target = cache / "statskontoret" / "budget-page.html"
    if session is not None:
        async with session.get(url, headers={"User-Agent": "ha-edp-radar profile"}) as response:
            html = await response.text()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html)
    else:
        html = target.read_text() if target.exists() else ""
    return {
        "url": url,
        "sb_ab_column": "SB + ÄB" in html or "SB&nbsp;+&nbsp;ÄB" in html,
        "uo6_row": UO6_NAME in html,
    }


def profile_section(provider: SpendingProvider, release: SourceRelease, result: ParseResult, today: date) -> str:
    spec = provider.spec
    points = result.datapoints
    metrics = Counter(p.metric_id for p in points)
    statuses = Counter(p.status.value for p in points)
    countries = sorted({p.country for p in points})
    latest_by_metric = {m: latest_reference(points, m, min_countries=1) for m in metrics}
    latest_end = max((r.end for r in latest_by_metric.values() if r), default=None)
    missing_latest: list[str] = []
    for metric_id, ref in latest_by_metric.items():
        if ref is None:
            continue
        have = {p.country for p in points if p.metric_id == metric_id and p.reference == ref}
        missing_latest.append(f"{metric_id} {ref.label}: {len(have)}/{len(countries)} countries")
    rows = [
        ("technical access confirmed", "yes"),
        ("discovery method", f"{spec.canonical_url} → {release.download_url}"),
        ("format", release.format),
        ("latest release found", f"`{release.release_id}` published {release.published_at} (etag {release.etag!r}, checksum {(release.checksum or '')[:12]}…)"),
        ("latest reference period", latest_end.isoformat() if latest_end else "n/a"),
        ("available countries", f"{len(countries)}: {', '.join(countries)}"),
        ("available metrics", ", ".join(f"{m} ({n})" for m, n in sorted(metrics.items()))),
        ("actual/estimate/projection distinctions", ", ".join(f"{s}: {n}" for s, n in sorted(statuses.items()))),
        ("source publication date available", "yes" if release.published_at else "no"),
        ("revision behaviour", REVISION_BEHAVIOUR[spec.source_id]),
        ("missing data", "; ".join(missing_latest) + (f"; warnings: {'; '.join(result.warnings)}" if result.warnings else "")),
        ("parser risk", PARSER_RISK[spec.source_id]),
        ("freshness today", freshness_state(spec, latest_end, release.published_at, today).value
            + f" (publication age {publication_age_days(release.published_at, today)} d, reference age {reference_age_days(latest_end, today) if latest_end else 'n/a'} d)"),
        ("layout fingerprint", f"`{result.layout_fingerprint[:160]}`"),
    ]
    return f"## {spec.display_name}\n\n" + _table(rows, ("Item", "Value")) + "\n"


def _rank_line(points: tuple[SpendingDataPoint, ...], metric_id: str, unit: str) -> str:
    ref = latest_reference(points, metric_id)
    if ref is None:
        return f"- {metric_id}: no reference period with ≥ 2 countries"
    ranking = rank(points, metric_id=metric_id, unit=unit, reference=ref)
    if ranking is None:
        return f"- {metric_id} {ref.label}: Sweden missing"
    nordic = ", ".join(f"{e.country} #{e.rank} {_fmt(e.value)}" for e in nordic_subset(ranking))
    return (
        f"- {metric_id} {ref.label} ({unit}, statuses {'/'.join(ranking.statuses)}): "
        f"Sweden #{ranking.focus_rank} of {ranking.population}, {_fmt(ranking.focus_value)}; "
        f"top {ranking.top.country} {_fmt(ranking.top.value)}; median {_fmt(ranking.median)}; Nordic: {nordic}"
    )


def validation_section(results: dict[str, tuple[SourceRelease, ParseResult]], budget: dict[str, Any]) -> str:
    out = ["# Factual validation (plan §71)\n"]
    if "statskontoret" in results:
        release, result = results["statskontoret"]
        points = result.datapoints
        latest = latest_month(points, "materiel_outturn", FOCUS_COUNTRY)
        lines = ["## Statskontoret\n"]
        if latest:
            y, m = latest.reference.start.year, latest.reference.start.month
            current = ytd(points, "materiel_outturn", FOCUS_COUNTRY, y, m)
            previous = ytd(points, "materiel_outturn", FOCUS_COUNTRY, y - 1, m)
            lines += [
                f"- Latest Swedish reference month: **{latest.reference.label}** (status {latest.status.value})",
                f"- Materiel acquisition latest month: SEK {_fmt(latest.value)} m",
                f"- Materiel acquisition YTD Jan–{latest.reference.label}: SEK {_fmt(current)} m; same period {y - 1}: SEK {_fmt(previous)} m; nominal change {_fmt(nominal_change_pct(current, previous))} %",
                f"- Defence appropriations (1:1–1:14) YTD: SEK {_fmt(ytd(points, 'uo6_defence_outturn', FOCUS_COUNTRY, y, m))} m; UO6 total YTD: SEK {_fmt(ytd(points, 'uo6_total_outturn', FOCUS_COUNTRY, y, m))} m",
                f"- Publication date: {release.published_at}; release `{release.release_id}`",
            ]
        lines.append(
            f"- Budget utilisation (plan §53): human-readable page {budget['url']} — SB + ÄB column present: {budget['sb_ab_column']}, UO6 row present: {budget['uo6_row']}. "
            + ("A per-expenditure-area budget is exposed; a budget metric can be designed in Plan 2." if budget["uo6_row"] and budget["sb_ab_column"] else "No per-expenditure-area budget with provenance found; budget utilisation is omitted (S16).")
        )
        out.append("\n".join(lines) + "\n")
    if "eurostat" in results:
        points = results["eurostat"][1].datapoints
        out.append("## Eurostat\n\n" + "\n".join([
            _rank_line(points, "defence_expenditure", "EUR_MILLION"),
            _rank_line(points, "defence_expenditure_pct_gdp", "PCT_GDP"),
            _rank_line(points, "defence_investment", "EUR_MILLION"),
            _rank_line(points, "defence_investment_pct_gdp", "PCT_GDP"),
        ]) + "\n")
    if "nato" in results:
        points = results["nato"][1].datapoints
        actual_years = sorted({p.reference.start.year for p in points if p.status is DatapointStatus.ACTUAL})
        estimate_years = sorted({p.reference.start.year for p in points if p.status is DatapointStatus.ESTIMATE})
        out.append("## NATO\n\n" + "\n".join([
            f"- Actual years {actual_years[0]}–{actual_years[-1]}; estimate years {estimate_years}",
            _rank_line(points, "defence_expenditure_usd_current", "USD_MILLION"),
            _rank_line(points, "defence_expenditure_pct_gdp", "PCT_GDP"),
            _rank_line(points, "equipment_share_pct", "PCT"),
            _rank_line(points, "equipment_expenditure_usd_current", "USD_MILLION"),
        ]) + "\n")
    if "eda" in results:
        points = results["eda"][1].datapoints
        lines = ["## EDA\n"]
        for spec in metrics_for("eda"):
            ref = latest_reference(points, spec.metric_id, min_countries=1)
            have_se = any(p.metric_id == spec.metric_id and p.country == FOCUS_COUNTRY for p in points)
            lines.append(f"- {spec.metric_id}: latest {ref.label if ref else 'n/a'}, Sweden {'available' if have_se else 'missing'}")
        lines += [_rank_line(points, "defence_expenditure", "EUR_MILLION"), _rank_line(points, "defence_investment", "EUR_MILLION"), _rank_line(points, "equipment_procurement", "EUR_MILLION")]
        out.append("\n".join(lines) + "\n")
    if "sipri" in results:
        points = results["sipri"][1].datapoints
        se_years = sorted(p.reference.start.year for p in points if p.country == FOCUS_COUNTRY and p.metric_id == "military_expenditure_usd_constant")
        out.append("## SIPRI\n\n" + "\n".join([
            f"- Sweden available {se_years[0]}–{se_years[-1]} (stored from MIN_YEAR; the workbook starts 1949)",
            _rank_line(points, "military_expenditure_usd_constant", "USD_MILLION_CONSTANT_2024"),
            _rank_line(points, "military_expenditure_pct_gdp", "PCT_GDP"),
        ]) + "\n")
    return "\n".join(out)


async def run(args: argparse.Namespace) -> str:
    cache = Path(args.cache)
    today = date.fromisoformat(args.today) if args.today else datetime.now(UTC).date()
    providers = {p.spec.source_id: p for p in all_providers()}
    results: dict[str, tuple[SourceRelease, ParseResult]] = {}
    errors: dict[str, str] = {}
    session: aiohttp.ClientSession | None = None if args.no_fetch else aiohttp.ClientSession()
    try:
        for provider in providers.values():
            source_id = provider.spec.source_id
            try:
                release, payload = (
                    cached_release(provider, cache) if session is None else await fetch_release(provider, session, cache)
                )
                results[source_id] = (release, provider.parse_release(payload, release))
                print(f"{source_id}: {len(results[source_id][1].datapoints)} datapoints", file=sys.stderr)
            except (SpendingProviderError, OSError, ValueError) as err:
                errors[source_id] = f"{type(err).__name__}: {err}"
                print(f"{source_id}: FAILED {errors[source_id]}", file=sys.stderr)
        budget = await check_budget_page(session, cache, today)
    finally:
        if session is not None:
            await session.close()
    sections = [
        "# Phase 3 source profile\n",
        f"Generated {datetime.now(UTC).isoformat(timespec='seconds')} by `scripts/spending_profile.py` (report date {today}). "
        "Plan §70 profile per provider, then the plan §71 factual validation. Values are aggregates and Sweden facts with provenance; no raw payloads.\n",
    ]
    for source_id in SOURCE_ORDER:
        if source_id in results:
            sections.append(profile_section(providers[source_id], *results[source_id], today))
        else:
            sections.append(f"## {source_spec(source_id).display_name}\n\n| Item | Value |\n| --- | --- |\n| technical access confirmed | **no** — {errors.get(source_id, 'not attempted')} |\n")
    sections.append(validation_section(results, budget))
    return "\n".join(sections)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="docs/phase3-source-profile.md")
    parser.add_argument("--cache", default=".cache/spending/profile")
    parser.add_argument("--no-fetch", action="store_true", help="re-parse the newest cached release")
    parser.add_argument("--today", default=None, help="report date YYYY-MM-DD (default: today)")
    args = parser.parse_args(argv)
    report = asyncio.run(run(args))
    Path(args.out).write_text(report, encoding="utf-8")
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Ensure `.gitignore` contains `.cache/` (add the line if absent).

- [ ] **Step 2: Run the script live and read the output**

Run: `PYTHONPATH=. uv run python scripts/spending_profile.py --out docs/phase3-source-profile.md`
Expected on stderr: five `<source>: N datapoints` lines (Statskontoret ≈ 750, Eurostat 771, NATO ≈ 2 000, EDA ≈ 2 700, SIPRI ≈ 15 000) and `wrote docs/phase3-source-profile.md`. Then read the document and check every plan-§71 answer is present and plausible (Sweden materiel YTD through the latest month, Eurostat rank 4 of 22 for 2025 defence expenditure, NATO 2026 estimates flagged, EDA equipment procurement only to 2021, SIPRI Sweden from 1990). If a provider fails live, fix the provider (its fixture is real, so the failure means a source changed since 2026-09-12) — do not hand-edit the report.

Run again: `PYTHONPATH=. uv run python scripts/spending_profile.py --no-fetch --out /tmp/profile-check.md && diff <(grep -v Generated docs/phase3-source-profile.md) <(grep -v Generated /tmp/profile-check.md)`
Expected: no diff (the cache reproduces the report).

- [ ] **Step 3: Lint the script and commit**

```bash
uv run ruff check scripts && uv run ruff format scripts
git add scripts/spending_profile.py docs/phase3-source-profile.md .gitignore
git commit -m "docs: Phase 3 source profile and factual validation generated from live sources

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 16: Documentation, session notes and final gate

**Files:**
- Modify: `README.md` (short "Defence spending data layer (Phase 3, data only)" section)
- Modify: `docs/superpowers/NEXT-SESSION.md`
- Modify: `docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md` (§7.3 findings from the profile, if any decision changed)

- [ ] **Step 1: README section**

Add after the Phase 2 (country purchasing) section:

```markdown
## Defence spending data layer (Phase 3, data only)

Version 0.2.x ingests five spending sources into per-source stores — Statskontoret monthly budget outturn (SEK, appropriations 6:1:x incl. 1:3 materiel), Eurostat `gov_ev` (defence expenditure and investment, EU27), NATO defence expenditure tables, EDA defence data (member-state level) and the SIPRI Military Expenditure Database. Every value keeps its source, reference period, status (`actual`, `preliminary`, `provisional`, `estimate`, `projection`, `budget`), publication date and release; sources are never merged or ranked against each other. The requirement `openpyxl` reads the XLSX sources. Entities for this layer arrive in the next release; until then the data is visible in the integration diagnostics (`spending`) and in `docs/phase3-source-profile.md`. Provider details: `docs/providers/`.
```

- [ ] **Step 2: Update `docs/superpowers/NEXT-SESSION.md`**

Add under "Läge": a bullet that Phase 3 data layer (S1–S20, plan `docs/superpowers/plans/2026-09-12-edp-radar-spending-data-layer.md`) is implemented on `main`: package `custom_components/edp_radar/spending/`, five providers with real fixtures, `SpendingStore`, `SpendingCoordinator` (6 h tick, per-source cadence), diagnostics section `spending`, scripts `fetch_spending_fixtures.py` and `spending_profile.py`, the generated `docs/phase3-source-profile.md`, and that **Plan 2 = sensors/devices** (plan §72–§79) is next and starts with a brainstorming round on the profile findings (EDA equipment procurement ends 2021; Eurostat latest year has fewer countries; budget utilisation depends on the §53 finding). Update the quality-gate test count.

- [ ] **Step 3: Addendum §7.3 (only if the profile contradicted a decision)**

If the live profile changed a decision (e.g. a metric verdict), add `## 7.3 Findings from the source profile (date)` with numbered `S21…` entries; otherwise skip.

- [ ] **Step 4: Full quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components/edp_radar
git add README.md docs/superpowers/NEXT-SESSION.md docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md
git commit -m "docs: Phase 3 data layer README section and session notes

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

Do not push; do not bump the version (0.3.0 comes with the sensors, S20).

---

## Self-review notes (already applied)

- Spec coverage: S1 → Task 13; S2 → Task 2 (`FOCUS_COUNTRY`); S3 → Task 1; S4/S5 → Task 1, 11; S6 → units in Task 2 registry and each provider; S7 → Task 2; S8 → Task 2 + `rank` in Task 10; S9 → Task 4; S10 → Task 5; S11 → Tasks 6–8; S12 → Task 3; S13 → Task 11; S14 → Task 12; S15 → Task 9; S16 → Task 10 (+ budget check in Task 15); S17 → Task 14; S18 → Tasks 4–8 (fixtures) and 15 (profile); S19 → every task; S20 → nothing adds entities/translations/version.
- Plan §68 provider documents: Tasks 4, 5, 6, 7, 8. Plan §70/§71: Task 15. Plan §36 (EDA doc before parser): Task 7 step 1.
- Type consistency: `SpendingDataPoint` has no `retrieved_at` (it lives on `SourceSeries`); `ParseResult.warnings`/`layout_fingerprint` used by store (`warnings`) and profile; `with_fetch_metadata(release, fetched)` defined in Task 4's base.py addition and used by Statskontoret, Eurostat, NATO, SIPRI; EDA uses `dataclasses.replace`.

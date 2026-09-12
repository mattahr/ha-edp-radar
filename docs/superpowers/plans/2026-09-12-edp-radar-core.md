# EDP Radar Core Library Implementation Plan (Plan 1 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and test the Home-Assistant-independent core of `ha-edp-radar`: TED query builder and API client, normalizer and typed models, defence taxonomy, ECB FX normalization, monthly-partition storage, procedure lifecycle index, the complete metrics engine (`RadarSnapshot`), and the Phase 0 data-profile harness and report.

**Architecture:** Pure Python modules (`models`, `query`, `normalizer`, `taxonomy`, `fx_rates`, `lifecycle`, `metrics`) with frozen dataclasses and no Home Assistant imports, wrapped by two thin aiohttp clients (`api`, `fx`) and one Home Assistant storage adapter (`storage`). Everything the entities will later read comes from one immutable `RadarSnapshot` produced by `metrics.compute_snapshot`. Plan 2 adds the Home Assistant shell (config flow, coordinator, entities, diagnostics, dev container, README/HACS).

**Tech Stack:** Python 3.14, `uv`, `homeassistant==2026.9.2`, `pytest-homeassistant-custom-component==0.13.365` (pytest, pytest-asyncio, `AiohttpClientMocker`, `hass` fixture), `aiohttp`, `ruff`, `mypy`.

**Spec:** `docs/ha-edp-radar_PROJECT.md` (the plan) and `docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md` (verified API facts and decisions D1–D19). Decision references below (`D3`, `D6`, …) point at the addendum.

## Global Constraints

- Python `>=3.14.2`; Home Assistant `2026.9.2`; test harness `pytest-homeassistant-custom-component==0.13.365` (D13).
- No GitHub workflows, no issue templates (owner decision).
- Domain `edp_radar`; package `custom_components/edp_radar/`; tests in `tests/`.
- Pure modules (`models.py`, `const.py`, `query.py`, `normalizer.py`, `taxonomy.py`, `fx_rates.py`, `lifecycle.py`, `metrics.py`) must not import `homeassistant`.
- Missing values stay `None`; never `0`, `""` or `False` unless TED states them. Non-positive monetary amounts (TED uses `-1` for "not disclosed") are `None` (D20, defined in Task 2).
- Cross-currency sums use ECB reference rates for the event date with backwards fallback; unconvertible amounts reduce coverage (plan §10, D11).
- Safe page size `min(250, 10000 // (len(fields) + 1))` (D1). Requests paced ≥ 0.5 s apart; 429/5xx retried with exponential backoff, max 4 attempts (D9).
- Country codes: alpha-2 inside the integration, alpha-3 on the wire (D2).
- Stage from `form-type`; change notices keep the family stage and carry `ChangeInfo` (D3). All `(notice_id, notice_version)` pairs are stored (D4).
- Central-purchasing exclusion happens in metrics, never in ingestion (D5).
- Ruff: `select = ["E","F","I","UP","B","SIM","RUF","ASYNC"]`, line length 88, target `py314`. `mypy --strict` for `custom_components/edp_radar`.
- Commit after every task with a conventional-commit message ending in the attribution line `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.
- Run `uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components/edp_radar` before each commit; fix what it reports.

---

## File structure (this plan)

| File | Responsibility |
| --- | --- |
| `pyproject.toml` | Project metadata, dev dependency group, pytest/ruff/mypy config |
| `custom_components/edp_radar/__init__.py` | Package docstring only (HA setup comes in Plan 2) |
| `custom_components/edp_radar/const.py` | Domain, URLs, defaults, config keys, thresholds, country tables |
| `custom_components/edp_radar/models.py` | Frozen dataclasses + JSON round-trip |
| `custom_components/edp_radar/query.py` | `TedQueryBuilder` |
| `custom_components/edp_radar/taxonomy.py` + `data/defence_cpv.json` + `data/strategic_categories.json` | Relevance signals and strategic-category classification |
| `custom_components/edp_radar/normalizer.py` | Raw TED dict → `ProcurementNotice` |
| `custom_components/edp_radar/api.py` | `TedApiClient` (aiohttp, pacing, retries, iteration) |
| `custom_components/edp_radar/fx_rates.py` | `FxRateTable`, ECB parsers, fixed euro rates |
| `custom_components/edp_radar/fx.py` | `EcbFxClient` (aiohttp) |
| `custom_components/edp_radar/lifecycle.py` | `ProcedureIndex`, `ProcedureSummary` |
| `custom_components/edp_radar/metrics.py` | Pure metrics → `RadarSnapshot`, event attribute builder, watchlist matcher |
| `custom_components/edp_radar/storage.py` | `RadarStore` over HA `Store` (monthly partitions, index, fx, event keys) |
| `scripts/fetch_fixture_notices.py` | Re-fetches the real fixture notices by publication number |
| `scripts/data_profile.py` | Phase 0 harness → `docs/data-profile.md` |
| `tests/conftest.py`, `tests/factories.py` | Shared fixtures and builders |
| `tests/fixtures/ted/real_notices.json` | 18 real notices (see Task 6) |
| `tests/fixtures/ecb/*.xml`, `*.csv` | ECB samples |
| `tests/test_*.py` | One test module per source module |

---

### Task 1: Project scaffolding and tooling

**Files:**
- Modify: `pyproject.toml`
- Create: `.python-version`, `.gitignore`, `custom_components/edp_radar/__init__.py`, `custom_components/edp_radar/const.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/test_const.py`

**Interfaces:**
- Produces: `const.DOMAIN`, `const.RelevanceMode`, `const.to_alpha3(code: str) -> str`, `const.to_alpha2(code: str) -> str`, `const.EU_COUNTRIES`, `const.NORDIC_COUNTRIES`, `const.TED_COUNTRIES` (all alpha-2 frozensets), match-reason constants, default constants listed below.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "ha-edp-radar"
version = "0.1.0"
description = "Home Assistant custom integration: European Defence Procurement Radar (TED + ECB)"
requires-python = ">=3.14.2"
dependencies = []

[dependency-groups]
dev = [
    "homeassistant==2026.9.2",
    "pytest-homeassistant-custom-component==0.13.365",
    "ruff>=0.12",
    "mypy>=1.14",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
target-version = "py314"
line-length = 88
extend-exclude = ["dev/config"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF", "ASYNC"]
ignore = ["RUF001", "RUF002", "RUF003"]

[tool.ruff.lint.isort]
known-first-party = ["custom_components.edp_radar"]

[tool.mypy]
python_version = "3.14"
strict = true
warn_unreachable = true
files = ["custom_components/edp_radar"]

[[tool.mypy.overrides]]
module = ["homeassistant.*", "voluptuous.*"]
ignore_missing_imports = true
```

- [ ] **Step 2: Write `.python-version`, `.gitignore`**

`.python-version`:

```text
3.14
```

`.gitignore`:

```text
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.mypy_cache/
.env

# Home Assistant dev config: keep only configuration.yaml
dev/config/*
!dev/config/configuration.yaml

# data-profile cache
.cache/
```

- [ ] **Step 3: Write the package init and `const.py`**

`custom_components/edp_radar/__init__.py`:

```python
"""European Defence Procurement Radar for Home Assistant."""
```

`custom_components/edp_radar/const.py`:

```python
"""Constants for the European Defence Procurement Radar integration."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from enum import StrEnum

DOMAIN = "edp_radar"
NAME = "European Defence Procurement Radar"
MANUFACTURER = "TED / Publications Office of the European Union"
MODEL = "EDP Radar Analytics"

TED_API_BASE_URL = "https://api.ted.europa.eu/v3"
TED_NOTICE_URL = "https://ted.europa.eu/en/notice/-/detail/{publication_number}"
ECB_DAILY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
ECB_90D_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
ECB_HISTORY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"

DEFAULT_UPDATE_INTERVAL = timedelta(hours=4)
DEFAULT_RETENTION_DAYS = 400
DEFAULT_BOOTSTRAP_DAYS = 400
INCREMENTAL_OVERLAP_DAYS = 2
FRESH_CACHE_MAX_AGE = timedelta(hours=1)

# TED API limits (verified 2026-09-12, addendum D1/D9)
TED_MAX_PAGE_SIZE = 250
TED_MAX_FIELDS_PER_PAGE = 10_000
TED_PAGE_NUMBER_CEILING = 15_000
TED_MIN_REQUEST_INTERVAL = 0.5
TED_MAX_ATTEMPTS = 4

# Relevance signals (plan §5–6)
DEFENCE_ACTIVITY_CODE = "defence"
DEFENCE_LEGAL_BASIS_CODE = "32009L0081"
MATCH_DEFENCE_BUYER = "defence_buyer"
MATCH_DEFENCE_LEGAL_BASIS = "defence_legal_basis"
MATCH_DEFENCE_CPV = "defence_cpv"

# Metric thresholds (plan §16.3, addendum D5)
CENTRAL_PURCHASING_BUYER_THRESHOLD = 10
GROWTH_MIN_PROCEDURES = 5
GROWTH_MIN_VALUE_EUR = Decimal("50000000")
RANKING_LIMIT = 10
RECENT_ITEMS_LIMIT = 10
TITLE_MAX_LENGTH = 200
EMITTED_EVENT_KEYS_LIMIT = 5000

# Config / options keys
CONF_RELEVANCE_MODE = "relevance_mode"
CONF_MARKET_PRESET = "market_preset"
CONF_MARKET_COUNTRIES = "market_countries"
CONF_OWN_ORGANISATION = "own_organisation"
CONF_OWN_IDENTIFIERS = "identifiers"
CONF_OWN_COUNTRY = "country"
CONF_OWN_NAME = "canonical_name"
CONF_OWN_ALIASES = "aliases"
CONF_PEER_PRESET = "peer_preset"
CONF_PEER_COUNTRIES = "peer_countries"
CONF_PEER_ORGANISATIONS = "peer_organisations"
CONF_SELECTED_COUNTRY = "selected_country"
CONF_PINNED_CATEGORIES = "pinned_categories"
CONF_WATCHLIST_COUNTRIES = "watchlist_countries"
CONF_WATCHLIST_BUYERS = "watchlist_buyers"
CONF_WATCHLIST_CATEGORIES = "watchlist_categories"
CONF_WATCHLIST_MIN_ESTIMATED_EUR = "watchlist_min_estimated_eur"
CONF_WATCHLIST_MIN_AWARD_EUR = "watchlist_min_award_eur"


class RelevanceMode(StrEnum):
    """Which defence signals define the procurement universe."""

    STRICT = "strict"
    BROAD = "broad"


class MarketPreset(StrEnum):
    """Country universe presets."""

    EU = "eu"
    NORDIC = "nordic"
    TED = "ted"
    CUSTOM = "custom"


# ISO 3166-1 alpha-2 -> alpha-3 for the countries TED publishes (D2).
ALPHA2_TO_ALPHA3: dict[str, str] = {
    "AT": "AUT", "BE": "BEL", "BG": "BGR", "HR": "HRV", "CY": "CYP", "CZ": "CZE",
    "DK": "DNK", "EE": "EST", "FI": "FIN", "FR": "FRA", "DE": "DEU", "GR": "GRC",
    "HU": "HUN", "IE": "IRL", "IT": "ITA", "LV": "LVA", "LT": "LTU", "LU": "LUX",
    "MT": "MLT", "NL": "NLD", "PL": "POL", "PT": "PRT", "RO": "ROU", "SK": "SVK",
    "SI": "SVN", "ES": "ESP", "SE": "SWE",
    "NO": "NOR", "IS": "ISL", "LI": "LIE", "CH": "CHE", "GB": "GBR", "UA": "UKR",
    "MD": "MDA", "RS": "SRB", "ME": "MNE", "MK": "MKD", "AL": "ALB", "BA": "BIH",
    "TR": "TUR", "XK": "XKX", "GE": "GEO",
}
ALPHA3_TO_ALPHA2: dict[str, str] = {v: k for k, v in ALPHA2_TO_ALPHA3.items()}

EU_COUNTRIES: frozenset[str] = frozenset(
    {
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
        "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
        "SI", "ES", "SE",
    }
)
NORDIC_COUNTRIES: frozenset[str] = frozenset({"SE", "FI", "DK", "NO", "IS"})
TED_COUNTRIES: frozenset[str] = EU_COUNTRIES | frozenset({"NO", "IS", "LI", "CH"})

MARKET_PRESET_COUNTRIES: dict[MarketPreset, frozenset[str]] = {
    MarketPreset.EU: EU_COUNTRIES,
    MarketPreset.NORDIC: NORDIC_COUNTRIES,
    MarketPreset.TED: TED_COUNTRIES,
}


def to_alpha3(code: str) -> str:
    """Return the alpha-3 code for an alpha-2 code (unknown codes pass through)."""
    return ALPHA2_TO_ALPHA3.get(code.upper(), code.upper())


def to_alpha2(code: str) -> str:
    """Return the alpha-2 code for an alpha-3 code (unknown codes pass through)."""
    return ALPHA3_TO_ALPHA2.get(code.upper(), code.upper())
```

- [ ] **Step 4: Write `tests/__init__.py` (empty), `tests/conftest.py` and the first test**

`tests/conftest.py`:

```python
"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def real_notices() -> list[dict[str, Any]]:
    """Real TED notices captured on 2026-09-12 (see scripts/fetch_fixture_notices.py)."""
    return json.loads((FIXTURES / "ted" / "real_notices.json").read_text())


@pytest.fixture
def real_notice(real_notices: list[dict[str, Any]]):
    """Return a lookup by publication number."""
    by_number = {n["publication-number"]: n for n in real_notices}

    def _get(publication_number: str) -> dict[str, Any]:
        return json.loads(json.dumps(by_number[publication_number]))

    return _get
```

`tests/test_const.py`:

```python
from custom_components.edp_radar.const import (
    EU_COUNTRIES,
    NORDIC_COUNTRIES,
    TED_COUNTRIES,
    to_alpha2,
    to_alpha3,
)


def test_alpha_round_trip() -> None:
    assert to_alpha3("SE") == "SWE"
    assert to_alpha2("SWE") == "SE"
    assert to_alpha3("se") == "SWE"


def test_unknown_codes_pass_through() -> None:
    assert to_alpha2("XXX") == "XXX"
    assert to_alpha3("ZZ") == "ZZ"


def test_country_sets() -> None:
    assert len(EU_COUNTRIES) == 27
    assert NORDIC_COUNTRIES == {"SE", "FI", "DK", "NO", "IS"}
    assert EU_COUNTRIES < TED_COUNTRIES
    for code in TED_COUNTRIES:
        assert to_alpha2(to_alpha3(code)) == code
```

- [ ] **Step 5: Install and run**

Run: `uv sync --group dev && uv run pytest tests/test_const.py -v`
Expected: 3 passed.

Run: `uv run ruff check . && uv run ruff format . && uv run mypy custom_components/edp_radar`
Expected: no errors (format may rewrite files; that is fine).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .python-version .gitignore custom_components tests
git commit -m "chore: scaffold project, tooling and constants

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Typed models with JSON round-trip

**Files:**
- Create: `custom_components/edp_radar/models.py`, `tests/test_models.py`

**Interfaces:**
- Produces (all `@dataclass(frozen=True, slots=True)` unless noted):
  - `class NoticeStage(StrEnum)`: `PLANNING="planning"`, `COMPETITION="competition"`, `RESULT="result"`, `DIRECT_AWARD="direct_award"`, `MODIFICATION="modification"`, `COMPLETION="completion"`, `OTHER="other"`.
  - `Money(amount: Decimal, currency: str)`; `Money.parse(amount: str | int | float | None, currency: str | None) -> Money | None` returns `None` unless `amount > 0` and currency is a 3-letter code (D20).
  - `Buyer(name, identifiers: tuple[str, ...], country: str | None, legal_type, main_activities: tuple[str, ...], count: int)`.
  - `Winner(name, identifier, country, size)`; `Winner.identity_key -> str` = identifier if set else `f"{country or '??'}:{normalized name}"`.
  - `SubmissionStatistic(type_code: str, value: int)`; `TenderStatistics(statistics, selection_statuses, non_award_justifications, decision_dates)` with `tender_counts -> tuple[int, ...]` (values where `type_code == "tenders"`).
  - `ChangeInfo(reason_code, description, changed_notice_id)`; `ModificationInfo(description, justifications: tuple[str, ...], previous_notice_ids: tuple[str, ...])`.
  - `ProcurementNotice(...)` fields listed in the code; properties `is_change`, `version_key` (`f"{notice_id}:{notice_version}"`), `award_date` (first decision date else publication date).
  - `to_dict()` / `from_dict()` on `ProcurementNotice`.
  - `normalize_name(name: str) -> str` (casefold, collapse whitespace, strip punctuation).

- [ ] **Step 1: Write the failing tests**

`tests/test_models.py`:

```python
from datetime import date
from decimal import Decimal

from custom_components.edp_radar.models import (
    Buyer,
    ChangeInfo,
    Money,
    NoticeStage,
    ProcurementNotice,
    SubmissionStatistic,
    TenderStatistics,
    Winner,
    normalize_name,
)


def test_money_parse_rejects_missing_and_sentinels() -> None:
    assert Money.parse(None, "EUR") is None
    assert Money.parse("100", None) is None
    assert Money.parse("-1", "EUR") is None
    assert Money.parse("0", "EUR") is None
    assert Money.parse("abc", "EUR") is None
    assert Money.parse("1475225.00", "eur") == Money(Decimal("1475225.00"), "EUR")


def test_tender_counts_only_uses_tenders_code() -> None:
    stats = TenderStatistics(
        statistics=(
            SubmissionStatistic("tenders", 3),
            SubmissionStatistic("t-sme", 2),
            SubmissionStatistic("part-req", 7),
            SubmissionStatistic("tenders", 1),
        ),
        selection_statuses=("selec-w", "selec-w"),
        non_award_justifications=(),
        decision_dates=(),
    )
    assert stats.tender_counts == (3, 1)


def test_winner_identity_key_prefers_identifier() -> None:
    assert Winner("Saab AB", "556036-0793", "SE", "large").identity_key == "556036-0793"
    assert Winner("Saab  AB", None, "SE", None).identity_key == "SE:saab ab"
    assert Winner("Saab AB", None, None, None).identity_key == "??:saab ab"


def test_normalize_name() -> None:
    assert normalize_name("  Försvarets  Materielverk, FMV. ") == "försvarets materielverk fmv"


def _notice(**overrides) -> ProcurementNotice:
    base = dict(
        notice_id="n1",
        notice_version=1,
        publication_number="1-2026",
        publication_date=date(2026, 9, 1),
        procedure_id="p1",
        stage=NoticeStage.COMPETITION,
        notice_type="cn-standard",
        notice_subtype="16",
        title="Title",
        buyer=Buyer("FMV", ("202100-0340",), "SE", "cga", ("defence",), 1),
        legal_basis=("32014L0024",),
        cpv_codes=("35300000",),
        match_reasons=frozenset({"defence_buyer"}),
        categories=("other_defence",),
        procedure_type="open",
        contract_nature=("supplies",),
        estimated_value=Money(Decimal("100"), "SEK"),
        result_value=None,
        tender_statistics=None,
        winners=(),
        change=None,
        modification=None,
        source_url="https://ted.europa.eu/en/notice/-/detail/1-2026",
    )
    base.update(overrides)
    return ProcurementNotice(**base)


def test_round_trip_preserves_everything() -> None:
    notice = _notice(
        result_value=Money(Decimal("55600000"), "DKK"),
        tender_statistics=TenderStatistics(
            (SubmissionStatistic("tenders", 3),),
            ("selec-w",),
            ("no-rece",),
            (date(2026, 7, 21),),
        ),
        winners=(Winner("Element Logic", "29847096", "DK", "sme"),),
        change=ChangeInfo("update-add", "Deadline moved", "abc"),
    )
    data = notice.to_dict()
    assert data["publication_date"] == "2026-09-01"
    assert data["estimated_value"] == {"amount": "100", "currency": "SEK"}
    assert ProcurementNotice.from_dict(data) == notice


def test_properties() -> None:
    plain = _notice()
    assert plain.is_change is False
    assert plain.version_key == "n1:1"
    assert plain.award_date == date(2026, 9, 1)
    changed = _notice(change=ChangeInfo("cor-buy", None, None))
    assert changed.is_change is True
    decided = _notice(
        stage=NoticeStage.RESULT,
        tender_statistics=TenderStatistics((), (), (), (date(2026, 7, 21),)),
    )
    assert decided.award_date == date(2026, 7, 21)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_models.py -v`
Expected: ImportError / ModuleNotFoundError for `custom_components.edp_radar.models`.

- [ ] **Step 3: Implement `models.py`**

```python
"""Normalized, Home-Assistant-independent domain models (plan §9, addendum D3/D4)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Self

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_name(name: str) -> str:
    """Casefold, strip punctuation and collapse whitespace for conservative matching."""
    return _WHITESPACE.sub(" ", _PUNCTUATION.sub("", name.casefold())).strip()


class NoticeStage(StrEnum):
    """Lifecycle family derived from the TED ``form-type`` (D3)."""

    PLANNING = "planning"
    COMPETITION = "competition"
    RESULT = "result"
    DIRECT_AWARD = "direct_award"
    MODIFICATION = "modification"
    COMPLETION = "completion"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class Money:
    """An amount in its original currency. EUR normalization happens in metrics."""

    amount: Decimal
    currency: str

    @classmethod
    def parse(cls, amount: str | int | float | None, currency: str | None) -> Money | None:
        """Return Money only for a positive amount with a 3-letter currency (D20)."""
        if amount is None or currency is None or len(currency) != 3:
            return None
        try:
            value = Decimal(str(amount))
        except InvalidOperation:
            return None
        if not value.is_finite() or value <= 0:
            return None
        return cls(value, currency.upper())

    def to_dict(self) -> dict[str, str]:
        return {"amount": str(self.amount), "currency": self.currency}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Money:
        return cls(Decimal(data["amount"]), data["currency"])


@dataclass(frozen=True, slots=True)
class Buyer:
    """Primary buyer plus notice-wide buyer facts (arrays are not aligned, D5)."""

    name: str | None
    identifiers: tuple[str, ...]
    country: str | None
    legal_type: str | None
    main_activities: tuple[str, ...]
    count: int


@dataclass(frozen=True, slots=True)
class Winner:
    name: str | None
    identifier: str | None
    country: str | None
    size: str | None

    @property
    def identity_key(self) -> str:
        """Conservative identity: stable identifier, else country + normalized name."""
        if self.identifier:
            return self.identifier
        return f"{self.country or '??'}:{normalize_name(self.name or '')}"


@dataclass(frozen=True, slots=True)
class SubmissionStatistic:
    type_code: str
    value: int


@dataclass(frozen=True, slots=True)
class TenderStatistics:
    statistics: tuple[SubmissionStatistic, ...]
    selection_statuses: tuple[str, ...]
    non_award_justifications: tuple[str, ...]
    decision_dates: tuple[date, ...]

    @property
    def tender_counts(self) -> tuple[int, ...]:
        """One entry per lot result whose statistic code is the total ``tenders`` (D7)."""
        return tuple(s.value for s in self.statistics if s.type_code == "tenders")


@dataclass(frozen=True, slots=True)
class ChangeInfo:
    reason_code: str | None
    description: str | None
    changed_notice_id: str | None


@dataclass(frozen=True, slots=True)
class ModificationInfo:
    description: str | None
    justifications: tuple[str, ...]
    previous_notice_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProcurementNotice:
    """One published notice version, normalized (plan §9)."""

    notice_id: str
    notice_version: int
    publication_number: str
    publication_date: date
    procedure_id: str | None
    stage: NoticeStage
    notice_type: str | None
    notice_subtype: str | None
    title: str | None
    buyer: Buyer
    legal_basis: tuple[str, ...]
    cpv_codes: tuple[str, ...]
    match_reasons: frozenset[str]
    categories: tuple[str, ...]
    procedure_type: str | None
    contract_nature: tuple[str, ...]
    estimated_value: Money | None
    result_value: Money | None
    tender_statistics: TenderStatistics | None
    winners: tuple[Winner, ...]
    change: ChangeInfo | None
    modification: ModificationInfo | None
    source_url: str | None
    classification_rule_version: str | None = field(default=None)

    @property
    def is_change(self) -> bool:
        return self.change is not None

    @property
    def version_key(self) -> str:
        return f"{self.notice_id}:{self.notice_version}"

    @property
    def award_date(self) -> date:
        """Date used for FX normalization of result values (plan §10)."""
        if self.tender_statistics and self.tender_statistics.decision_dates:
            return min(self.tender_statistics.decision_dates)
        return self.publication_date

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["publication_date"] = self.publication_date.isoformat()
        data["stage"] = self.stage.value
        data["match_reasons"] = sorted(self.match_reasons)
        data["estimated_value"] = self.estimated_value.to_dict() if self.estimated_value else None
        data["result_value"] = self.result_value.to_dict() if self.result_value else None
        if self.tender_statistics:
            data["tender_statistics"]["decision_dates"] = [
                d.isoformat() for d in self.tender_statistics.decision_dates
            ]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        kwargs: dict[str, Any] = {f.name: data.get(f.name) for f in fields(cls)}
        kwargs["publication_date"] = date.fromisoformat(data["publication_date"])
        kwargs["stage"] = NoticeStage(data["stage"])
        kwargs["buyer"] = Buyer(
            name=data["buyer"]["name"],
            identifiers=tuple(data["buyer"]["identifiers"]),
            country=data["buyer"]["country"],
            legal_type=data["buyer"]["legal_type"],
            main_activities=tuple(data["buyer"]["main_activities"]),
            count=data["buyer"]["count"],
        )
        kwargs["legal_basis"] = tuple(data["legal_basis"])
        kwargs["cpv_codes"] = tuple(data["cpv_codes"])
        kwargs["match_reasons"] = frozenset(data["match_reasons"])
        kwargs["categories"] = tuple(data["categories"])
        kwargs["contract_nature"] = tuple(data["contract_nature"])
        kwargs["estimated_value"] = (
            Money.from_dict(data["estimated_value"]) if data.get("estimated_value") else None
        )
        kwargs["result_value"] = (
            Money.from_dict(data["result_value"]) if data.get("result_value") else None
        )
        ts = data.get("tender_statistics")
        kwargs["tender_statistics"] = (
            TenderStatistics(
                statistics=tuple(SubmissionStatistic(**s) for s in ts["statistics"]),
                selection_statuses=tuple(ts["selection_statuses"]),
                non_award_justifications=tuple(ts["non_award_justifications"]),
                decision_dates=tuple(date.fromisoformat(d) for d in ts["decision_dates"]),
            )
            if ts
            else None
        )
        kwargs["winners"] = tuple(Winner(**w) for w in data.get("winners") or ())
        change = data.get("change")
        kwargs["change"] = ChangeInfo(**change) if change else None
        modification = data.get("modification")
        kwargs["modification"] = (
            ModificationInfo(
                description=modification["description"],
                justifications=tuple(modification["justifications"]),
                previous_notice_ids=tuple(modification["previous_notice_ids"]),
            )
            if modification
            else None
        )
        return cls(**kwargs)
```

- [ ] **Step 4: Run tests, lint, type-check**

Run: `uv run pytest tests/test_models.py -v && uv run ruff check . && uv run mypy custom_components/edp_radar`
Expected: 6 passed, no lint/type errors.

- [ ] **Step 5: Commit**

```bash
git add custom_components/edp_radar/models.py tests/test_models.py
git commit -m "feat(models): add normalized procurement models with JSON round-trip

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: TED query builder

**Files:**
- Create: `custom_components/edp_radar/query.py`, `tests/test_query.py`

**Interfaces:**
- Produces `class TedQueryBuilder` with static methods, all returning `str`:
  - `defence_universe(mode: RelevanceMode, cpv_prefixes: Sequence[str]) -> str`
  - `publication_range(start: date, end: date | None = None) -> str` → `PD>=20250809 AND PD<=20260912`
  - `countries(alpha2: Iterable[str]) -> str` → `buyer-country IN (SWE FIN)` (sorted, alpha-3)
  - `buyer_identifiers(identifiers: Iterable[str]) -> str` → `buyer-identifier IN ("202100-0340")`
  - `buyer_name_search(term: str) -> str` → `buyer-name ~ ("försvar*")`
  - `publication_number(number: str) -> str` → `ND="626136-2026"`
  - `combine_and(*parts: str) -> str`, `combine_or(*parts: str) -> str` (skip empty parts, parenthesize each part that contains a space)
  - `sort_by_publication_date(query: str, *, descending: bool = True) -> str`
  - `quote(value: str) -> str` (escapes `\` and `"`)
  - `ted_date(d: date) -> str` → `yyyymmdd`

- [ ] **Step 1: Write the failing tests**

`tests/test_query.py`:

```python
from datetime import date

from custom_components.edp_radar.const import RelevanceMode
from custom_components.edp_radar.query import TedQueryBuilder as Q


def test_strict_universe() -> None:
    assert (
        Q.defence_universe(RelevanceMode.STRICT, ["353", "354"])
        == "(authority-main-activity=defence OR legal-basis=32009L0081)"
    )


def test_broad_universe_adds_cpv_prefixes_as_wildcards() -> None:
    assert Q.defence_universe(RelevanceMode.BROAD, ["353", "35811300"]) == (
        "(authority-main-activity=defence OR legal-basis=32009L0081"
        " OR classification-cpv IN (353* 35811300*))"
    )


def test_publication_range() -> None:
    assert Q.publication_range(date(2025, 8, 9)) == "PD>=20250809"
    assert (
        Q.publication_range(date(2025, 8, 9), date(2026, 9, 12))
        == "(PD>=20250809 AND PD<=20260912)"
    )


def test_countries_use_alpha3_sorted() -> None:
    assert Q.countries(["FI", "SE"]) == "buyer-country IN (FIN SWE)"
    assert Q.countries([]) == ""


def test_buyer_filters_are_quoted_and_escaped() -> None:
    assert Q.buyer_identifiers(["202100-0340"]) == 'buyer-identifier IN ("202100-0340")'
    assert Q.buyer_identifiers(['Leitweg-ID: 991"x']) == (
        'buyer-identifier IN ("Leitweg-ID: 991\\"x")'
    )
    assert Q.buyer_name_search("försvar") == 'buyer-name ~ ("försvar*")'
    assert Q.buyer_name_search(' Försvarets "materiel" ') == (
        'buyer-name ~ ("Försvarets \\"materiel\\"*")'
    )
    assert Q.publication_number("626136-2026") == 'ND="626136-2026"'


def test_combinators_skip_empty_and_keep_precedence() -> None:
    assert Q.combine_and("PD>=20250809", "", "buyer-country IN (SWE)") == (
        "PD>=20250809 AND (buyer-country IN (SWE))"
    )
    assert Q.combine_or("a=1", "b=2") == "(a=1 OR b=2)"
    assert Q.combine_and("a=1") == "a=1"
    assert Q.combine_and() == ""


def test_full_bootstrap_query_shape() -> None:
    query = Q.sort_by_publication_date(
        Q.combine_and(
            Q.publication_range(date(2025, 8, 9)),
            Q.defence_universe(RelevanceMode.STRICT, []),
            Q.countries(["SE", "FI"]),
        )
    )
    assert query == (
        "PD>=20250809 AND (authority-main-activity=defence OR legal-basis=32009L0081)"
        " AND (buyer-country IN (FIN SWE)) SORT BY publication-date DESC"
    )
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_query.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `query.py`**

```python
"""Expert-search query builder for the TED Search API (plan §36, addendum §1)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from .const import (
    DEFENCE_ACTIVITY_CODE,
    DEFENCE_LEGAL_BASIS_CODE,
    RelevanceMode,
    to_alpha3,
)


class TedQueryBuilder:
    """Compose TED expert-search fragments. All methods are pure and return strings."""

    @staticmethod
    def quote(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    @staticmethod
    def ted_date(d: date) -> str:
        return d.strftime("%Y%m%d")

    @staticmethod
    def _group(part: str) -> str:
        if " " in part and not (part.startswith("(") and part.endswith(")")):
            return f"({part})"
        return part

    @classmethod
    def combine_and(cls, *parts: str) -> str:
        kept = [cls._group(p) for p in parts if p]
        return " AND ".join(kept)

    @classmethod
    def combine_or(cls, *parts: str) -> str:
        kept = [p for p in parts if p]
        if not kept:
            return ""
        if len(kept) == 1:
            return kept[0]
        return "(" + " OR ".join(kept) + ")"

    @classmethod
    def defence_universe(cls, mode: RelevanceMode, cpv_prefixes: Sequence[str]) -> str:
        signals = [
            f"authority-main-activity={DEFENCE_ACTIVITY_CODE}",
            f"legal-basis={DEFENCE_LEGAL_BASIS_CODE}",
        ]
        if mode is RelevanceMode.BROAD and cpv_prefixes:
            wildcards = " ".join(f"{p}*" for p in cpv_prefixes)
            signals.append(f"classification-cpv IN ({wildcards})")
        return "(" + " OR ".join(signals) + ")"

    @classmethod
    def publication_range(cls, start: date, end: date | None = None) -> str:
        lower = f"PD>={cls.ted_date(start)}"
        if end is None:
            return lower
        return f"({lower} AND PD<={cls.ted_date(end)})"

    @staticmethod
    def countries(alpha2: Iterable[str]) -> str:
        codes = sorted({to_alpha3(c) for c in alpha2})
        if not codes:
            return ""
        return f"buyer-country IN ({' '.join(codes)})"

    @classmethod
    def buyer_identifiers(cls, identifiers: Iterable[str]) -> str:
        quoted = [cls.quote(i) for i in identifiers if i]
        if not quoted:
            return ""
        return f"buyer-identifier IN ({' '.join(quoted)})"

    @classmethod
    def buyer_name_search(cls, term: str) -> str:
        return f"buyer-name ~ ({cls.quote(term.strip() + '*')})"

    @classmethod
    def publication_number(cls, number: str) -> str:
        return f"ND={cls.quote(number)}"

    @staticmethod
    def sort_by_publication_date(query: str, *, descending: bool = True) -> str:
        direction = "DESC" if descending else "ASC"
        return f"{query} SORT BY publication-date {direction}"
```

- [ ] **Step 4: Run tests, lint, type-check**

Run: `uv run pytest tests/test_query.py -v && uv run ruff check . && uv run mypy custom_components/edp_radar`
Expected: 7 passed.

- [ ] **Step 5: Verify the produced syntax against the live API once** (no test; a one-off check)

Run:

```bash
uv run python - <<'EOF'
import asyncio, json, aiohttp
from datetime import date
from custom_components.edp_radar.const import RelevanceMode
from custom_components.edp_radar.query import TedQueryBuilder as Q
queries = [
    Q.combine_and(Q.publication_range(date(2026, 6, 14)), Q.defence_universe(RelevanceMode.STRICT, []), Q.countries(["SE", "FI"])),
    Q.combine_and(Q.publication_range(date(2026, 6, 14)), Q.defence_universe(RelevanceMode.BROAD, ["353", "354", "355", "356", "357"])),
    Q.combine_and(Q.publication_range(date(2025, 8, 9)), Q.buyer_name_search("försvarets materiel"), Q.countries(["SE"])),
    Q.combine_and(Q.publication_range(date(2025, 8, 9)), Q.buyer_identifiers(["202100-0340", "Leitweg-ID: 991-00606-79"])),
    Q.publication_number("626136-2026"),
]
async def main():
    async with aiohttp.ClientSession() as s:
        for q in queries:
            async with s.post("https://api.ted.europa.eu/v3/notices/search", json={"query": q, "fields": ["publication-number"], "limit": 1, "checkQuerySyntax": True}) as r:
                print(r.status, q[:90], (await r.text())[:120])
            await asyncio.sleep(1)
asyncio.run(main())
EOF
```

Expected: every line starts with `200`. If a line returns 400, adjust the builder (and its test) to the syntax the error message describes before continuing.

- [ ] **Step 6: Commit**

```bash
git add custom_components/edp_radar/query.py tests/test_query.py
git commit -m "feat(query): add TED expert-search query builder

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Defence taxonomy and strategic categories

**Files:**
- Create: `custom_components/edp_radar/data/defence_cpv.json`, `custom_components/edp_radar/data/strategic_categories.json`, `custom_components/edp_radar/taxonomy.py`, `tests/test_taxonomy.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class CategoryRule(category_id: str, label: str, cpv_prefixes: tuple[str, ...])`
  - `@dataclass(frozen=True) class Taxonomy(version: str, defence_cpv_prefixes: tuple[str, ...], rules: tuple[CategoryRule, ...])`
    - `Taxonomy.load() -> Taxonomy` (reads both JSON files from the package `data/` directory; cached with `functools.cache`)
    - `normalize_cpv(code: str) -> str | None` (module function: strips a `-N` check digit, keeps 8 digits, else `None`)
    - `is_defence_cpv(self, code: str) -> bool`
    - `match_reasons(self, *, activities: Iterable[str], legal_basis: Iterable[str], cpv_codes: Iterable[str]) -> frozenset[str]` (all signals, independent of mode)
    - `is_relevant(self, reasons: frozenset[str], mode: RelevanceMode) -> bool`
    - `classify(self, cpv_codes: Iterable[str]) -> tuple[str, ...]` (sorted unique category ids; longest matching prefix wins per code)
    - `category_ids -> tuple[str, ...]`, `label(category_id) -> str`

- [ ] **Step 1: Write the data files**

`custom_components/edp_radar/data/defence_cpv.json`:

```json
{
  "version": "2026.09.1",
  "description": "CPV prefixes that identify defence-specific procurement (plan §5.3). Prefix matching on the 8-digit CPV code. Deliberately excludes CPV 351* (emergency/security equipment), 352* (police equipment) and generic 358* support equipment.",
  "prefixes": [
    {"prefix": "353", "label": "Weapons, ammunition and associated parts"},
    {"prefix": "354", "label": "Military vehicles and associated parts"},
    {"prefix": "355", "label": "Warships and associated parts"},
    {"prefix": "356", "label": "Military aircraft, missiles and spacecraft"},
    {"prefix": "357", "label": "Military electronic systems"},
    {"prefix": "35811300", "label": "Military uniforms"},
    {"prefix": "35812", "label": "Combat uniforms"},
    {"prefix": "35813", "label": "Military helmets"},
    {"prefix": "246", "label": "Explosives"},
    {"prefix": "734", "label": "R&D services on security and defence materials"},
    {"prefix": "7522", "label": "Defence services"},
    {"prefix": "806", "label": "Training services for defence and security materials"},
    {"prefix": "5062", "label": "Repair and maintenance of firearms and ammunition"},
    {"prefix": "5063", "label": "Repair and maintenance of military vehicles"},
    {"prefix": "5064", "label": "Repair and maintenance of warships"},
    {"prefix": "5065", "label": "Repair and maintenance of military aircraft, missiles and spacecraft"},
    {"prefix": "5066", "label": "Repair and maintenance of military electronic systems"}
  ]
}
```

`custom_components/edp_radar/data/strategic_categories.json`:

```json
{
  "version": "2026.09.1",
  "description": "Deterministic CPV-prefix rules (plan §14, phase 1). A CPV code is assigned to the category owning the longest matching prefix. A notice may belong to several categories. Codes matching no rule are unclassified.",
  "categories": [
    {"id": "air_missile_defence", "label": "Air & missile defence", "cpv_prefixes": ["3562", "35322100"]},
    {"id": "ammunition_explosives", "label": "Ammunition & explosives", "cpv_prefixes": ["3533", "246"]},
    {"id": "land_systems", "label": "Land systems", "cpv_prefixes": ["3531", "3532", "3534", "354", "5062", "5063"]},
    {"id": "naval_maritime", "label": "Naval & maritime", "cpv_prefixes": ["355", "5064"]},
    {"id": "air_systems", "label": "Air systems", "cpv_prefixes": ["3561", "3564", "5065"]},
    {"id": "uas_cuas", "label": "UAS / C-UAS", "cpv_prefixes": ["35612"]},
    {"id": "c4isr_communications", "label": "C4ISR & communications", "cpv_prefixes": ["3571", "5066", "32"]},
    {"id": "sensors_radar_ew", "label": "Sensors, radar & electronic warfare", "cpv_prefixes": ["3572", "3573", "38115"]},
    {"id": "cyber_it", "label": "Cyber & IT", "cpv_prefixes": ["72", "48", "302"]},
    {"id": "space", "label": "Space", "cpv_prefixes": ["3563"]},
    {"id": "logistics_support", "label": "Logistics & support", "cpv_prefixes": ["358", "60", "63", "09", "15", "18", "501", "341", "342", "343"]},
    {"id": "defence_rd", "label": "Defence R&D", "cpv_prefixes": ["73"]},
    {"id": "other_defence", "label": "Other defence", "cpv_prefixes": ["353", "7522", "806", "50600000"]}
  ]
}
```

- [ ] **Step 2: Write the failing tests**

`tests/test_taxonomy.py`:

```python
import json
from pathlib import Path

from custom_components.edp_radar.const import (
    MATCH_DEFENCE_BUYER,
    MATCH_DEFENCE_CPV,
    MATCH_DEFENCE_LEGAL_BASIS,
    RelevanceMode,
)
from custom_components.edp_radar.taxonomy import Taxonomy, normalize_cpv

DATA = Path("custom_components/edp_radar/data")


def test_normalize_cpv() -> None:
    assert normalize_cpv("35300000-7") == "35300000"
    assert normalize_cpv("35300000") == "35300000"
    assert normalize_cpv(" 353 ") is None
    assert normalize_cpv("abc") is None


def test_load_reads_versions_and_rules() -> None:
    tax = Taxonomy.load()
    assert tax.version == "2026.09.1"
    assert "353" in tax.defence_cpv_prefixes
    assert tax.label("uas_cuas") == "UAS / C-UAS"
    assert "other_defence" in tax.category_ids


def test_defence_cpv_excludes_police_and_fire() -> None:
    tax = Taxonomy.load()
    assert tax.is_defence_cpv("35330000") is True
    assert tax.is_defence_cpv("35811300-5") is True
    assert tax.is_defence_cpv("35110000") is False
    assert tax.is_defence_cpv("35200000") is False
    assert tax.is_defence_cpv("35815100") is False


def test_match_reasons_are_independent_signals() -> None:
    tax = Taxonomy.load()
    reasons = tax.match_reasons(
        activities=["gen-pub", "defence"],
        legal_basis=["32014L0024"],
        cpv_codes=["30125100"],
    )
    assert reasons == frozenset({MATCH_DEFENCE_BUYER})
    reasons = tax.match_reasons(
        activities=[], legal_basis=["32009L0081"], cpv_codes=["35330000", "15811000"]
    )
    assert reasons == frozenset({MATCH_DEFENCE_LEGAL_BASIS, MATCH_DEFENCE_CPV})
    assert tax.match_reasons(activities=["health"], legal_basis=[], cpv_codes=[]) == frozenset()


def test_is_relevant_depends_on_mode() -> None:
    tax = Taxonomy.load()
    cpv_only = frozenset({MATCH_DEFENCE_CPV})
    assert tax.is_relevant(cpv_only, RelevanceMode.STRICT) is False
    assert tax.is_relevant(cpv_only, RelevanceMode.BROAD) is True
    assert tax.is_relevant(frozenset({MATCH_DEFENCE_BUYER}), RelevanceMode.STRICT) is True
    assert tax.is_relevant(frozenset(), RelevanceMode.BROAD) is False


def test_classify_longest_prefix_and_multi_label() -> None:
    tax = Taxonomy.load()
    assert tax.classify(["35612000"]) == ("uas_cuas",)
    assert tax.classify(["35611100"]) == ("air_systems",)
    assert tax.classify(["35300000"]) == ("other_defence",)
    assert tax.classify(["35310000"]) == ("land_systems",)
    assert tax.classify(["72000000", "35620000", "72000000"]) == (
        "air_missile_defence",
        "cyber_it",
    )
    assert tax.classify(["45200000"]) == ()
    assert tax.classify(["not-a-cpv"]) == ()


def test_no_prefix_is_owned_by_two_categories() -> None:
    data = json.loads((DATA / "strategic_categories.json").read_text())
    seen: dict[str, str] = {}
    for cat in data["categories"]:
        for prefix in cat["cpv_prefixes"]:
            assert prefix not in seen, f"{prefix} in both {seen[prefix]} and {cat['id']}"
            seen[prefix] = cat["id"]
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_taxonomy.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `taxonomy.py`**

```python
"""Defence relevance signals and strategic-category classification (plan §5, §6, §14)."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from .const import (
    DEFENCE_ACTIVITY_CODE,
    DEFENCE_LEGAL_BASIS_CODE,
    MATCH_DEFENCE_BUYER,
    MATCH_DEFENCE_CPV,
    MATCH_DEFENCE_LEGAL_BASIS,
    RelevanceMode,
)

_DATA_DIR = Path(__file__).parent / "data"
_CPV = re.compile(r"^(\d{8})(?:-\d)?$")
STRICT_REASONS = frozenset({MATCH_DEFENCE_BUYER, MATCH_DEFENCE_LEGAL_BASIS})


def normalize_cpv(code: str) -> str | None:
    """Return the 8-digit CPV code without check digit, or None."""
    match = _CPV.match(code.strip())
    return match.group(1) if match else None


@dataclass(frozen=True)
class CategoryRule:
    category_id: str
    label: str
    cpv_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class Taxonomy:
    version: str
    defence_cpv_prefixes: tuple[str, ...]
    rules: tuple[CategoryRule, ...]

    @classmethod
    @cache
    def load(cls) -> Taxonomy:
        defence = json.loads((_DATA_DIR / "defence_cpv.json").read_text(encoding="utf-8"))
        categories = json.loads(
            (_DATA_DIR / "strategic_categories.json").read_text(encoding="utf-8")
        )
        rules = tuple(
            CategoryRule(c["id"], c["label"], tuple(c["cpv_prefixes"]))
            for c in categories["categories"]
        )
        version = f"{defence['version']}/{categories['version']}"
        return cls(version, tuple(p["prefix"] for p in defence["prefixes"]), rules)

    @property
    def category_ids(self) -> tuple[str, ...]:
        return tuple(r.category_id for r in self.rules)

    def label(self, category_id: str) -> str:
        for rule in self.rules:
            if rule.category_id == category_id:
                return rule.label
        return category_id

    def is_defence_cpv(self, code: str) -> bool:
        normalized = normalize_cpv(code)
        return normalized is not None and normalized.startswith(self.defence_cpv_prefixes)

    def match_reasons(
        self,
        *,
        activities: Iterable[str],
        legal_basis: Iterable[str],
        cpv_codes: Iterable[str],
    ) -> frozenset[str]:
        reasons: set[str] = set()
        if DEFENCE_ACTIVITY_CODE in set(activities):
            reasons.add(MATCH_DEFENCE_BUYER)
        if DEFENCE_LEGAL_BASIS_CODE in set(legal_basis):
            reasons.add(MATCH_DEFENCE_LEGAL_BASIS)
        if any(self.is_defence_cpv(code) for code in cpv_codes):
            reasons.add(MATCH_DEFENCE_CPV)
        return frozenset(reasons)

    @staticmethod
    def is_relevant(reasons: frozenset[str], mode: RelevanceMode) -> bool:
        if mode is RelevanceMode.STRICT:
            return bool(reasons & STRICT_REASONS)
        return bool(reasons)

    def classify(self, cpv_codes: Iterable[str]) -> tuple[str, ...]:
        """Assign each code to the category with the longest matching prefix."""
        categories: set[str] = set()
        for raw in cpv_codes:
            code = normalize_cpv(raw)
            if code is None:
                continue
            best: tuple[int, str] | None = None
            for rule in self.rules:
                for prefix in rule.cpv_prefixes:
                    if code.startswith(prefix) and (best is None or len(prefix) > best[0]):
                        best = (len(prefix), rule.category_id)
            if best is not None:
                categories.add(best[1])
        return tuple(sorted(categories))
```

- [ ] **Step 5: Run tests, lint, type-check**

Run: `uv run pytest tests/test_taxonomy.py -v && uv run ruff check . && uv run mypy custom_components/edp_radar`
Expected: 8 passed. (If mypy complains about stacking `@classmethod` and `@cache`, replace with a module-level `@cache def _load() -> Taxonomy` called by `Taxonomy.load()`.)

- [ ] **Step 6: Commit**

```bash
git add custom_components/edp_radar/data custom_components/edp_radar/taxonomy.py tests/test_taxonomy.py
git commit -m "feat(taxonomy): add versioned defence CPV taxonomy and strategic categories

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Real-notice fixtures

**Files:**
- Create: `scripts/__init__.py` (empty), `scripts/fetch_fixture_notices.py`, `tests/fixtures/ted/real_notices.json`

**Interfaces:**
- Produces the fixture file consumed by `real_notices`/`real_notice` fixtures (Task 1). Notices included, by publication number and the case they cover (plan §47):

| Publication number | Case |
| --- | --- |
| `626028-2026` | planning notice, no procedure id, legal basis 2009/81 only |
| `626977-2026` | competition, single lot, procedure-level EUR value, two buyer identifiers |
| `626146-2026` | competition, 3 lots with lot values, no procedure value, collapsed currency list |
| `626585-2026` | competition, procedure value and lot values both present |
| `626359-2026` | change notice as new notice id (v1) with `change-reason-code` |
| `626569-2026` | change notice as version 2, `change-description` |
| `628113-2026` | version 2 without change info |
| `626136-2026` | result, DKK, single winner, `tenders`=3, decision date |
| `627236-2026` | result, 14 lots, PLN, four winners, several `clos-nw`, non-award justifications |
| `627671-2026` | result fully non-awarded (`all-rej`) |
| `628418-2026` | result, two lots, `result-value-lot` = `-1` sentinels, single bid per lot, legal basis 2009/81 |
| `627391-2026` | result, single bid, nine submission codes including `part-req` |
| `626308-2026` | direct award (VEAT) |
| `619411-2026` | contract modification |
| `626862-2026` | result, SEK, Swedish buyer FOI, three lots all `clos-nw` |
| `613361-2026` | central purchasing body with >10 buyers, defence is one of many activities |
| `626208-2026` | result with two winner identifiers for one winner |
| `627092-2026` | result with two lots, two winners, tender values summing to notice value |

- [ ] **Step 1: Write the fetch script**

`scripts/fetch_fixture_notices.py`:

```python
"""Re-fetch the real TED notices used as test fixtures.

Usage: uv run python scripts/fetch_fixture_notices.py
Writes tests/fixtures/ted/real_notices.json. Long multilingual text is trimmed and
multi-buyer arrays are cut to 12 entries to keep the file small; nothing personal
is requested (organisation names and public identifiers only).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiohttp

from custom_components.edp_radar.api import TedApiClient
from custom_components.edp_radar.normalizer import REQUESTED_FIELDS
from custom_components.edp_radar.query import TedQueryBuilder as Q

PUBLICATION_NUMBERS = [
    "626028-2026", "626977-2026", "626146-2026", "626585-2026", "626359-2026",
    "626569-2026", "628113-2026", "626136-2026", "627236-2026", "627671-2026",
    "628418-2026", "627391-2026", "626308-2026", "619411-2026", "626862-2026",
    "613361-2026", "626208-2026", "627092-2026",
]
OUT = Path("tests/fixtures/ted/real_notices.json")
MULTI_BUYER_FIELDS = (
    "buyer-identifier", "buyer-country", "buyer-legal-type", "authority-main-activity"
)


def _trim(notice: dict) -> dict:
    notice["links"] = {"xml": {"MUL": notice["links"]["xml"]["MUL"]}}
    if notice.get("description-proc"):
        notice["description-proc"] = {
            k: (v[:200] + "…" if len(v) > 200 else v)
            for k, v in notice["description-proc"].items()
        }
    names = notice.get("buyer-name") or {}
    if any(len(v) > 12 for v in names.values()):
        notice["buyer-name"] = {k: v[:12] for k, v in names.items()}
        for field in MULTI_BUYER_FIELDS:
            if isinstance(notice.get(field), list):
                notice[field] = notice[field][:12]
    return notice


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        client = TedApiClient(session)
        notices = []
        for number in PUBLICATION_NUMBERS:
            async for raw in client.async_search_notices(
                Q.publication_number(number), REQUESTED_FIELDS
            ):
                notices.append(_trim(raw))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(notices, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(notices)} notices to {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
```

The script imports `api.py` and `normalizer.py`, which do not exist yet. For this task, create the fixture from the captured sample instead: copy `real_notices.json` produced during Phase 0 research (it is byte-identical to what the script produces) into `tests/fixtures/ted/real_notices.json`. If no captured sample is available, defer running this script to the end of Task 7 (after `api.py` and `normalizer.py` exist) and use the JSON snippets shown in Task 6 tests meanwhile.

- [ ] **Step 2: Verify the fixture loads**

Run: `uv run python -c "import json; d=json.load(open('tests/fixtures/ted/real_notices.json')); print(len(d), sorted(n['publication-number'] for n in d))"`
Expected: `18` and the list of numbers above.

- [ ] **Step 3: Commit**

```bash
git add scripts tests/fixtures/ted/real_notices.json
git commit -m "test: add real TED notice fixtures and fetch script

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Normalizer (raw TED dict → `ProcurementNotice`)

**Files:**
- Create: `custom_components/edp_radar/normalizer.py`, `tests/test_normalizer.py`

**Interfaces:**
- Consumes: `models.*`, `taxonomy.Taxonomy`, `const.to_alpha2`, `const.TED_NOTICE_URL`, `const.TITLE_MAX_LENGTH`.
- Produces:
  - `REQUESTED_FIELDS: tuple[str, ...]` (54 field names — the list in the code below; `description-proc` is deliberately not requested, D10).
  - `class NormalizationError(ValueError)`.
  - `normalize_notice(raw: Mapping[str, Any], taxonomy: Taxonomy) -> ProcurementNotice`.
  - `normalize_many(raws: Iterable[Mapping[str, Any]], taxonomy: Taxonomy) -> tuple[list[ProcurementNotice], int]` — second element is the number of skipped malformed notices (plan §43).
  - Helper functions used by the data-profile script: `first_text(value) -> str | None`, `as_strings(value) -> tuple[str, ...]`, `parse_ted_date(value) -> date | None`.

- [ ] **Step 1: Write the failing tests**

`tests/test_normalizer.py`:

```python
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from custom_components.edp_radar.const import (
    MATCH_DEFENCE_BUYER,
    MATCH_DEFENCE_CPV,
    MATCH_DEFENCE_LEGAL_BASIS,
)
from custom_components.edp_radar.models import Money, NoticeStage
from custom_components.edp_radar.normalizer import (
    REQUESTED_FIELDS,
    NormalizationError,
    as_strings,
    first_text,
    normalize_many,
    normalize_notice,
    parse_ted_date,
)
from custom_components.edp_radar.taxonomy import Taxonomy


@pytest.fixture
def taxonomy() -> Taxonomy:
    return Taxonomy.load()


def test_requested_fields_are_unique_and_exclude_descriptions() -> None:
    assert len(REQUESTED_FIELDS) == len(set(REQUESTED_FIELDS))
    assert "description-proc" not in REQUESTED_FIELDS
    assert "notice-identifier" in REQUESTED_FIELDS
    assert "change-notice-version-identifier" in REQUESTED_FIELDS


def test_helpers() -> None:
    assert first_text({"deu": "Titel"}) == "Titel"
    assert first_text({"swe": ["FMV"], "eng": ["FMV Ltd"]}) == "FMV Ltd"
    assert first_text(["a", "b"]) == "a"
    assert first_text(None) is None
    assert first_text("  ") is None
    assert as_strings(None) == ()
    assert as_strings("x") == ("x",)
    assert as_strings(["a", None, 1]) == ("a", "1")
    assert parse_ted_date("2026-09-11+02:00") == date(2026, 9, 11)
    assert parse_ted_date("2026-07-21Z") == date(2026, 7, 21)
    assert parse_ted_date("nonsense") is None


def test_competition_single_lot(real_notice, taxonomy: Taxonomy) -> None:
    notice = normalize_notice(real_notice("626977-2026"), taxonomy)
    assert notice.notice_id == "05bda7d3-9510-41db-81d2-0fa4e0eef464"
    assert notice.notice_version == 1
    assert notice.publication_number == "626977-2026"
    assert notice.publication_date == date(2026, 9, 11)
    assert notice.procedure_id == "df98839a-96e5-40e5-bfc8-165dc0c6e571"
    assert notice.stage is NoticeStage.COMPETITION
    assert notice.is_change is False
    assert notice.title.startswith("Suministro de dos grupos")
    assert notice.buyer.name == "Intendente de San Fernando"
    assert notice.buyer.identifiers == ("10000140000584", "S1115005I")
    assert notice.buyer.country == "ES"
    assert notice.buyer.count == 1
    assert notice.buyer.main_activities == ("defence",)
    assert notice.legal_basis == ("32014L0024",)
    assert notice.cpv_codes == ("31000000",)
    assert notice.match_reasons == frozenset({MATCH_DEFENCE_BUYER})
    assert notice.estimated_value == Money(Decimal("185000"), "EUR")
    assert notice.result_value is None
    assert notice.winners == ()
    assert notice.tender_statistics is None
    assert notice.source_url == "https://ted.europa.eu/en/notice/-/detail/626977-2026"
    assert notice.classification_rule_version == taxonomy.version


def test_lot_values_with_collapsed_currency_are_summed(real_notice, taxonomy) -> None:
    notice = normalize_notice(real_notice("626146-2026"), taxonomy)
    assert notice.estimated_value == Money(Decimal("647008.8"), "EUR")
    assert notice.categories == ("logistics_support",)


def test_procedure_value_wins_over_lot_values(real_notice, taxonomy) -> None:
    notice = normalize_notice(real_notice("626585-2026"), taxonomy)
    assert notice.estimated_value == Money(Decimal("339075"), "EUR")


def test_lot_values_with_ambiguous_currencies_are_unknown(real_notice, taxonomy) -> None:
    raw = real_notice("626146-2026")
    raw["estimated-value-cur-lot"] = ["EUR", "SEK"]
    assert normalize_notice(raw, taxonomy).estimated_value is None


def test_change_notice_as_new_id_and_as_new_version(real_notice, taxonomy) -> None:
    new_id = normalize_notice(real_notice("626359-2026"), taxonomy)
    assert new_id.stage is NoticeStage.COMPETITION
    assert new_id.is_change is True
    assert new_id.change is not None
    assert new_id.change.reason_code == "cor-buy"
    assert new_id.match_reasons == frozenset({MATCH_DEFENCE_LEGAL_BASIS})
    assert new_id.buyer.main_activities == ()

    v2 = normalize_notice(real_notice("626569-2026"), taxonomy)
    assert v2.notice_version == 2
    assert v2.is_change is True
    assert v2.change is not None
    assert v2.change.reason_code == "update-add"
    assert v2.change.description == "Modification de la date limite de réception des offres"
    assert v2.version_key.endswith(":2")

    plain_v2 = normalize_notice(real_notice("628113-2026"), taxonomy)
    assert plain_v2.notice_version == 2
    assert plain_v2.is_change is False


def test_result_single_winner(real_notice, taxonomy) -> None:
    notice = normalize_notice(real_notice("626136-2026"), taxonomy)
    assert notice.stage is NoticeStage.RESULT
    assert notice.result_value == Money(Decimal("55600000"), "DKK")
    assert notice.estimated_value == Money(Decimal("85000000"), "DKK")
    assert len(notice.winners) == 1
    winner = notice.winners[0]
    assert winner.identifier == "29847096"
    assert winner.country == "DK"
    assert winner.size == "sme"
    assert winner.name == "Element Logic Denmark A/S"
    assert notice.tender_statistics is not None
    assert notice.tender_statistics.tender_counts == (3,)
    assert notice.tender_statistics.selection_statuses == ("selec-w",)
    assert notice.tender_statistics.decision_dates == (date(2026, 7, 21),)
    assert notice.award_date == date(2026, 7, 21)


def test_result_multi_lot_statistics_and_non_awards(real_notice, taxonomy) -> None:
    notice = normalize_notice(real_notice("627236-2026"), taxonomy)
    assert notice.result_value == Money(Decimal("10306545.8"), "PLN")
    stats = notice.tender_statistics
    assert stats is not None
    assert len(stats.tender_counts) == 14
    assert stats.selection_statuses.count("clos-nw") == 5
    assert stats.selection_statuses.count("selec-w") == 9
    assert stats.non_award_justifications == ("no-rece",) * 5
    assert len(notice.winners) == 4
    assert all(w.identifier for w in notice.winners)
    # 35322100 → air & missile defence, 3534*/35322200 → land, 35813000 (358*) → logistics
    assert notice.categories == ("air_missile_defence", "land_systems", "logistics_support")
    assert notice.match_reasons == frozenset({MATCH_DEFENCE_BUYER, MATCH_DEFENCE_CPV})


def test_result_value_sentinel_minus_one_is_unknown(real_notice, taxonomy) -> None:
    notice = normalize_notice(real_notice("628418-2026"), taxonomy)
    assert notice.result_value is None
    assert notice.estimated_value == Money(Decimal("1149499.20"), "EUR")
    assert notice.tender_statistics is not None
    assert notice.tender_statistics.tender_counts == (1, 1)
    assert notice.match_reasons == frozenset({MATCH_DEFENCE_BUYER, MATCH_DEFENCE_LEGAL_BASIS, MATCH_DEFENCE_CPV})


def test_winner_with_two_identifiers_gets_no_identifier(real_notice, taxonomy) -> None:
    notice = normalize_notice(real_notice("626208-2026"), taxonomy)
    assert len(notice.winners) == 1
    assert notice.winners[0].identifier is None
    assert notice.winners[0].country == "SK"
    assert notice.winners[0].identity_key.startswith("SK:")


def test_other_stages(real_notice, taxonomy) -> None:
    assert normalize_notice(real_notice("626028-2026"), taxonomy).stage is NoticeStage.PLANNING
    assert normalize_notice(real_notice("626028-2026"), taxonomy).procedure_id is None
    assert normalize_notice(real_notice("626308-2026"), taxonomy).stage is NoticeStage.DIRECT_AWARD
    modification = normalize_notice(real_notice("619411-2026"), taxonomy)
    assert modification.stage is NoticeStage.MODIFICATION
    assert modification.modification is not None
    assert modification.modification.justifications == ("add-wss",)
    assert modification.modification.previous_notice_ids == ("291876-2024",)


def test_unknown_form_type_is_other(real_notice, taxonomy) -> None:
    raw = real_notice("626977-2026")
    raw["form-type"] = "bri"
    assert normalize_notice(raw, taxonomy).stage is NoticeStage.OTHER


def test_multi_buyer_central_purchasing(real_notice, taxonomy) -> None:
    notice = normalize_notice(real_notice("613361-2026"), taxonomy)
    assert notice.buyer.count == 12
    assert notice.buyer.country == "HR"
    assert "defence" in notice.buyer.main_activities
    assert notice.match_reasons == frozenset({MATCH_DEFENCE_BUYER})


def test_swedish_sek_notice(real_notice, taxonomy) -> None:
    notice = normalize_notice(real_notice("626862-2026"), taxonomy)
    assert notice.buyer.country == "SE"
    assert notice.buyer.identifiers == ("2021005182",)
    assert notice.estimated_value == Money(Decimal("6000000"), "SEK")
    assert notice.tender_statistics is not None
    assert notice.tender_statistics.tender_counts == (0, 1, 1)
    assert notice.tender_statistics.selection_statuses == ("clos-nw",) * 3


def test_title_is_truncated(real_notice, taxonomy) -> None:
    raw = real_notice("626977-2026")
    raw["title-proc"] = {"spa": "x" * 500}
    assert len(normalize_notice(raw, taxonomy).title) == 200


def test_missing_identity_raises_and_normalize_many_counts(real_notice, taxonomy) -> None:
    raw = real_notice("626977-2026")
    del raw["notice-identifier"]
    with pytest.raises(NormalizationError):
        normalize_notice(raw, taxonomy)
    notices, errors = normalize_many([raw, real_notice("626136-2026")], taxonomy)
    assert errors == 1
    assert [n.publication_number for n in notices] == ["626136-2026"]


def test_all_fixtures_normalize(real_notices: list[dict[str, Any]], taxonomy) -> None:
    notices, errors = normalize_many(real_notices, taxonomy)
    assert errors == 0
    assert len(notices) == 18
    for notice in notices:
        assert notice.to_dict() and type(notice).from_dict(notice.to_dict()) == notice
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_normalizer.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `normalizer.py`**

```python
"""Raw TED search results → ProcurementNotice (plan §8–9; addendum §1.1, D3, D6, D7)."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any

from .const import TED_NOTICE_URL, TITLE_MAX_LENGTH, to_alpha2
from .models import (
    Buyer,
    ChangeInfo,
    ModificationInfo,
    Money,
    NoticeStage,
    ProcurementNotice,
    SubmissionStatistic,
    TenderStatistics,
    Winner,
)
from .taxonomy import Taxonomy, normalize_cpv

_LOGGER = logging.getLogger(__name__)

REQUESTED_FIELDS: tuple[str, ...] = (
    # identity and lifecycle
    "publication-number",
    "publication-date",
    "notice-identifier",
    "notice-version",
    "notice-type",
    "notice-subtype",
    "form-type",
    "procedure-identifier",
    "previous-notice-id-proc",
    "change-notice-version-identifier",
    # procedure
    "title-proc",
    "internal-identifier-proc",
    "procedure-type",
    "contract-nature",
    # buyer
    "buyer-name",
    "buyer-identifier",
    "buyer-country",
    "buyer-legal-type",
    "authority-main-activity",
    # legal / classification
    "legal-basis",
    "classification-cpv",
    "main-classification-proc",
    "additional-classification-proc",
    "main-classification-lot",
    "additional-classification-lot",
    # estimated value
    "estimated-value-proc",
    "estimated-value-cur-proc",
    "estimated-value-lot",
    "estimated-value-cur-lot",
    # results
    "result-value-notice",
    "result-value-cur-notice",
    "result-value-lot",
    "result-value-cur-lot",
    "winner-name",
    "winner-identifier",
    "winner-country",
    "winner-size",
    "winner-decision-date",
    "winner-selection-status",
    "received-submissions-type-code",
    "received-submissions-type-val",
    "non-award-justification",
    "tender-value",
    "tender-value-cur",
    # changes
    "change-description",
    "change-reason-code",
    "change-reason-description",
    # contract modifications
    "modification-description",
    "modification-justification",
    "modification-reason-description",
    "modification-previous-notice-identifier",
    # deadlines
    "deadline-receipt-tender-date-lot",
)

PREFERRED_LANGUAGES = ("eng", "swe")

_STAGE_BY_FORM_TYPE: dict[str, NoticeStage] = {
    "planning": NoticeStage.PLANNING,
    "competition": NoticeStage.COMPETITION,
    "result": NoticeStage.RESULT,
    "dir-awa-pre": NoticeStage.DIRECT_AWARD,
    "cont-modif": NoticeStage.MODIFICATION,
    "compl": NoticeStage.COMPLETION,
}

_CPV_FIELDS = (
    "classification-cpv",
    "main-classification-proc",
    "additional-classification-proc",
    "main-classification-lot",
    "additional-classification-lot",
)


class NormalizationError(ValueError):
    """The notice lacks the identity fields required by plan §7."""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def as_strings(value: Any) -> tuple[str, ...]:
    """Flatten a scalar-or-list field into non-empty strings."""
    return tuple(str(v) for v in _as_list(value) if v is not None and str(v) != "")


def _language(value: Mapping[str, Any]) -> str | None:
    for lang in PREFERRED_LANGUAGES:
        if lang in value:
            return lang
    return next(iter(value), None)


def first_text(value: Any) -> str | None:
    """First non-empty text of a multilingual ({lang: str | [str]}), list or scalar field."""
    if isinstance(value, Mapping):
        lang = _language(value)
        return first_text(value[lang]) if lang is not None else None
    if isinstance(value, list):
        return first_text(value[0]) if value else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _texts(value: Any) -> tuple[str, ...]:
    """All texts of a multilingual list field in one language."""
    if isinstance(value, Mapping):
        lang = _language(value)
        return as_strings(value[lang]) if lang is not None else ()
    return as_strings(value)


def parse_ted_date(value: Any) -> date | None:
    """Parse ``2026-09-11+02:00`` / ``2026-07-21Z`` into a date."""
    text = first_text(value)
    if text is None or len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _dates(value: Any) -> tuple[date, ...]:
    return tuple(d for d in (parse_ted_date(v) for v in _as_list(value)) if d is not None)


def _int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _lot_money(values: Sequence[str], currencies: Sequence[str]) -> Money | None:
    """Sum lot values only when the structure is unambiguous (D6)."""
    if not values or not currencies:
        return None
    if len(currencies) == 1:
        pairs = [(v, currencies[0]) for v in values]
    elif len(currencies) == len(values):
        pairs = list(zip(values, currencies, strict=True))
    else:
        return None
    monies = [Money.parse(v, c) for v, c in pairs]
    if any(m is None for m in monies):
        return None
    currency_set = {m.currency for m in monies if m is not None}
    if len(currency_set) != 1:
        return None
    total = sum((m.amount for m in monies if m is not None), start=Money.parse("0", "EUR") or 0)
    return Money(sum(m.amount for m in monies if m is not None), currency_set.pop())


def _estimated_value(raw: Mapping[str, Any]) -> Money | None:
    procedure = Money.parse(
        first_text(raw.get("estimated-value-proc")),
        first_text(raw.get("estimated-value-cur-proc")),
    )
    if procedure is not None:
        return procedure
    return _lot_money(
        as_strings(raw.get("estimated-value-lot")),
        as_strings(raw.get("estimated-value-cur-lot")),
    )


def _result_value(raw: Mapping[str, Any]) -> Money | None:
    notice = Money.parse(
        first_text(raw.get("result-value-notice")),
        first_text(raw.get("result-value-cur-notice")),
    )
    if notice is not None:
        return notice
    return _lot_money(
        as_strings(raw.get("result-value-lot")),
        as_strings(raw.get("result-value-cur-lot")),
    )


def _buyer(raw: Mapping[str, Any]) -> Buyer:
    names = _texts(raw.get("buyer-name"))
    countries = as_strings(raw.get("buyer-country"))
    legal_types = as_strings(raw.get("buyer-legal-type"))
    return Buyer(
        name=names[0] if names else None,
        identifiers=_unique(as_strings(raw.get("buyer-identifier"))),
        country=to_alpha2(countries[0]) if countries else None,
        legal_type=legal_types[0] if legal_types else None,
        main_activities=_unique(as_strings(raw.get("authority-main-activity"))),
        count=max(len(names), len(countries), 1),
    )


def _winners(raw: Mapping[str, Any]) -> tuple[Winner, ...]:
    names = _texts(raw.get("winner-name"))
    identifiers = as_strings(raw.get("winner-identifier"))
    countries = as_strings(raw.get("winner-country"))
    sizes = as_strings(raw.get("winner-size"))
    count = max(len(names), len(countries))
    if count == 0:
        return ()

    def aligned(values: tuple[str, ...], index: int) -> str | None:
        return values[index] if len(values) == count else None

    winners = []
    for index in range(count):
        country = aligned(countries, index)
        winners.append(
            Winner(
                name=aligned(names, index),
                identifier=aligned(identifiers, index),
                country=to_alpha2(country) if country else None,
                size=aligned(sizes, index),
            )
        )
    return tuple(winners)


def _tender_statistics(raw: Mapping[str, Any]) -> TenderStatistics | None:
    codes = as_strings(raw.get("received-submissions-type-code"))
    values = as_strings(raw.get("received-submissions-type-val"))
    statistics: tuple[SubmissionStatistic, ...] = ()
    if codes and len(codes) == len(values):
        parsed = [(code, _int(value)) for code, value in zip(codes, values, strict=True)]
        statistics = tuple(
            SubmissionStatistic(code, value)
            for code, value in parsed
            if value is not None and value >= 0
        )
    statuses = as_strings(raw.get("winner-selection-status"))
    justifications = as_strings(raw.get("non-award-justification"))
    decision_dates = _dates(raw.get("winner-decision-date"))
    if not (statistics or statuses or justifications or decision_dates):
        return None
    return TenderStatistics(statistics, statuses, justifications, decision_dates)


def _change(raw: Mapping[str, Any]) -> ChangeInfo | None:
    reason = first_text(raw.get("change-reason-code"))
    description = first_text(raw.get("change-description")) or first_text(
        raw.get("change-reason-description")
    )
    if reason is None and description is None:
        return None
    return ChangeInfo(reason, description, first_text(raw.get("change-notice-version-identifier")))


def _modification(raw: Mapping[str, Any]) -> ModificationInfo | None:
    description = first_text(raw.get("modification-description")) or first_text(
        raw.get("modification-reason-description")
    )
    justifications = _unique(as_strings(raw.get("modification-justification")))
    previous = _unique(as_strings(raw.get("modification-previous-notice-identifier")))
    if description is None and not justifications and not previous:
        return None
    return ModificationInfo(description, justifications, previous)


def _cpv_codes(raw: Mapping[str, Any]) -> tuple[str, ...]:
    codes: list[str] = []
    for field in _CPV_FIELDS:
        for value in as_strings(raw.get(field)):
            code = normalize_cpv(value)
            if code is not None:
                codes.append(code)
    return _unique(codes)


def normalize_notice(raw: Mapping[str, Any], taxonomy: Taxonomy) -> ProcurementNotice:
    """Normalize one raw search hit. Raises NormalizationError on missing identity."""
    notice_id = first_text(raw.get("notice-identifier"))
    publication_number = first_text(raw.get("publication-number"))
    publication_date = parse_ted_date(raw.get("publication-date"))
    version = _int(raw.get("notice-version"))
    form_type = first_text(raw.get("form-type"))
    if not (notice_id and publication_number and publication_date and form_type):
        raise NormalizationError(f"notice {publication_number or '?'} lacks identity fields")
    if version is None:
        raise NormalizationError(f"notice {publication_number} lacks notice-version")

    buyer = _buyer(raw)
    legal_basis = _unique(as_strings(raw.get("legal-basis")))
    cpv_codes = _cpv_codes(raw)
    title = first_text(raw.get("title-proc"))
    if title is not None and len(title) > TITLE_MAX_LENGTH:
        title = title[: TITLE_MAX_LENGTH - 1] + "…"

    return ProcurementNotice(
        notice_id=notice_id,
        notice_version=version,
        publication_number=publication_number,
        publication_date=publication_date,
        procedure_id=first_text(raw.get("procedure-identifier")),
        stage=_STAGE_BY_FORM_TYPE.get(form_type, NoticeStage.OTHER),
        notice_type=first_text(raw.get("notice-type")),
        notice_subtype=first_text(raw.get("notice-subtype")),
        title=title,
        buyer=buyer,
        legal_basis=legal_basis,
        cpv_codes=cpv_codes,
        match_reasons=taxonomy.match_reasons(
            activities=buyer.main_activities, legal_basis=legal_basis, cpv_codes=cpv_codes
        ),
        categories=taxonomy.classify(cpv_codes),
        procedure_type=first_text(raw.get("procedure-type")),
        contract_nature=_unique(as_strings(raw.get("contract-nature"))),
        estimated_value=_estimated_value(raw),
        result_value=_result_value(raw),
        tender_statistics=_tender_statistics(raw),
        winners=_winners(raw),
        change=_change(raw),
        modification=_modification(raw),
        source_url=TED_NOTICE_URL.format(publication_number=publication_number),
        classification_rule_version=taxonomy.version,
    )


def normalize_many(
    raws: Iterable[Mapping[str, Any]], taxonomy: Taxonomy
) -> tuple[list[ProcurementNotice], int]:
    """Normalize a batch, skipping malformed notices and counting them (plan §43)."""
    notices: list[ProcurementNotice] = []
    errors = 0
    for raw in raws:
        try:
            notices.append(normalize_notice(raw, taxonomy))
        except NormalizationError as err:
            errors += 1
            _LOGGER.warning("Skipping malformed TED notice: %s", err)
    return notices, errors
```

Remove the stray `total = sum(...)` line in `_lot_money` (it is a leftover; the function must only contain the checks and the final `return Money(...)`).

- [ ] **Step 4: Run tests, lint, type-check**

Run: `uv run pytest tests/test_normalizer.py -v && uv run ruff check . && uv run mypy custom_components/edp_radar`
Expected: 18 passed. If a real-fixture assertion fails because the captured data differs from the table in Task 5 (e.g. a different lot count), inspect the fixture with `uv run python -c "import json; ..."` and fix the *test expectation* to the real data, never the fixture.

- [ ] **Step 5: Commit**

```bash
git add custom_components/edp_radar/normalizer.py tests/test_normalizer.py
git commit -m "feat(normalizer): normalize raw TED notices into typed models

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: TED API client

**Files:**
- Create: `custom_components/edp_radar/api.py`, `tests/test_api.py`
- Modify: `tests/conftest.py` (add the autouse `enable_custom_integrations` fixture and a `ted_url` constant)

**Interfaces:**
- Consumes: `const.TED_API_BASE_URL`, `TED_MAX_PAGE_SIZE`, `TED_MAX_FIELDS_PER_PAGE`, `TED_PAGE_NUMBER_CEILING`, `TED_MIN_REQUEST_INTERVAL`, `TED_MAX_ATTEMPTS`.
- Produces:
  - `class PaginationMode(StrEnum)`: `PAGE_NUMBER`, `ITERATION`.
  - `class TedApiError(Exception)`, `class TedApiTemporaryError(TedApiError)` (429, 5xx, timeouts, connection errors), `class TedQueryError(TedApiError)` (HTTP 400 with `error.type` starting `QUERY_`).
  - `safe_page_size(field_count: int) -> int` = `max(1, min(250, 10000 // (field_count + 1)))`.
  - `class TedApiClient(session, *, base_url=..., min_interval=0.5, max_attempts=4, request_timeout=90.0, sleep=asyncio.sleep, clock=time.monotonic)`:
    - `async_search_notices(query: str, fields: Sequence[str], *, pagination_mode=PaginationMode.ITERATION, page_size: int | None = None, only_latest_versions: bool = False, progress: Callable[[int, int | None], None] | None = None) -> AsyncIterator[dict[str, Any]]`
    - `async_count_notices(query: str) -> int`
    - `async_validate_query(query: str) -> None` (raises `TedQueryError`)

- [ ] **Step 1: Extend `tests/conftest.py`**

Append:

```python
from custom_components.edp_radar.const import TED_API_BASE_URL

TED_SEARCH_URL = f"{TED_API_BASE_URL}/notices/search"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of custom_components in every test."""
```

- [ ] **Step 2: Write the failing tests**

`tests/test_api.py`:

```python
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.edp_radar.api import (
    PaginationMode,
    TedApiClient,
    TedApiError,
    TedApiTemporaryError,
    TedQueryError,
    safe_page_size,
)

from .conftest import TED_SEARCH_URL

FIELDS = ["publication-number", "notice-identifier"]


def test_safe_page_size_counts_the_links_field() -> None:
    assert safe_page_size(57) == 172
    assert safe_page_size(1) == 250
    assert safe_page_size(20000) == 1


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _client(hass: HomeAssistant, **kwargs: Any) -> tuple[TedApiClient, AsyncMock, FakeClock]:
    sleep = AsyncMock()
    clock = FakeClock()

    async def fake_sleep(seconds: float) -> None:
        await sleep(seconds)
        clock.now += seconds

    client = TedApiClient(
        async_get_clientsession(hass), sleep=fake_sleep, clock=clock, **kwargs
    )
    return client, sleep, clock


def _page(numbers: list[str], token: str | None, total: int) -> dict[str, Any]:
    return {
        "notices": [{"publication-number": n, "links": {}} for n in numbers],
        "totalNoticeCount": total,
        "iterationNextToken": token,
        "timedOut": False,
    }


async def test_iteration_mode_follows_tokens_and_stops_on_short_page(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    pages = {None: _page(["1", "2"], "t1", 3), "t1": _page(["3"], "t2", 3)}
    bodies: list[dict[str, Any]] = []

    async def handler(method: str, url: Any, data: dict[str, Any]) -> AiohttpClientMockResponse:
        bodies.append(data)
        return AiohttpClientMockResponse(
            method, url, json=pages[data.get("iterationNextToken")]
        )

    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    client, _sleep, _clock = _client(hass)
    seen: list[tuple[int, int | None]] = []
    numbers = [
        n["publication-number"]
        async for n in client.async_search_notices(
            "PD>=20260101", FIELDS, page_size=2, progress=lambda done, total: seen.append((done, total))
        )
    ]
    assert numbers == ["1", "2", "3"]
    assert seen == [(2, 3), (3, 3)]
    assert bodies[0]["paginationMode"] == "ITERATION"
    assert bodies[0]["limit"] == 2
    assert bodies[0]["fields"] == FIELDS
    assert "iterationNextToken" not in bodies[0]
    assert bodies[1]["iterationNextToken"] == "t1"
    assert bodies[0]["onlyLatestVersions"] is False


async def test_page_number_mode_increments_pages(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    pages = {1: _page(["1", "2"], None, 3), 2: _page(["3"], None, 3)}

    async def handler(method: str, url: Any, data: dict[str, Any]) -> AiohttpClientMockResponse:
        return AiohttpClientMockResponse(method, url, json=pages[data["page"]])

    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    client, _sleep, _clock = _client(hass)
    numbers = [
        n["publication-number"]
        async for n in client.async_search_notices(
            "PD>=20260101", FIELDS, pagination_mode=PaginationMode.PAGE_NUMBER, page_size=2
        )
    ]
    assert numbers == ["1", "2", "3"]


async def test_default_page_size_uses_safe_formula(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    captured: list[dict[str, Any]] = []

    async def handler(method: str, url: Any, data: dict[str, Any]) -> AiohttpClientMockResponse:
        captured.append(data)
        return AiohttpClientMockResponse(method, url, json=_page([], None, 0))

    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    client, _sleep, _clock = _client(hass)
    fields = [f"f{i}" for i in range(57)]
    assert [n async for n in client.async_search_notices("q", fields)] == []
    assert captured[0]["limit"] == 172


async def test_requests_are_paced(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    pages = {None: _page(["1", "2"], "t1", 4), "t1": _page(["3", "4"], "t2", 4), "t2": _page([], None, 4)}

    async def handler(method: str, url: Any, data: dict[str, Any]) -> AiohttpClientMockResponse:
        return AiohttpClientMockResponse(method, url, json=pages[data.get("iterationNextToken")])

    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    client, sleep, _clock = _client(hass, min_interval=0.5)
    assert len([n async for n in client.async_search_notices("q", FIELDS, page_size=2)]) == 4
    # three requests; the first is immediate, the next two wait the full interval
    assert [round(call.args[0], 3) for call in sleep.await_args_list] == [0.5, 0.5]


async def test_429_then_success_backs_off(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    calls = 0

    async def handler(method: str, url: Any, data: dict[str, Any]) -> AiohttpClientMockResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            return AiohttpClientMockResponse(method, url, status=429, text="<html>429</html>")
        return AiohttpClientMockResponse(method, url, json=_page(["1"], None, 1))

    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    client, sleep, _clock = _client(hass, min_interval=0)
    assert await client.async_count_notices("q") == 1
    assert calls == 2
    assert sleep.await_args_list[0].args[0] == 1  # 2 ** 0


async def test_persistent_5xx_raises_temporary_error(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(TED_SEARCH_URL, status=503, text="down")
    client, sleep, _clock = _client(hass, min_interval=0, max_attempts=3)
    with pytest.raises(TedApiTemporaryError):
        await client.async_count_notices("q")
    assert [call.args[0] for call in sleep.await_args_list] == [1, 2]


async def test_query_error_is_not_retried(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(
        TED_SEARCH_URL,
        status=400,
        json={
            "message": "Syntax error in expert query at line 1, col 21",
            "error": {"type": "QUERY_SYNTAX_ERROR", "location": {"beginColumn": 21}},
        },
    )
    client, sleep, _clock = _client(hass, min_interval=0)
    with pytest.raises(TedQueryError, match="Syntax error"):
        await client.async_validate_query("PD>=20250809 AND (foo")
    assert sleep.await_count == 0
    assert aioclient_mock.mock_calls[-1][2]["checkQuerySyntax"] is True


async def test_other_400_is_generic_error(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(
        TED_SEARCH_URL,
        status=400,
        json={"message": "Value (10150) exceeds", "error": {"type": "SEARCH_FIELDS_PER_PAGE_EXCEEDS_MAX_LIMIT"}},
    )
    client, _sleep, _clock = _client(hass, min_interval=0)
    with pytest.raises(TedApiError, match="10150") as info:
        await client.async_count_notices("q")
    assert not isinstance(info.value, TedQueryError)


async def test_connection_error_becomes_temporary(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    from aiohttp import ClientError

    aioclient_mock.post(TED_SEARCH_URL, exc=ClientError("boom"))
    client, _sleep, _clock = _client(hass, min_interval=0, max_attempts=2)
    with pytest.raises(TedApiTemporaryError):
        await client.async_count_notices("q")


async def test_validate_query_ok(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(TED_SEARCH_URL, json={"notices": [], "totalNoticeCount": None})
    client, _sleep, _clock = _client(hass, min_interval=0)
    await client.async_validate_query("PD>=20250809")
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_api.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `api.py`**

```python
"""Async client for the TED Search API (plan §35; addendum §1, D1, D9)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from enum import StrEnum
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import (
    TED_API_BASE_URL,
    TED_MAX_ATTEMPTS,
    TED_MAX_FIELDS_PER_PAGE,
    TED_MAX_PAGE_SIZE,
    TED_MIN_REQUEST_INTERVAL,
    TED_PAGE_NUMBER_CEILING,
)

_LOGGER = logging.getLogger(__name__)
_MAX_BACKOFF_SECONDS = 60


class PaginationMode(StrEnum):
    PAGE_NUMBER = "PAGE_NUMBER"
    ITERATION = "ITERATION"


class TedApiError(Exception):
    """Base error for the TED Search API."""


class TedApiTemporaryError(TedApiError):
    """429, 5xx, timeout or connection problem: retry later (plan §43)."""


class TedQueryError(TedApiError):
    """The expert query was rejected (HTTP 400 with a QUERY_* error type)."""


def safe_page_size(field_count: int) -> int:
    """Largest page size within the 10 000 fields-per-page limit (D1)."""
    return max(1, min(TED_MAX_PAGE_SIZE, TED_MAX_FIELDS_PER_PAGE // (field_count + 1)))


class TedApiClient:
    """Thin, paced, retrying client around ``POST /v3/notices/search``."""

    def __init__(
        self,
        session: ClientSession,
        *,
        base_url: str = TED_API_BASE_URL,
        min_interval: float = TED_MIN_REQUEST_INTERVAL,
        max_attempts: int = TED_MAX_ATTEMPTS,
        request_timeout: float = 90.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session = session
        self._url = f"{base_url.rstrip('/')}/notices/search"
        self._min_interval = min_interval
        self._max_attempts = max(1, max_attempts)
        self._timeout = request_timeout
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None

    async def async_search_notices(
        self,
        query: str,
        fields: Sequence[str],
        *,
        pagination_mode: PaginationMode = PaginationMode.ITERATION,
        page_size: int | None = None,
        only_latest_versions: bool = False,
        progress: Callable[[int, int | None], None] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield raw notices page by page."""
        limit = page_size or safe_page_size(len(fields))
        base: dict[str, Any] = {
            "query": query,
            "fields": list(fields),
            "limit": limit,
            "scope": "ALL",
            "paginationMode": pagination_mode.value,
            "onlyLatestVersions": only_latest_versions,
        }
        token: str | None = None
        page = 1
        fetched = 0
        while True:
            body = dict(base)
            if pagination_mode is PaginationMode.ITERATION:
                if token:
                    body["iterationNextToken"] = token
            else:
                body["page"] = page
            data = await self._async_post(body)
            notices: list[dict[str, Any]] = data.get("notices") or []
            fetched += len(notices)
            if progress is not None:
                progress(fetched, data.get("totalNoticeCount"))
            for notice in notices:
                yield notice
            if not notices or len(notices) < limit:
                return
            if pagination_mode is PaginationMode.ITERATION:
                token = data.get("iterationNextToken")
                if not token:
                    return
            else:
                page += 1
                if page * limit > TED_PAGE_NUMBER_CEILING:
                    return

    async def async_count_notices(self, query: str) -> int:
        data = await self._async_post(
            {"query": query, "fields": ["publication-number"], "limit": 1}
        )
        return int(data.get("totalNoticeCount") or 0)

    async def async_validate_query(self, query: str) -> None:
        """Raise TedQueryError if TED rejects the expert query syntax."""
        await self._async_post(
            {
                "query": query,
                "fields": ["publication-number"],
                "limit": 1,
                "checkQuerySyntax": True,
            }
        )

    async def _async_pace(self) -> None:
        if self._last_request is not None:
            wait = self._min_interval - (self._clock() - self._last_request)
            if wait > 0:
                await self._sleep(wait)
        self._last_request = self._clock()

    async def _async_post(self, body: dict[str, Any]) -> dict[str, Any]:
        last_error: TedApiError | None = None
        for attempt in range(self._max_attempts):
            if attempt:
                await self._sleep(min(_MAX_BACKOFF_SECONDS, 2 ** (attempt - 1)))
            await self._async_pace()
            try:
                async with asyncio.timeout(self._timeout):
                    response = await self._session.post(
                        self._url, json=body, headers={"Accept": "application/json"}
                    )
                    status = response.status
                    text = await response.text()
            except TimeoutError as err:
                last_error = TedApiTemporaryError("Timeout talking to TED")
                last_error.__cause__ = err
                continue
            except ClientError as err:
                last_error = TedApiTemporaryError(f"Error talking to TED: {err}")
                last_error.__cause__ = err
                continue
            if status == 200:
                try:
                    result: dict[str, Any] = json.loads(text)
                except ValueError as err:
                    raise TedApiError("TED returned invalid JSON") from err
                return result
            if status == 429 or status >= 500:
                _LOGGER.debug("TED returned HTTP %s (attempt %s)", status, attempt + 1)
                last_error = TedApiTemporaryError(f"TED returned HTTP {status}")
                continue
            raise _client_error(status, text)
        assert last_error is not None
        raise last_error


def _client_error(status: int, text: str) -> TedApiError:
    message = text[:300]
    error_type = ""
    try:
        payload = json.loads(text)
        message = str(payload.get("message") or message)
        error_type = str((payload.get("error") or {}).get("type") or "")
    except ValueError:
        pass
    if status == 400 and error_type.startswith("QUERY_"):
        return TedQueryError(message)
    return TedApiError(f"TED returned HTTP {status}: {message}")
```

- [ ] **Step 5: Run tests, lint, type-check**

Run: `uv run pytest tests/test_api.py -v && uv run ruff check . && uv run mypy custom_components/edp_radar`
Expected: 12 passed. If `AiohttpClientMockResponse`'s `side_effect` signature differs in the installed harness version, open `.venv/lib/python3.14/site-packages/pytest_homeassistant_custom_component/test_util/aiohttp.py`, read `match_request`, and adapt the handler signature in the tests (not the client).

- [ ] **Step 6: Now run the fixture fetch script from Task 5 and confirm the committed fixture is unchanged**

Run: `uv run python scripts/fetch_fixture_notices.py && git status --short tests/fixtures`
Expected: `wrote 18 notices …` and no diff (or only key-order differences; if the content differs, keep the freshly fetched file, re-run `uv run pytest tests/test_normalizer.py`, and fix expectations to the real data).

- [ ] **Step 7: Commit**

```bash
git add custom_components/edp_radar/api.py tests/test_api.py tests/conftest.py tests/fixtures
git commit -m "feat(api): add paced, retrying TED search client with iteration support

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: FX rate table and ECB parsers

**Files:**
- Create: `custom_components/edp_radar/fx_rates.py`, `tests/test_fx_rates.py`, `tests/fixtures/ecb/daily.xml`, `tests/fixtures/ecb/hist-90d.xml`, `tests/fixtures/ecb/hist.csv`

**Interfaces:**
- Consumes: `models.Money`.
- Produces:
  - `FIXED_EURO_RATES: dict[str, Decimal]` (BGN 1.95583, HRK 7.53450, LTL 3.45280, LVL 0.702804, EEK 15.6466, SKK 30.1260, SIT 239.640, CYP 0.585274, MTL 0.429300).
  - `MAX_LOOKBACK_DAYS = 10`.
  - `@dataclass(frozen=True) class FxConversion(eur_amount: Decimal, rate: Decimal, rate_date: date)`.
  - `class FxRateTable` with `add(day, rates)`, `update(table) -> int` (number of new dates), `dates -> list[date]`, `latest_date() -> date | None`, `rate_for(currency, on) -> tuple[Decimal, date] | None`, `convert_to_eur(money, on) -> FxConversion | None` (2-decimal EUR), `prune_before(cutoff) -> int`, `to_dict() -> dict[str, dict[str, str]]`, `FxRateTable.from_dict(data)`, `currencies() -> set[str]`, `__len__`.
  - `parse_ecb_xml(text: str) -> dict[date, dict[str, Decimal]]`, `parse_ecb_history_csv(text: str) -> dict[date, dict[str, Decimal]]`, `parse_ecb_history_zip(data: bytes) -> dict[date, dict[str, Decimal]]`.

- [ ] **Step 1: Write ECB fixtures**

`tests/fixtures/ecb/daily.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
	<gesmes:subject>Reference rates</gesmes:subject>
	<gesmes:Sender>
		<gesmes:name>European Central Bank</gesmes:name>
	</gesmes:Sender>
	<Cube>
		<Cube time='2026-09-11'>
			<Cube currency='USD' rate='1.1592'/>
			<Cube currency='CZK' rate='24.264'/>
			<Cube currency='DKK' rate='7.4748'/>
			<Cube currency='PLN' rate='4.3250'/>
			<Cube currency='SEK' rate='11.2373'/>
			<Cube currency='NOK' rate='10.7805'/>
		</Cube>
	</Cube>
</gesmes:Envelope>
```

`tests/fixtures/ecb/hist-90d.xml` (same envelope, two dated cubes: `2026-09-11` with `SEK 11.2373`, `PLN 4.3250`; `2026-09-10` with `SEK 11.1995`, `PLN 4.3220`):

```xml
<?xml version="1.0" encoding="UTF-8"?><gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref"><gesmes:subject>Reference rates</gesmes:subject><gesmes:Sender><gesmes:name>European Central Bank</gesmes:name></gesmes:Sender><Cube><Cube time="2026-09-11"><Cube currency="SEK" rate="11.2373"/><Cube currency="PLN" rate="4.325"/></Cube><Cube time="2026-09-10"><Cube currency="SEK" rate="11.1995"/><Cube currency="PLN" rate="4.322"/></Cube></Cube></gesmes:Envelope>
```

`tests/fixtures/ecb/hist.csv`:

```csv
Date,USD,BGN,PLN,SEK,HRK,
2026-09-11,1.1592,N/A,4.325,11.2373,N/A,
2026-09-10,1.1616,N/A,4.322,11.1995,N/A,
2026-09-08,1.1601,N/A,4.318,11.1500,N/A,
```

- [ ] **Step 2: Write the failing tests**

`tests/test_fx_rates.py`:

```python
import io
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from custom_components.edp_radar.fx_rates import (
    FIXED_EURO_RATES,
    FxConversion,
    FxRateTable,
    parse_ecb_history_csv,
    parse_ecb_history_zip,
    parse_ecb_xml,
)
from custom_components.edp_radar.models import Money

ECB = Path(__file__).parent / "fixtures" / "ecb"


def _table() -> FxRateTable:
    table = FxRateTable()
    table.add(date(2026, 9, 11), {"SEK": Decimal("11.2373"), "PLN": Decimal("4.3250")})
    table.add(date(2026, 9, 10), {"SEK": Decimal("11.1995"), "PLN": Decimal("4.3220")})
    return table


def test_parse_daily_xml() -> None:
    rates = parse_ecb_xml((ECB / "daily.xml").read_text())
    assert rates == {
        date(2026, 9, 11): {
            "USD": Decimal("1.1592"),
            "CZK": Decimal("24.264"),
            "DKK": Decimal("7.4748"),
            "PLN": Decimal("4.3250"),
            "SEK": Decimal("11.2373"),
            "NOK": Decimal("10.7805"),
        }
    }


def test_parse_90d_xml_has_two_dates() -> None:
    rates = parse_ecb_xml((ECB / "hist-90d.xml").read_text())
    assert sorted(rates) == [date(2026, 9, 10), date(2026, 9, 11)]
    assert rates[date(2026, 9, 10)]["PLN"] == Decimal("4.322")


def test_parse_history_csv_skips_na_and_trailing_comma() -> None:
    rates = parse_ecb_history_csv((ECB / "hist.csv").read_text())
    assert len(rates) == 3
    assert rates[date(2026, 9, 8)] == {
        "USD": Decimal("1.1601"),
        "PLN": Decimal("4.318"),
        "SEK": Decimal("11.1500"),
    }


def test_parse_history_zip() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("eurofxref-hist.csv", (ECB / "hist.csv").read_text())
    assert len(parse_ecb_history_zip(buffer.getvalue())) == 3


def test_eur_passthrough() -> None:
    conversion = _table().convert_to_eur(Money(Decimal("100.5"), "EUR"), date(2026, 9, 11))
    assert conversion == FxConversion(Decimal("100.50"), Decimal(1), date(2026, 9, 11))


def test_sek_and_pln_conversion_on_exact_date() -> None:
    table = _table()
    sek = table.convert_to_eur(Money(Decimal("6000000"), "SEK"), date(2026, 9, 11))
    assert sek is not None
    assert sek.eur_amount == Decimal("533936.55")
    assert sek.rate == Decimal("11.2373")
    assert sek.rate_date == date(2026, 9, 11)
    pln = table.convert_to_eur(Money(Decimal("10306545.8"), "PLN"), date(2026, 9, 10))
    assert pln is not None
    assert pln.eur_amount == Decimal("2384670.94")


def test_weekend_falls_back_to_latest_previous_rate() -> None:
    conversion = _table().convert_to_eur(Money(Decimal("100"), "SEK"), date(2026, 9, 13))
    assert conversion is not None
    assert conversion.rate_date == date(2026, 9, 11)


def test_never_uses_a_later_rate_and_gives_up_after_lookback() -> None:
    table = _table()
    assert table.rate_for("SEK", date(2026, 9, 9)) is None  # only later dates known
    assert table.rate_for("SEK", date(2026, 10, 30)) is None  # > 10 days after latest


def test_missing_currency_is_none() -> None:
    assert _table().convert_to_eur(Money(Decimal("1"), "XYZ"), date(2026, 9, 11)) is None


def test_fixed_euro_rates() -> None:
    conversion = FxRateTable().convert_to_eur(Money(Decimal("195.583"), "BGN"), date(2026, 1, 5))
    assert conversion is not None
    assert conversion.eur_amount == Decimal("100.00")
    assert FIXED_EURO_RATES["HRK"] == Decimal("7.53450")


def test_update_prune_and_round_trip() -> None:
    table = _table()
    assert table.update({date(2026, 9, 11): {"SEK": Decimal("11.2373")}, date(2026, 9, 9): {"SEK": Decimal("11.1")}}) == 1
    assert table.latest_date() == date(2026, 9, 11)
    assert table.currencies() == {"SEK", "PLN"}
    assert table.prune_before(date(2026, 9, 10)) == 1
    assert table.dates == [date(2026, 9, 10), date(2026, 9, 11)]
    data = table.to_dict()
    assert data["2026-09-11"]["SEK"] == "11.2373"
    assert FxRateTable.from_dict(data).to_dict() == data
    assert len(table) == 2
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_fx_rates.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `fx_rates.py`**

```python
"""ECB euro reference rates: table, parsers and EUR conversion (plan §10, D11)."""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from xml.etree import ElementTree

from .models import Money

# Currencies that joined the euro; ECB no longer publishes them (fixed conversion rates).
FIXED_EURO_RATES: dict[str, Decimal] = {
    "BGN": Decimal("1.95583"),
    "HRK": Decimal("7.53450"),
    "LTL": Decimal("3.45280"),
    "LVL": Decimal("0.702804"),
    "EEK": Decimal("15.6466"),
    "SKK": Decimal("30.1260"),
    "SIT": Decimal("239.640"),
    "CYP": Decimal("0.585274"),
    "MTL": Decimal("0.429300"),
}
MAX_LOOKBACK_DAYS = 10
_CENTS = Decimal("0.01")
_NS = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}


@dataclass(frozen=True)
class FxConversion:
    eur_amount: Decimal
    rate: Decimal
    rate_date: date


class FxRateTable:
    """Rates per date: EUR 1 = rate × currency."""

    def __init__(self) -> None:
        self._rates: dict[date, dict[str, Decimal]] = {}

    def __len__(self) -> int:
        return len(self._rates)

    def add(self, day: date, rates: Mapping[str, Decimal]) -> None:
        self._rates.setdefault(day, {}).update(rates)

    def update(self, table: Mapping[date, Mapping[str, Decimal]]) -> int:
        new_dates = 0
        for day, rates in table.items():
            if day not in self._rates:
                new_dates += 1
            self.add(day, rates)
        return new_dates

    @property
    def dates(self) -> list[date]:
        return sorted(self._rates)

    def latest_date(self) -> date | None:
        return max(self._rates) if self._rates else None

    def currencies(self) -> set[str]:
        return {c for rates in self._rates.values() for c in rates}

    def rate_for(self, currency: str, on: date) -> tuple[Decimal, date] | None:
        """Rate on the date, else the latest earlier date within the lookback."""
        code = currency.upper()
        if code == "EUR":
            return Decimal(1), on
        if code in FIXED_EURO_RATES:
            return FIXED_EURO_RATES[code], on
        for back in range(MAX_LOOKBACK_DAYS + 1):
            day = on - timedelta(days=back)
            rates = self._rates.get(day)
            if rates and code in rates:
                return rates[code], day
        return None

    def convert_to_eur(self, money: Money, on: date) -> FxConversion | None:
        found = self.rate_for(money.currency, on)
        if found is None:
            return None
        rate, day = found
        return FxConversion((money.amount / rate).quantize(_CENTS, ROUND_HALF_UP), rate, day)

    def prune_before(self, cutoff: date) -> int:
        old = [day for day in self._rates if day < cutoff]
        for day in old:
            del self._rates[day]
        return len(old)

    def to_dict(self) -> dict[str, dict[str, str]]:
        return {
            day.isoformat(): {c: str(r) for c, r in sorted(rates.items())}
            for day, rates in sorted(self._rates.items())
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Mapping[str, str]]) -> FxRateTable:
        table = cls()
        for day, rates in data.items():
            table.add(date.fromisoformat(day), {c: Decimal(r) for c, r in rates.items()})
        return table


def _decimal(value: str | None) -> Decimal | None:
    if value is None or value.strip() in {"", "N/A"}:
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        return None


def parse_ecb_xml(text: str) -> dict[date, dict[str, Decimal]]:
    """Parse the daily or 90-day ECB XML."""
    root = ElementTree.fromstring(text)
    result: dict[date, dict[str, Decimal]] = {}
    for day_cube in root.iterfind(".//e:Cube[@time]", _NS):
        day = date.fromisoformat(day_cube.attrib["time"])
        rates: dict[str, Decimal] = {}
        for cube in day_cube.iterfind("e:Cube[@currency]", _NS):
            rate = _decimal(cube.attrib.get("rate"))
            if rate is not None:
                rates[cube.attrib["currency"].upper()] = rate
        if rates:
            result[day] = rates
    return result


def parse_ecb_history_csv(text: str) -> dict[date, dict[str, Decimal]]:
    """Parse eurofxref-hist.csv (``Date,USD,...`` with ``N/A`` gaps)."""
    result: dict[date, dict[str, Decimal]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        raw_day = (row.get("Date") or "").strip()
        if not raw_day:
            continue
        rates: dict[str, Decimal] = {}
        for currency, value in row.items():
            if not currency or currency == "Date":
                continue
            rate = _decimal(value)
            if rate is not None:
                rates[currency.strip().upper()] = rate
        if rates:
            result[date.fromisoformat(raw_day)] = rates
    return result


def parse_ecb_history_zip(data: bytes) -> dict[date, dict[str, Decimal]]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        name = next(n for n in archive.namelist() if n.endswith(".csv"))
        return parse_ecb_history_csv(archive.read(name).decode("utf-8"))
```

- [ ] **Step 5: Run tests, lint, type-check**

Run: `uv run pytest tests/test_fx_rates.py -v && uv run ruff check . && uv run mypy custom_components/edp_radar`
Expected: 12 passed.

- [ ] **Step 6: Commit**

```bash
git add custom_components/edp_radar/fx_rates.py tests/test_fx_rates.py tests/fixtures/ecb
git commit -m "feat(fx): add ECB rate table, parsers and historical EUR conversion

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: ECB client

**Files:**
- Create: `custom_components/edp_radar/fx.py`, `tests/test_fx.py`

**Interfaces:**
- Consumes: `fx_rates.parse_ecb_xml`, `parse_ecb_history_zip`; `const.ECB_DAILY_URL`, `ECB_90D_URL`, `ECB_HISTORY_URL`.
- Produces: `class EcbFxError(Exception)`; `class EcbFxClient(session, *, request_timeout=60.0)` with `async_fetch_recent() -> dict[date, dict[str, Decimal]]` (90-day XML), `async_fetch_daily()`, `async_fetch_history()` (zip parsed in the default executor).

- [ ] **Step 1: Write the failing tests**

`tests/test_fx.py`:

```python
import io
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.edp_radar.const import ECB_90D_URL, ECB_DAILY_URL, ECB_HISTORY_URL
from custom_components.edp_radar.fx import EcbFxClient, EcbFxError

ECB = Path(__file__).parent / "fixtures" / "ecb"


async def test_fetch_recent_and_daily(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(ECB_90D_URL, text=(ECB / "hist-90d.xml").read_text())
    aioclient_mock.get(ECB_DAILY_URL, text=(ECB / "daily.xml").read_text())
    client = EcbFxClient(async_get_clientsession(hass))
    recent = await client.async_fetch_recent()
    assert recent[date(2026, 9, 10)]["SEK"] == Decimal("11.1995")
    daily = await client.async_fetch_daily()
    assert list(daily) == [date(2026, 9, 11)]


async def test_fetch_history_zip(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("eurofxref-hist.csv", (ECB / "hist.csv").read_text())
    aioclient_mock.get(ECB_HISTORY_URL, content=buffer.getvalue())
    history = await EcbFxClient(async_get_clientsession(hass)).async_fetch_history()
    assert len(history) == 3


async def test_errors_are_wrapped(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(ECB_90D_URL, status=503)
    aioclient_mock.get(ECB_DAILY_URL, exc=ClientError("boom"))
    aioclient_mock.get(ECB_HISTORY_URL, text="not xml")
    client = EcbFxClient(async_get_clientsession(hass))
    with pytest.raises(EcbFxError):
        await client.async_fetch_recent()
    with pytest.raises(EcbFxError):
        await client.async_fetch_daily()
    with pytest.raises(EcbFxError):
        await client.async_fetch_history()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_fx.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `fx.py`**

```python
"""Async client for ECB euro reference rates (plan §35, D11)."""

from __future__ import annotations

import asyncio
import zipfile
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree

from aiohttp import ClientError, ClientSession

from .const import ECB_90D_URL, ECB_DAILY_URL, ECB_HISTORY_URL
from .fx_rates import parse_ecb_history_zip, parse_ecb_xml

type RateTable = dict[date, dict[str, Decimal]]


class EcbFxError(Exception):
    """ECB data could not be fetched or parsed."""


class EcbFxClient:
    def __init__(self, session: ClientSession, *, request_timeout: float = 60.0) -> None:
        self._session = session
        self._timeout = request_timeout

    async def async_fetch_recent(self) -> RateTable:
        """Last ~90 days of rates (idempotent gap filler for each refresh)."""
        return self._parse_xml(await self._async_get(ECB_90D_URL))

    async def async_fetch_daily(self) -> RateTable:
        return self._parse_xml(await self._async_get(ECB_DAILY_URL))

    async def async_fetch_history(self) -> RateTable:
        """Full history zip (bootstrap only); parsed off the event loop."""
        data = await self._async_get(ECB_HISTORY_URL)
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, parse_ecb_history_zip, data)
        except (zipfile.BadZipFile, StopIteration, UnicodeDecodeError, ValueError) as err:
            raise EcbFxError(f"ECB history archive is invalid: {err}") from err

    async def _async_get(self, url: str) -> bytes:
        try:
            async with asyncio.timeout(self._timeout):
                response = await self._session.get(url)
                if response.status != 200:
                    raise EcbFxError(f"ECB returned HTTP {response.status} for {url}")
                return await response.read()
        except TimeoutError as err:
            raise EcbFxError(f"Timeout fetching {url}") from err
        except ClientError as err:
            raise EcbFxError(f"Error fetching {url}: {err}") from err

    @staticmethod
    def _parse_xml(data: bytes) -> RateTable:
        try:
            return parse_ecb_xml(data.decode("utf-8"))
        except (ElementTree.ParseError, UnicodeDecodeError, ValueError) as err:
            raise EcbFxError(f"ECB XML is invalid: {err}") from err
```

- [ ] **Step 4: Run tests, lint, type-check**

Run: `uv run pytest tests/test_fx.py -v && uv run ruff check . && uv run mypy custom_components/edp_radar`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add custom_components/edp_radar/fx.py tests/test_fx.py
git commit -m "feat(fx): add ECB reference-rate client

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Test factories and procedure lifecycle index

**Files:**
- Create: `tests/factories.py`, `custom_components/edp_radar/lifecycle.py`, `tests/test_lifecycle.py`

**Interfaces:**
- Consumes: `models.*`.
- Produces:
  - `tests/factories.py`: `make_notice(**overrides) -> ProcurementNotice` (defaults: competition, `notice_id="n1"`, version 1, `procedure_id="p1"`, buyer FMV/SE with identifier `202100-0340`, `publication_date=date(2026, 9, 1)`, `estimated_value=Money("1000000","EUR")`, `match_reasons={defence_buyer}`, `categories=("land_systems",)`); `competition(...)`, `result(...)`, `change_of(notice, *, version=None, notice_id=None, publication_date=...)`, `flat_fx(rates: dict[str, str], start: date, end: date) -> FxRateTable`.
  - `lifecycle.py`:
    - `@dataclass(frozen=True) class ProcedureSummary(key, procedure_id, buyer, country, match_reasons: frozenset[str], categories: frozenset[str], first_planning, first_competition, latest_competition, first_result, results: tuple[ProcurementNotice, ...], changes: tuple[...], modifications: tuple[...], direct_awards: tuple[...], notices: tuple[...])` with properties `linked -> bool`, `estimated_value -> Money | None`, `estimated_value_date -> date | None`, `time_to_result_days -> int | None`, `buyer_count -> int`.
    - `class ProcedureIndex` with `ProcedureIndex.build(notices: Iterable[ProcurementNotice]) -> ProcedureIndex`, `.procedures: Mapping[str, ProcedureSummary]`, `.notices: tuple[ProcurementNotice, ...]` (latest version per notice id, sorted by publication date), `.originals: tuple[ProcurementNotice, ...]` (latest versions of notice ids whose first version was not a change), `.changes: tuple[ProcurementNotice, ...]` (every stored version that carries change info), `results() -> list[ProcurementNotice]` (originals with stage RESULT), `competitions() -> list[ProcurementNotice]` (originals with stage COMPETITION), `__len__` (procedure count).

- [ ] **Step 1: Write `tests/factories.py`**

```python
"""Builders for deterministic metrics/lifecycle tests."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from custom_components.edp_radar.fx_rates import FxRateTable
from custom_components.edp_radar.models import (
    Buyer,
    ChangeInfo,
    Money,
    NoticeStage,
    ProcurementNotice,
    SubmissionStatistic,
    TenderStatistics,
    Winner,
)

FMV = Buyer("FMV", ("202100-0340",), "SE", "cga", ("defence",), 1)


def buyer(name: str, country: str, identifier: str | None = None, count: int = 1) -> Buyer:
    return Buyer(name, (identifier,) if identifier else (), country, "cga", ("defence",), count)


def make_notice(**overrides: Any) -> ProcurementNotice:
    base: dict[str, Any] = dict(
        notice_id="n1",
        notice_version=1,
        publication_number="1-2026",
        publication_date=date(2026, 9, 1),
        procedure_id="p1",
        stage=NoticeStage.COMPETITION,
        notice_type="cn-standard",
        notice_subtype="16",
        title="Title",
        buyer=FMV,
        legal_basis=("32014L0024",),
        cpv_codes=("35400000",),
        match_reasons=frozenset({"defence_buyer"}),
        categories=("land_systems",),
        procedure_type="open",
        contract_nature=("supplies",),
        estimated_value=Money(Decimal("1000000"), "EUR"),
        result_value=None,
        tender_statistics=None,
        winners=(),
        change=None,
        modification=None,
        source_url=None,
        classification_rule_version="test",
    )
    base.update(overrides)
    if "publication_number" not in overrides:
        base["publication_number"] = f"{base['notice_id']}-{base['notice_version']}"
    return ProcurementNotice(**base)


def competition(notice_id: str, procedure_id: str | None, published: date, **overrides: Any) -> ProcurementNotice:
    return make_notice(
        notice_id=notice_id, procedure_id=procedure_id, publication_date=published,
        stage=NoticeStage.COMPETITION, **overrides,
    )


def result(
    notice_id: str,
    procedure_id: str | None,
    published: date,
    *,
    value: Money | None = None,
    tenders: tuple[int, ...] = (),
    statuses: tuple[str, ...] = (),
    winners: tuple[Winner, ...] = (),
    decision_dates: tuple[date, ...] = (),
    **overrides: Any,
) -> ProcurementNotice:
    stats = None
    if tenders or statuses or decision_dates:
        stats = TenderStatistics(
            tuple(SubmissionStatistic("tenders", t) for t in tenders),
            statuses or tuple("selec-w" for _ in tenders),
            (),
            decision_dates,
        )
    return make_notice(
        notice_id=notice_id, procedure_id=procedure_id, publication_date=published,
        stage=NoticeStage.RESULT, estimated_value=None, result_value=value,
        tender_statistics=stats, winners=winners, **overrides,
    )


def change_of(
    notice: ProcurementNotice,
    *,
    published: date,
    version: int | None = None,
    notice_id: str | None = None,
    reason: str = "update-add",
) -> ProcurementNotice:
    """A change: same id with a higher version, or a new id (D3)."""
    from dataclasses import replace

    return replace(
        notice,
        notice_id=notice_id or notice.notice_id,
        notice_version=version if version is not None else (1 if notice_id else notice.notice_version + 1),
        publication_number=f"{notice_id or notice.notice_id}-chg",
        publication_date=published,
        change=ChangeInfo(reason, "changed", notice.notice_id),
    )


def flat_fx(rates: dict[str, str], start: date, end: date) -> FxRateTable:
    """The same rates on every day of [start, end] (weekends included)."""
    table = FxRateTable()
    day = start
    decimals = {c: Decimal(r) for c, r in rates.items()}
    while day <= end:
        table.add(day, decimals)
        day += timedelta(days=1)
    return table


def days_ago(today: date, days: int) -> date:
    return today - timedelta(days=days)
```

- [ ] **Step 2: Write the failing lifecycle tests**

`tests/test_lifecycle.py`:

```python
from datetime import date
from decimal import Decimal

from custom_components.edp_radar.lifecycle import ProcedureIndex
from custom_components.edp_radar.models import Money, NoticeStage

from .factories import change_of, competition, make_notice, result


def test_competition_change_result_chain() -> None:
    comp = competition("c1", "p1", date(2026, 3, 1))
    change = change_of(comp, published=date(2026, 3, 20))
    res = result("r1", "p1", date(2026, 6, 15), value=Money(Decimal("900000"), "EUR"))
    index = ProcedureIndex.build([comp, change, res])
    assert len(index) == 1
    proc = index.procedures["p1"]
    assert proc.linked is True
    assert proc.first_competition == date(2026, 3, 1)
    assert proc.latest_competition is change  # latest version carries the data
    assert proc.first_result == date(2026, 6, 15)
    assert proc.results == (res,)
    assert proc.changes == (change,)
    assert proc.time_to_result_days == 106
    assert proc.estimated_value == Money(Decimal("1000000"), "EUR")
    assert proc.estimated_value_date == date(2026, 3, 20)
    assert index.competitions() == [change]
    assert index.results() == [res]
    assert index.changes == (change,)


def test_two_versions_of_a_competition_count_once() -> None:
    v1 = competition("c1", "p1", date(2026, 3, 1))
    v2 = make_notice(notice_id="c1", notice_version=2, procedure_id="p1", publication_date=date(2026, 3, 5))
    index = ProcedureIndex.build([v2, v1])
    assert [n.notice_version for n in index.notices] == [2]
    proc = index.procedures["p1"]
    assert proc.first_competition == date(2026, 3, 1)
    assert proc.latest_competition is v2


def test_change_published_as_new_id_never_starts_a_competition() -> None:
    comp = competition("c1", "p1", date(2026, 3, 1))
    change = change_of(comp, published=date(2026, 3, 20), notice_id="c1-chg")
    index = ProcedureIndex.build([change])  # original outside the retention window
    proc = index.procedures["p1"]
    assert proc.first_competition is None
    assert proc.latest_competition is None
    assert proc.changes == (change,)
    assert index.originals == ()
    assert index.competitions() == []


def test_planning_competition_result_modification() -> None:
    plan = make_notice(notice_id="pl", stage=NoticeStage.PLANNING, publication_date=date(2026, 1, 10), estimated_value=Money(Decimal("5"), "EUR"))
    comp = competition("c1", "p1", date(2026, 2, 1), estimated_value=None)
    res = result("r1", "p1", date(2026, 5, 1))
    mod = make_notice(notice_id="m1", stage=NoticeStage.MODIFICATION, publication_date=date(2026, 8, 1))
    index = ProcedureIndex.build([plan, comp, res, mod])
    proc = index.procedures["p1"]
    assert proc.first_planning == date(2026, 1, 10)
    assert proc.first_competition == date(2026, 2, 1)
    assert proc.first_result == date(2026, 5, 1)
    assert proc.modifications == (mod,)
    assert proc.estimated_value == Money(Decimal("5"), "EUR")  # planning fallback
    assert proc.estimated_value_date == date(2026, 1, 10)


def test_result_without_known_competition_has_no_duration() -> None:
    res = result("r1", "p1", date(2026, 5, 1))
    proc = ProcedureIndex.build([res]).procedures["p1"]
    assert proc.first_competition is None
    assert proc.time_to_result_days is None
    assert proc.buyer.name == "FMV"


def test_missing_procedure_id_creates_unlinked_pseudo_procedures() -> None:
    a = competition("a", None, date(2026, 3, 1))
    b = result("b", None, date(2026, 6, 1))
    index = ProcedureIndex.build([a, b])
    assert set(index.procedures) == {"notice:a", "notice:b"}
    assert index.procedures["notice:a"].linked is False
    assert index.procedures["notice:b"].time_to_result_days is None


def test_union_of_reasons_and_categories_and_buyer_count() -> None:
    comp = competition("c1", "p1", date(2026, 3, 1), categories=("land_systems",))
    res = result("r1", "p1", date(2026, 5, 1), categories=("cyber_it",), match_reasons=frozenset({"defence_cpv"}))
    proc = ProcedureIndex.build([comp, res]).procedures["p1"]
    assert proc.categories == frozenset({"land_systems", "cyber_it"})
    assert proc.match_reasons == frozenset({"defence_buyer", "defence_cpv"})
    assert proc.buyer_count == 1
    assert proc.direct_awards == ()
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_lifecycle.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `lifecycle.py`**

```python
"""Procedure lifecycle index (plan §7, §38; addendum D3, D4)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from .models import Buyer, Money, NoticeStage, ProcurementNotice


@dataclass(frozen=True)
class ProcedureSummary:
    key: str
    procedure_id: str | None
    buyer: Buyer
    country: str | None
    match_reasons: frozenset[str]
    categories: frozenset[str]
    first_planning: date | None
    first_competition: date | None
    latest_competition: ProcurementNotice | None
    first_result: date | None
    results: tuple[ProcurementNotice, ...]
    changes: tuple[ProcurementNotice, ...]
    modifications: tuple[ProcurementNotice, ...]
    direct_awards: tuple[ProcurementNotice, ...]
    notices: tuple[ProcurementNotice, ...]

    @property
    def linked(self) -> bool:
        return self.procedure_id is not None

    def _value_source(self) -> ProcurementNotice | None:
        if self.latest_competition is not None and self.latest_competition.estimated_value:
            return self.latest_competition
        for notice in self.notices:
            if notice.stage is NoticeStage.PLANNING and notice.estimated_value:
                return notice
        return None

    @property
    def estimated_value(self) -> Money | None:
        source = self._value_source()
        return source.estimated_value if source else None

    @property
    def estimated_value_date(self) -> date | None:
        source = self._value_source()
        return source.publication_date if source else None

    @property
    def time_to_result_days(self) -> int | None:
        """Days from first original competition to first original result (plan §17.3)."""
        if not self.linked or self.first_competition is None or self.first_result is None:
            return None
        return (self.first_result - self.first_competition).days

    @property
    def buyer_count(self) -> int:
        return max((n.buyer.count for n in self.notices), default=1)


def _sort_key(notice: ProcurementNotice) -> tuple[date, int]:
    return (notice.publication_date, notice.notice_version)


class ProcedureIndex:
    """Groups stored notice versions into procedures; O(n) to build."""

    def __init__(
        self,
        procedures: dict[str, ProcedureSummary],
        notices: tuple[ProcurementNotice, ...],
        originals: tuple[ProcurementNotice, ...],
        changes: tuple[ProcurementNotice, ...],
    ) -> None:
        self._procedures = procedures
        self.notices = notices
        self.originals = originals
        self.changes = changes

    def __len__(self) -> int:
        return len(self._procedures)

    @property
    def procedures(self) -> Mapping[str, ProcedureSummary]:
        return self._procedures

    def results(self) -> list[ProcurementNotice]:
        return [n for n in self.originals if n.stage is NoticeStage.RESULT]

    def competitions(self) -> list[ProcurementNotice]:
        return [n for n in self.originals if n.stage is NoticeStage.COMPETITION]

    @classmethod
    def build(cls, notices: Iterable[ProcurementNotice]) -> ProcedureIndex:
        versions_by_id: dict[str, list[ProcurementNotice]] = defaultdict(list)
        for notice in notices:
            versions_by_id[notice.notice_id].append(notice)

        latest: dict[str, ProcurementNotice] = {}
        original_ids: set[str] = set()
        all_changes: list[ProcurementNotice] = []
        for notice_id, versions in versions_by_id.items():
            versions.sort(key=lambda n: n.notice_version)
            latest[notice_id] = versions[-1]
            if any(not v.is_change for v in versions):
                original_ids.add(notice_id)
            all_changes.extend(v for v in versions if v.is_change)

        groups: dict[str, list[ProcurementNotice]] = defaultdict(list)
        for versions in versions_by_id.values():
            for version in versions:
                key = version.procedure_id or f"notice:{version.notice_id}"
                groups[key].append(version)

        procedures: dict[str, ProcedureSummary] = {}
        for key, versions in groups.items():
            latest_notices = sorted(
                {v.notice_id: latest[v.notice_id] for v in versions}.values(), key=_sort_key
            )
            originals = [v for v in versions if v.notice_id in original_ids and not v.is_change]
            competitions = [
                n for n in latest_notices
                if n.stage is NoticeStage.COMPETITION and n.notice_id in original_ids
            ]
            latest_competition = max(competitions, key=_sort_key) if competitions else None
            anchor = latest_competition or latest_notices[0]
            procedures[key] = ProcedureSummary(
                key=key,
                procedure_id=versions[0].procedure_id,
                buyer=anchor.buyer,
                country=anchor.buyer.country,
                match_reasons=frozenset().union(*(n.match_reasons for n in latest_notices)),
                categories=frozenset(c for n in latest_notices for c in n.categories),
                first_planning=_first_date(originals, NoticeStage.PLANNING),
                first_competition=_first_date(originals, NoticeStage.COMPETITION),
                latest_competition=latest_competition,
                first_result=_first_date(originals, NoticeStage.RESULT),
                results=tuple(
                    n for n in latest_notices
                    if n.stage is NoticeStage.RESULT and n.notice_id in original_ids
                ),
                changes=tuple(sorted((v for v in versions if v.is_change), key=_sort_key)),
                modifications=tuple(n for n in latest_notices if n.stage is NoticeStage.MODIFICATION),
                direct_awards=tuple(n for n in latest_notices if n.stage is NoticeStage.DIRECT_AWARD),
                notices=tuple(latest_notices),
            )

        latest_sorted = tuple(sorted(latest.values(), key=_sort_key))
        originals_sorted = tuple(n for n in latest_sorted if n.notice_id in original_ids)
        return cls(procedures, latest_sorted, originals_sorted, tuple(sorted(all_changes, key=_sort_key)))


def _first_date(originals: list[ProcurementNotice], stage: NoticeStage) -> date | None:
    dates = [n.publication_date for n in originals if n.stage is stage]
    return min(dates) if dates else None
```

- [ ] **Step 5: Run tests, lint, type-check**

Run: `uv run pytest tests/test_lifecycle.py -v && uv run ruff check . && uv run mypy custom_components/edp_radar`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add tests/factories.py custom_components/edp_radar/lifecycle.py tests/test_lifecycle.py
git commit -m "feat(lifecycle): add procedure index linking notice versions and stages

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Metrics foundation — configuration, windows, result types, helpers

**Files:**
- Create: `custom_components/edp_radar/metrics.py`, `tests/test_metrics.py`

**Interfaces:**
- Consumes: `models`, `lifecycle.ProcedureIndex/ProcedureSummary`, `fx_rates.FxRateTable`, `taxonomy.Taxonomy`, `const.*` thresholds.
- Produces (all in `metrics.py`; later tasks add functions to the same module):
  - Config: `OwnOrganisation(identifiers: frozenset[str], country: str | None, names: frozenset[str])` with `matches(notice) -> bool` and `OwnOrganisation.from_options(identifiers, country, canonical_name, aliases)`; `WatchlistConfig(countries=frozenset(), buyer_identifiers=frozenset(), categories=frozenset(), min_estimated_value_eur=None, min_award_value_eur=None)` with `is_empty`; `MetricsConfig(relevance_mode=STRICT, market_countries=frozenset(), own_organisation=None, peer_countries=frozenset(), peer_organisation_identifiers=frozenset(), selected_country=None, pinned_categories=(), watchlist=WatchlistConfig())`.
  - Windows: `Window(start: date, end: date)` (`start` exclusive, `end` inclusive) with `days`, `contains(d)`; `current_window(today, days)`, `previous_window(today, days)`.
  - Helpers: `pct_change(current, previous) -> float | None` (None when previous is None or 0), `pct(numerator, denominator) -> float | None`, `median(values) -> float | None`, `value_in_eur(money, on, fx) -> Decimal | None`, `format_eur(amount) -> str`.
  - Universe: `is_central_purchasing_only(notice) -> bool`, `relevant_notices(notices, config, taxonomy) -> tuple[list[ProcurementNotice], int]` (second: excluded count).
  - Result types: `Coverage(covered, population)` with `pct`; `CountMetric(value, previous, period_days)` with `change`, `change_pct`; `ValueMetric(value_eur, previous_eur, sample_size, covered, period_days)` with `coverage_pct`, `change_pct`; `RankingEntry(key, label, rank, value_eur, procedures, previous_value_eur, previous_procedures, change_pct)` with `change_eur`; `Ranking(entries, population, population_size)` with `leader`; `NoticeHighlight(...)`; `MedianMetric(value, sample_size, coverage)`; `ShareMetric(pct, numerator, denominator, coverage)`; `ProcessMetrics`; `MarketMetrics`; `ExternalMetrics`; `OrganisationMetrics`; `PeerMetrics` (includes `rank_population`, `rank_population_size` for the selected-country rank); `SupplierEntry`; `SupplierMetrics`; `CategoryMetrics`; `DataQualityMetrics`; `RadarSnapshot` — fields exactly as in the code below.

- [ ] **Step 1: Write the failing tests**

`tests/test_metrics.py` (initial content; later tasks append to this file):

```python
from datetime import date
from decimal import Decimal

import pytest

from custom_components.edp_radar.const import RelevanceMode
from custom_components.edp_radar.metrics import (
    CountMetric,
    Coverage,
    MetricsConfig,
    OwnOrganisation,
    ValueMetric,
    WatchlistConfig,
    Window,
    current_window,
    format_eur,
    is_central_purchasing_only,
    median,
    pct,
    pct_change,
    previous_window,
    relevant_notices,
    value_in_eur,
)
from custom_components.edp_radar.models import Money
from custom_components.edp_radar.taxonomy import Taxonomy

from .factories import buyer, flat_fx, make_notice

TODAY = date(2026, 9, 12)


@pytest.fixture
def taxonomy() -> Taxonomy:
    return Taxonomy.load()


def test_windows_are_half_open() -> None:
    w = current_window(TODAY, 30)
    assert w == Window(date(2026, 8, 13), TODAY)
    assert w.days == 30
    assert w.contains(TODAY) and w.contains(date(2026, 8, 14))
    assert not w.contains(date(2026, 8, 13))
    p = previous_window(TODAY, 30)
    assert p == Window(date(2026, 7, 14), date(2026, 8, 13))
    assert p.contains(date(2026, 8, 13))


def test_helpers() -> None:
    assert pct_change(142, 100) == 42.0
    assert pct_change(50, 100) == -50.0
    assert pct_change(5, 0) is None
    assert pct_change(5, None) is None
    assert pct_change(Decimal("3"), Decimal("2")) == 50.0
    assert pct(1, 4) == 25.0
    assert pct(0, 0) is None
    assert median([]) is None
    assert median([3, 1, 2]) == 2
    assert median([1, 2, 3, 4]) == 2.5
    assert format_eur(None) == "EUR n/a"
    assert format_eur(Decimal("31400000000")) == "EUR 31.4bn"
    assert format_eur(Decimal("640000000")) == "EUR 640m"
    assert format_eur(Decimal("8400000")) == "EUR 8.4m"
    assert format_eur(Decimal("85000")) == "EUR 85k"
    assert format_eur(Decimal("950")) == "EUR 950"


def test_value_in_eur_uses_event_date_rate() -> None:
    fx = flat_fx({"SEK": "10"}, date(2026, 1, 1), date(2026, 12, 31))
    assert value_in_eur(Money(Decimal("100"), "SEK"), date(2026, 3, 1), fx) == Decimal("10.00")
    assert value_in_eur(Money(Decimal("100"), "EUR"), date(2026, 3, 1), fx) == Decimal("100.00")
    assert value_in_eur(Money(Decimal("100"), "XXX"), date(2026, 3, 1), fx) is None
    assert value_in_eur(None, date(2026, 3, 1), fx) is None


def test_metric_types() -> None:
    assert Coverage(211, 328).pct == 64.3
    assert Coverage(0, 0).pct is None
    count = CountMetric(173, 142, 30)
    assert count.change == 31 and count.change_pct == 21.8
    assert CountMetric(5, None, 30).change is None
    value = ValueMetric(Decimal("8400000000"), Decimal("7000000000"), 328, 211, 90)
    assert value.coverage_pct == 64.3
    assert value.change_pct == 20.0
    assert ValueMetric(None, None, 0, 0, 90).coverage_pct is None


def test_own_organisation_matching() -> None:
    own = OwnOrganisation.from_options(["202100-0340"], "SE", "FMV", ["Försvarets materielverk"])
    assert own.matches(make_notice()) is True
    assert own.matches(make_notice(buyer=buyer("Saab", "SE", "556036-0793"))) is False
    assert own.matches(make_notice(buyer=buyer("Försvarets Materielverk", "SE"))) is True
    assert own.matches(make_notice(buyer=buyer("Försvarets Materielverk", "FI"))) is False
    assert OwnOrganisation.from_options([], None, "FMV", []).matches(make_notice(buyer=buyer("fmv", "NO"))) is True


def test_watchlist_is_empty_by_default() -> None:
    assert WatchlistConfig().is_empty is True
    assert WatchlistConfig(countries=frozenset({"PL"})).is_empty is False
    assert MetricsConfig().relevance_mode is RelevanceMode.STRICT


def test_relevant_notices_apply_mode_and_central_purchasing_rule(taxonomy: Taxonomy) -> None:
    strict = make_notice(notice_id="a", match_reasons=frozenset({"defence_buyer"}))
    cpv_only = make_notice(notice_id="b", match_reasons=frozenset({"defence_cpv"}))
    cpb = make_notice(notice_id="c", buyer=buyer("CPB", "HR", "1", count=537), match_reasons=frozenset({"defence_buyer"}))
    cpb_with_cpv = make_notice(notice_id="d", buyer=buyer("CPB", "HR", "1", count=537), match_reasons=frozenset({"defence_buyer", "defence_cpv"}))
    none = make_notice(notice_id="e", match_reasons=frozenset())
    assert is_central_purchasing_only(cpb) is True
    assert is_central_purchasing_only(cpb_with_cpv) is False
    assert is_central_purchasing_only(strict) is False

    kept, excluded = relevant_notices([strict, cpv_only, cpb, cpb_with_cpv, none], MetricsConfig(), taxonomy)
    assert [n.notice_id for n in kept] == ["a", "d"]
    assert excluded == 1
    kept, excluded = relevant_notices([strict, cpv_only, cpb, cpb_with_cpv, none], MetricsConfig(relevance_mode=RelevanceMode.BROAD), taxonomy)
    assert [n.notice_id for n in kept] == ["a", "b", "d"]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the foundation of `metrics.py`**

```python
"""Pure metrics engine: notices + FX + configuration + date → RadarSnapshot (plan §16–20, §37)."""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from .const import (
    CENTRAL_PURCHASING_BUYER_THRESHOLD,
    MATCH_DEFENCE_BUYER,
    RelevanceMode,
)
from .fx_rates import FxRateTable
from .lifecycle import ProcedureIndex, ProcedureSummary
from .models import Money, NoticeStage, ProcurementNotice, normalize_name
from .taxonomy import Taxonomy

# --------------------------------------------------------------------------- config


@dataclass(frozen=True)
class OwnOrganisation:
    """Public identity of the tracked organisation (plan §12, D17)."""

    identifiers: frozenset[str]
    country: str | None
    names: frozenset[str]

    @classmethod
    def from_options(
        cls,
        identifiers: Iterable[str],
        country: str | None,
        canonical_name: str | None,
        aliases: Iterable[str],
    ) -> OwnOrganisation:
        names = {normalize_name(n) for n in [canonical_name or "", *aliases] if n}
        return cls(frozenset(i for i in identifiers if i), country, frozenset(names))

    def matches(self, notice: ProcurementNotice) -> bool:
        if self.identifiers and self.identifiers & set(notice.buyer.identifiers):
            return True
        if not self.names or not notice.buyer.name:
            return False
        if self.country is not None and notice.buyer.country != self.country:
            return False
        return normalize_name(notice.buyer.name) in self.names


@dataclass(frozen=True)
class WatchlistConfig:
    countries: frozenset[str] = frozenset()
    buyer_identifiers: frozenset[str] = frozenset()
    categories: frozenset[str] = frozenset()
    min_estimated_value_eur: Decimal | None = None
    min_award_value_eur: Decimal | None = None

    @property
    def is_empty(self) -> bool:
        return not (
            self.countries
            or self.buyer_identifiers
            or self.categories
            or self.min_estimated_value_eur is not None
            or self.min_award_value_eur is not None
        )


@dataclass(frozen=True)
class MetricsConfig:
    relevance_mode: RelevanceMode = RelevanceMode.STRICT
    market_countries: frozenset[str] = frozenset()
    own_organisation: OwnOrganisation | None = None
    peer_countries: frozenset[str] = frozenset()
    peer_organisation_identifiers: frozenset[str] = frozenset()
    selected_country: str | None = None
    pinned_categories: tuple[str, ...] = ()
    watchlist: WatchlistConfig = field(default_factory=WatchlistConfig)


# --------------------------------------------------------------------------- windows & helpers


@dataclass(frozen=True)
class Window:
    """Half-open rolling period: start < d <= end (plan §15)."""

    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    def contains(self, d: date) -> bool:
        return self.start < d <= self.end


def current_window(today: date, days: int) -> Window:
    return Window(today - timedelta(days=days), today)


def previous_window(today: date, days: int) -> Window:
    return Window(today - timedelta(days=2 * days), today - timedelta(days=days))


def pct_change(current: Decimal | int | None, previous: Decimal | int | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round(float((Decimal(current) - Decimal(previous)) / Decimal(previous) * 100), 1)


def pct(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 1)


def median(values: Sequence[float | int]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def value_in_eur(money: Money | None, on: date, fx: FxRateTable) -> Decimal | None:
    if money is None:
        return None
    conversion = fx.convert_to_eur(money, on)
    return conversion.eur_amount if conversion else None


def format_eur(amount: Decimal | None) -> str:
    if amount is None:
        return "EUR n/a"
    value = float(amount)
    if value >= 1e9:
        return f"EUR {value / 1e9:.1f}bn"
    if value >= 1e7:
        return f"EUR {value / 1e6:.0f}m"
    if value >= 1e6:
        return f"EUR {value / 1e6:.1f}m"
    if value >= 1e3:
        return f"EUR {value / 1e3:.0f}k"
    return f"EUR {value:.0f}"


# --------------------------------------------------------------------------- universe


def is_central_purchasing_only(notice: ProcurementNotice) -> bool:
    """Many buyers and only the defence-buyer signal: a central purchasing body (D5)."""
    return (
        notice.buyer.count > CENTRAL_PURCHASING_BUYER_THRESHOLD
        and notice.match_reasons == frozenset({MATCH_DEFENCE_BUYER})
    )


def relevant_notices(
    notices: Iterable[ProcurementNotice], config: MetricsConfig, taxonomy: Taxonomy
) -> tuple[list[ProcurementNotice], int]:
    """Notices in the configured universe, and how many were excluded as CPB-only."""
    kept: list[ProcurementNotice] = []
    excluded = 0
    for notice in notices:
        if not taxonomy.is_relevant(notice.match_reasons, config.relevance_mode):
            continue
        if is_central_purchasing_only(notice):
            excluded += 1
            continue
        kept.append(notice)
    return kept, excluded


# --------------------------------------------------------------------------- result types


@dataclass(frozen=True)
class Coverage:
    covered: int
    population: int

    @property
    def pct(self) -> float | None:
        return pct(self.covered, self.population)


@dataclass(frozen=True)
class CountMetric:
    value: int
    previous: int | None
    period_days: int

    @property
    def change(self) -> int | None:
        return None if self.previous is None else self.value - self.previous

    @property
    def change_pct(self) -> float | None:
        return pct_change(self.value, self.previous)


@dataclass(frozen=True)
class ValueMetric:
    value_eur: Decimal | None
    previous_eur: Decimal | None
    sample_size: int
    covered: int
    period_days: int

    @property
    def coverage_pct(self) -> float | None:
        return pct(self.covered, self.sample_size)

    @property
    def change_pct(self) -> float | None:
        return pct_change(self.value_eur, self.previous_eur)


@dataclass(frozen=True)
class RankingEntry:
    key: str
    label: str
    rank: int
    value_eur: Decimal | None
    procedures: int
    previous_value_eur: Decimal | None
    previous_procedures: int
    change_pct: float | None

    @property
    def change_eur(self) -> Decimal | None:
        if self.value_eur is None or self.previous_value_eur is None:
            return None
        return self.value_eur - self.previous_value_eur


@dataclass(frozen=True)
class Ranking:
    entries: tuple[RankingEntry, ...]
    population: str
    population_size: int

    @property
    def leader(self) -> RankingEntry | None:
        return self.entries[0] if self.entries else None


@dataclass(frozen=True)
class NoticeHighlight:
    notice_id: str
    publication_number: str
    procedure_id: str | None
    title: str | None
    buyer: str | None
    country: str | None
    publication_date: date
    stage: NoticeStage
    original_amount: Decimal | None
    original_currency: str | None
    value_eur: Decimal | None
    categories: tuple[str, ...]
    source_url: str | None


@dataclass(frozen=True)
class MedianMetric:
    value: float | None
    sample_size: int
    coverage: Coverage


@dataclass(frozen=True)
class ShareMetric:
    pct: float | None
    numerator: int
    denominator: int
    coverage: Coverage


@dataclass(frozen=True)
class ProcessMetrics:
    median_tenders_365d: MedianMetric
    single_bid_share_365d: ShareMetric
    median_time_to_result_365d: MedianMetric
    non_award_share_365d: ShareMetric


@dataclass(frozen=True)
class MarketMetrics:
    new_competitions_30d: CountMetric
    new_competitions_90d: CountMetric
    estimated_value_30d: ValueMetric
    estimated_value_90d: ValueMetric
    award_value_30d: ValueMetric
    award_value_90d: ValueMetric
    country_ranking_90d: Ranking
    country_growth_90d: Ranking
    category_ranking_90d: Ranking
    category_growth_90d: Ranking
    largest_country_change_90d: RankingEntry | None
    largest_category_change_90d: RankingEntry | None
    process: ProcessMetrics
    snapshot_text: str
    country_ranking_text: str


@dataclass(frozen=True)
class ExternalMetrics:
    new_competitions_7d: int
    recent_competitions: tuple[NoticeHighlight, ...]
    largest_competition_7d: NoticeHighlight | None
    largest_award_7d: NoticeHighlight | None
    latest_text: str | None


@dataclass(frozen=True)
class OrganisationMetrics:
    competitions_30d: CountMetric
    estimated_value_30d: ValueMetric
    awards_30d: CountMetric
    award_value_30d: ValueMetric
    changes_30d: CountMetric
    modifications_365d: CountMetric
    process: ProcessMetrics
    recent: tuple[NoticeHighlight, ...]


@dataclass(frozen=True)
class PeerMetrics:
    population: str
    population_size: int
    selected_country: str | None
    rank_population: str
    rank_population_size: int
    value_rank_90d: int | None
    activity_rank_90d: int | None
    value_percentile_90d: float | None
    process: ProcessMetrics
    single_bid_delta_pp: float | None
    median_tenders_delta: float | None
    time_to_result_delta_days: float | None


@dataclass(frozen=True)
class SupplierEntry:
    key: str
    name: str
    country: str | None
    rank: int
    award_value_eur: Decimal
    awards: int


@dataclass(frozen=True)
class SupplierMetrics:
    top_suppliers: tuple[SupplierEntry, ...]
    top5_share_pct: float | None
    total_award_value_eur: Decimal | None
    groups: int
    coverage: Coverage


@dataclass(frozen=True)
class CategoryMetrics:
    category_id: str
    label: str
    competitions_30d: CountMetric
    estimated_value_90d: ValueMetric
    award_value_90d: ValueMetric


@dataclass(frozen=True)
class DataQualityMetrics:
    stored_versions: int
    stored_notices: int
    stored_procedures: int
    relevant_notices: int
    excluded_central_purchasing: int
    records_by_stage: Mapping[str, int]
    parse_errors: int
    unlinked_results: int
    fx_coverage: Coverage
    estimated_value_coverage: Coverage
    result_value_coverage: Coverage
    bid_count_coverage: Coverage
    procedure_link_coverage: Coverage
    unclassified_share_pct: float | None
    latest_publication_date: date | None
    fx_latest_date: date | None


@dataclass(frozen=True)
class RadarSnapshot:
    computed_at: datetime
    today: date
    market: MarketMetrics
    external: ExternalMetrics
    own: OrganisationMetrics | None
    peers: PeerMetrics | None
    suppliers: SupplierMetrics
    categories: Mapping[str, CategoryMetrics]
    quality: DataQualityMetrics
    bootstrap_complete: bool
```

`ProcedureIndex`/`ProcedureSummary` are imported now so the module type-checks; later tasks use them.

- [ ] **Step 4: Run tests, lint, type-check**

Run: `uv run pytest tests/test_metrics.py -v && uv run ruff check . && uv run mypy custom_components/edp_radar`
Expected: 7 passed. (Ruff may flag the unused `ProcedureIndex`/`ProcedureSummary` imports — keep them by referencing them in a `__all__` list at the end of the module, or add them when Task 12 uses them; do not suppress with `noqa`.)

- [ ] **Step 5: Commit**

```bash
git add custom_components/edp_radar/metrics.py tests/test_metrics.py
git commit -m "feat(metrics): add configuration, rolling windows and snapshot result types

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Market metrics — counts, values, rankings, growth, process metrics

**Files:**
- Modify: `custom_components/edp_radar/metrics.py` (append), `tests/test_metrics.py` (append)

**Interfaces:**
- Consumes: Task 11 types, `ProcedureIndex`, `const.GROWTH_MIN_PROCEDURES`, `GROWTH_MIN_VALUE_EUR`, `RANKING_LIMIT`.
- Produces:
  - `procedures_started_in(index, window) -> list[ProcedureSummary]`, `results_in(index, window) -> list[ProcurementNotice]`
  - `new_competitions(index, today, days) -> CountMetric`, `awards_count(index, today, days) -> CountMetric`
  - `estimated_value(index, today, days, fx) -> ValueMetric`, `award_value(index, today, days, fx) -> ValueMetric`
  - `rank_by(index, today, fx, key_fn: Callable[[ProcedureSummary], Iterable[str]], label_fn: Callable[[str], str], *, days=90) -> list[RankingEntry]` (full population, competition ranking on `(value_eur desc nulls last, procedures desc)`, keys from both periods)
  - `top_ranking(entries, population, limit=RANKING_LIMIT) -> Ranking`, `growth_ranking(entries, population) -> Ranking`, `largest_change(entries) -> RankingEntry | None`, `is_growth_eligible(entry) -> bool`
  - `process_metrics(index, today) -> ProcessMetrics`
  - `market_metrics(index, today, fx, taxonomy) -> MarketMetrics`
  - `market_snapshot_text(competitions_90d, value_90d) -> str`, `country_ranking_text(ranking) -> str`

- [ ] **Step 1: Append the failing tests to `tests/test_metrics.py`**

```python
# --- Task 12: market metrics -------------------------------------------------
from custom_components.edp_radar.lifecycle import ProcedureIndex  # noqa: E402
from custom_components.edp_radar.metrics import (  # noqa: E402
    award_value,
    awards_count,
    estimated_value,
    growth_ranking,
    largest_change,
    market_metrics,
    new_competitions,
    process_metrics,
    rank_by,
    top_ranking,
)
from custom_components.edp_radar.models import Winner  # noqa: E402

from .factories import change_of, competition, days_ago, result  # noqa: E402

FX = flat_fx({"SEK": "10", "PLN": "4"}, date(2025, 1, 1), date(2026, 12, 31))


def _market_notices() -> list:
    """Hand-built dataset. today = 2026-09-12; 30d window = (Aug 13, Sep 12]."""
    return [
        # SE: two competitions in current 30d, one in previous 30d (Jul 20)
        competition("se1", "p-se1", days_ago(TODAY, 5), estimated_value=Money(Decimal("2000000"), "SEK")),
        competition("se2", "p-se2", days_ago(TODAY, 20), estimated_value=None),
        competition("se3", "p-se3", days_ago(TODAY, 54)),
        # version 2 + change of se1 in window: must not add a competition
        make_notice(notice_id="se1", notice_version=2, procedure_id="p-se1", publication_date=days_ago(TODAY, 3), estimated_value=Money(Decimal("2500000"), "SEK")),
        change_of(competition("se1", "p-se1", days_ago(TODAY, 5)), published=days_ago(TODAY, 1), notice_id="se1-chg"),
        # DE: one big competition now, none before; PL: 1 now, 1 before (EUR 1m each)
        competition("de1", "p-de1", days_ago(TODAY, 10), buyer=buyer("BAAINBw", "DE", "de-1"), estimated_value=Money(Decimal("60000000"), "EUR"), categories=("air_missile_defence", "air_systems")),
        competition("pl1", "p-pl1", days_ago(TODAY, 15), buyer=buyer("AU", "PL", "pl-1"), estimated_value=Money(Decimal("4000000"), "PLN")),
        competition("pl0", "p-pl0", days_ago(TODAY, 45), buyer=buyer("AU", "PL", "pl-1"), estimated_value=Money(Decimal("4000000"), "PLN")),
        # results: one in window with value, one without value, one in previous window
        result("r1", "p-se3", days_ago(TODAY, 2), value=Money(Decimal("900000"), "EUR"), tenders=(3,), winners=(Winner("Saab", "556036-0793", "SE", "large"),)),
        result("r2", "p-pl0", days_ago(TODAY, 4), value=None, tenders=(1, 4), statuses=("selec-w", "clos-nw")),
        result("r0", "p-old", days_ago(TODAY, 40), value=Money(Decimal("100000"), "EUR"), tenders=(1,)),
    ]


def test_new_competitions_count_unique_procedures_not_versions_or_changes() -> None:
    index = ProcedureIndex.build(_market_notices())
    metric = new_competitions(index, TODAY, 30)
    assert metric.value == 4  # se1, se2, de1, pl1
    assert metric.previous == 2  # se3, pl0
    assert metric.change_pct == 100.0
    assert new_competitions(index, TODAY, 90).value == 6


def test_estimated_value_uses_latest_version_and_reports_coverage() -> None:
    index = ProcedureIndex.build(_market_notices())
    metric = estimated_value(index, TODAY, 30, FX)
    # se1 latest version 2.5m SEK = 250k EUR; de1 60m; pl1 4m PLN = 1m; se2 unknown
    assert metric.value_eur == Decimal("61250000.00")
    assert metric.sample_size == 4
    assert metric.covered == 3
    assert metric.coverage_pct == 75.0
    assert metric.previous_eur == Decimal("2000000.00")  # se3 1m EUR + pl0 1m


def test_award_value_and_count() -> None:
    index = ProcedureIndex.build(_market_notices())
    value = award_value(index, TODAY, 30, FX)
    assert value.value_eur == Decimal("900000.00")
    assert value.sample_size == 2 and value.covered == 1
    assert value.previous_eur == Decimal("100000.00")
    count = awards_count(index, TODAY, 30)
    assert count.value == 2 and count.previous == 1


def test_rank_by_country_with_ties_and_previous_period() -> None:
    index = ProcedureIndex.build(_market_notices())
    entries = rank_by(index, TODAY, FX, lambda p: [p.country or "??"], str, days=90)
    assert [(e.key, e.rank) for e in entries] == [("DE", 1), ("PL", 2), ("SE", 3)]
    de = entries[0]
    assert de.value_eur == Decimal("60000000.00") and de.procedures == 1
    assert de.previous_value_eur is None and de.change_pct is None
    ranking = top_ranking(entries, "market countries", limit=2)
    assert ranking.population_size == 3 and len(ranking.entries) == 2
    assert ranking.leader is de

    tie_a = competition("a", "pa", days_ago(TODAY, 1), buyer=buyer("A", "AT", "a"), estimated_value=Money(Decimal("5"), "EUR"))
    tie_b = competition("b", "pb", days_ago(TODAY, 1), buyer=buyer("B", "BE", "b"), estimated_value=Money(Decimal("5"), "EUR"))
    tied = rank_by(ProcedureIndex.build([tie_a, tie_b]), TODAY, FX, lambda p: [p.country or "??"], str)
    assert [(e.key, e.rank) for e in tied] == [("AT", 1), ("BE", 1)]


def test_growth_ranking_applies_minimum_activity() -> None:
    today = TODAY
    notices = []
    # FI: 6 procedures now (>=5), 3 before -> +100 %
    for i in range(6):
        notices.append(competition(f"fi{i}", f"p-fi{i}", days_ago(today, 10), buyer=buyer("PV", "FI", "fi"), estimated_value=Money(Decimal("100"), "EUR")))
    for i in range(3):
        notices.append(competition(f"fi-old{i}", f"p-fi-old{i}", days_ago(today, 100), buyer=buyer("PV", "FI", "fi"), estimated_value=Money(Decimal("100"), "EUR")))
    # EE: 1 tiny procedure now, 1 before -> +900 % but not eligible
    notices.append(competition("ee1", "p-ee1", days_ago(today, 10), buyer=buyer("RKIK", "EE", "ee"), estimated_value=Money(Decimal("1000"), "EUR")))
    notices.append(competition("ee0", "p-ee0", days_ago(today, 100), buyer=buyer("RKIK", "EE", "ee"), estimated_value=Money(Decimal("100"), "EUR")))
    # DE: 1 procedure worth 60m now (eligible by value), 30m before -> +100 %
    notices.append(competition("de1", "p-de1", days_ago(today, 10), buyer=buyer("B", "DE", "de"), estimated_value=Money(Decimal("60000000"), "EUR")))
    notices.append(competition("de0", "p-de0", days_ago(today, 100), buyer=buyer("B", "DE", "de"), estimated_value=Money(Decimal("30000000"), "EUR")))
    entries = rank_by(ProcedureIndex.build(notices), today, FX, lambda p: [p.country or "??"], str)
    growth = growth_ranking(entries, "eligible countries")
    assert [(e.key, e.change_pct, e.rank) for e in growth.entries] == [("DE", 100.0, 1), ("FI", 100.0, 2)]
    assert growth.population_size == 2
    change = largest_change(entries)
    assert change is not None and change.key == "DE" and change.change_eur == Decimal("30000000.00")


def test_process_metrics_definitions() -> None:
    notices = [
        competition("c1", "p1", date(2026, 1, 1)),
        result("r1", "p1", date(2026, 4, 11), tenders=(3, 1), statuses=("selec-w", "selec-w")),
        result("r2", "p2", date(2026, 5, 1), tenders=(1,), statuses=("clos-nw",)),
        result("r3", "p3", date(2026, 6, 1)),  # no statistics at all
        result("r4", "p4", date(2025, 1, 1), tenders=(9,)),  # outside 365d
    ]
    process = process_metrics(ProcedureIndex.build(notices), TODAY)
    assert process.median_tenders_365d.value == 1
    assert process.median_tenders_365d.sample_size == 3
    assert process.median_tenders_365d.coverage == Coverage(2, 3)
    assert process.single_bid_share_365d.pct == 66.7
    assert process.single_bid_share_365d.numerator == 2
    assert process.median_time_to_result_365d.value == 100
    assert process.median_time_to_result_365d.coverage == Coverage(1, 3)
    assert process.non_award_share_365d.pct == 33.3
    assert process.non_award_share_365d.denominator == 3


def test_market_metrics_assembles_rankings_and_texts(taxonomy: Taxonomy) -> None:
    market = market_metrics(ProcedureIndex.build(_market_notices()), TODAY, FX, taxonomy)
    assert market.new_competitions_30d.value == 4
    assert market.country_ranking_90d.leader is not None
    assert market.country_ranking_90d.leader.key == "DE"
    assert market.category_ranking_90d.leader is not None
    assert market.category_ranking_90d.leader.key == "air_missile_defence"
    assert market.category_ranking_90d.leader.label == "Air & missile defence"
    assert market.snapshot_text == "6 competitions / 90d · EUR 63m"
    assert market.country_ranking_text == "DE EUR 60m · PL EUR 2.0m · SE EUR 1.2m"
    assert market.process.median_tenders_365d.sample_size == 4
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: ImportError for the new names.

- [ ] **Step 3: Append the implementation to `metrics.py`**

Add these imports at the top of the module: `from collections.abc import Callable`, `from dataclasses import replace`, and from `.const`: `GROWTH_MIN_PROCEDURES, GROWTH_MIN_VALUE_EUR, RANKING_LIMIT, RECENT_ITEMS_LIMIT`. Then append:

```python
# --------------------------------------------------------------------------- periods

type KeyFn = Callable[[ProcedureSummary], Iterable[str]]
type LabelFn = Callable[[str], str]


def procedures_started_in(index: ProcedureIndex, window: Window) -> list[ProcedureSummary]:
    """Procedures whose first original competition was published in the window."""
    return [
        p
        for p in index.procedures.values()
        if p.first_competition is not None and window.contains(p.first_competition)
    ]


def results_in(index: ProcedureIndex, window: Window) -> list[ProcurementNotice]:
    return [n for n in index.results() if window.contains(n.publication_date)]


def new_competitions(index: ProcedureIndex, today: date, days: int) -> CountMetric:
    return CountMetric(
        len(procedures_started_in(index, current_window(today, days))),
        len(procedures_started_in(index, previous_window(today, days))),
        days,
    )


def awards_count(index: ProcedureIndex, today: date, days: int) -> CountMetric:
    return CountMetric(
        len(results_in(index, current_window(today, days))),
        len(results_in(index, previous_window(today, days))),
        days,
    )


def _sum_eur(
    items: Iterable[tuple[Money | None, date]], fx: FxRateTable
) -> tuple[Decimal | None, int, int]:
    total = Decimal(0)
    sample = covered = 0
    for money, on in items:
        sample += 1
        eur = value_in_eur(money, on, fx)
        if eur is not None:
            covered += 1
            total += eur
    return (total if covered else None), sample, covered


def _estimated_items(
    procedures: Iterable[ProcedureSummary], today: date
) -> list[tuple[Money | None, date]]:
    return [(p.estimated_value, p.estimated_value_date or today) for p in procedures]


def estimated_value(index: ProcedureIndex, today: date, days: int, fx: FxRateTable) -> ValueMetric:
    total, sample, covered = _sum_eur(
        _estimated_items(procedures_started_in(index, current_window(today, days)), today), fx
    )
    previous, _, _ = _sum_eur(
        _estimated_items(procedures_started_in(index, previous_window(today, days)), today), fx
    )
    return ValueMetric(total, previous, sample, covered, days)


def award_value(index: ProcedureIndex, today: date, days: int, fx: FxRateTable) -> ValueMetric:
    total, sample, covered = _sum_eur(
        ((r.result_value, r.award_date) for r in results_in(index, current_window(today, days))), fx
    )
    previous, _, _ = _sum_eur(
        ((r.result_value, r.award_date) for r in results_in(index, previous_window(today, days))), fx
    )
    return ValueMetric(total, previous, sample, covered, days)


# --------------------------------------------------------------------------- rankings


def rank_by(
    index: ProcedureIndex,
    today: date,
    fx: FxRateTable,
    key_fn: KeyFn,
    label_fn: LabelFn,
    *,
    days: int = 90,
) -> list[RankingEntry]:
    """Competition-rank keys by normalized estimated value of new competitions (plan §16.3)."""

    def accumulate(window: Window) -> dict[str, tuple[Decimal, int, int]]:
        acc: dict[str, tuple[Decimal, int, int]] = {}
        for procedure in procedures_started_in(index, window):
            eur = value_in_eur(procedure.estimated_value, procedure.estimated_value_date or today, fx)
            for key in key_fn(procedure):
                total, count, covered = acc.get(key, (Decimal(0), 0, 0))
                if eur is not None:
                    total += eur
                    covered += 1
                acc[key] = (total, count + 1, covered)
        return acc

    current = accumulate(current_window(today, days))
    previous = accumulate(previous_window(today, days))
    rows: list[tuple[str, Decimal | None, int, Decimal | None, int]] = []
    for key in set(current) | set(previous):
        total, count, covered = current.get(key, (Decimal(0), 0, 0))
        prev_total, prev_count, prev_covered = previous.get(key, (Decimal(0), 0, 0))
        rows.append(
            (key, total if covered else None, count, prev_total if prev_covered else None, prev_count)
        )
    rows.sort(key=lambda r: (r[1] is None, -(r[1] or Decimal(0)), -r[2], r[0]))
    entries: list[RankingEntry] = []
    rank = 0
    last: tuple[Decimal | None, int] | None = None
    for position, (key, value, count, prev_value, prev_count) in enumerate(rows, 1):
        if (value, count) != last:
            rank = position
            last = (value, count)
        entries.append(
            RankingEntry(key, label_fn(key), rank, value, count, prev_value, prev_count, pct_change(value, prev_value))
        )
    return entries


def top_ranking(entries: Sequence[RankingEntry], population: str, limit: int = RANKING_LIMIT) -> Ranking:
    return Ranking(tuple(entries[:limit]), population, len(entries))


def is_growth_eligible(entry: RankingEntry) -> bool:
    """Minimum activity in the current period (plan §16.3)."""
    return entry.procedures >= GROWTH_MIN_PROCEDURES or (
        entry.value_eur is not None and entry.value_eur >= GROWTH_MIN_VALUE_EUR
    )


def _was_active(entry: RankingEntry) -> bool:
    return entry.previous_procedures >= GROWTH_MIN_PROCEDURES or (
        entry.previous_value_eur is not None and entry.previous_value_eur >= GROWTH_MIN_VALUE_EUR
    )


def growth_ranking(entries: Sequence[RankingEntry], population: str) -> Ranking:
    eligible = [e for e in entries if is_growth_eligible(e) and e.change_pct is not None]
    eligible.sort(key=lambda e: (-(e.change_pct or 0), e.key))
    ranked = tuple(replace(e, rank=i) for i, e in enumerate(eligible, 1))
    return Ranking(ranked[:RANKING_LIMIT], population, len(eligible))


def largest_change(entries: Sequence[RankingEntry]) -> RankingEntry | None:
    """Largest absolute EUR change among keys active in either period."""
    candidates = [
        e for e in entries if (is_growth_eligible(e) or _was_active(e)) and e.change_eur is not None
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda e: (-abs(e.change_eur or Decimal(0)), e.key))


# --------------------------------------------------------------------------- process metrics


def process_metrics(index: ProcedureIndex, today: date) -> ProcessMetrics:
    """Competition/process metrics over the last 365 days (plan §17, D7)."""
    window = current_window(today, 365)
    results = results_in(index, window)
    observations = [
        count for r in results if r.tender_statistics for count in r.tender_statistics.tender_counts
    ]
    with_counts = sum(1 for r in results if r.tender_statistics and r.tender_statistics.tender_counts)
    count_coverage = Coverage(with_counts, len(results))
    single = sum(1 for count in observations if count == 1)

    decided = [
        p for p in index.procedures.values() if p.first_result is not None and window.contains(p.first_result)
    ]
    durations = [p.time_to_result_days for p in decided if p.time_to_result_days is not None]

    statuses = [
        s for r in results if r.tender_statistics for s in r.tender_statistics.selection_statuses
    ]
    with_status = sum(1 for r in results if r.tender_statistics and r.tender_statistics.selection_statuses)
    closed_no_winner = statuses.count("clos-nw")
    decided_lots = closed_no_winner + statuses.count("selec-w")

    return ProcessMetrics(
        median_tenders_365d=MedianMetric(median(observations), len(observations), count_coverage),
        single_bid_share_365d=ShareMetric(pct(single, len(observations)), single, len(observations), count_coverage),
        median_time_to_result_365d=MedianMetric(median(durations), len(durations), Coverage(len(durations), len(decided))),
        non_award_share_365d=ShareMetric(pct(closed_no_winner, decided_lots), closed_no_winner, decided_lots, Coverage(with_status, len(results))),
    )


# --------------------------------------------------------------------------- market


def market_snapshot_text(competitions_90d: CountMetric, value_90d: ValueMetric) -> str:
    text = f"{competitions_90d.value} competitions / 90d · {format_eur(value_90d.value_eur)}"
    if value_90d.change_pct is not None:
        text += f" · {value_90d.change_pct:+.1f}% vs previous 90d"
    return text


def country_ranking_text(ranking: Ranking) -> str:
    parts = [f"{e.key} {format_eur(e.value_eur)}" for e in ranking.entries[:5]]
    return " · ".join(parts) if parts else "no data"


def market_metrics(index: ProcedureIndex, today: date, fx: FxRateTable, taxonomy: Taxonomy) -> MarketMetrics:
    countries = rank_by(index, today, fx, lambda p: [p.country or "??"], str)
    categories = rank_by(index, today, fx, lambda p: sorted(p.categories), taxonomy.label)
    country_population = "market countries with new competitions in the last 90 or previous 90 days"
    category_population = "strategic categories with new competitions in the last 90 or previous 90 days"
    country_ranking = top_ranking(countries, country_population)
    competitions_90d = new_competitions(index, today, 90)
    value_90d = estimated_value(index, today, 90, fx)
    return MarketMetrics(
        new_competitions_30d=new_competitions(index, today, 30),
        new_competitions_90d=competitions_90d,
        estimated_value_30d=estimated_value(index, today, 30, fx),
        estimated_value_90d=value_90d,
        award_value_30d=award_value(index, today, 30, fx),
        award_value_90d=award_value(index, today, 90, fx),
        country_ranking_90d=country_ranking,
        country_growth_90d=growth_ranking(countries, f"eligible {country_population}"),
        category_ranking_90d=top_ranking(categories, category_population),
        category_growth_90d=growth_ranking(categories, f"eligible {category_population}"),
        largest_country_change_90d=largest_change(countries),
        largest_category_change_90d=largest_change(categories),
        process=process_metrics(index, today),
        snapshot_text=market_snapshot_text(competitions_90d, value_90d),
        country_ranking_text=country_ranking_text(country_ranking),
    )
```

- [ ] **Step 4: Run tests, lint, type-check**

Run: `uv run pytest tests/test_metrics.py -v && uv run ruff check . && uv run mypy custom_components/edp_radar`
Expected: all pass (14 tests). Hand-check the expected numbers in `_market_notices` if any assertion fails: the dataset is small enough to recompute on paper; fix the *test expectation* only when the paper calculation agrees with the code, otherwise fix the code.

- [ ] **Step 5: Commit**

```bash
git add custom_components/edp_radar/metrics.py tests/test_metrics.py
git commit -m "feat(metrics): add market counts, EUR values, rankings, growth and process metrics

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: External radar and own public footprint

**Files:**
- Modify: `custom_components/edp_radar/metrics.py` (append), `tests/test_metrics.py` (append)

**Interfaces:**
- Produces: `highlight(notice, fx) -> NoticeHighlight`, `external_metrics(index, today, fx, taxonomy) -> ExternalMetrics`, `external_latest_text(highlight, taxonomy) -> str`, `organisation_metrics(index, today, fx) -> OrganisationMetrics`, `latest_notices_in(index, window) -> list[ProcurementNotice]`.

- [ ] **Step 1: Append the failing tests**

```python
# --- Task 13: external radar & own footprint --------------------------------
from custom_components.edp_radar.metrics import (  # noqa: E402
    external_metrics,
    highlight,
    organisation_metrics,
)
from custom_components.edp_radar.models import NoticeStage  # noqa: E402


def test_highlight_uses_estimated_value_for_competitions_and_result_value_for_results() -> None:
    comp = competition("c", "p", TODAY, estimated_value=Money(Decimal("100"), "SEK"))
    h = highlight(comp, FX)
    assert (h.original_amount, h.original_currency, h.value_eur) == (Decimal("100"), "SEK", Decimal("10.00"))
    res = result("r", "p", TODAY, value=Money(Decimal("40"), "PLN"), decision_dates=(date(2026, 8, 1),))
    assert highlight(res, FX).value_eur == Decimal("10.00")
    assert highlight(res, FX).stage is NoticeStage.RESULT


def test_external_metrics_7d(taxonomy: Taxonomy) -> None:
    notices = [
        competition("a", "pa", days_ago(TODAY, 1), buyer=buyer("A", "DE", "a"), estimated_value=Money(Decimal("640000000"), "EUR"), categories=("air_missile_defence",)),
        competition("b", "pb", days_ago(TODAY, 6), buyer=buyer("B", "PL", "b"), estimated_value=None),
        competition("c", "pc", days_ago(TODAY, 8), buyer=buyer("C", "FR", "c")),  # outside 7d
        result("r", "pc", days_ago(TODAY, 2), value=Money(Decimal("5000000"), "EUR")),
        result("r-old", "px", days_ago(TODAY, 9), value=Money(Decimal("9000000"), "EUR")),
    ]
    external = external_metrics(ProcedureIndex.build(notices), TODAY, FX, taxonomy)
    assert external.new_competitions_7d == 2
    assert [h.notice_id for h in external.recent_competitions] == ["a", "b"]
    assert external.largest_competition_7d is not None
    assert external.largest_competition_7d.notice_id == "a"
    assert external.largest_award_7d is not None
    assert external.largest_award_7d.notice_id == "r"
    assert external.latest_text == f"DE · Air & missile defence · EUR 640m · published {days_ago(TODAY, 1).isoformat()}"


def test_external_metrics_without_values_is_unknown(taxonomy: Taxonomy) -> None:
    external = external_metrics(ProcedureIndex.build([competition("b", "pb", TODAY, estimated_value=None)]), TODAY, FX, taxonomy)
    assert external.largest_competition_7d is None
    assert external.largest_award_7d is None
    assert external.new_competitions_7d == 1
    assert external.latest_text is not None and external.latest_text.startswith("SE · Land systems · EUR n/a")
    assert external_metrics(ProcedureIndex.build([]), TODAY, FX, taxonomy).latest_text is None


def test_organisation_metrics_counts_changes_and_modifications() -> None:
    comp = competition("c1", "p1", days_ago(TODAY, 10))
    notices = [
        comp,
        change_of(comp, published=days_ago(TODAY, 5)),
        change_of(comp, published=days_ago(TODAY, 40), notice_id="c1-chg", version=1),
        result("r1", "p1", days_ago(TODAY, 3), value=Money(Decimal("2000000"), "SEK"), tenders=(2,)),
        make_notice(notice_id="m1", stage=NoticeStage.MODIFICATION, publication_date=days_ago(TODAY, 200)),
        make_notice(notice_id="m2", stage=NoticeStage.MODIFICATION, publication_date=days_ago(TODAY, 400)),
    ]
    own = organisation_metrics(ProcedureIndex.build(notices), TODAY, FX)
    assert own.competitions_30d.value == 1
    assert own.estimated_value_30d.value_eur == Decimal("1000000.00")
    assert own.awards_30d.value == 1
    assert own.award_value_30d.value_eur == Decimal("200000.00")
    assert own.changes_30d.value == 1 and own.changes_30d.previous == 1
    assert own.modifications_365d.value == 1 and own.modifications_365d.previous == 1
    assert own.process.median_tenders_365d.value == 2
    assert [h.notice_id for h in own.recent][:2] == ["r1", "c1"]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_metrics.py -v -k "highlight or external or organisation"`
Expected: ImportError.

- [ ] **Step 3: Append the implementation**

```python
# --------------------------------------------------------------------------- external radar


def highlight(notice: ProcurementNotice, fx: FxRateTable) -> NoticeHighlight:
    if notice.stage is NoticeStage.RESULT:
        money, on = notice.result_value, notice.award_date
    else:
        money, on = notice.estimated_value, notice.publication_date
    return NoticeHighlight(
        notice_id=notice.notice_id,
        publication_number=notice.publication_number,
        procedure_id=notice.procedure_id,
        title=notice.title,
        buyer=notice.buyer.name,
        country=notice.buyer.country,
        publication_date=notice.publication_date,
        stage=notice.stage,
        original_amount=money.amount if money else None,
        original_currency=money.currency if money else None,
        value_eur=value_in_eur(money, on, fx),
        categories=notice.categories,
        source_url=notice.source_url,
    )


def _by_significance(h: NoticeHighlight) -> tuple[bool, Decimal, date, str]:
    return (h.value_eur is None, -(h.value_eur or Decimal(0)), h.publication_date, h.notice_id)


def _largest(highlights: Iterable[NoticeHighlight]) -> NoticeHighlight | None:
    valued = [h for h in highlights if h.value_eur is not None]
    if not valued:
        return None
    return min(valued, key=lambda h: (-(h.value_eur or Decimal(0)), h.publication_date, h.notice_id))


def latest_notices_in(index: ProcedureIndex, window: Window) -> list[ProcurementNotice]:
    return [n for n in index.notices if window.contains(n.publication_date)]


def external_latest_text(h: NoticeHighlight, taxonomy: Taxonomy) -> str:
    category = taxonomy.label(h.categories[0]) if h.categories else "Unclassified"
    return f"{h.country or '??'} · {category} · {format_eur(h.value_eur)} · published {h.publication_date.isoformat()}"


def external_metrics(index: ProcedureIndex, today: date, fx: FxRateTable, taxonomy: Taxonomy) -> ExternalMetrics:
    window = current_window(today, 7)
    competitions = [
        p.latest_competition for p in procedures_started_in(index, window) if p.latest_competition is not None
    ]
    highlights = [highlight(n, fx) for n in competitions]
    recent = sorted(highlights, key=lambda h: (_by_significance(h)[0], _by_significance(h)[1], -h.publication_date.toordinal(), h.notice_id))
    awards = [highlight(r, fx) for r in results_in(index, window)]
    latest = max(highlights, key=lambda h: (h.publication_date, h.value_eur or Decimal(0)), default=None)
    return ExternalMetrics(
        new_competitions_7d=len(competitions),
        recent_competitions=tuple(recent[:RECENT_ITEMS_LIMIT]),
        largest_competition_7d=_largest(highlights),
        largest_award_7d=_largest(awards),
        latest_text=external_latest_text(latest, taxonomy) if latest else None,
    )


# --------------------------------------------------------------------------- own public footprint


def organisation_metrics(index: ProcedureIndex, today: date, fx: FxRateTable) -> OrganisationMetrics:
    changes_now = [c for c in index.changes if current_window(today, 30).contains(c.publication_date)]
    changes_before = [c for c in index.changes if previous_window(today, 30).contains(c.publication_date)]
    modifications = [n for n in index.notices if n.stage is NoticeStage.MODIFICATION]
    mods_now = [m for m in modifications if current_window(today, 365).contains(m.publication_date)]
    mods_before = [m for m in modifications if previous_window(today, 365).contains(m.publication_date)]
    recent = sorted(index.notices, key=lambda n: (n.publication_date, n.notice_version), reverse=True)
    return OrganisationMetrics(
        competitions_30d=new_competitions(index, today, 30),
        estimated_value_30d=estimated_value(index, today, 30, fx),
        awards_30d=awards_count(index, today, 30),
        award_value_30d=award_value(index, today, 30, fx),
        changes_30d=CountMetric(len(changes_now), len(changes_before), 30),
        modifications_365d=CountMetric(len(mods_now), len(mods_before), 365),
        process=process_metrics(index, today),
        recent=tuple(highlight(n, fx) for n in recent[:RECENT_ITEMS_LIMIT]),
    )
```

- [ ] **Step 4: Run tests, lint, type-check**

Run: `uv run pytest tests/test_metrics.py -v && uv run ruff check . && uv run mypy custom_components/edp_radar`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add custom_components/edp_radar/metrics.py tests/test_metrics.py
git commit -m "feat(metrics): add external radar highlights and own public footprint metrics

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 14: Peers, suppliers and pinned categories

**Files:**
- Modify: `custom_components/edp_radar/metrics.py` (append), `tests/test_metrics.py` (append)

**Interfaces:**
- Produces: `activity_rank(entries, key) -> int | None`, `value_percentile(entries, key) -> float | None`, `peer_metrics(config, relevant, market_countries_ranking: Sequence[RankingEntry], own: OrganisationMetrics | None, today, fx) -> PeerMetrics | None`, `supplier_metrics(index, today, fx) -> SupplierMetrics`, `category_metrics(index_all, notices, category_id, label, today, fx) -> CategoryMetrics`, `notices_for_procedures(notices, keys) -> list[ProcurementNotice]`.

- [ ] **Step 1: Append the failing tests**

```python
# --- Task 14: peers, suppliers, categories ----------------------------------
from custom_components.edp_radar.metrics import (  # noqa: E402
    activity_rank,
    category_metrics,
    peer_metrics,
    supplier_metrics,
    value_percentile,
)


def _entries() -> list:
    notices = [
        competition("de", "p-de", days_ago(TODAY, 10), buyer=buyer("B", "DE", "de"), estimated_value=Money(Decimal("300"), "EUR")),
        competition("pl", "p-pl", days_ago(TODAY, 10), buyer=buyer("A", "PL", "pl"), estimated_value=Money(Decimal("200"), "EUR")),
        competition("pl2", "p-pl2", days_ago(TODAY, 11), buyer=buyer("A", "PL", "pl"), estimated_value=None),
        competition("se", "p-se", days_ago(TODAY, 10), estimated_value=Money(Decimal("100"), "EUR")),
        competition("fi", "p-fi", days_ago(TODAY, 10), buyer=buyer("PV", "FI", "fi"), estimated_value=None),
    ]
    return rank_by(ProcedureIndex.build(notices), TODAY, FX, lambda p: [p.country or "??"], str)


def test_ranks_and_percentile() -> None:
    entries = _entries()
    assert [e.key for e in entries] == ["DE", "PL", "SE", "FI"]
    assert activity_rank(entries, "PL") == 1
    assert activity_rank(entries, "SE") == 2  # DE, SE, FI tie on 1 procedure
    assert activity_rank(entries, "XX") is None
    assert value_percentile(entries, "SE") == 50.0  # SE and FI(None→0) are <= SE
    assert value_percentile(entries, "DE") == 100.0
    assert value_percentile(entries, "XX") is None


def test_peer_metrics_by_country_and_deltas() -> None:
    notices = [
        result("r-se", "p-se", days_ago(TODAY, 10), tenders=(1, 1)),
        result("r-fi", "p-fi", days_ago(TODAY, 10), buyer=buyer("PV", "FI", "fi"), tenders=(4, 2, 1)),
        result("r-dk", "p-dk", days_ago(TODAY, 10), buyer=buyer("FMI", "DK", "dk"), tenders=(3,)),
    ]
    config = MetricsConfig(peer_countries=frozenset({"FI", "DK"}), selected_country="SE")
    own = organisation_metrics(ProcedureIndex.build([notices[0]]), TODAY, FX)
    peers = peer_metrics(config, notices, _entries(), own, TODAY, FX)
    assert peers is not None
    assert peers.population == "configured peer countries" and peers.population_size == 2
    assert peers.process.median_tenders_365d.value == 2.5
    assert peers.process.single_bid_share_365d.pct == 25.0
    assert peers.single_bid_delta_pp == 75.0
    assert peers.median_tenders_delta == -1.5
    assert peers.time_to_result_delta_days is None
    assert peers.selected_country == "SE" and peers.value_rank_90d == 3
    assert peers.rank_population_size == 4


def test_peer_metrics_by_organisation_and_none_when_unconfigured() -> None:
    notices = [result("r-x", "p-x", days_ago(TODAY, 10), buyer=buyer("X", "NO", "no-1"), tenders=(2,))]
    peers = peer_metrics(MetricsConfig(peer_organisation_identifiers=frozenset({"no-1"})), notices, [], None, TODAY, FX)
    assert peers is not None and peers.population == "configured peer organisations"
    assert peers.process.median_tenders_365d.value == 2
    assert peers.single_bid_delta_pp is None
    assert peer_metrics(MetricsConfig(), notices, [], None, TODAY, FX) is None


def test_supplier_metrics_do_not_double_count_consortia() -> None:
    saab = Winner("Saab AB", "556036-0793", "SE", "large")
    bae = Winner("BAE Systems Hägglunds", "556028-3838", "SE", "large")
    notices = [
        result("r1", "p1", days_ago(TODAY, 10), value=Money(Decimal("100"), "EUR"), winners=(saab,)),
        result("r2", "p2", days_ago(TODAY, 20), value=Money(Decimal("300"), "EUR"), winners=(bae, saab)),
        result("r3", "p3", days_ago(TODAY, 30), value=Money(Decimal("50"), "EUR"), winners=(bae,)),
        result("r4", "p4", days_ago(TODAY, 30), value=None, winners=(bae,)),
        result("r5", "p5", days_ago(TODAY, 30), value=Money(Decimal("999"), "EUR"), winners=()),
        result("r6", "p6", days_ago(TODAY, 400), value=Money(Decimal("999"), "EUR"), winners=(saab,)),
    ]
    suppliers = supplier_metrics(ProcedureIndex.build(notices), TODAY, FX)
    assert [(s.name, s.award_value_eur, s.awards, s.rank) for s in suppliers.top_suppliers] == [
        ("BAE Systems Hägglunds + Saab AB", Decimal("300.00"), 1, 1),
        ("Saab AB", Decimal("100.00"), 1, 2),
        ("BAE Systems Hägglunds", Decimal("50.00"), 1, 3),
    ]
    assert suppliers.total_award_value_eur == Decimal("450.00")
    assert suppliers.top5_share_pct == 100.0
    assert suppliers.groups == 3
    assert suppliers.coverage == Coverage(3, 4)
    assert suppliers.top_suppliers[0].country == "SE"


def test_category_metrics_use_procedure_level_membership(taxonomy: Taxonomy) -> None:
    notices = [
        competition("c1", "p1", days_ago(TODAY, 10), categories=("naval_maritime",), estimated_value=Money(Decimal("10"), "EUR")),
        result("r1", "p1", days_ago(TODAY, 5), categories=(), value=Money(Decimal("7"), "EUR")),
        competition("c2", "p2", days_ago(TODAY, 10), categories=("cyber_it",)),
    ]
    index_all = ProcedureIndex.build(notices)
    naval = category_metrics(index_all, notices, "naval_maritime", taxonomy.label("naval_maritime"), TODAY, FX)
    assert naval.label == "Naval & maritime"
    assert naval.competitions_30d.value == 1
    assert naval.estimated_value_90d.value_eur == Decimal("10.00")
    assert naval.award_value_90d.value_eur == Decimal("7.00")  # result inherits membership via procedure
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_metrics.py -v -k "rank or peer or supplier or category"`
Expected: ImportError.

- [ ] **Step 3: Append the implementation**

```python
# --------------------------------------------------------------------------- peers


def activity_rank(entries: Sequence[RankingEntry], key: str) -> int | None:
    """Competition rank by number of new procedures."""
    ordered = sorted(entries, key=lambda e: (-e.procedures, e.key))
    rank = 0
    last: int | None = None
    for position, entry in enumerate(ordered, 1):
        if entry.procedures != last:
            rank = position
            last = entry.procedures
        if entry.key == key:
            return rank
    return None


def value_percentile(entries: Sequence[RankingEntry], key: str) -> float | None:
    """Share of the population whose value is <= the key's value (inclusive percentile rank)."""
    selected = next((e for e in entries if e.key == key), None)
    if selected is None or not entries:
        return None
    own_value = selected.value_eur or Decimal(0)
    below = sum(1 for e in entries if (e.value_eur or Decimal(0)) <= own_value)
    return pct(below, len(entries))


def _delta(own: float | None, peer: float | None) -> float | None:
    if own is None or peer is None:
        return None
    return round(own - peer, 1)


def peer_metrics(
    config: MetricsConfig,
    relevant: Sequence[ProcurementNotice],
    market_countries_ranking: Sequence[RankingEntry],
    own: OrganisationMetrics | None,
    today: date,
    fx: FxRateTable,
) -> PeerMetrics | None:
    if config.peer_organisation_identifiers:
        population = "configured peer organisations"
        size = len(config.peer_organisation_identifiers)
        notices = [n for n in relevant if set(n.buyer.identifiers) & config.peer_organisation_identifiers]
    elif config.peer_countries:
        population = "configured peer countries"
        size = len(config.peer_countries)
        notices = [n for n in relevant if n.buyer.country in config.peer_countries]
    elif config.selected_country:
        population = "none"
        size = 0
        notices = []
    else:
        return None
    process = process_metrics(ProcedureIndex.build(notices), today)
    selected = config.selected_country
    entry = next((e for e in market_countries_ranking if e.key == selected), None)
    return PeerMetrics(
        population=population,
        population_size=size,
        selected_country=selected,
        rank_population="market countries with new competitions in the last 90 or previous 90 days",
        rank_population_size=len(market_countries_ranking),
        value_rank_90d=entry.rank if entry else None,
        activity_rank_90d=activity_rank(market_countries_ranking, selected) if selected else None,
        value_percentile_90d=value_percentile(market_countries_ranking, selected) if selected else None,
        process=process,
        single_bid_delta_pp=_delta(own.process.single_bid_share_365d.pct, process.single_bid_share_365d.pct) if own else None,
        median_tenders_delta=_delta(own.process.median_tenders_365d.value, process.median_tenders_365d.value) if own else None,
        time_to_result_delta_days=_delta(own.process.median_time_to_result_365d.value, process.median_time_to_result_365d.value) if own else None,
    )


# --------------------------------------------------------------------------- suppliers


def supplier_metrics(index: ProcedureIndex, today: date, fx: FxRateTable) -> SupplierMetrics:
    """Top supplier groups by normalized award value; a consortium is one group (plan §18, §41)."""
    results = [r for r in results_in(index, current_window(today, 365)) if r.winners]
    groups: dict[str, tuple[str, str | None, Decimal, int]] = {}
    covered = 0
    for notice in results:
        eur = value_in_eur(notice.result_value, notice.award_date, fx)
        if eur is None:
            continue
        covered += 1
        winners = sorted(notice.winners, key=lambda w: w.identity_key)
        key = "+".join(w.identity_key for w in winners)
        name = " + ".join(w.name or w.identity_key for w in winners)
        countries = {w.country for w in winners}
        country = countries.pop() if len(countries) == 1 else None
        _, _, total, awards = groups.get(key, (name, country, Decimal(0), 0))
        groups[key] = (name, country, total + eur, awards + 1)
    ordered = sorted(groups.items(), key=lambda item: (-item[1][2], item[0]))
    total = sum((g[2] for g in groups.values()), Decimal(0)) if groups else None
    top5 = sum((g[2] for _, g in ordered[:5]), Decimal(0))
    return SupplierMetrics(
        top_suppliers=tuple(
            SupplierEntry(key, name, country, rank, value, awards)
            for rank, (key, (name, country, value, awards)) in enumerate(ordered[:RANKING_LIMIT], 1)
        ),
        top5_share_pct=round(float(top5 / total * 100), 1) if total else None,
        total_award_value_eur=total,
        groups=len(groups),
        coverage=Coverage(covered, len(results)),
    )


# --------------------------------------------------------------------------- pinned categories


def notices_for_procedures(notices: Iterable[ProcurementNotice], keys: set[str]) -> list[ProcurementNotice]:
    return [n for n in notices if (n.procedure_id or f"notice:{n.notice_id}") in keys]


def category_metrics(
    index_all: ProcedureIndex,
    notices: Sequence[ProcurementNotice],
    category_id: str,
    label: str,
    today: date,
    fx: FxRateTable,
) -> CategoryMetrics:
    keys = {p.key for p in index_all.procedures.values() if category_id in p.categories}
    index = ProcedureIndex.build(notices_for_procedures(notices, keys))
    return CategoryMetrics(
        category_id=category_id,
        label=label,
        competitions_30d=new_competitions(index, today, 30),
        estimated_value_90d=estimated_value(index, today, 90, fx),
        award_value_90d=award_value(index, today, 90, fx),
    )
```

- [ ] **Step 4: Run tests, lint, type-check**

Run: `uv run pytest tests/test_metrics.py -v && uv run ruff check . && uv run mypy custom_components/edp_radar`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add custom_components/edp_radar/metrics.py tests/test_metrics.py
git commit -m "feat(metrics): add peer comparison, supplier landscape and pinned category metrics

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 15: Data quality, snapshot assembly, event facts and watchlist

**Files:**
- Modify: `custom_components/edp_radar/metrics.py` (append), `tests/test_metrics.py` (append)

**Interfaces:**
- Produces:
  - `data_quality(all_notices, relevant, excluded, parse_errors, fx, index_all) -> DataQualityMetrics`
  - `compute_snapshot(notices: Iterable[ProcurementNotice], fx: FxRateTable, config: MetricsConfig, today: date, *, taxonomy: Taxonomy, parse_errors: int = 0, bootstrap_complete: bool = True, computed_at: datetime | None = None) -> RadarSnapshot`
  - `event_type_for(notice) -> str | None` (`"new_competition"`, `"change"`, `"result"`, `"contract_modification"`, else `None`)
  - `notice_event_attributes(notice, fx) -> dict[str, Any]` (JSON-safe: dates ISO, Decimals as float)
  - `watchlist_matches(notice, watchlist, fx) -> bool` (False when the watchlist is empty)

- [ ] **Step 1: Append the failing tests**

```python
# --- Task 15: quality, snapshot, events -------------------------------------
from datetime import UTC, datetime  # noqa: E402

from custom_components.edp_radar.metrics import (  # noqa: E402
    compute_snapshot,
    event_type_for,
    notice_event_attributes,
    watchlist_matches,
)
from custom_components.edp_radar.models import ChangeInfo  # noqa: E402


def test_compute_snapshot_end_to_end(taxonomy: Taxonomy) -> None:
    cpb = make_notice(notice_id="cpb", buyer=buyer("CPB", "HR", "1", count=500), publication_date=days_ago(TODAY, 3))
    own_comp = competition("own", "p-own", days_ago(TODAY, 4))
    de = competition("de", "p-de", days_ago(TODAY, 2), buyer=buyer("B", "DE", "de"), estimated_value=Money(Decimal("60000000"), "EUR"), categories=("air_systems",))
    no = competition("no", "p-no", days_ago(TODAY, 2), buyer=buyer("FMA", "NO", "no"))
    unparsed = competition("x", "p-x", days_ago(TODAY, 2), match_reasons=frozenset())
    config = MetricsConfig(
        market_countries=frozenset({"SE", "DE"}),
        own_organisation=OwnOrganisation.from_options(["202100-0340"], "SE", "FMV", []),
        peer_countries=frozenset({"NO"}),
        selected_country="SE",
        pinned_categories=("air_systems",),
    )
    snapshot = compute_snapshot([cpb, own_comp, de, no, unparsed], FX, config, TODAY, taxonomy=taxonomy, parse_errors=2, computed_at=datetime(2026, 9, 12, 12, tzinfo=UTC))
    assert snapshot.today == TODAY and snapshot.bootstrap_complete is True
    assert snapshot.market.new_competitions_30d.value == 2  # own + de (NO outside market, cpb excluded, x irrelevant)
    assert snapshot.external.new_competitions_7d == 1  # de only: own excluded
    assert snapshot.own is not None and snapshot.own.competitions_30d.value == 1
    assert snapshot.peers is not None and snapshot.peers.population_size == 1
    assert snapshot.peers.value_rank_90d == 2
    assert set(snapshot.categories) == {"air_systems"}
    assert snapshot.categories["air_systems"].competitions_30d.value == 1
    q = snapshot.quality
    assert q.stored_versions == 5 and q.stored_notices == 5 and q.relevant_notices == 3
    assert q.excluded_central_purchasing == 1 and q.parse_errors == 2
    assert q.records_by_stage == {"competition": 5}
    assert q.estimated_value_coverage == Coverage(5, 5)
    assert q.fx_coverage == Coverage(5, 5)
    assert q.unclassified_share_pct == 0.0
    assert q.latest_publication_date == days_ago(TODAY, 2)
    assert q.fx_latest_date == date(2026, 12, 31)
    assert snapshot.suppliers.groups == 0


def test_compute_snapshot_without_own_or_peers(taxonomy: Taxonomy) -> None:
    snapshot = compute_snapshot([], FX, MetricsConfig(), TODAY, taxonomy=taxonomy, bootstrap_complete=False)
    assert snapshot.own is None and snapshot.peers is None
    assert snapshot.market.new_competitions_30d.value == 0
    assert snapshot.market.estimated_value_90d.value_eur is None
    assert snapshot.quality.unclassified_share_pct is None
    assert snapshot.bootstrap_complete is False


def test_event_type_and_attributes() -> None:
    comp = competition("c", "p", TODAY, estimated_value=Money(Decimal("100"), "SEK"))
    assert event_type_for(comp) == "new_competition"
    assert event_type_for(change_of(comp, published=TODAY)) == "change"
    assert event_type_for(result("r", "p", TODAY)) == "result"
    assert event_type_for(make_notice(stage=NoticeStage.MODIFICATION)) == "contract_modification"
    assert event_type_for(make_notice(stage=NoticeStage.PLANNING)) is None
    attrs = notice_event_attributes(comp, FX)
    assert attrs["notice_id"] == "c" and attrs["stage"] == "competition"
    assert attrs["publication_date"] == TODAY.isoformat()
    assert attrs["estimated_value"] == 100.0 and attrs["estimated_currency"] == "SEK"
    assert attrs["estimated_value_eur"] == 10.0
    assert attrs["result_value"] is None
    assert attrs["categories"] == ["land_systems"] and attrs["match_reasons"] == ["defence_buyer"]
    assert attrs["buyer"] == "FMV" and attrs["buyer_country"] == "SE"


def test_watchlist_matching() -> None:
    comp = competition("c", "p", TODAY, buyer=buyer("AU", "PL", "pl"), categories=("air_missile_defence",), estimated_value=Money(Decimal("600000000"), "EUR"))
    assert watchlist_matches(comp, WatchlistConfig(), FX) is False
    assert watchlist_matches(comp, WatchlistConfig(countries=frozenset({"PL"})), FX) is True
    assert watchlist_matches(comp, WatchlistConfig(countries=frozenset({"SE"})), FX) is False
    assert watchlist_matches(comp, WatchlistConfig(buyer_identifiers=frozenset({"pl"})), FX) is True
    assert watchlist_matches(comp, WatchlistConfig(categories=frozenset({"space"})), FX) is False
    assert watchlist_matches(comp, WatchlistConfig(countries=frozenset({"PL"}), min_estimated_value_eur=Decimal("500000000")), FX) is True
    assert watchlist_matches(comp, WatchlistConfig(min_estimated_value_eur=Decimal("700000000")), FX) is False
    assert watchlist_matches(comp, WatchlistConfig(min_award_value_eur=Decimal("1")), FX) is False
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_metrics.py -v -k "snapshot or event or watchlist"`
Expected: ImportError.

- [ ] **Step 3: Append the implementation**

Add `from collections import Counter`, `from datetime import UTC`, and `from typing import Any` to the imports. Append:

```python
# --------------------------------------------------------------------------- data quality


def data_quality(
    all_notices: Sequence[ProcurementNotice],
    relevant: Sequence[ProcurementNotice],
    excluded: int,
    parse_errors: int,
    fx: FxRateTable,
    index_all: ProcedureIndex,
) -> DataQualityMetrics:
    latest = index_all.notices
    competitions = index_all.competitions()
    results = index_all.results()
    monetary = [n for n in latest if n.estimated_value or n.result_value]
    convertible = sum(
        1
        for n in monetary
        if (n.estimated_value and value_in_eur(n.estimated_value, n.publication_date, fx) is not None)
        or (n.result_value and value_in_eur(n.result_value, n.award_date, fx) is not None)
    )
    return DataQualityMetrics(
        stored_versions=len(all_notices),
        stored_notices=len(latest),
        stored_procedures=len(index_all),
        relevant_notices=len(relevant),
        excluded_central_purchasing=excluded,
        records_by_stage=dict(sorted(Counter(n.stage.value for n in latest).items())),
        parse_errors=parse_errors,
        unlinked_results=sum(1 for r in results if r.procedure_id is None),
        fx_coverage=Coverage(convertible, len(monetary)),
        estimated_value_coverage=Coverage(sum(1 for c in competitions if c.estimated_value), len(competitions)),
        result_value_coverage=Coverage(sum(1 for r in results if r.result_value), len(results)),
        bid_count_coverage=Coverage(
            sum(1 for r in results if r.tender_statistics and r.tender_statistics.tender_counts), len(results)
        ),
        procedure_link_coverage=Coverage(sum(1 for r in results if r.procedure_id), len(results)),
        unclassified_share_pct=pct(sum(1 for n in relevant if not n.categories), len(relevant)),
        latest_publication_date=max((n.publication_date for n in all_notices), default=None),
        fx_latest_date=fx.latest_date(),
    )


# --------------------------------------------------------------------------- snapshot


def compute_snapshot(
    notices: Iterable[ProcurementNotice],
    fx: FxRateTable,
    config: MetricsConfig,
    today: date,
    *,
    taxonomy: Taxonomy,
    parse_errors: int = 0,
    bootstrap_complete: bool = True,
    computed_at: datetime | None = None,
) -> RadarSnapshot:
    """Compute every metric from stored notice versions (plan §33, §37)."""
    all_notices = list(notices)
    relevant, excluded = relevant_notices(all_notices, config, taxonomy)
    own_org = config.own_organisation
    market = [n for n in relevant if not config.market_countries or n.buyer.country in config.market_countries]
    own_notices = [n for n in relevant if own_org is not None and own_org.matches(n)]
    external = [n for n in market if own_org is None or not own_org.matches(n)]

    index_all = ProcedureIndex.build(all_notices)
    index_market = ProcedureIndex.build(market)
    market_result = market_metrics(index_market, today, fx, taxonomy)
    own_result = organisation_metrics(ProcedureIndex.build(own_notices), today, fx) if own_org else None
    country_entries = rank_by(index_market, today, fx, lambda p: [p.country or "??"], str)
    return RadarSnapshot(
        computed_at=computed_at or datetime.now(UTC),
        today=today,
        market=market_result,
        external=external_metrics(ProcedureIndex.build(external), today, fx, taxonomy),
        own=own_result,
        peers=peer_metrics(config, relevant, country_entries, own_result, today, fx),
        suppliers=supplier_metrics(index_market, today, fx),
        categories={
            category_id: category_metrics(index_market, market, category_id, taxonomy.label(category_id), today, fx)
            for category_id in config.pinned_categories
        },
        quality=data_quality(all_notices, relevant, excluded, parse_errors, fx, index_all),
        bootstrap_complete=bootstrap_complete,
    )


# --------------------------------------------------------------------------- events & watchlist


def event_type_for(notice: ProcurementNotice) -> str | None:
    if notice.is_change:
        return "change"
    if notice.stage is NoticeStage.COMPETITION:
        return "new_competition"
    if notice.stage is NoticeStage.RESULT:
        return "result"
    if notice.stage is NoticeStage.MODIFICATION:
        return "contract_modification"
    return None


def _float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def notice_event_attributes(notice: ProcurementNotice, fx: FxRateTable) -> dict[str, Any]:
    """Hard facts only (plan §23)."""
    estimated, result = notice.estimated_value, notice.result_value
    return {
        "notice_id": notice.notice_id,
        "notice_version": notice.notice_version,
        "publication_number": notice.publication_number,
        "procedure_id": notice.procedure_id,
        "stage": notice.stage.value,
        "is_change": notice.is_change,
        "title": notice.title,
        "buyer": notice.buyer.name,
        "buyer_country": notice.buyer.country,
        "publication_date": notice.publication_date.isoformat(),
        "estimated_value": _float(estimated.amount) if estimated else None,
        "estimated_currency": estimated.currency if estimated else None,
        "estimated_value_eur": _float(value_in_eur(estimated, notice.publication_date, fx)),
        "result_value": _float(result.amount) if result else None,
        "result_currency": result.currency if result else None,
        "result_value_eur": _float(value_in_eur(result, notice.award_date, fx)),
        "categories": list(notice.categories),
        "match_reasons": sorted(notice.match_reasons),
        "source_url": notice.source_url,
    }


def watchlist_matches(notice: ProcurementNotice, watchlist: WatchlistConfig, fx: FxRateTable) -> bool:
    if watchlist.is_empty:
        return False
    if watchlist.countries and notice.buyer.country not in watchlist.countries:
        return False
    if watchlist.buyer_identifiers and not (set(notice.buyer.identifiers) & watchlist.buyer_identifiers):
        return False
    if watchlist.categories and not (set(notice.categories) & watchlist.categories):
        return False
    if watchlist.min_estimated_value_eur is not None:
        estimated = value_in_eur(notice.estimated_value, notice.publication_date, fx)
        if estimated is None or estimated < watchlist.min_estimated_value_eur:
            return False
    if watchlist.min_award_value_eur is not None:
        awarded = value_in_eur(notice.result_value, notice.award_date, fx)
        if awarded is None or awarded < watchlist.min_award_value_eur:
            return False
    return True
```

- [ ] **Step 4: Run the whole suite, lint, type-check**

Run: `uv run pytest -v && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components/edp_radar`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add custom_components/edp_radar/metrics.py tests/test_metrics.py
git commit -m "feat(metrics): assemble RadarSnapshot with data quality, event facts and watchlist

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 16: Local persistence — monthly partitions over the Home Assistant store

**Files:**
- Create: `custom_components/edp_radar/storage.py`, `tests/test_storage.py`

**Interfaces:**
- Consumes: `homeassistant.helpers.storage.Store`, `models.ProcurementNotice`, `fx_rates.FxRateTable`, `const.DOMAIN`, `DEFAULT_RETENTION_DAYS`, `EMITTED_EVENT_KEYS_LIMIT`.
- Produces:
  - `STORAGE_VERSION = 1`, `SCHEMA_VERSION = 1`, `SAVE_DELAY_SECONDS = 30`.
  - `@dataclass class StoreIndex(schema_version=SCHEMA_VERSION, partitions: list[str] = [], last_successful_update: datetime | None = None, last_publication_date: date | None = None, bootstrap_complete: bool = False, retention_days: int = DEFAULT_RETENTION_DAYS, taxonomy_version: str | None = None, parse_errors: int = 0)` with `to_dict()` / `from_dict()`.
  - `class RadarStore(hass, entry_id, *, retention_days=DEFAULT_RETENTION_DAYS)`:
    - attributes `index: StoreIndex`, `notices: dict[str, ProcurementNotice]` (keyed by `version_key`), `fx: FxRateTable`, `emitted_event_keys: dict[str, None]` (insertion-ordered)
    - `async_load() -> None` (discards partitions with a foreign `schema_version` and resets `bootstrap_complete`)
    - `upsert(notice) -> bool` (True when the version key is new), `upsert_many(notices) -> int`
    - `prune(today) -> int` (removes notices older than `retention_days`, drops empty partitions, returns removed notice count)
    - `mark_events_emitted(keys)`, `was_event_emitted(key) -> bool`
    - `update_fx(rates) -> int`
    - `async_save(*, immediate: bool = False) -> None` (delayed save via `Store.async_delay_save` unless immediate; only dirty partitions are written)
    - `async_remove() -> None`
    - `RadarStore.partition_key(day: date) -> str` (`YYYY-MM`)

- [ ] **Step 1: Write the failing tests**

`tests/test_storage.py`:

```python
from datetime import UTC, date, datetime
from decimal import Decimal

from homeassistant.core import HomeAssistant

from custom_components.edp_radar.const import DOMAIN, EMITTED_EVENT_KEYS_LIMIT
from custom_components.edp_radar.storage import SCHEMA_VERSION, RadarStore, StoreIndex

from .factories import competition, make_notice

TODAY = date(2026, 9, 12)
ENTRY = "entry1"


def _key(suffix: str) -> str:
    return f"{DOMAIN}.{ENTRY}.{suffix}"


async def test_fresh_store_is_empty_and_not_bootstrapped(hass: HomeAssistant) -> None:
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    assert store.index == StoreIndex()
    assert store.notices == {}
    assert len(store.fx) == 0
    assert store.index.bootstrap_complete is False


async def test_save_writes_partitions_index_fx_and_events(hass: HomeAssistant, hass_storage: dict) -> None:
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    assert store.upsert(competition("a", "p1", date(2026, 9, 1))) is True
    assert store.upsert(competition("b", "p2", date(2026, 8, 15))) is True
    assert store.upsert(competition("a", "p1", date(2026, 9, 1))) is False
    assert store.upsert_many([make_notice(notice_id="a", notice_version=2, publication_date=date(2026, 9, 3))]) == 1
    store.update_fx({date(2026, 9, 11): {"SEK": Decimal("11.2373")}})
    store.mark_events_emitted(["a:1"])
    store.index.bootstrap_complete = True
    store.index.last_successful_update = datetime(2026, 9, 12, 8, tzinfo=UTC)
    store.index.last_publication_date = date(2026, 9, 3)
    await store.async_save(immediate=True)

    assert sorted(store.index.partitions) == ["2026-08", "2026-09"]
    assert hass_storage[_key("index")]["data"]["partitions"] == ["2026-08", "2026-09"]
    assert hass_storage[_key("index")]["data"]["bootstrap_complete"] is True
    assert hass_storage[_key("index")]["data"]["last_publication_date"] == "2026-09-03"
    september = hass_storage[_key("notices.2026-09")]["data"]
    assert september["schema_version"] == SCHEMA_VERSION
    assert sorted(n["notice_version"] for n in september["notices"]) == [1, 2]
    assert len(hass_storage[_key("notices.2026-08")]["data"]["notices"]) == 1
    assert hass_storage[_key("fx")]["data"]["rates"]["2026-09-11"]["SEK"] == "11.2373"
    assert hass_storage[_key("events")]["data"]["keys"] == ["a:1"]


async def test_restart_reloads_everything(hass: HomeAssistant, hass_storage: dict) -> None:
    first = RadarStore(hass, ENTRY)
    await first.async_load()
    first.upsert(competition("a", "p1", date(2026, 9, 1)))
    first.update_fx({date(2026, 9, 11): {"SEK": Decimal("11.2373")}})
    first.mark_events_emitted(["a:1"])
    first.index.bootstrap_complete = True
    await first.async_save(immediate=True)

    second = RadarStore(hass, ENTRY)
    await second.async_load()
    assert second.index.bootstrap_complete is True
    assert list(second.notices) == ["a:1"]
    assert second.notices["a:1"] == first.notices["a:1"]
    assert second.fx.rate_for("SEK", date(2026, 9, 11)) == (Decimal("11.2373"), date(2026, 9, 11))
    assert second.was_event_emitted("a:1") is True
    assert second.was_event_emitted("b:1") is False


async def test_only_dirty_partitions_are_rewritten(hass: HomeAssistant, hass_storage: dict) -> None:
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    store.upsert(competition("a", "p1", date(2026, 9, 1)))
    store.upsert(competition("b", "p2", date(2026, 8, 1)))
    await store.async_save(immediate=True)
    del hass_storage[_key("notices.2026-08")]  # simulate: nothing should touch August again
    store.upsert(competition("c", "p3", date(2026, 9, 2)))
    await store.async_save(immediate=True)
    assert _key("notices.2026-08") not in hass_storage
    assert len(hass_storage[_key("notices.2026-09")]["data"]["notices"]) == 2


async def test_prune_drops_old_notices_and_whole_partitions(hass: HomeAssistant, hass_storage: dict) -> None:
    store = RadarStore(hass, ENTRY, retention_days=400)
    await store.async_load()
    store.upsert(competition("old", "p0", date(2025, 7, 1)))  # 438 days before TODAY
    store.upsert(competition("edge", "p1", date(2025, 8, 9)))  # exactly 399 days: kept
    store.upsert(competition("new", "p2", date(2026, 9, 1)))
    await store.async_save(immediate=True)
    assert store.prune(TODAY) == 1
    await store.async_save(immediate=True)
    assert set(store.notices) == {"edge:1", "new:1"}
    assert store.index.partitions == ["2025-08", "2026-09"]
    assert _key("notices.2025-07") not in hass_storage


async def test_foreign_schema_version_is_discarded(hass: HomeAssistant, hass_storage: dict) -> None:
    hass_storage[_key("index")] = {
        "version": 1,
        "key": _key("index"),
        "data": {**StoreIndex(bootstrap_complete=True, partitions=["2026-09"]).to_dict(), "schema_version": 0},
    }
    hass_storage[_key("notices.2026-09")] = {
        "version": 1,
        "key": _key("notices.2026-09"),
        "data": {"schema_version": 0, "month": "2026-09", "notices": [{"garbage": True}]},
    }
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    assert store.notices == {}
    assert store.index.bootstrap_complete is False
    assert store.index.partitions == []


async def test_missing_partition_resets_bootstrap(hass: HomeAssistant, hass_storage: dict) -> None:
    hass_storage[_key("index")] = {
        "version": 1,
        "key": _key("index"),
        "data": StoreIndex(bootstrap_complete=True, partitions=["2026-09"]).to_dict(),
    }
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    assert store.index.bootstrap_complete is False


async def test_event_keys_are_bounded(hass: HomeAssistant) -> None:
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    store.mark_events_emitted(f"n{i}:1" for i in range(EMITTED_EVENT_KEYS_LIMIT + 10))
    assert len(store.emitted_event_keys) == EMITTED_EVENT_KEYS_LIMIT
    assert store.was_event_emitted("n0:1") is False
    assert store.was_event_emitted(f"n{EMITTED_EVENT_KEYS_LIMIT + 9}:1") is True


async def test_remove_deletes_all_keys(hass: HomeAssistant, hass_storage: dict) -> None:
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    store.upsert(competition("a", "p1", date(2026, 9, 1)))
    await store.async_save(immediate=True)
    await store.async_remove()
    assert not [k for k in hass_storage if k.startswith(f"{DOMAIN}.{ENTRY}.")]


def test_partition_key() -> None:
    assert RadarStore.partition_key(date(2026, 9, 1)) == "2026-09"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_storage.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `storage.py`**

```python
"""Local persistence: monthly notice partitions over Home Assistant's Store (plan §31–32, D12)."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DEFAULT_RETENTION_DAYS, DOMAIN, EMITTED_EVENT_KEYS_LIMIT
from .fx_rates import FxRateTable
from .models import ProcurementNotice

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SCHEMA_VERSION = 1
SAVE_DELAY_SECONDS = 30


@dataclass
class StoreIndex:
    schema_version: int = SCHEMA_VERSION
    partitions: list[str] = field(default_factory=list)
    last_successful_update: datetime | None = None
    last_publication_date: date | None = None
    bootstrap_complete: bool = False
    retention_days: int = DEFAULT_RETENTION_DAYS
    taxonomy_version: str | None = None
    parse_errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "partitions": sorted(self.partitions),
            "last_successful_update": (
                self.last_successful_update.isoformat() if self.last_successful_update else None
            ),
            "last_publication_date": (
                self.last_publication_date.isoformat() if self.last_publication_date else None
            ),
            "bootstrap_complete": self.bootstrap_complete,
            "retention_days": self.retention_days,
            "taxonomy_version": self.taxonomy_version,
            "parse_errors": self.parse_errors,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StoreIndex:
        return cls(
            schema_version=int(data.get("schema_version", 0)),
            partitions=sorted(data.get("partitions") or []),
            last_successful_update=(
                datetime.fromisoformat(data["last_successful_update"])
                if data.get("last_successful_update")
                else None
            ),
            last_publication_date=(
                date.fromisoformat(data["last_publication_date"])
                if data.get("last_publication_date")
                else None
            ),
            bootstrap_complete=bool(data.get("bootstrap_complete", False)),
            retention_days=int(data.get("retention_days", DEFAULT_RETENTION_DAYS)),
            taxonomy_version=data.get("taxonomy_version"),
            parse_errors=int(data.get("parse_errors", 0)),
        )


class RadarStore:
    """Normalized notices partitioned by publication month, plus index, FX and event keys."""

    def __init__(
        self, hass: HomeAssistant, entry_id: str, *, retention_days: int = DEFAULT_RETENTION_DAYS
    ) -> None:
        self._hass = hass
        self._prefix = f"{DOMAIN}.{entry_id}"
        self.index = StoreIndex(retention_days=retention_days)
        self.notices: dict[str, ProcurementNotice] = {}
        self.fx = FxRateTable()
        self.emitted_event_keys: dict[str, None] = {}
        self._index_store = self._store("index")
        self._fx_store = self._store("fx")
        self._events_store = self._store("events")
        self._partition_stores: dict[str, Store[dict[str, Any]]] = {}
        self._dirty_partitions: set[str] = set()
        self._fx_dirty = False
        self._events_dirty = False

    @staticmethod
    def partition_key(day: date) -> str:
        return day.strftime("%Y-%m")

    def _store(self, suffix: str) -> Store[dict[str, Any]]:
        return Store(self._hass, STORAGE_VERSION, f"{self._prefix}.{suffix}")

    def _partition_store(self, month: str) -> Store[dict[str, Any]]:
        if month not in self._partition_stores:
            self._partition_stores[month] = self._store(f"notices.{month}")
        return self._partition_stores[month]

    async def async_load(self) -> None:
        raw_index = await self._index_store.async_load()
        retention = self.index.retention_days
        loaded = StoreIndex.from_dict(raw_index) if raw_index else StoreIndex()
        if loaded.schema_version != SCHEMA_VERSION:
            _LOGGER.warning(
                "Discarding stored radar data with schema %s (current %s)",
                loaded.schema_version,
                SCHEMA_VERSION,
            )
            for month in loaded.partitions:
                await self._partition_store(month).async_remove()
            loaded = StoreIndex()
        loaded.retention_days = retention
        self.index = loaded

        kept: list[str] = []
        for month in list(self.index.partitions):
            data = await self._partition_store(month).async_load()
            if not data or data.get("schema_version") != SCHEMA_VERSION:
                _LOGGER.warning("Partition %s missing or incompatible; bootstrap required", month)
                self.index.bootstrap_complete = False
                continue
            for item in data.get("notices") or []:
                notice = ProcurementNotice.from_dict(item)
                self.notices[notice.version_key] = notice
            kept.append(month)
        self.index.partitions = sorted(kept)

        raw_fx = await self._fx_store.async_load()
        if raw_fx and raw_fx.get("schema_version") == SCHEMA_VERSION:
            self.fx = FxRateTable.from_dict(raw_fx.get("rates") or {})
        raw_events = await self._events_store.async_load()
        if raw_events:
            self.emitted_event_keys = dict.fromkeys(raw_events.get("keys") or [])

    def upsert(self, notice: ProcurementNotice) -> bool:
        key = notice.version_key
        is_new = key not in self.notices
        if is_new or self.notices[key] != notice:
            self.notices[key] = notice
            month = self.partition_key(notice.publication_date)
            self._dirty_partitions.add(month)
            if month not in self.index.partitions:
                self.index.partitions = sorted([*self.index.partitions, month])
        return is_new

    def upsert_many(self, notices: Iterable[ProcurementNotice]) -> int:
        return sum(1 for notice in notices if self.upsert(notice))

    def prune(self, today: date) -> int:
        cutoff = today - timedelta(days=self.index.retention_days)
        removed = [key for key, n in self.notices.items() if n.publication_date < cutoff]
        touched: set[str] = set()
        for key in removed:
            touched.add(self.partition_key(self.notices[key].publication_date))
            del self.notices[key]
        self._dirty_partitions |= touched
        self.fx.prune_before(cutoff - timedelta(days=30))
        self._fx_dirty = True
        return len(removed)

    def mark_events_emitted(self, keys: Iterable[str]) -> None:
        for key in keys:
            self.emitted_event_keys.pop(key, None)
            self.emitted_event_keys[key] = None
        while len(self.emitted_event_keys) > EMITTED_EVENT_KEYS_LIMIT:
            del self.emitted_event_keys[next(iter(self.emitted_event_keys))]
        self._events_dirty = True

    def was_event_emitted(self, key: str) -> bool:
        return key in self.emitted_event_keys

    def update_fx(self, rates: Mapping[date, Mapping[str, Decimal]]) -> int:
        added = self.fx.update(rates)
        self._fx_dirty = True
        return added

    def _partition_payload(self, month: str) -> dict[str, Any]:
        notices = [
            n.to_dict()
            for n in self.notices.values()
            if self.partition_key(n.publication_date) == month
        ]
        return {"schema_version": SCHEMA_VERSION, "month": month, "notices": notices}

    async def async_save(self, *, immediate: bool = False) -> None:
        for month in sorted(self._dirty_partitions):
            payload = self._partition_payload(month)
            store = self._partition_store(month)
            if not payload["notices"]:
                await store.async_remove()
                self.index.partitions = [m for m in self.index.partitions if m != month]
            elif immediate:
                await store.async_save(payload)
            else:
                store.async_delay_save(lambda p=payload: p, SAVE_DELAY_SECONDS)
        self._dirty_partitions.clear()
        if self._fx_dirty:
            fx_payload = {"schema_version": SCHEMA_VERSION, "rates": self.fx.to_dict()}
            if immediate:
                await self._fx_store.async_save(fx_payload)
            else:
                self._fx_store.async_delay_save(lambda p=fx_payload: p, SAVE_DELAY_SECONDS)
            self._fx_dirty = False
        if self._events_dirty:
            events_payload = {"keys": list(self.emitted_event_keys)}
            if immediate:
                await self._events_store.async_save(events_payload)
            else:
                self._events_store.async_delay_save(lambda p=events_payload: p, SAVE_DELAY_SECONDS)
            self._events_dirty = False
        index_payload = self.index.to_dict()
        if immediate:
            await self._index_store.async_save(index_payload)
        else:
            self._index_store.async_delay_save(lambda p=index_payload: p, SAVE_DELAY_SECONDS)

    async def async_remove(self) -> None:
        for month in list(self.index.partitions):
            await self._partition_store(month).async_remove()
        await self._fx_store.async_remove()
        await self._events_store.async_remove()
        await self._index_store.async_remove()
        self.notices.clear()
        self.index = StoreIndex(retention_days=self.index.retention_days)
```

- [ ] **Step 4: Run tests, lint, type-check**

Run: `uv run pytest tests/test_storage.py -v && uv run ruff check . && uv run mypy custom_components/edp_radar`
Expected: 10 passed. If `hass_storage` shows keys without `data` for delayed saves, that is expected — the tests only use `immediate=True`.

- [ ] **Step 5: Commit**

```bash
git add custom_components/edp_radar/storage.py tests/test_storage.py
git commit -m "feat(storage): persist normalized notices in monthly partitions with index, FX and event keys

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 17: Phase 0 data-profile harness and report

**Files:**
- Create: `scripts/data_profile.py`, `docs/data-profile.md` (generated)

**Interfaces:**
- Consumes: `api.TedApiClient`, `query.TedQueryBuilder`, `normalizer.REQUESTED_FIELDS/normalize_many`, `taxonomy.Taxonomy`, `fx.EcbFxClient`, `fx_rates.FxRateTable`, `lifecycle.ProcedureIndex`, `metrics.compute_snapshot/MetricsConfig`.
- Produces: a reproducible CLI: `uv run python scripts/data_profile.py --days 90 --mode strict --out docs/data-profile.md [--countries SE,FI] [--cache .cache/profile] [--no-fetch]`.

- [ ] **Step 1: Write the script**

```python
"""Phase 0 research harness (plan §50 Phase 0, §54): profile real TED data.

Usage:
    uv run python scripts/data_profile.py --days 90 --mode strict --out docs/data-profile.md

Raw pages are cached under --cache (default .cache/profile) so the report can be
regenerated without hitting the API (--no-fetch). The report contains only
aggregates; no notice text is written.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import aiohttp

from custom_components.edp_radar.api import TedApiClient
from custom_components.edp_radar.const import RelevanceMode
from custom_components.edp_radar.fx import EcbFxClient
from custom_components.edp_radar.fx_rates import FxRateTable
from custom_components.edp_radar.lifecycle import ProcedureIndex
from custom_components.edp_radar.metrics import (
    MetricsConfig,
    compute_snapshot,
    format_eur,
    is_central_purchasing_only,
    value_in_eur,
)
from custom_components.edp_radar.models import NoticeStage, ProcurementNotice
from custom_components.edp_radar.normalizer import REQUESTED_FIELDS, as_strings, normalize_many
from custom_components.edp_radar.query import TedQueryBuilder as Q
from custom_components.edp_radar.taxonomy import Taxonomy


def _pct(part: int, whole: int) -> str:
    return "n/a" if whole == 0 else f"{part / whole * 100:.1f}%"


def _table(rows: list[tuple[Any, ...]], header: tuple[str, ...]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


async def fetch(args: argparse.Namespace, taxonomy: Taxonomy) -> tuple[list[dict[str, Any]], FxRateTable]:
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    raw_path = cache / f"{args.mode}-{args.days}d-{args.countries or 'all'}.json"
    fx_path = cache / f"fx-{args.days}d.json"
    if args.no_fetch and raw_path.exists() and fx_path.exists():
        return json.loads(raw_path.read_text()), FxRateTable.from_dict(json.loads(fx_path.read_text()))

    start = date.today() - timedelta(days=args.days)
    mode = RelevanceMode(args.mode)
    query = Q.combine_and(
        Q.publication_range(start),
        Q.defence_universe(mode, taxonomy.defence_cpv_prefixes),
        Q.countries(args.countries.split(",")) if args.countries else "",
    )
    print(f"query: {query}", file=sys.stderr)
    raw: list[dict[str, Any]] = []
    async with aiohttp.ClientSession() as session:
        client = TedApiClient(session)
        await client.async_validate_query(query)

        def progress(done: int, total: int | None) -> None:
            print(f"  fetched {done}/{total}", file=sys.stderr)

        async for notice in client.async_search_notices(query, REQUESTED_FIELDS, progress=progress):
            raw.append(notice)
        ecb = EcbFxClient(session)
        rates = await ecb.async_fetch_history() if args.days > 80 else await ecb.async_fetch_recent()
    table = FxRateTable()
    table.update({d: r for d, r in rates.items() if d >= start - timedelta(days=30)})
    raw_path.write_text(json.dumps(raw))
    fx_path.write_text(json.dumps(table.to_dict()))
    return raw, table


def profile(raw: list[dict[str, Any]], fx: FxRateTable, taxonomy: Taxonomy, args: argparse.Namespace) -> str:
    notices, errors = normalize_many(raw, taxonomy)
    index = ProcedureIndex.build(notices)
    latest = index.notices
    competitions = index.competitions()
    results = index.results()
    today = date.today()
    lines: list[str] = []
    add = lines.append

    add(f"# TED data profile — {args.mode} mode, last {args.days} days")
    add("")
    add(f"Generated {datetime.now(UTC).isoformat(timespec='seconds')} by `scripts/data_profile.py` "
        f"(taxonomy {taxonomy.version}). Countries: {args.countries or 'all'}.")
    add("")
    add("## Volume")
    add("")
    add(_table([
        ("raw notices returned", len(raw)),
        ("parse errors", errors),
        ("notice versions", len(notices)),
        ("unique notice ids", len(latest)),
        ("unique procedures (incl. unlinked pseudo-procedures)", len(index)),
        ("central-purchasing-only notices (>10 buyers, defence buyer signal only)",
         sum(1 for n in latest if is_central_purchasing_only(n))),
    ], ("measure", "value")))
    add("")
    add("## Versions and changes")
    add("")
    versions = Counter(n.notice_version for n in notices)
    add(_table(sorted(versions.items()), ("notice-version", "count")))
    add("")
    add(f"- notice versions carrying change info: {sum(1 for n in notices if n.is_change)} "
        f"(v1: {sum(1 for n in notices if n.is_change and n.notice_version == 1)}, "
        f"v>1: {sum(1 for n in notices if n.is_change and n.notice_version > 1)})")
    add(f"- modification notices: {sum(1 for n in latest if n.stage is NoticeStage.MODIFICATION)}")
    add("")
    add("## Stage distribution (latest versions)")
    add("")
    add(_table(sorted(Counter(n.stage.value for n in latest).items()), ("stage", "count")))
    add("")
    add("## Match reasons (latest versions)")
    add("")
    add(_table(sorted(Counter("+".join(sorted(n.match_reasons)) or "(none)" for n in latest).items()),
               ("reasons", "count")))
    add("")
    add("## Primary buyer country (latest versions, top 30)")
    add("")
    add(_table(Counter(n.buyer.country or "??" for n in latest).most_common(30), ("country", "count")))
    add("")
    add("## Coverage")
    add("")
    est = sum(1 for c in competitions if c.estimated_value)
    est_eur = sum(1 for c in competitions if value_in_eur(c.estimated_value, c.publication_date, fx) is not None)
    res = sum(1 for r in results if r.result_value)
    res_eur = sum(1 for r in results if value_in_eur(r.result_value, r.award_date, fx) is not None)
    with_winners = [r for r in results if r.winners]
    add(_table([
        ("procedure-id coverage (latest versions)", _pct(sum(1 for n in latest if n.procedure_id), len(latest))),
        ("buyer-identifier coverage", _pct(sum(1 for n in latest if n.buyer.identifiers), len(latest))),
        ("competitions with estimated value", f"{est}/{len(competitions)} ({_pct(est, len(competitions))})"),
        ("… convertible to EUR", f"{est_eur}/{len(competitions)} ({_pct(est_eur, len(competitions))})"),
        ("results with result value", f"{res}/{len(results)} ({_pct(res, len(results))})"),
        ("… convertible to EUR", f"{res_eur}/{len(results)} ({_pct(res_eur, len(results))})"),
        ("results with winners", f"{len(with_winners)}/{len(results)}"),
        ("… with a winner identifier for every winner",
         _pct(sum(1 for r in with_winners if all(w.identifier for w in r.winners)), len(with_winners))),
        ("results with comparable tender counts",
         _pct(sum(1 for r in results if r.tender_statistics and r.tender_statistics.tender_counts), len(results))),
        ("results with selection statuses",
         _pct(sum(1 for r in results if r.tender_statistics and r.tender_statistics.selection_statuses), len(results))),
        ("results linked to a competition in the window",
         _pct(sum(1 for p in index.procedures.values() if p.first_result and p.first_competition),
              sum(1 for p in index.procedures.values() if p.first_result))),
        ("relevant notices without strategic category", _pct(sum(1 for n in latest if not n.categories), len(latest))),
    ], ("measure", "value")))
    add("")
    add("## Currencies")
    add("")
    currencies = Counter(m.currency for n in latest for m in (n.estimated_value, n.result_value) if m)
    add(_table(currencies.most_common(), ("currency", "monetary fields")))
    add("")
    add("## Received-submission type codes (all result notices, per lot entry)")
    add("")
    codes = Counter(s.type_code for r in results if r.tender_statistics for s in r.tender_statistics.statistics)
    add(_table(codes.most_common(), ("type code", "entries")))
    add("")
    add("## Selection status and non-award justifications")
    add("")
    statuses = Counter(s for r in results if r.tender_statistics for s in r.tender_statistics.selection_statuses)
    add(_table(statuses.most_common(), ("winner-selection-status", "lot entries")))
    add("")
    justifications = Counter(j for r in results if r.tender_statistics for j in r.tender_statistics.non_award_justifications)
    add(_table(justifications.most_common(), ("non-award-justification", "entries")))
    add("")
    add("## Top CPV divisions (latest versions)")
    add("")
    divisions = Counter(code[:2] for n in latest for code in set(n.cpv_codes))
    add(_table(divisions.most_common(15), ("CPV division", "notices")))
    add("")
    add("## Strategic categories (latest versions, multi-label)")
    add("")
    cats = Counter(c for n in latest for c in n.categories)
    add(_table([(taxonomy.label(c), v) for c, v in cats.most_common()], ("category", "notices")))
    add("")
    add("## Raw-array alignment anomalies")
    add("")
    def mismatch(a: str, b: str) -> int:
        return sum(1 for r in raw if r.get(a) and len(as_strings(r.get(a))) != len(as_strings(r.get(b))))
    add(_table([
        ("estimated-value-lot vs estimated-value-cur-lot length mismatch", mismatch("estimated-value-lot", "estimated-value-cur-lot")),
        ("result-value-lot vs result-value-cur-lot length mismatch", mismatch("result-value-lot", "result-value-cur-lot")),
        ("received-submissions code vs val length mismatch", mismatch("received-submissions-type-code", "received-submissions-type-val")),
        ("winner-name vs winner-country length mismatch", sum(1 for n in latest if n.winners and any(w.name is None for w in n.winners))),
        ("buyer-identifier count != buyer-country count", mismatch("buyer-identifier", "buyer-country")),
        ("notices with > 10 buyers", sum(1 for n in latest if n.buyer.count > 10)),
    ], ("check", "notices")))
    add("")
    add("## Snapshot preview (market metrics, strict universe, all countries)")
    add("")
    snapshot = compute_snapshot(notices, fx, MetricsConfig(relevance_mode=RelevanceMode(args.mode)), today, taxonomy=taxonomy)
    m = snapshot.market
    add(_table([
        ("new competitions 30d / previous", f"{m.new_competitions_30d.value} / {m.new_competitions_30d.previous}"),
        ("estimated value 30d", f"{format_eur(m.estimated_value_30d.value_eur)} (coverage {m.estimated_value_30d.coverage_pct}%)"),
        ("award value 30d", f"{format_eur(m.award_value_30d.value_eur)} (coverage {m.award_value_30d.coverage_pct}%)"),
        ("top country 90d", m.country_ranking_90d.leader.key if m.country_ranking_90d.leader else "n/a"),
        ("top category 90d", m.category_ranking_90d.leader.label if m.category_ranking_90d.leader else "n/a"),
        ("median tenders 365d", f"{m.process.median_tenders_365d.value} (n={m.process.median_tenders_365d.sample_size})"),
        ("single-bid share 365d", f"{m.process.single_bid_share_365d.pct}%"),
        ("median public time to result 365d", f"{m.process.median_time_to_result_365d.value} days (n={m.process.median_time_to_result_365d.sample_size})"),
        ("non-award share 365d", f"{m.process.non_award_share_365d.pct}%"),
        ("snapshot text", m.snapshot_text),
        ("country ranking text", m.country_ranking_text),
    ], ("metric", "value")))
    add("")
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--mode", choices=["strict", "broad"], default="strict")
    parser.add_argument("--countries", default="", help="comma-separated alpha-2 codes")
    parser.add_argument("--out", default="docs/data-profile.md")
    parser.add_argument("--cache", default=".cache/profile")
    parser.add_argument("--no-fetch", action="store_true", help="use cached pages only")
    args = parser.parse_args()
    taxonomy = Taxonomy.load()
    raw, fx = await fetch(args, taxonomy)
    report = profile(raw, fx, taxonomy, args)
    Path(args.out).write_text(report, encoding="utf-8")
    print(f"wrote {args.out} ({len(raw)} raw notices)", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run it for the required 90-day strict sample**

Run: `uv run python scripts/data_profile.py --days 90 --mode strict --out docs/data-profile.md`
Expected: ~35 pages fetched (≈6 000 notices, about 30 s with pacing), `docs/data-profile.md` written. Read the report and sanity-check: stage distribution dominated by competition/result, `tenders` the most common type code, EUR the most common currency, procedure-id coverage > 95 %.

- [ ] **Step 3: If time permits, run the 400-day window in the background**

Run: `uv run python scripts/data_profile.py --days 400 --mode strict --out docs/data-profile-400d.md` (≈150 pages, several minutes). Also run `--mode broad --days 90 --out docs/data-profile-broad-90d.md` to quantify what broad mode adds.

- [ ] **Step 4: Lint and commit**

Run: `uv run ruff check . && uv run ruff format --check .`

```bash
git add scripts/data_profile.py docs/data-profile.md docs/data-profile-*.md
git commit -m "docs: add Phase 0 data-profile harness and generated TED data profile

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Self-review notes (already applied)

- **Spec coverage (Plan 1 scope):** §4 API limits → Task 7 (D1, D9); §5–6 signals/modes → Task 4; §7 lifecycle → Tasks 6, 10 (D3, D4); §8 fields → Task 6 `REQUESTED_FIELDS`; §9 models → Task 2; §10 FX → Tasks 8–9, 11; §11 coverage → `Coverage`/`ValueMetric` in Tasks 11–15; §12 own org → `OwnOrganisation` (Task 11), Task 13; §13 peers → Task 14; §14 categories → Task 4 + Task 14; §15 windows → Task 11; §16–20 metrics → Tasks 12–15; §24 watchlist matcher → Task 15; §25 texts → Tasks 12–13; §30–32 storage → Task 16; §36 query builder → Task 3; §37 metrics purity → Tasks 11–15; §39 monetary rules → Task 6 (`_lot_money`), §40 tender counts → Task 6; §41 supplier identity → Task 2 (`identity_key`) + Task 14; §42 event keys → Task 16; §43 malformed notices → Task 6 `normalize_many`; §47 tests → every task; §50 Phase 0 → Task 17; §54 report → Task 17. Everything in §21–23, §26–29, §33–35 (HA shell), §44–46 belongs to Plan 2.
- **Deferred to Plan 2:** manifest, config flow, coordinator (bootstrap task, incremental refresh, event emission using `event_type_for`/`notice_event_attributes`/`watchlist_matches`/`RadarStore.was_event_emitted`), entities, diagnostics, translations, dev container (D19), README/HACS.
- **Type consistency:** `ProcedureIndex.build` consumes all versions; every metrics function that builds a sub-index receives *notices* (all versions), never `index.notices` (latest only) — see `category_metrics`, `peer_metrics`, `compute_snapshot`. `NoticeHighlight`, `RankingEntry`, `Coverage` names are identical across Tasks 11–15. `FxRateTable.update` returns an int in both Task 8 and Task 16.
- **D20 (new, minor):** monetary amounts `<= 0` are treated as unknown because TED uses `-1` for undisclosed lot values; recorded in Task 2 and the Global Constraints.
- **D11 refinement:** each refresh fetches the ECB *90-day* XML (idempotent gap filler) rather than the daily file; the daily endpoint remains available on the client.
- **D14 refinement:** the harness uses `aiohttp` via `TedApiClient` (available in the dev venv) instead of the standard library only, to avoid duplicating pacing/retry logic.

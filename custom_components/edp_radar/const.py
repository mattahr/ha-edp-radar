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
    "AT": "AUT",
    "BE": "BEL",
    "BG": "BGR",
    "HR": "HRV",
    "CY": "CYP",
    "CZ": "CZE",
    "DK": "DNK",
    "EE": "EST",
    "FI": "FIN",
    "FR": "FRA",
    "DE": "DEU",
    "GR": "GRC",
    "HU": "HUN",
    "IE": "IRL",
    "IT": "ITA",
    "LV": "LVA",
    "LT": "LTU",
    "LU": "LUX",
    "MT": "MLT",
    "NL": "NLD",
    "PL": "POL",
    "PT": "PRT",
    "RO": "ROU",
    "SK": "SVK",
    "SI": "SVN",
    "ES": "ESP",
    "SE": "SWE",
    "NO": "NOR",
    "IS": "ISL",
    "LI": "LIE",
    "CH": "CHE",
    "GB": "GBR",
    "UA": "UKR",
    "MD": "MDA",
    "RS": "SRB",
    "ME": "MNE",
    "MK": "MKD",
    "AL": "ALB",
    "BA": "BIH",
    "TR": "TUR",
    "XK": "XKX",
    "GE": "GEO",
}
ALPHA3_TO_ALPHA2: dict[str, str] = {v: k for k, v in ALPHA2_TO_ALPHA3.items()}

EU_COUNTRIES: frozenset[str] = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
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

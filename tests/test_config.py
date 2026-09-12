"""Tests for ConfigEntry option parsing."""

from datetime import date
from decimal import Decimal

from custom_components.edp_radar.config import RadarConfig
from custom_components.edp_radar.const import (
    CONF_MARKET_COUNTRIES,
    CONF_MARKET_PRESET,
    CONF_OWN_ALIASES,
    CONF_OWN_COUNTRY,
    CONF_OWN_IDENTIFIERS,
    CONF_OWN_NAME,
    CONF_OWN_ORGANISATION,
    CONF_PEER_COUNTRIES,
    CONF_PEER_PRESET,
    CONF_PINNED_CATEGORIES,
    CONF_RAW_COUNTRIES,
    CONF_RELEVANCE_MODE,
    CONF_SELECTED_COUNTRY,
    CONF_WATCHLIST_COUNTRIES,
    CONF_WATCHLIST_MIN_ESTIMATED_EUR,
    EU_COUNTRIES,
    NORDIC_COUNTRIES,
    MarketPreset,
    RelevanceMode,
)
from custom_components.edp_radar.taxonomy import Taxonomy


def test_defaults() -> None:
    config = RadarConfig.from_options({})
    assert config.relevance_mode is RelevanceMode.STRICT
    assert config.market_preset is MarketPreset.EU
    assert config.market_countries == EU_COUNTRIES
    assert config.metrics.own_organisation is None
    assert config.metrics.peer_countries == frozenset()
    assert config.metrics.watchlist.is_empty
    assert config.bootstrap_days == 760 and config.retention_days == 760


def test_full_options() -> None:
    config = RadarConfig.from_options(
        {
            CONF_RELEVANCE_MODE: "broad",
            CONF_MARKET_PRESET: "custom",
            CONF_MARKET_COUNTRIES: ["SE", "fi"],
            CONF_OWN_ORGANISATION: {
                CONF_OWN_IDENTIFIERS: ["202100-0340"],
                CONF_OWN_COUNTRY: "SE",
                CONF_OWN_NAME: "FMV",
                CONF_OWN_ALIASES: ["Försvarets materielverk"],
            },
            CONF_PEER_PRESET: "nordic",
            CONF_SELECTED_COUNTRY: "SE",
            CONF_PINNED_CATEGORIES: ["land_systems"],
            CONF_RAW_COUNTRIES: ["se", "FI"],
            CONF_WATCHLIST_COUNTRIES: ["PL"],
            CONF_WATCHLIST_MIN_ESTIMATED_EUR: 500000000,
        }
    )
    assert config.relevance_mode is RelevanceMode.BROAD
    assert config.market_countries == frozenset({"SE", "FI"})
    assert config.metrics.own_organisation is not None
    assert config.metrics.own_organisation.identifiers == frozenset({"202100-0340"})
    assert config.metrics.own_organisation.country == "SE"
    assert config.metrics.peer_countries == NORDIC_COUNTRIES
    assert config.metrics.selected_country == "SE"
    assert config.metrics.pinned_categories == ("land_systems",)
    assert config.metrics.raw_countries == ("SE", "FI")
    assert config.metrics.watchlist.countries == frozenset({"PL"})
    assert config.metrics.watchlist.min_estimated_value_eur == Decimal("500000000")
    assert config.metrics.watchlist.min_award_value_eur is None


def test_number_selector_floats_and_zero_become_decimal_or_none() -> None:
    config = RadarConfig.from_options(
        {CONF_WATCHLIST_MIN_ESTIMATED_EUR: 1500000.0, "watchlist_min_award_eur": 0}
    )
    assert config.metrics.watchlist.min_estimated_value_eur == Decimal("1500000")
    assert config.metrics.watchlist.min_award_value_eur is None


def test_custom_peers_and_query() -> None:
    config = RadarConfig.from_options(
        {
            CONF_MARKET_PRESET: "nordic",
            CONF_PEER_PRESET: "custom",
            CONF_PEER_COUNTRIES: ["PL"],
        }
    )
    query = config.universe_query(Taxonomy.load(), date(2025, 8, 9))
    assert query.startswith("PD>=20250809 AND (authority-main-activity=defence")
    assert query.endswith("AND (buyer-country IN (DNK FIN ISL NOR POL SWE))")


def test_query_countries_include_own_organisation_watchlist_and_raw() -> None:
    config = RadarConfig.from_options(
        {
            CONF_MARKET_PRESET: "nordic",
            CONF_OWN_ORGANISATION: {CONF_OWN_COUNTRY: "DE", CONF_OWN_NAME: "BAAINBw"},
            CONF_WATCHLIST_COUNTRIES: ["FR"],
            CONF_RAW_COUNTRIES: ["PL"],
        }
    )
    assert config.query_countries == NORDIC_COUNTRIES | {"DE", "FR", "PL"}


def test_query_countries_include_the_selected_country() -> None:
    """My country controls presentation, but it must be ingested to exist."""
    config = RadarConfig.from_options(
        {CONF_MARKET_PRESET: "eu", CONF_SELECTED_COUNTRY: "NO"}
    )
    assert config.query_countries == EU_COUNTRIES | {"NO"}


def test_ted_preset_has_no_country_filter() -> None:
    config = RadarConfig.from_options({CONF_MARKET_PRESET: "ted"})
    assert config.query_countries == frozenset()
    assert "buyer-country" not in config.universe_query(
        Taxonomy.load(), date(2025, 8, 9)
    )


def test_broad_mode_adds_cpv_signal() -> None:
    config = RadarConfig.from_options({CONF_RELEVANCE_MODE: "broad"})
    query = config.universe_query(Taxonomy.load(), date(2025, 8, 9))
    assert "classification-cpv IN (" in query

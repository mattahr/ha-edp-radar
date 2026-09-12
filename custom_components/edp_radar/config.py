"""Translate ConfigEntry options into typed configuration (plan §27–28, §46).

Nothing in this module imports Home Assistant so it can be unit-tested and reused
by the Phase 0 scripts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from .const import (
    CONF_MARKET_COUNTRIES,
    CONF_MARKET_PRESET,
    CONF_OWN_ALIASES,
    CONF_OWN_COUNTRY,
    CONF_OWN_IDENTIFIERS,
    CONF_OWN_NAME,
    CONF_OWN_ORGANISATION,
    CONF_PEER_COUNTRIES,
    CONF_PEER_ORGANISATIONS,
    CONF_PEER_PRESET,
    CONF_PINNED_CATEGORIES,
    CONF_RELEVANCE_MODE,
    CONF_SELECTED_COUNTRY,
    CONF_WATCHLIST_BUYERS,
    CONF_WATCHLIST_CATEGORIES,
    CONF_WATCHLIST_COUNTRIES,
    CONF_WATCHLIST_MIN_AWARD_EUR,
    CONF_WATCHLIST_MIN_ESTIMATED_EUR,
    DEFAULT_BOOTSTRAP_DAYS,
    DEFAULT_RETENTION_DAYS,
    MARKET_PRESET_COUNTRIES,
    MarketPreset,
    RelevanceMode,
)
from .metrics import MetricsConfig, OwnOrganisation, WatchlistConfig
from .query import TedQueryBuilder
from .taxonomy import Taxonomy

PEER_PRESET_NONE = "none"
PEER_PRESET_CUSTOM = "custom"
PEER_PRESETS = (PEER_PRESET_NONE, MarketPreset.NORDIC, MarketPreset.EU, "custom")


def _countries(value: Any) -> frozenset[str]:
    return frozenset(str(c).upper() for c in (value or []) if c)


def _strings(value: Any) -> frozenset[str]:
    return frozenset(str(v) for v in (value or []) if v)


def _decimal(value: Any) -> Decimal | None:
    """Number selectors deliver floats; empty, zero and junk mean "not set"."""
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    if not parsed.is_finite() or parsed <= 0:
        return None
    return parsed


def _own_organisation(raw: Any) -> OwnOrganisation | None:
    if not isinstance(raw, Mapping):
        return None
    own = OwnOrganisation.from_options(
        [str(i) for i in raw.get(CONF_OWN_IDENTIFIERS) or []],
        raw.get(CONF_OWN_COUNTRY) or None,
        raw.get(CONF_OWN_NAME) or None,
        [str(a) for a in raw.get(CONF_OWN_ALIASES) or []],
    )
    if not own.identifiers and not own.names:
        return None
    return own


def _peer_countries(options: Mapping[str, Any]) -> frozenset[str]:
    preset = str(options.get(CONF_PEER_PRESET) or PEER_PRESET_NONE)
    if preset == PEER_PRESET_CUSTOM:
        return _countries(options.get(CONF_PEER_COUNTRIES))
    if preset in (MarketPreset.NORDIC, MarketPreset.EU):
        return MARKET_PRESET_COUNTRIES[MarketPreset(preset)]
    return frozenset()


@dataclass(frozen=True)
class RadarConfig:
    """Everything the coordinator and metrics need, parsed once per entry."""

    metrics: MetricsConfig
    relevance_mode: RelevanceMode
    market_preset: MarketPreset
    market_countries: frozenset[str]
    bootstrap_days: int = DEFAULT_BOOTSTRAP_DAYS
    retention_days: int = DEFAULT_RETENTION_DAYS

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> RadarConfig:
        mode = RelevanceMode(options.get(CONF_RELEVANCE_MODE) or RelevanceMode.STRICT)
        preset = MarketPreset(options.get(CONF_MARKET_PRESET) or MarketPreset.EU)
        market = (
            _countries(options.get(CONF_MARKET_COUNTRIES))
            if preset is MarketPreset.CUSTOM
            else MARKET_PRESET_COUNTRIES[preset]
        )
        watchlist = WatchlistConfig(
            countries=_countries(options.get(CONF_WATCHLIST_COUNTRIES)),
            buyer_identifiers=_strings(options.get(CONF_WATCHLIST_BUYERS)),
            categories=_strings(options.get(CONF_WATCHLIST_CATEGORIES)),
            min_estimated_value_eur=_decimal(
                options.get(CONF_WATCHLIST_MIN_ESTIMATED_EUR)
            ),
            min_award_value_eur=_decimal(options.get(CONF_WATCHLIST_MIN_AWARD_EUR)),
        )
        metrics = MetricsConfig(
            relevance_mode=mode,
            market_countries=market,
            own_organisation=_own_organisation(options.get(CONF_OWN_ORGANISATION)),
            peer_countries=_peer_countries(options),
            peer_organisation_identifiers=_strings(
                options.get(CONF_PEER_ORGANISATIONS)
            ),
            selected_country=(
                str(options[CONF_SELECTED_COUNTRY]).upper()
                if options.get(CONF_SELECTED_COUNTRY)
                else None
            ),
            pinned_categories=tuple(
                str(c) for c in options.get(CONF_PINNED_CATEGORIES) or []
            ),
            watchlist=watchlist,
        )
        return cls(metrics, mode, preset, market)

    @property
    def query_countries(self) -> frozenset[str]:
        """Countries to fetch: market plus peers, own organisation and watchlist.

        Peers outside the market must still be ingested for the comparison to
        work; the TED preset already covers everything, so it needs no filter.
        """
        if self.market_preset is MarketPreset.TED:
            return frozenset()
        extra: set[str] = set(self.metrics.peer_countries)
        extra |= self.metrics.watchlist.countries
        own = self.metrics.own_organisation
        if own is not None and own.country:
            extra.add(own.country)
        return self.market_countries | extra

    def universe_query(self, taxonomy: Taxonomy, since: date) -> str:
        """The TED expert query that fetches everything this entry needs."""
        return TedQueryBuilder.combine_and(
            TedQueryBuilder.publication_range(since),
            TedQueryBuilder.defence_universe(
                self.relevance_mode, taxonomy.defence_cpv_prefixes
            ),
            TedQueryBuilder.countries(self.query_countries),
        )

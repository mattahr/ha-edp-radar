"""Config entry diagnostics (plan §44): configuration, store state, data quality.

No notices are dumped; nothing in the options is sensitive.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import fields
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EdpRadarConfigEntry
from .metrics import Coverage, DataQualityMetrics, RadarSnapshot, WatchlistConfig
from .purchasing_attrs import europe_attrs, period_attrs, summary_attrs
from .spending.calculations import latest_reference
from .spending.freshness import (
    freshness_state,
    next_release_deadline,
    publication_age_days,
    reference_age_days,
    reference_overdue,
)
from .spending.models import SourceSeries
from .spending.registry import source_spec
from .spending.store import SCHEMA_VERSION as SPENDING_SCHEMA_VERSION


def _plain(value: Any) -> Any:
    if isinstance(value, Coverage):
        return {
            "covered": value.covered,
            "population": value.population,
            "pct": value.pct,
        }
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, frozenset | set | tuple):
        return sorted(value)
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    return value


def _quality(quality: DataQualityMetrics) -> dict[str, Any]:
    return {f.name: _plain(getattr(quality, f.name)) for f in fields(quality)}


def _watchlist(watchlist: WatchlistConfig) -> dict[str, Any]:
    return {
        "is_empty": watchlist.is_empty,
        "countries": sorted(watchlist.countries),
        "buyer_identifiers": sorted(watchlist.buyer_identifiers),
        "categories": sorted(watchlist.categories),
        "min_estimated_value_eur": _plain(watchlist.min_estimated_value_eur),
        "min_award_value_eur": _plain(watchlist.min_award_value_eur),
    }


def _purchasing(snapshot: RadarSnapshot, my_country: str | None) -> dict[str, Any]:
    """The 12-month country purchasing picture at a glance (Phase 2 §29)."""
    period = snapshot.purchasing.primary
    europe = period.europe
    mine = period.countries.get(my_country) if my_country else None
    return {
        **europe_attrs(europe),
        "largest_buyer": europe.largest_buyer.country if europe.largest_buyer else None,
        "ranked_countries": len(period.ranking),
        "unranked": list(period.unranked),
        "quarantined_total": len(snapshot.purchasing.quarantined),
        "my_country": (
            summary_attrs(mine)
            if mine
            else {"country": my_country, "awards": 0, **period_attrs(europe)}
            if my_country
            else None
        ),
    }


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
                source_spec(series.source_id),
                latest.end if latest else None,
                published,
                today,
            ).value,
            "publication_age_days": publication_age_days(published, today),
            "reference_age_days": None
            if latest is None
            else reference_age_days(latest.end, today),
            "reference_overdue": reference_overdue(
                source_spec(series.source_id), latest.end if latest else None, today
            ),
            "next_release_expected": _plain(
                next_release_deadline(
                    source_spec(series.source_id),
                    latest.end if latest else None,
                    published,
                )
            ),
        },
        "parse_warnings": list(series.health.warnings),
        "revisions": len(series.revisions),
        "schema_version": SPENDING_SCHEMA_VERSION,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EdpRadarConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    integration = await async_get_integration(hass, DOMAIN)
    runtime = entry.runtime_data
    coordinator = runtime.radar
    config = coordinator.config
    metrics = config.metrics
    own = metrics.own_organisation
    store = coordinator.store
    index = store.index
    data = coordinator.data
    progress = coordinator.bootstrap_progress
    return {
        "integration_version": integration.version,
        "options": dict(entry.options),
        "config": {
            "relevance_mode": config.relevance_mode.value,
            "market_preset": config.market_preset.value,
            "market_countries": sorted(config.market_countries),
            "query_countries": sorted(config.query_countries),
            "peer_countries": sorted(metrics.peer_countries),
            "peer_organisations": sorted(metrics.peer_organisation_identifiers),
            "selected_country": metrics.selected_country,
            "pinned_categories": list(metrics.pinned_categories),
            "raw_countries": list(metrics.raw_countries),
            "own_organisation": (
                {
                    "identifiers": sorted(own.identifiers),
                    "country": own.country,
                    "names": sorted(own.names),
                }
                if own
                else None
            ),
            "watchlist": _watchlist(metrics.watchlist),
            "bootstrap_days": config.bootstrap_days,
            "retention_days": config.retention_days,
        },
        "taxonomy_version": coordinator.taxonomy.version,
        "store": {
            "schema_version": index.schema_version,
            "partitions": list(index.partitions),
            "bootstrap_complete": index.bootstrap_complete,
            "bootstrap_progress": (
                {"fetched": progress[0], "total": progress[1]} if progress else None
            ),
            "last_successful_update": _plain(index.last_successful_update),
            "last_publication_date": _plain(index.last_publication_date),
            "stored_versions": len(store.notices),
            "stored_notices": data.quality.stored_notices if data else None,
            "stored_procedures": data.quality.stored_procedures if data else None,
            "parse_errors": index.parse_errors,
            "emitted_event_keys": len(store.emitted_event_keys),
        },
        "quality": _quality(data.quality) if data else None,
        "purchasing": (
            _purchasing(data, metrics.selected_country)
            if data and data.bootstrap_complete
            else None
        ),
        "errors": {
            "last_ted_error": coordinator.last_ted_error,
            "last_fx_error": coordinator.last_fx_error,
            "last_update_success": coordinator.last_update_success,
        },
        "fx": {
            "latest_date": _plain(store.fx.latest_date()),
            "first_date": _plain(store.fx.dates[0]) if len(store.fx) else None,
            "date_count": len(store.fx),
            "currencies": sorted(store.fx.currencies()),
        },
        "spending": {
            source_id: _spending_series(series, dt_util.now().date())
            for source_id, series in runtime.spending.store.series.items()
        },
    }

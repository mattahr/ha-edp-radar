"""Config entry diagnostics (plan §44): configuration, store state, data quality.

No notices are dumped; nothing in the options is sensitive.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinator import EdpRadarConfigEntry
from .metrics import Coverage, DataQualityMetrics, WatchlistConfig


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


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EdpRadarConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    integration = await async_get_integration(hass, DOMAIN)
    coordinator = entry.runtime_data
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
    }

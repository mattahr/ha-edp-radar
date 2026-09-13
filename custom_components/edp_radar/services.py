"""Actions: ``edp_radar.get_notices`` returns stored notices as raw facts and
``edp_radar.get_country_purchasing`` the purchasing picture of one country (or
every country) — the complete country/category matrix behind the sensors
(Phase 2 §21)."""

from __future__ import annotations

from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util.json import JsonValueType

from .const import DOMAIN, PURCHASING_PERIOD_DAYS, PURCHASING_SECONDARY_PERIODS
from .coordinator import EdpRadarCoordinator
from .metrics import notice_raw_attributes
from .models import NoticeStage, ProcurementNotice
from .purchasing import PurchasingModel, PurchasingPeriod
from .purchasing_attrs import (
    award_attrs,
    categories_attrs,
    eur,
    europe_attrs,
    monthly_attrs,
    period_attrs,
    rank_row,
    summary_attrs,
)

SERVICE_GET_NOTICES = "get_notices"
SERVICE_GET_COUNTRY_PURCHASING = "get_country_purchasing"
ATTR_PERIOD = "period"
COUNTRY_ALL = "ALL"
PERIODS = {
    "12m": PURCHASING_PERIOD_DAYS,
    **{f"{days}d": days for days in PURCHASING_SECONDARY_PERIODS},
}
ATTR_COUNTRY = "country"
ATTR_STAGE = "stage"
ATTR_SINCE = "since"
ATTR_UNTIL = "until"
ATTR_CATEGORY = "category"
ATTR_BUYER_IDENTIFIER = "buyer_identifier"
ATTR_LIMIT = "limit"
STAGE_CHANGE = "change"
DEFAULT_LIMIT = 100
MAX_LIMIT = 500

GET_NOTICES_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_COUNTRY): vol.All(cv.string, vol.Upper),
        vol.Optional(ATTR_STAGE): vol.In(
            [*[s.value for s in NoticeStage], STAGE_CHANGE]
        ),
        vol.Optional(ATTR_SINCE): cv.date,
        vol.Optional(ATTR_UNTIL): cv.date,
        vol.Optional(ATTR_CATEGORY): cv.string,
        vol.Optional(ATTR_BUYER_IDENTIFIER): cv.string,
        vol.Optional(ATTR_LIMIT, default=DEFAULT_LIMIT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_LIMIT)
        ),
    }
)


GET_COUNTRY_PURCHASING_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_COUNTRY): vol.All(cv.string, vol.Upper),
        vol.Optional(ATTR_PERIOD, default="12m"): vol.In(list(PERIODS)),
    }
)


def _coordinator(hass: HomeAssistant) -> EdpRadarCoordinator:
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        coordinator: EdpRadarCoordinator = entry.runtime_data.radar
        return coordinator
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="not_loaded"
    )


def _matches(notice: ProcurementNotice, call: ServiceCall) -> bool:
    data = call.data
    if (country := data.get(ATTR_COUNTRY)) and notice.buyer.country != country:
        return False
    if stage := data.get(ATTR_STAGE):
        if stage == STAGE_CHANGE:
            if not notice.is_change:
                return False
        elif notice.is_change or notice.stage.value != stage:
            return False
    since: date | None = data.get(ATTR_SINCE)
    if since is not None and notice.publication_date < since:
        return False
    until: date | None = data.get(ATTR_UNTIL)
    if until is not None and notice.publication_date > until:
        return False
    if (category := data.get(ATTR_CATEGORY)) and category not in notice.categories:
        return False
    identifier = data.get(ATTR_BUYER_IDENTIFIER)
    return not identifier or identifier in notice.buyer.identifiers


async def _async_get_notices(call: ServiceCall) -> ServiceResponse:
    coordinator = _coordinator(call.hass)
    mode = coordinator.config.relevance_mode
    taxonomy = coordinator.taxonomy
    matched = sorted(
        (
            n
            for n in coordinator.store.notices.values()
            if taxonomy.is_relevant(n.match_reasons, mode) and _matches(n, call)
        ),
        key=lambda n: (n.publication_date, n.notice_version, n.notice_id),
        reverse=True,
    )
    limit: int = call.data[ATTR_LIMIT]
    fx = coordinator.store.fx
    notices: list[JsonValueType] = []
    for notice in matched[:limit]:
        facts: dict[str, Any] = notice_raw_attributes(notice, fx)
        notices.append(facts)
    return {"count": len(matched), "returned": len(notices), "notices": notices}


def _period(model: PurchasingModel, name: str) -> PurchasingPeriod:
    days = PERIODS[name]
    return model.primary if days == PURCHASING_PERIOD_DAYS else model.secondary[days]


def _country_response(
    model: PurchasingModel, period: PurchasingPeriod, country: str
) -> dict[str, Any]:
    summary = period.countries.get(country)
    entry = period.rank_of(country)
    response: dict[str, Any] = {
        "country": country,
        **period_attrs(period.europe),
        "rank": entry.rank if entry else None,
        "share_pct": entry.share_pct if entry else None,
        "population_size": len(period.ranking),
    }
    if summary is None:
        response.update(
            {
                "awarded_value_eur": None,
                "awards": 0,
                "categories": [],
                "largest_awards": [],
            }
        )
    else:
        response.update(summary_attrs(summary))
        response.update(categories_attrs(summary))
        response["unclassified_share_pct"] = summary.unclassified_share_pct
        response["largest_awards"] = [award_attrs(a) for a in summary.largest_awards]
    if period is model.primary:
        response["monthly"] = monthly_attrs(model.monthly_series(country))
    return response


def _all_countries_response(
    period: PurchasingPeriod, my_country: str | None
) -> dict[str, Any]:
    return {
        "country": COUNTRY_ALL,
        **period_attrs(period.europe),
        "europe": europe_attrs(period.europe),
        "ranking": [rank_row(entry, my_country) for entry in period.ranking],
        "growth": [rank_row(entry, my_country) for entry in period.growth],
        "unranked": list(period.unranked),
        "joint_multinational_eur": eur(period.europe.joint_value_eur),
    }


async def _async_get_country_purchasing(call: ServiceCall) -> ServiceResponse:
    coordinator = _coordinator(call.hass)
    snapshot = coordinator.data
    if snapshot is None or not snapshot.bootstrap_complete:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_bootstrapped"
        )
    my_country = coordinator.config.metrics.selected_country
    country: str | None = call.data.get(ATTR_COUNTRY) or my_country
    if country is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_country"
        )
    model = snapshot.purchasing
    period = _period(model, call.data[ATTR_PERIOD])
    if country == COUNTRY_ALL:
        return _all_countries_response(period, my_country)
    return _country_response(model, period, country)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions (called once from async_setup)."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_NOTICES,
        _async_get_notices,
        schema=GET_NOTICES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_COUNTRY_PURCHASING,
        _async_get_country_purchasing,
        schema=GET_COUNTRY_PURCHASING_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

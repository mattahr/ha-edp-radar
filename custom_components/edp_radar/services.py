"""Actions: ``edp_radar.get_notices`` returns stored notices as raw facts."""

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

from .const import DOMAIN
from .coordinator import EdpRadarCoordinator
from .metrics import notice_raw_attributes
from .models import NoticeStage, ProcurementNotice

SERVICE_GET_NOTICES = "get_notices"
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


def _coordinator(hass: HomeAssistant) -> EdpRadarCoordinator:
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        coordinator: EdpRadarCoordinator = entry.runtime_data
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

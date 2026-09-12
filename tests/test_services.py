"""Tests for the edp_radar.get_notices action."""

from __future__ import annotations

from typing import Any

import pytest
import voluptuous as vol
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.const import DOMAIN
from custom_components.edp_radar.services import SERVICE_GET_NOTICES

from .test_coordinator import NOW


async def get_notices(hass: HomeAssistant, **data: Any) -> dict[str, Any]:
    response = await hass.services.async_call(
        DOMAIN, SERVICE_GET_NOTICES, data, blocking=True, return_response=True
    )
    assert response is not None
    return dict(response)


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_get_notices_filters_and_returns_raw_facts(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_entry(hass, config_entry)

    everything = await get_notices(hass)
    assert everything["count"] == 18 and everything["returned"] == 18
    dates = [n["publication_date"] for n in everything["notices"]]
    assert dates == sorted(dates, reverse=True)

    sweden = await get_notices(hass, country="se")
    assert sweden["count"] == 1
    (notice,) = sweden["notices"]
    assert notice["publication_number"] == "626862-2026"
    assert notice["buyer_identifiers"] == ["2021005182"]
    assert notice["cpv_codes"] and notice["notice_type"]
    assert notice["central_purchasing"] is False
    assert notice["ted_url"].endswith("626862-2026")

    slovak_results = await get_notices(hass, country="SK", stage="result")
    assert sorted(n["publication_number"] for n in slovak_results["notices"]) == [
        "626208-2026",
        "627391-2026",
    ]
    by_buyer = await get_notices(hass, buyer_identifier="30845572")
    assert by_buyer["count"] == 2

    changes = await get_notices(hass, stage="change")
    assert sorted(n["publication_number"] for n in changes["notices"]) == [
        "626359-2026",
        "626569-2026",
    ]
    assert all(n["change_reason"] for n in changes["notices"])
    competitions = await get_notices(hass, stage="competition")
    assert competitions["count"] == 4  # the two changes are not competitions

    recent = await get_notices(hass, since="2026-09-11")
    assert recent["count"] == 15
    window = await get_notices(hass, since="2026-09-07", until="2026-09-10")
    assert sorted(n["publication_number"] for n in window["notices"]) == [
        "613361-2026",
        "619411-2026",
        "626028-2026",
    ]

    cyber = await get_notices(hass, category="cyber_it")
    assert [n["publication_number"] for n in cyber["notices"]] == ["627092-2026"]

    limited = await get_notices(hass, limit=2)
    assert limited["count"] == 18 and limited["returned"] == 2
    assert len(limited["notices"]) == 2


async def test_get_notices_rejects_bad_input_and_missing_entry(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service(DOMAIN, SERVICE_GET_NOTICES)
    with pytest.raises(ServiceValidationError):
        await get_notices(hass, country="SE")

    await setup_entry(hass, config_entry)
    with pytest.raises(vol.Invalid):
        await get_notices(hass, stage="bogus")
    with pytest.raises(vol.Invalid):
        await get_notices(hass, limit=0)

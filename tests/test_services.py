"""Tests for the edp_radar.get_notices and get_country_purchasing actions."""

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

from custom_components.edp_radar.const import CONF_SELECTED_COUNTRY, DOMAIN
from custom_components.edp_radar.services import (
    SERVICE_GET_COUNTRY_PURCHASING,
    SERVICE_GET_NOTICES,
)

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


async def get_country_purchasing(hass: HomeAssistant, **data: Any) -> dict[str, Any]:
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_COUNTRY_PURCHASING,
        data,
        blocking=True,
        return_response=True,
    )
    assert response is not None
    return dict(response)


async def test_get_country_purchasing_returns_the_country_category_matrix(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test-entry",
        unique_id=DOMAIN,
        version=2,
        data={},
        options={CONF_SELECTED_COUNTRY: "SI"},
    )
    await setup_entry(hass, entry)

    mine = await get_country_purchasing(hass)
    assert mine["country"] == "SI"
    assert mine["period_days"] == 365
    assert mine["awarded_value_eur"] == 531315.0
    assert mine["rank"] == 1 and mine["share_pct"] == 88.1
    assert mine["categories"][0]["category"] == "cyber_it"
    assert mine["largest_awards"][0]["publication_number"] == "627092-2026"
    assert len(mine["monthly"]) == 24

    slovakia = await get_country_purchasing(hass, country="sk", period="90d")
    assert slovakia["country"] == "SK"
    assert slovakia["period_days"] == 90
    assert slovakia["awarded_value_eur"] == 71803.5
    assert slovakia["awards"] == 2
    assert slovakia["categories"] == [
        {
            "category": "unclassified",
            "label": "Unclassified",
            "value_eur": 71803.5,
            "share_pct": 100.0,
            "awards": 2,
        }
    ]
    assert "monthly" not in slovakia  # the monthly series is 12m-only

    unknown = await get_country_purchasing(hass, country="PL")
    assert unknown["awarded_value_eur"] is None
    assert unknown["rank"] is None
    assert unknown["awards"] == 1

    absent = await get_country_purchasing(hass, country="ES")
    assert absent["awards"] == 0 and absent["awarded_value_eur"] is None
    assert absent["categories"] == [] and absent["largest_awards"] == []

    everyone = await get_country_purchasing(hass, country="all")
    assert [row["country"] for row in everyone["ranking"]] == ["SI", "SK", "NO", "SE"]
    assert everyone["europe"]["total_value_eur"] == 603118.5
    assert everyone["unranked"] == ["DE", "DK", "PL"]

    with pytest.raises(vol.Invalid):
        await get_country_purchasing(hass, period="7d")


async def test_get_country_purchasing_without_my_country_needs_a_country(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_entry(hass, config_entry)
    with pytest.raises(ServiceValidationError):
        await get_country_purchasing(hass)
    assert (await get_country_purchasing(hass, country="SI"))["rank"] == 1

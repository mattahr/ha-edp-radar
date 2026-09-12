"""Tests for the procurement activity and watchlist event entities."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.const import (
    CONF_WATCHLIST_COUNTRIES,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from custom_components.edp_radar.coordinator import SIGNAL_ACTIVITY, SIGNAL_WATCHLIST

from .test_coordinator import ENTRY, NOW, new_notice

FACTS = {
    "notice_id": "abc",
    "publication_number": "1-2026",
    "stage": "competition",
    "buyer": "FMV",
    "buyer_country": "SE",
    "estimated_value_eur": 1000000.0,
}


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


def entity_id(hass: HomeAssistant, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id("event", DOMAIN, f"{ENTRY}_{key}")


def get_state(hass: HomeAssistant, key: str) -> State:
    eid = entity_id(hass, key)
    assert eid is not None, f"event {key} not registered"
    state = hass.states.get(eid)
    assert state is not None
    return state


async def test_activity_event_entity_follows_the_signal(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_entry(hass, config_entry)
    assert entity_id(hass, "procurement_activity") == (
        "event.european_defence_market_procurement_activity"
    )
    assert entity_id(hass, "watchlist_activity") is None

    state = get_state(hass, "procurement_activity")
    assert state.state == STATE_UNKNOWN
    assert state.attributes["event_types"] == [
        "new_competition",
        "change",
        "result",
        "contract_modification",
    ]

    freezer.tick(timedelta(seconds=5))
    async_dispatcher_send(
        hass, SIGNAL_ACTIVITY.format(ENTRY), "new_competition", dict(FACTS)
    )
    await hass.async_block_till_done()
    state = get_state(hass, "procurement_activity")
    assert state.state == "2026-09-12T12:00:05.000+00:00"
    assert state.attributes["event_type"] == "new_competition"
    assert state.attributes["buyer"] == "FMV"
    assert state.attributes["estimated_value_eur"] == 1000000.0

    async_dispatcher_send(hass, SIGNAL_ACTIVITY.format(ENTRY), "bogus", {})
    await hass.async_block_till_done()
    assert get_state(hass, "procurement_activity").attributes["event_type"] == (
        "new_competition"
    )


async def test_watchlist_entity_exists_with_a_watchlist(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY,
        unique_id=DOMAIN,
        data={},
        options={CONF_WATCHLIST_COUNTRIES: ["ES"]},
    )
    await setup_entry(hass, entry)
    assert get_state(hass, "watchlist_activity").state == STATE_UNKNOWN

    async_dispatcher_send(hass, SIGNAL_WATCHLIST.format(ENTRY), "result", dict(FACTS))
    await hass.async_block_till_done()
    assert get_state(hass, "watchlist_activity").attributes["event_type"] == "result"
    assert get_state(hass, "procurement_activity").state == STATE_UNKNOWN


async def test_refresh_triggers_event_entities_end_to_end(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    real_notices: list[dict[str, Any]],
    real_notice: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY,
        unique_id=DOMAIN,
        data={},
        options={CONF_WATCHLIST_COUNTRIES: ["ES"]},
    )
    await setup_entry(hass, entry)

    real_notices.append(new_notice(real_notice, "2026-09-12+02:00"))
    freezer.tick(DEFAULT_UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    activity = get_state(hass, "procurement_activity")
    assert activity.attributes["event_type"] == "new_competition"
    assert activity.attributes["publication_number"] == "999999-2026"
    assert activity.attributes["buyer_country"] == "ES"
    watchlist = get_state(hass, "watchlist_activity")
    assert watchlist.attributes["publication_number"] == "999999-2026"

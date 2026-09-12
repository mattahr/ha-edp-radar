"""Tests for the coordinator: bootstrap, incremental refresh, FX and events."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.edp_radar.const import (
    CONF_WATCHLIST_COUNTRIES,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ECB_90D_URL,
    ECB_HISTORY_URL,
)
from custom_components.edp_radar.coordinator import (
    BOOTSTRAP_RETRY_SECONDS,
    SIGNAL_ACTIVITY,
    SIGNAL_WATCHLIST,
    EdpRadarCoordinator,
)
from custom_components.edp_radar.storage import SCHEMA_VERSION

from .conftest import FIXTURES, TED_SEARCH_URL, ecb_history_zip

NOW = "2026-09-12 12:00:00+00:00"
ENTRY = "test-entry"
INDEX_KEY = f"{DOMAIN}.{ENTRY}.index"
EVENTS_KEY = f"{DOMAIN}.{ENTRY}.events"


def ted_queries(aioclient_mock: AiohttpClientMocker) -> list[str]:
    return [
        call[2]["query"]
        for call in aioclient_mock.mock_calls
        if call[0] == "POST" and str(call[1]) == TED_SEARCH_URL
    ]


def ted_calls(aioclient_mock: AiohttpClientMocker) -> int:
    return len(ted_queries(aioclient_mock))


def listen(hass: HomeAssistant, signal: str) -> list[tuple[str, dict[str, Any]]]:
    received: list[tuple[str, dict[str, Any]]] = []

    def _on_event(event_type: str, attributes: dict[str, Any]) -> None:
        received.append((event_type, attributes))

    async_dispatcher_connect(hass, signal, _on_event)
    return received


async def setup_entry(
    hass: HomeAssistant, entry: MockConfigEntry
) -> EdpRadarCoordinator:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    coordinator: EdpRadarCoordinator = entry.runtime_data
    return coordinator


async def advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, entry: MockConfigEntry
) -> None:
    """Move to the next scheduled refresh and run it.

    The coordinator only arms its timer once entities listen, so the refresh is
    triggered directly here; timer-driven refreshes are covered by the sensor
    tests.
    """
    freezer.tick(DEFAULT_UPDATE_INTERVAL + timedelta(seconds=1))
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done(wait_background_tasks=True)


def new_notice(real_notice: Any, publication_date: str) -> dict[str, Any]:
    """A brand-new Spanish competition derived from a real fixture notice."""
    raw = real_notice("626977-2026")
    raw["publication-number"] = "999999-2026"
    raw["notice-identifier"] = "00000000-0000-0000-0000-000000000999"
    raw["procedure-identifier"] = "99999999-0000-0000-0000-000000000999"
    raw["publication-date"] = publication_date
    return raw


async def test_fresh_entry_bootstraps_in_background_without_events(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    activity = listen(hass, SIGNAL_ACTIVITY.format(ENTRY))
    coordinator = await setup_entry(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert coordinator.data.bootstrap_complete is True
    assert coordinator.bootstrap_progress is None
    assert coordinator.data.quality.stored_versions == 18
    assert coordinator.last_update_success is True
    assert activity == []

    queries = ted_queries(mock_backend)
    assert len(queries) == 1
    assert queries[0].startswith("PD>=20240813 AND (authority-main-activity=defence")
    assert "buyer-country IN (" in queries[0]
    ecb = [str(c[1]) for c in mock_backend.mock_calls if c[0] == "GET"]
    assert ecb == [ECB_HISTORY_URL]

    index = hass_storage[INDEX_KEY]["data"]
    assert index["bootstrap_complete"] is True
    assert index["last_publication_date"] == "2026-09-11"
    assert index["partitions"] == ["2026-09"]
    assert len(hass_storage[EVENTS_KEY]["data"]["keys"]) == 18
    assert len(hass_storage[f"{DOMAIN}.{ENTRY}.fx"]["data"]["rates"]) > 0


async def test_restart_skips_bootstrap_and_refreshes_incrementally(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_entry(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_backend.mock_calls.clear()

    coordinator = await setup_entry(hass, config_entry)
    assert coordinator.data.bootstrap_complete is True
    assert coordinator.data.quality.stored_versions == 18
    queries = ted_queries(mock_backend)
    assert queries == [q for q in queries if q.startswith("PD>=20260909 AND")]
    assert len(queries) == 1
    ecb = [str(c[1]) for c in mock_backend.mock_calls if c[0] == "GET"]
    assert ecb == [ECB_90D_URL]


async def test_new_notice_emits_one_activity_event(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    real_notices: list[dict[str, Any]],
    real_notice: Any,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    activity = listen(hass, SIGNAL_ACTIVITY.format(ENTRY))
    watchlist = listen(hass, SIGNAL_WATCHLIST.format(ENTRY))
    coordinator = await setup_entry(hass, config_entry)
    assert activity == []

    real_notices.append(new_notice(real_notice, "2026-09-12+02:00"))
    await advance(hass, freezer, config_entry)
    assert coordinator.data.quality.stored_versions == 19
    assert [event_type for event_type, _ in activity] == ["new_competition"]
    attributes = activity[0][1]
    assert attributes["publication_number"] == "999999-2026"
    assert attributes["buyer_country"] == "ES"
    assert attributes["estimated_value_eur"] == 185000.0
    assert attributes["own_organisation"] is False
    assert watchlist == []

    await advance(hass, freezer, config_entry)
    assert len(activity) == 1
    freezer.tick(31)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    keys = hass_storage[EVENTS_KEY]["data"]["keys"]
    assert "00000000-0000-0000-0000-000000000999:1" in keys


async def test_watchlist_event_for_matching_country(
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
    watchlist = listen(hass, SIGNAL_WATCHLIST.format(ENTRY))
    await setup_entry(hass, entry)
    assert watchlist == []

    real_notices.append(new_notice(real_notice, "2026-09-12+02:00"))
    await advance(hass, freezer, entry)
    assert [event_type for event_type, _ in watchlist] == ["new_competition"]
    assert watchlist[0][1]["buyer_country"] == "ES"


async def test_ted_failure_keeps_stored_snapshot(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    coordinator = await setup_entry(hass, config_entry)
    before = coordinator.data

    mock_backend.clear_requests()
    mock_backend.post(TED_SEARCH_URL, status=503, text="upstream")
    mock_backend.get(ECB_90D_URL, text=(FIXTURES / "ecb" / "hist-90d.xml").read_text())
    await advance(hass, freezer, config_entry)

    assert coordinator.last_update_success is True
    assert coordinator.last_ted_error == "TED returned HTTP 503"
    assert coordinator.data is not before
    assert coordinator.data.bootstrap_complete is True
    assert coordinator.data.quality.stored_versions == 18


async def test_ted_failure_with_empty_store_fails_setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    fast_ted_client: None,
    config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    hass_storage[INDEX_KEY] = {
        "version": 1,
        "key": INDEX_KEY,
        "data": {
            "schema_version": SCHEMA_VERSION,
            "partitions": [],
            "bootstrap_complete": True,
            "last_publication_date": "2026-09-11",
        },
    }
    aioclient_mock.post(TED_SEARCH_URL, status=503, text="upstream")
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_ecb_failure_is_recorded_but_not_fatal(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    real_notices: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    coordinator = await setup_entry(hass, config_entry)
    assert coordinator.last_fx_error is None

    mock_backend.clear_requests()
    mock_backend.post(
        TED_SEARCH_URL,
        json={"notices": real_notices, "totalNoticeCount": 18},
    )
    mock_backend.get(ECB_90D_URL, status=500)
    await advance(hass, freezer, config_entry)

    assert coordinator.last_update_success is True
    assert coordinator.last_fx_error is not None
    assert "500" in coordinator.last_fx_error
    assert coordinator.last_ted_error is None


async def test_bootstrap_failure_is_retried_later(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    fast_ted_client: None,
    config_entry: MockConfigEntry,
    real_notices: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    aioclient_mock.post(TED_SEARCH_URL, status=503, text="upstream")
    aioclient_mock.get(ECB_HISTORY_URL, content=ecb_history_zip())
    aioclient_mock.get(
        ECB_90D_URL, text=(FIXTURES / "ecb" / "hist-90d.xml").read_text()
    )
    coordinator = await setup_entry(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert coordinator.data.bootstrap_complete is False
    assert coordinator.last_ted_error == "TED returned HTTP 503"
    assert coordinator.bootstrap_progress is None

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        TED_SEARCH_URL,
        json={"notices": real_notices, "totalNoticeCount": 18},
    )
    aioclient_mock.get(ECB_HISTORY_URL, content=ecb_history_zip())
    freezer.tick(BOOTSTRAP_RETRY_SECONDS + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data.bootstrap_complete is True
    assert coordinator.last_ted_error is None
    assert coordinator.data.quality.stored_versions == 18


async def test_bootstrap_progress_is_visible_while_running(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    fast_ted_client: None,
    config_entry: MockConfigEntry,
    real_notices: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A two-page bootstrap reports (fetched, total) after the first page."""
    freezer.move_to(NOW)
    first = real_notices[:10]
    second = real_notices[10:]
    seen: list[tuple[int, int | None] | None] = []
    original = EdpRadarCoordinator._on_progress

    def spy(self: EdpRadarCoordinator, fetched: int, total: int | None) -> None:
        original(self, fetched, total)
        seen.append(self.bootstrap_progress)

    async def handler(
        method: str, url: Any, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        if data.get("iterationNextToken"):
            return AiohttpClientMockResponse(
                method, url, json={"notices": second, "totalNoticeCount": 18}
            )
        return AiohttpClientMockResponse(
            method,
            url,
            json={
                "notices": first,
                "totalNoticeCount": 18,
                "iterationNextToken": "t",
            },
        )

    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    aioclient_mock.get(ECB_HISTORY_URL, content=ecb_history_zip())
    with (
        patch("custom_components.edp_radar.api.safe_page_size", return_value=10),
        patch.object(EdpRadarCoordinator, "_on_progress", spy),
    ):
        coordinator = await setup_entry(hass, config_entry)

    assert seen == [(10, 18), (18, 18)]
    assert coordinator.bootstrap_progress is None
    assert coordinator.data.bootstrap_complete is True
    assert coordinator.data.quality.stored_versions == 18
    assert coordinator.last_ted_error is None

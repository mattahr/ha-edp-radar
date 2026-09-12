"""Tests for devices and sensor entities."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.const import (
    CONF_OWN_COUNTRY,
    CONF_OWN_IDENTIFIERS,
    CONF_OWN_NAME,
    CONF_OWN_ORGANISATION,
    CONF_PEER_PRESET,
    CONF_PINNED_CATEGORIES,
    CONF_RAW_COUNTRIES,
    CONF_SELECTED_COUNTRY,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)

from .conftest import TED_SEARCH_URL, ecb_history_zip
from .test_coordinator import ENTRY, NOW, new_notice

FULL_OPTIONS = {
    CONF_OWN_ORGANISATION: {
        CONF_OWN_IDENTIFIERS: ["2021005182"],
        CONF_OWN_COUNTRY: "SE",
        CONF_OWN_NAME: "Totalförsvarets forskningsinstitut",
    },
    CONF_PEER_PRESET: "nordic",
    CONF_SELECTED_COUNTRY: "ES",
    CONF_PINNED_CATEGORIES: ["land_systems", "logistics_support"],
    CONF_RAW_COUNTRIES: ["SE"],
}

DISABLED_BY_DEFAULT = (
    "market_non_award_share_365d",
    "ted_data_last_updated",
    "top_supplier_by_award_value_365d",
    "supplier_top5_share_365d",
)


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


def entity_id(hass: HomeAssistant, unique_key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{ENTRY}_{unique_key}"
    )


def get_state(hass: HomeAssistant, unique_key: str) -> State:
    eid = entity_id(hass, unique_key)
    assert eid is not None, f"sensor {unique_key} not registered"
    state = hass.states.get(eid)
    assert state is not None, f"{eid} has no state"
    return state


async def test_market_and_external_sensors(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_entry(hass, config_entry)

    competitions = get_state(hass, "market_new_competitions_30d")
    assert competitions.state == "5"
    assert competitions.attributes["previous_period"] == 0
    assert competitions.attributes["change"] == 5
    assert competitions.attributes["change_pct"] is None
    assert competitions.attributes["period_days"] == 30
    assert competitions.attributes["state_class"] == "measurement"
    assert (
        competitions.attributes["friendly_name"]
        == "European Defence Market New competitions 30 d"
    )
    assert get_state(hass, "market_new_competitions_90d").state == "5"

    estimated = get_state(hass, "market_estimated_value_30d")
    assert estimated.state == "2509898.0"
    assert estimated.attributes["unit_of_measurement"] == "EUR"
    assert estimated.attributes["device_class"] == "monetary"
    assert estimated.attributes["sample_size"] == 5
    assert estimated.attributes["covered_records"] == 4
    assert estimated.attributes["coverage_pct"] == 80.0
    assert estimated.attributes["previous_period_eur"] is None
    assert get_state(hass, "market_award_value_30d").state == "603118.5"

    top_country = get_state(hass, "top_country_by_value_90d")
    assert top_country.state == "FR"
    assert top_country.attributes["population_size"] == 3
    ranking = top_country.attributes["ranking"]
    assert [r["key"] for r in ranking] == ["FR", "ES", "FI"]
    assert ranking[0] == {
        "rank": 1,
        "key": "FR",
        "label": "FR",
        "value_eur": 1985823.0,
        "procedures": 2,
        "previous_value_eur": None,
        "previous_procedures": 0,
        "change_pct": None,
    }
    assert get_state(hass, "fastest_growing_country_90d").state == STATE_UNKNOWN
    top_category = get_state(hass, "top_category_by_value_90d")
    assert top_category.state == "Logistics & support"
    assert top_category.attributes["ranking"][0]["key"] == "logistics_support"
    assert get_state(hass, "largest_country_change_90d").state == STATE_UNKNOWN

    assert (
        get_state(hass, "market_snapshot_text").state
        == "5 competitions / 90d · EUR 2.5m"
    )
    assert (
        get_state(hass, "country_ranking_text").state
        == "FR EUR 2.0m · ES EUR 524k · FI EUR n/a"
    )

    median = get_state(hass, "market_median_tenders_365d")
    assert median.state == "1.0"
    assert median.attributes["sample_size"] == 19
    assert median.attributes["coverage_pct"] == 100.0
    single = get_state(hass, "market_single_bid_share_365d")
    assert single.state == "84.2"
    assert single.attributes["unit_of_measurement"] == "%"
    assert single.attributes["single_bid_lot_results"] == 16
    assert single.attributes["lot_results_with_bid_count"] == 19
    ttr = get_state(hass, "market_median_public_time_to_result_365d")
    assert ttr.state == STATE_UNKNOWN
    assert ttr.attributes["unit_of_measurement"] == "d"
    assert ttr.attributes["procedure_link_coverage_pct"] == 0.0

    assert get_state(hass, "external_new_competitions_7d").state == "5"
    recent = get_state(hass, "external_new_competitions_7d").attributes["recent"]
    assert len(recent) == 5
    assert recent[0]["publication_number"] == "626569-2026"
    largest = get_state(hass, "largest_external_competition_7d")
    assert largest.state == "1338814.2"
    assert largest.attributes["country"] == "FR"
    assert largest.attributes["buyer"] == "PFC Est"
    assert largest.attributes["original_currency"] == "EUR"
    assert largest.attributes["publication_date"] == "2026-09-11"
    assert largest.attributes["ted_url"] == (
        "https://ted.europa.eu/en/notice/-/detail/626569-2026"
    )
    award = get_state(hass, "largest_external_award_7d")
    assert award.state == "531315.0"
    assert award.attributes["country"] == "SI"
    assert award.attributes["categories"] == ["cyber_it"]
    assert (
        get_state(hass, "external_latest_text").state
        == "FR · Unclassified · EUR 1.3m · published 2026-09-11"
    )


async def test_optional_devices_absent_by_default(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_entry(hass, config_entry)
    assert entity_id(hass, "own_public_competitions_30d") is None
    assert entity_id(hass, "peer_single_bid_share_365d") is None
    assert entity_id(hass, "selected_country_value_rank_90d") is None
    assert entity_id(hass, "own_vs_peer_single_bid_delta_pp") is None
    registry = dr.async_get(hass)
    names = sorted(
        d.name for d in dr.async_entries_for_config_entry(registry, ENTRY) if d.name
    )
    assert names == ["European Defence Market", "External Radar", "Supplier Landscape"]
    market = registry.async_get_device_by_identifier((DOMAIN, f"{ENTRY}_market"), ENTRY)
    assert market is not None
    assert market.manufacturer == MANUFACTURER
    assert market.model == MODEL
    assert market.entry_type is dr.DeviceEntryType.SERVICE


async def test_disabled_by_default_entities_are_registered(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_entry(hass, config_entry)
    registry = er.async_get(hass)
    for key in DISABLED_BY_DEFAULT:
        eid = entity_id(hass, key)
        assert eid is not None, key
        entry = registry.async_get(eid)
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION, key
        assert hass.states.get(eid) is None


async def test_organisation_peer_and_category_sensors(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id=ENTRY, unique_id=DOMAIN, data={}, options=FULL_OPTIONS
    )
    await setup_entry(hass, entry)

    assert get_state(hass, "own_public_competitions_30d").state == "0"
    awards = get_state(hass, "own_public_awards_30d")
    assert awards.state == "1"
    assert awards.attributes["friendly_name"] == (
        "Selected Organisation Public awards 30 d"
    )
    assert get_state(hass, "own_public_award_value_30d").state == STATE_UNKNOWN
    assert get_state(hass, "own_public_changes_30d").state == "0"
    assert get_state(hass, "own_public_modifications_365d").state == "0"

    peer_single = get_state(hass, "peer_single_bid_share_365d")
    assert peer_single.state == "40.0"
    assert peer_single.attributes["population"] == "configured peer countries"
    assert peer_single.attributes["population_size"] == 5
    assert get_state(hass, "peer_median_tenders_365d").state == "1.0"

    value_rank = get_state(hass, "selected_country_value_rank_90d")
    assert value_rank.state == "2"
    assert value_rank.attributes["country"] == "ES"
    assert value_rank.attributes["population_size"] == 3
    assert get_state(hass, "selected_country_activity_rank_90d").state == "1"
    assert get_state(hass, "selected_country_value_percentile_90d").state == "66.7"
    delta = get_state(hass, "own_vs_peer_single_bid_delta_pp")
    assert delta.state == "26.7"
    assert delta.attributes["own_value"] == 66.7
    assert delta.attributes["peer_value"] == 40.0
    assert get_state(hass, "own_single_bid_share_365d").state == "66.7"
    assert get_state(hass, "own_vs_peer_median_tenders_delta").state == "0.0"

    registry = dr.async_get(hass)
    land = registry.async_get_device_by_identifier(
        (DOMAIN, f"{ENTRY}_category_land_systems"), ENTRY
    )
    assert land is not None and land.name == "Pinned Category: Land systems"
    logistics = registry.async_get_device_by_identifier(
        (DOMAIN, f"{ENTRY}_category_logistics_support"), ENTRY
    )
    assert logistics is not None
    assert logistics.name == "Pinned Category: Logistics & support"

    assert get_state(hass, "cat_land_systems_competitions_30d").state == "0"
    assert get_state(hass, "cat_logistics_support_competitions_30d").state == "1"
    value = get_state(hass, "cat_logistics_support_estimated_value_90d")
    assert value.state == "647008.8"
    assert value.attributes["coverage_pct"] == 100.0
    assert (
        get_state(hass, "cat_logistics_support_estimated_value_change_pct").state
        == STATE_UNKNOWN
    )
    assert get_state(hass, "cat_land_systems_award_value_90d").state == STATE_UNKNOWN


async def test_supplier_sensors_when_enabled(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    registry = er.async_get(hass)
    for key in ("top_supplier_by_award_value_365d", "supplier_top5_share_365d"):
        registry.async_get_or_create(
            "sensor", DOMAIN, f"{ENTRY}_{key}", disabled_by=None
        )
    await setup_entry(hass, config_entry)

    top = get_state(hass, "top_supplier_by_award_value_365d")
    assert top.state.startswith("OUR SPACE APPLIANCES")
    assert top.attributes["coverage_pct"] == 50.0
    assert top.attributes["total_award_value_eur"] == 603118.5
    assert top.attributes["groups"] == 2
    assert top.attributes["ranking"][1]["name"] == "IGGY-TRADE s.r.o."
    assert top.attributes["ranking"][1]["awards"] == 2
    assert get_state(hass, "supplier_top5_share_365d").state == "100.0"


async def test_sensors_are_unknown_until_bootstrap_completes(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    fast_ted_client: None,
    config_entry: MockConfigEntry,
    real_notices: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    er.async_get(hass).async_get_or_create(
        "sensor", DOMAIN, f"{ENTRY}_ted_data_last_updated", disabled_by=None
    )
    aioclient_mock.post(TED_SEARCH_URL, status=503, text="upstream")
    aioclient_mock.get(
        "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip",
        content=ecb_history_zip(),
    )
    await setup_entry(hass, config_entry)

    assert get_state(hass, "market_new_competitions_30d").state == STATE_UNKNOWN
    freshness = get_state(hass, "ted_data_last_updated")
    assert freshness.state == STATE_UNKNOWN
    assert freshness.attributes["device_class"] == "timestamp"
    assert freshness.attributes["bootstrap_complete"] is False
    assert freshness.attributes["last_ted_error"] == "TED returned HTTP 503"
    assert freshness.attributes["stored_notices"] == 0

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        TED_SEARCH_URL, json={"notices": real_notices, "totalNoticeCount": 18}
    )
    aioclient_mock.get(
        "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip",
        content=ecb_history_zip(),
    )
    freezer.tick(timedelta(seconds=901))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert get_state(hass, "market_new_competitions_30d").state == "5"
    freshness = get_state(hass, "ted_data_last_updated")
    assert freshness.state == "2026-09-12T12:15:01+00:00"
    assert freshness.attributes["bootstrap_complete"] is True
    assert freshness.attributes["bootstrap_progress"] is None
    assert freshness.attributes["last_ted_error"] is None
    assert freshness.attributes["latest_publication_date"] == "2026-09-11"
    assert freshness.attributes["stored_notices"] == 18
    assert freshness.attributes["stored_procedures"] == 18
    assert freshness.attributes["fx_latest_date"] == "2026-09-11"


async def test_scheduled_refresh_updates_sensors(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    real_notices: list[dict[str, Any]],
    real_notice: Any,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_entry(hass, config_entry)
    assert get_state(hass, "market_new_competitions_30d").state == "5"

    real_notices.append(new_notice(real_notice, "2026-09-12+02:00"))
    freezer.tick(DEFAULT_UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert get_state(hass, "market_new_competitions_30d").state == "6"
    assert get_state(hass, "external_new_competitions_7d").state == "6"


async def test_raw_data_device_for_a_country(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id=ENTRY, unique_id=DOMAIN, data={}, options=FULL_OPTIONS
    )
    await setup_entry(hass, entry)

    registry = dr.async_get(hass)
    device = registry.async_get_device_by_identifier((DOMAIN, f"{ENTRY}_raw_SE"), ENTRY)
    assert device is not None and device.name == "Raw Data: Sweden"

    results = get_state(hass, "raw_SE_results_30d")
    assert results.state == "1"
    assert results.attributes["friendly_name"] == "Raw Data: Sweden Results 30 d"
    (notice,) = results.attributes["notices"]
    assert notice["publication_number"] == "626862-2026"
    assert notice["publication_date"] == "2026-09-11"
    assert notice["stage"] == "result"
    assert notice["buyer"] == "Totalförsvarets Forskningsinstitut, Foi"
    assert notice["buyer_identifier"] == "2021005182"
    assert notice["estimated_value"] == 6000000.0
    assert notice["estimated_currency"] == "SEK"
    assert notice["estimated_value_eur"] is not None
    assert notice["result_value"] is None
    assert notice["ted_url"] == "https://ted.europa.eu/en/notice/-/detail/626862-2026"
    assert set(notice) == {
        "publication_number",
        "publication_date",
        "stage",
        "is_change",
        "title",
        "buyer",
        "buyer_identifier",
        "estimated_value",
        "estimated_currency",
        "estimated_value_eur",
        "result_value",
        "result_currency",
        "result_value_eur",
        "is_framework",
        "categories",
        "winners",
        "tenders",
        "ted_url",
    }

    assert get_state(hass, "raw_SE_notices_7d").state == "1"
    assert get_state(hass, "raw_SE_notices_7d").attributes["notices"] == [notice]
    competitions = get_state(hass, "raw_SE_competitions_30d")
    assert competitions.state == "0"
    assert competitions.attributes["notices"] == []
    for key in ("changes", "planning", "direct_awards", "modifications"):
        assert get_state(hass, f"raw_SE_{key}_30d").state == "0"

    stored = get_state(hass, "raw_SE_stored_notices")
    assert stored.state == "1"
    assert stored.attributes["stored_versions"] == 1
    assert stored.attributes["by_stage"] == {"result": 1}
    assert stored.attributes["by_month"] == {"2026-09": 1}
    assert stored.attributes["by_category"] == {"unclassified": 1}
    assert stored.attributes["top_buyers"] == [
        {
            "name": "Totalförsvarets Forskningsinstitut, Foi",
            "identifiers": ["2021005182"],
            "notices": 1,
        }
    ]
    assert entity_id(hass, "raw_FI_stored_notices") is None

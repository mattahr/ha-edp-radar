"""Spending sensors: five source devices, Sweden focus (Phase 3 Plan 2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.const import DOMAIN
from custom_components.edp_radar.spending.coordinator import SpendingCoordinator
from custom_components.edp_radar.spending.models import (
    DatapointStatus,
    ReferencePeriod,
    SpendingDataPoint,
)
from custom_components.edp_radar.spending.providers.eurostat import API_URL
from custom_components.edp_radar.spending.sensors import (
    SPENDING_SENSORS,
    SpendingSensor,
    _ytd_reference,
)
from custom_components.edp_radar.spending.store import SpendingStore

from .spending.mocks import mock_spending_sources
from .test_coordinator import NOW

ENTRY = "test-entry"
MILLION = 1_000_000
DEFENCE_JUL_2026 = 10267.82747284

SPENDING_KEYS = {
    "statskontoret": [
        "statskontoret_materiel_ytd",
        "statskontoret_materiel_latest_month",
        "statskontoret_materiel_ytd_change_pct",
        "statskontoret_defence_ytd",
        "statskontoret_defence_latest_month",
        "statskontoret_defence_ytd_change_pct",
        "statskontoret_snapshot_text",
        "statskontoret_data_age",
    ],
    "eurostat": [
        "eurostat_defence_expenditure",
        "eurostat_defence_expenditure_rank",
        "eurostat_defence_investment",
        "eurostat_defence_investment_rank",
        "eurostat_data_age",
    ],
    "nato": [
        "nato_defence_expenditure",
        "nato_defence_expenditure_pct_gdp",
        "nato_defence_expenditure_pct_gdp_rank",
        "nato_equipment_share_pct",
        "nato_position_text",
        "nato_data_age",
    ],
    "eda": [
        "eda_defence_expenditure",
        "eda_defence_expenditure_rank",
        "eda_defence_investment_rank",
        "eda_data_age",
    ],
    "sipri": [
        "sipri_military_expenditure",
        "sipri_military_expenditure_rank",
        "sipri_military_expenditure_pct_gdp",
        "sipri_data_age",
    ],
}
DATA_AGE_KEYS = [
    k for keys in SPENDING_KEYS.values() for k in keys if k.endswith("_data_age")
]


async def setup_spending(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker
) -> MockConfigEntry:
    mock_spending_sources(mock_backend)
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id=ENTRY, unique_id=DOMAIN, data={}, options={}, version=2
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def entity_id(hass: HomeAssistant, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{ENTRY}_spending_{key}"
    )


def get_state(hass: HomeAssistant, key: str) -> State:
    eid = entity_id(hass, key)
    assert eid is not None, f"spending sensor {key} not registered"
    state = hass.states.get(eid)
    assert state is not None, f"{eid} has no state"
    return state


def provenance(attrs: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "source",
        "source_id",
        "source_url",
        "reference_label",
        "reference_start",
        "reference_end",
        "reference_period_complete",
        "status",
        "published_at",
        "publication_age_days",
        "reference_age_days",
        "retrieved_at",
        "release_id",
        "unit_definition",
    )
    missing = [k for k in keys if k not in attrs]
    assert not missing, f"provenance keys missing: {missing}"
    return {k: attrs[k] for k in keys}


@pytest.mark.spending_live
async def test_source_devices_and_every_sensor_exist(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_spending(hass, mock_backend)
    devices = dr.async_get(hass)
    registry = er.async_get(hass)
    for source_id, keys in SPENDING_KEYS.items():
        device = devices.async_get_device_by_identifier(
            (DOMAIN, f"{ENTRY}_spending_{source_id}"), ENTRY
        )
        assert device is not None, source_id
        assert device.name in {"Statskontoret", "Eurostat", "NATO", "EDA", "SIPRI"}
        assert device.configuration_url
        for key in keys:
            eid = entity_id(hass, key)
            assert eid is not None, key
            assert registry.async_get(eid).device_id == device.id
    for key in DATA_AGE_KEYS:
        entry = registry.async_get(entity_id(hass, key))
        assert (
            entry is not None
            and entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        )
    assert (
        entity_id(hass, "statskontoret_materiel_ytd")
        == "sensor.statskontoret_materiel_acquisition_ytd"
    )
    assert (
        entity_id(hass, "eurostat_defence_expenditure")
        == "sensor.eurostat_defence_expenditure"
    )


@pytest.mark.spending_live
async def test_statskontoret_sensors(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_spending(hass, mock_backend)

    ytd = get_state(hass, "statskontoret_materiel_ytd")
    assert float(ytd.state) == pytest.approx(25876.95768163 * MILLION)
    assert ytd.attributes["unit_of_measurement"] == "SEK"
    assert ytd.attributes["device_class"] == "monetary"
    assert ytd.attributes["months_included"] == 7
    assert ytd.attributes["previous_year_ytd_sek"] == pytest.approx(
        19905.38365486 * MILLION
    )
    assert ytd.attributes["change_pct"] == pytest.approx(30.0, abs=0.05)
    assert [row["month"] for row in ytd.attributes["monthly_current_year"]] == [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
    ]
    assert len(ytd.attributes["monthly_previous_year"]) == 12
    assert ytd.attributes["monthly_previous_year"][11]["status"] == "actual"
    prov = provenance(ytd.attributes)
    assert prov["source"] == "Statskontoret"
    assert prov["reference_label"] == "Jan–Jul 2026"
    assert prov["reference_start"] == "2026-01-01"
    assert prov["reference_end"] == "2026-07-31"
    assert prov["status"] == "actual"
    assert prov["published_at"] == "2026-08-24"
    assert prov["publication_age_days"] == 19
    assert prov["reference_age_days"] == 43
    assert prov["release_id"] == "2026-07-definitiv-2026-08-24"

    latest = get_state(hass, "statskontoret_materiel_latest_month")
    assert float(latest.state) == pytest.approx(3753.54717975 * MILLION)
    assert latest.attributes["month_label"] == "Jul 2026"
    assert latest.attributes["same_month_previous_year_sek"] == pytest.approx(
        2939.12460557 * MILLION
    )
    assert latest.attributes["change_pct"] == pytest.approx(27.7, abs=0.05)
    assert provenance(latest.attributes)["reference_label"] == "Jul 2026"

    change = get_state(hass, "statskontoret_materiel_ytd_change_pct")
    assert float(change.state) == pytest.approx(30.0, abs=0.05)
    assert change.attributes["unit_of_measurement"] == "%"
    assert change.attributes["current_sek"] == pytest.approx(25876.95768163 * MILLION)

    defence = get_state(hass, "statskontoret_defence_ytd")
    assert float(defence.state) == pytest.approx(81422.36229634 * MILLION)
    assert defence.attributes["uo6_total_ytd_sek"] == pytest.approx(
        87336.30036421 * MILLION
    )
    defence_month = get_state(hass, "statskontoret_defence_latest_month")
    assert float(defence_month.state) == pytest.approx(DEFENCE_JUL_2026 * MILLION)
    assert defence_month.attributes["same_month_previous_year_sek"] == pytest.approx(
        9041.86392863 * MILLION
    )
    assert float(
        get_state(hass, "statskontoret_defence_ytd_change_pct").state
    ) == pytest.approx(21.6, abs=0.05)

    text = get_state(hass, "statskontoret_snapshot_text")
    assert (
        text.state
        == "Materiel YTD SEK 25.9bn · +30.0% YoY · Statskontoret · through Jul 2026"
    )
    assert provenance(text.attributes)["reference_label"] == "Jan–Jul 2026"


async def test_sensors_are_unknown_before_the_first_refresh(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker
) -> None:
    """Without providers (conftest stubs them) every value sensor is unknown."""
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id=ENTRY, unique_id=DOMAIN, data={}, options={}, version=2
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert get_state(hass, "statskontoret_materiel_ytd").state == STATE_UNKNOWN
    assert get_state(hass, "statskontoret_snapshot_text").state == STATE_UNKNOWN


@pytest.mark.spending_live
async def test_eurostat_sensors(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_spending(hass, mock_backend)

    value = get_state(hass, "eurostat_defence_expenditure")
    assert float(value.state) == pytest.approx(17196.9 * MILLION)
    assert value.attributes["unit_of_measurement"] == "EUR"
    assert value.attributes["reference_year"] == 2025
    assert value.attributes["pct_gdp"] == pytest.approx(2.9)
    assert value.attributes["nac_million"] == pytest.approx(190306.0)
    assert value.attributes["previous_year_eur"] == pytest.approx(11093.8 * MILLION)
    assert value.attributes["change_pct"] == pytest.approx(55.0, abs=0.05)
    assert value.attributes["rank"] == 4
    assert value.attributes["pct_gdp_rank"] == 4
    assert value.attributes["population"] == 22
    prov = provenance(value.attributes)
    assert prov["source"] == "Eurostat"
    assert prov["reference_label"] == "2025"
    assert prov["status"] == "actual"
    assert prov["published_at"] == "2026-04-27"

    ranking = get_state(hass, "eurostat_defence_expenditure_rank")
    assert ranking.state == "4"
    attrs = ranking.attributes
    assert attrs["population"] == 22
    assert attrs["population_total"] == 27
    assert attrs["missing"] == ["CY", "ES", "IE", "IT", "NL"]
    assert attrs["excluded_zero"] == []
    assert attrs["top"] == {"country": "DE", "eur": pytest.approx(68824.0 * MILLION)}
    assert attrs["ranking"][0]["country"] == "DE"
    assert attrs["ranking"][3] == {
        "rank": 4,
        "country": "SE",
        "eur": pytest.approx(17196.9 * MILLION),
        "pct_gdp": pytest.approx(2.9),
    }
    assert len(attrs["ranking"]) == 22
    assert [row["country"] for row in attrs["nordic"]] == ["SE", "DK", "FI"]
    assert attrs["sweden"] == {"rank": 4, "eur": pytest.approx(17196.9 * MILLION)}
    assert attrs["statuses"] == ["actual"]
    assert attrs["median_eur"] == pytest.approx(3808.3 * MILLION)
    assert provenance(attrs)["reference_label"] == "2025"

    investment = get_state(hass, "eurostat_defence_investment")
    assert float(investment.state) == pytest.approx(4864.3 * MILLION)
    assert investment.attributes["rank"] == 5
    inv_rank = get_state(hass, "eurostat_defence_investment_rank")
    assert inv_rank.state == "5"
    assert inv_rank.attributes["population"] == 27
    assert inv_rank.attributes["missing"] == []
    assert inv_rank.attributes["top"]["country"] == "PL"
    assert set(inv_rank.attributes["ranking"][0]) == {"rank", "country", "eur"}


@pytest.mark.spending_live
async def test_nato_sensors(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_spending(hass, mock_backend)

    value = get_state(hass, "nato_defence_expenditure")
    assert float(value.state) == pytest.approx(24186 * MILLION)
    assert value.attributes["unit_of_measurement"] == "USD"
    assert value.attributes["reference_year"] == 2026
    assert value.attributes["nac_million"] == pytest.approx(217902)
    assert value.attributes["usd_constant"] == pytest.approx(21538 * MILLION)
    assert value.attributes["price_base_year"] == 2021
    assert value.attributes["pct_gdp"] == pytest.approx(3.22)
    assert value.attributes["latest_actual"] == {
        "year": 2024,
        "usd": pytest.approx(13300 * MILLION),
    }
    assert value.attributes["previous_year_usd"] == pytest.approx(19122 * MILLION)
    assert value.attributes["change_pct"] == pytest.approx(26.5, abs=0.05)
    assert value.attributes["rank"] == 11
    assert value.attributes["population"] == 31
    prov = provenance(value.attributes)
    assert prov["status"] == "estimate"
    assert prov["reference_period_complete"] is False
    assert prov["reference_age_days"] is None
    assert prov["published_at"] == "2026-07-10"

    share = get_state(hass, "nato_defence_expenditure_pct_gdp")
    assert float(share.state) == pytest.approx(3.22)
    assert share.attributes["rank"] == 7
    assert share.attributes["population"] == 31
    assert share.attributes["alliance_median_pct_gdp"] == pytest.approx(2.22)

    ranking = get_state(hass, "nato_defence_expenditure_pct_gdp_rank")
    assert ranking.state == "7"
    assert ranking.attributes["top"] == {
        "country": "LT",
        "pct_gdp": pytest.approx(5.33),
    }
    assert ranking.attributes["ranking"][6] == {
        "rank": 7,
        "country": "SE",
        "pct_gdp": pytest.approx(3.22),
        "usd": pytest.approx(24186 * MILLION),
    }
    assert [row["country"] for row in ranking.attributes["nordic"]] == [
        "DK",
        "SE",
        "NO",
        "FI",
    ]
    assert ranking.attributes["statuses"] == ["estimate"]
    assert ranking.attributes["population_total"] == 31

    equipment = get_state(hass, "nato_equipment_share_pct")
    assert float(equipment.state) == pytest.approx(25.41)
    assert equipment.attributes["equipment_usd"] == pytest.approx(6145.6626 * MILLION)
    assert equipment.attributes["rank"] == 25

    text = get_state(hass, "nato_position_text")
    assert text.state == "SE #7 of 31 · USD 24.2bn · 3.2% GDP · NATO 2026 estimate"
    assert provenance(text.attributes)["status"] == "estimate"


@pytest.mark.spending_live
async def test_eda_sensors(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_spending(hass, mock_backend)

    value = get_state(hass, "eda_defence_expenditure")
    assert float(value.state) == pytest.approx(14788.962566848055 * MILLION)
    assert value.attributes["reference_year"] == 2025
    assert value.attributes["pct_gdp"] == pytest.approx(2.488, abs=0.001)
    assert value.attributes["pct_government"] == pytest.approx(5.697, abs=0.001)
    assert value.attributes["per_capita_eur"] == pytest.approx(1386.96, abs=0.01)
    assert value.attributes["investment_eur"] == pytest.approx(
        4227.901618627983 * MILLION
    )
    # SE 2025 14 788.96 MEUR vs 2024 11 414.1 MEUR (2024 workbook, Task 9)
    assert value.attributes["change_pct"] == pytest.approx(29.57, abs=0.05)
    assert value.attributes["previous_year_eur"] == pytest.approx(11414.1 * MILLION)
    assert value.attributes["rank"] == 7
    assert value.attributes["population"] == 27
    assert provenance(value.attributes)["published_at"] == "2026-09-04"

    ranking = get_state(hass, "eda_defence_expenditure_rank")
    assert ranking.state == "7"
    assert ranking.attributes["top"]["country"] == "DE"
    assert set(ranking.attributes["ranking"][6]) == {
        "rank",
        "country",
        "eur",
        "pct_gdp",
        "per_capita_eur",
    }
    assert ranking.attributes["ranking"][6]["country"] == "SE"
    assert [row["country"] for row in ranking.attributes["nordic"]] == [
        "SE",
        "DK",
        "FI",
    ]
    assert ranking.attributes["statuses"] == ["actual", "estimate"]
    assert ranking.attributes["population_total"] == 27

    investment = get_state(hass, "eda_defence_investment_rank")
    assert investment.state == "7"
    assert investment.attributes["sweden"] == {
        "rank": 7,
        "eur": pytest.approx(4227.901618627983 * MILLION),
    }
    assert set(investment.attributes["ranking"][0]) == {"rank", "country", "eur"}


@pytest.mark.spending_live
async def test_sipri_sensors(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_spending(hass, mock_backend)

    value = get_state(hass, "sipri_military_expenditure")
    assert float(value.state) == pytest.approx(14954.07135864315 * MILLION)
    assert value.attributes["unit_of_measurement"] == "USD"
    assert value.attributes["reference_year"] == 2025
    assert value.attributes["price_base_year"] == 2024
    assert value.attributes["flags"] == []
    assert value.attributes["pct_gdp"] == pytest.approx(2.471, abs=0.001)
    assert value.attributes["previous_year_usd"] == pytest.approx(
        12046.97008544414 * MILLION
    )
    assert value.attributes["change_pct"] == pytest.approx(24.1, abs=0.05)
    assert value.attributes["value_10y_ago_usd"] == pytest.approx(
        5696.73409992092 * MILLION
    )
    assert value.attributes["change_10y_pct"] == pytest.approx(162.5, abs=0.1)
    series = value.attributes["annual_series"]
    assert series[0] == {
        "year": 1990,
        "usd": pytest.approx(6900.298751312625 * MILLION),
        "status": "actual",
    }
    assert series[-1]["year"] == 2025 and len(series) == 36
    assert value.attributes["rank"] == 14
    assert (
        value.attributes["population"] == 54
    )  # 55 countries report 2025, minus Iceland's zero
    assert provenance(value.attributes)["published_at"] == "2026-04-27"

    ranking = get_state(hass, "sipri_military_expenditure_rank")
    assert ranking.state == "14"
    assert ranking.attributes["excluded_zero"] == ["IS"]
    assert ranking.attributes["top"]["country"] == "RU"
    assert len(ranking.attributes["ranking"]) == 40
    assert [row["country"] for row in ranking.attributes["nordic"]] == [
        "NO",
        "SE",
        "DK",
        "FI",
    ]
    assert ranking.attributes["ranking"][13] == {
        "rank": 14,
        "country": "SE",
        "usd": pytest.approx(14954.07135864315 * MILLION),
        "pct_gdp": pytest.approx(2.471, abs=0.001),
    }
    assert ranking.attributes["statuses"] == ["actual", "budget", "estimate"]
    assert len(str(ranking.attributes)) < 16_000

    pct = get_state(hass, "sipri_military_expenditure_pct_gdp")
    assert float(pct.state) == pytest.approx(2.471, abs=0.001)
    assert pct.attributes["rank"] == 21
    assert pct.attributes["population"] == 54


def test_catalogue_has_27_sensors() -> None:
    from custom_components.edp_radar.spending.sensors import SPENDING_SENSORS

    assert len(SPENDING_SENSORS) == 27
    assert len({d.key for d in SPENDING_SENSORS}) == 27


def test_every_source_has_a_device_name() -> None:
    from custom_components.edp_radar.entity import SPENDING_DEVICE_NAMES
    from custom_components.edp_radar.spending.registry import SOURCE_ORDER

    assert set(SPENDING_DEVICE_NAMES) == set(SOURCE_ORDER)


def test_ytd_reference_label_in_january() -> None:
    latest = SpendingDataPoint(
        "statskontoret",
        "materiel_outturn",
        "SE",
        ReferencePeriod.month(2027, 1),
        Decimal("100"),
        "SEK_MILLION",
        DatapointStatus.ACTUAL,
        "r",
        date(2027, 2, 24),
        "u",
    )
    reference = _ytd_reference(latest)
    assert reference.label == "Jan 2027"
    assert reference.start == date(2027, 1, 1)
    assert reference.end == date(2027, 1, 31)


@pytest.mark.spending_live
async def test_data_age_sensors_are_diagnostic_and_survive_source_failures(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    registry = er.async_get(hass)
    # Enable the five diagnostics before setup so they get states.
    await setup_spending(hass, mock_backend)
    for key in DATA_AGE_KEYS:
        registry.async_update_entity(entity_id(hass, key), disabled_by=None)
    await hass.config_entries.async_reload(ENTRY)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        registry.async_get(entity_id(hass, "statskontoret_data_age")).entity_category
        is EntityCategory.DIAGNOSTIC
    )
    age = get_state(hass, "statskontoret_data_age")
    assert age.state == "19"
    assert age.attributes["unit_of_measurement"] == "d"
    assert age.attributes["state_class"] == "measurement"
    assert age.attributes["freshness_state"] == "current"
    assert age.attributes["reference_overdue"] is False
    assert age.attributes["next_release_expected"] == "2026-09-30"
    assert age.attributes["latest_reference_end"] == "2026-07-31"
    assert age.attributes["reference_period_complete"] is True
    assert age.attributes["reference_age_days"] == 43
    assert age.attributes["published_at"] == "2026-08-24"
    assert age.attributes["release_id"] == "2026-07-definitiv-2026-08-24"
    assert age.attributes["health_state"] == "available"
    assert age.attributes["last_error"] is None
    assert age.attributes["datapoints"] == 57
    assert age.attributes["revisions"] == 0

    nato = get_state(hass, "nato_data_age")
    assert nato.state == "64"
    assert nato.attributes["latest_reference_end"] == "2026-12-31"
    assert nato.attributes["reference_period_complete"] is False
    assert nato.attributes["reference_age_days"] == -110  # 2026-09-12 → 2026-12-31

    # A source that fails on the next tick keeps its values; the age sensor says why.
    # The mocker answers with the first registration per URL, so clear and
    # register the failure before the healthy sources.
    mock_backend.clear_requests()
    mock_backend.get(API_URL, status=503)
    mock_spending_sources(mock_backend)
    entry = hass.config_entries.async_get_entry(ENTRY)
    assert entry is not None
    await entry.runtime_data.spending.async_refresh_source("eurostat")
    await hass.async_block_till_done()
    assert float(
        get_state(hass, "eurostat_defence_expenditure").state
    ) == pytest.approx(17196.9 * MILLION)
    failed = get_state(hass, "eurostat_data_age")
    assert failed.attributes["health_state"] == "stale_but_cached"
    assert "HTTP 503" in failed.attributes["last_error"]


@pytest.mark.spending_live
async def test_value_sensor_is_unknown_before_setup_and_unavailable_after_failure(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    # (a) Before async_setup(), the coordinator's `data` is still None: every
    # sensor must handle that without touching a snapshot that doesn't exist.
    unset_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="unset-entry",
        unique_id=DOMAIN,
        data={},
        options={},
        version=2,
    )
    unset_entry.add_to_hass(hass)
    store = SpendingStore(hass, unset_entry.entry_id)
    coordinator = SpendingCoordinator(
        hass,
        unset_entry,
        session=async_get_clientsession(hass),
        store=store,
        providers=(),
    )
    sensor = SpendingSensor(coordinator, SPENDING_SENSORS[0])
    assert sensor.native_value is None
    assert sensor.extra_state_attributes is None

    # (b) A coordinator that has loaded data but whose latest refresh failed
    # must mark its sensors unavailable, not merely unknown (S33).
    await setup_spending(hass, mock_backend)
    entry = hass.config_entries.async_get_entry(ENTRY)
    assert entry is not None
    entry.runtime_data.spending.last_update_success = False
    entry.runtime_data.spending.async_update_listeners()
    await hass.async_block_till_done()
    assert get_state(hass, "eurostat_defence_expenditure").state == STATE_UNAVAILABLE


@pytest.mark.spending_live
async def test_source_that_never_loaded_is_temporarily_unavailable(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    registry = er.async_get(hass)
    # The mocker answers with the first registration per URL, so register the
    # Eurostat failure before the healthy sources are registered.
    mock_backend.get(API_URL, status=503)
    mock_spending_sources(mock_backend)
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id=ENTRY, unique_id=DOMAIN, data={}, options={}, version=2
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    registry.async_update_entity(entity_id(hass, "eurostat_data_age"), disabled_by=None)
    await hass.config_entries.async_reload(ENTRY)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert get_state(hass, "eurostat_defence_expenditure").state == STATE_UNKNOWN
    age = get_state(hass, "eurostat_data_age")
    assert age.attributes["health_state"] == "temporarily_unavailable"
    assert "HTTP 503" in age.attributes["last_error"]
    assert float(get_state(hass, "nato_defence_expenditure").state) > 0
    assert float(get_state(hass, "eda_defence_expenditure").state) > 0
    assert float(get_state(hass, "sipri_military_expenditure").state) > 0
    assert float(get_state(hass, "statskontoret_materiel_ytd").state) > 0

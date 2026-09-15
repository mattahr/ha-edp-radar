"""Spending sensors: five source devices, Sweden focus (Phase 3 Plan 2)."""

from __future__ import annotations

from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.const import DOMAIN

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
        device = devices.async_get_device({(DOMAIN, f"{ENTRY}_spending_{source_id}")})
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

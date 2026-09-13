"""Tests for config entry diagnostics."""

from __future__ import annotations

import json

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.const import DOMAIN
from custom_components.edp_radar.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .test_coordinator import NOW
from .test_sensor import FULL_OPTIONS


async def test_diagnostics_shape(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test-entry",
        unique_id=DOMAIN,
        data={},
        options=FULL_OPTIONS,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    json.dumps(diagnostics)  # must be serialisable as-is

    assert diagnostics["integration_version"] == "0.2.0"
    assert diagnostics["options"] == FULL_OPTIONS
    config = diagnostics["config"]
    assert config["relevance_mode"] == "strict"
    assert config["market_preset"] == "eu"
    assert len(config["market_countries"]) == 27
    assert config["peer_countries"] == ["DK", "FI", "IS", "NO", "SE"]
    assert config["selected_country"] == "ES"
    assert config["pinned_categories"] == ["land_systems", "logistics_support"]
    assert config["raw_countries"] == ["SE"]
    assert config["own_organisation"] == {
        "identifiers": ["2021005182"],
        "country": "SE",
        "names": ["totalförsvarets forskningsinstitut"],
    }
    assert config["watchlist"]["is_empty"] is True
    assert config["retention_days"] == 760

    assert diagnostics["taxonomy_version"] == "2026.09.1/2026.09.1"
    store = diagnostics["store"]
    assert store["schema_version"] == 1
    assert store["partitions"] == ["2026-09"]
    assert store["bootstrap_complete"] is True
    assert store["bootstrap_progress"] is None
    assert store["last_successful_update"] == "2026-09-12T12:00:00+00:00"
    assert store["last_publication_date"] == "2026-09-11"
    assert store["stored_versions"] == 18
    assert store["stored_notices"] == 18
    assert store["stored_procedures"] == 18
    assert store["parse_errors"] == 0
    assert store["emitted_event_keys"] == 18

    quality = diagnostics["quality"]
    assert quality["relevant_notices"] == 17
    assert quality["excluded_central_purchasing"] == 1
    assert quality["records_by_stage"]["result"] == 9
    assert quality["estimated_value_coverage"] == {
        "covered": 4,
        "population": 5,
        "pct": 80.0,
    }
    assert quality["latest_publication_date"] == "2026-09-11"
    assert quality["unclassified_share_pct"] == 58.8

    purchasing = diagnostics["purchasing"]
    assert purchasing["period_days"] == 365
    assert purchasing["total_value_eur"] == 603118.5
    assert purchasing["countries_with_value"] == 2
    assert purchasing["countries_active"] == 5
    assert purchasing["awards"] == 6 and purchasing["valued_awards"] == 3
    assert purchasing["quarantined_results"] == 0
    assert purchasing["unranked"] == ["DE", "DK", "PL"]
    assert purchasing["my_country"]["country"] == "ES"
    assert purchasing["my_country"]["awards"] == 0
    assert purchasing["largest_buyer"] == "SI"

    assert diagnostics["errors"] == {
        "last_ted_error": None,
        "last_fx_error": None,
        "last_update_success": True,
    }
    fx = diagnostics["fx"]
    assert fx["latest_date"] == "2026-09-11"
    assert fx["date_count"] == 3
    assert fx["first_date"] == "2026-09-08"
    assert "SEK" in fx["currencies"]
    assert "notices" not in diagnostics


@pytest.mark.spending_live
async def test_spending_diagnostics(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    from .spending.mocks import mock_spending_sources

    freezer.move_to(NOW)
    mock_spending_sources(mock_backend)
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test-entry",
        unique_id=DOMAIN,
        data={},
        options=FULL_OPTIONS,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    spending = diagnostics["spending"]
    assert sorted(spending) == ["eda", "eurostat", "nato", "sipri", "statskontoret"]
    sk = spending["statskontoret"]
    assert sk["health"]["state"] == "available"
    assert sk["release"]["release_id"] == "2026-07-definitiv-2026-08-24"
    assert sk["release"]["published_at"] == "2026-08-24"
    assert sk["datapoints"] == 57
    assert sk["countries"] == ["SE"]
    assert sk["metrics"] == [
        "materiel_outturn",
        "uo6_defence_outturn",
        "uo6_total_outturn",
    ]
    assert sk["latest_reference"] == {
        "start": "2026-07-01",
        "end": "2026-07-31",
        "label": "Jul 2026",
    }
    assert sk["freshness"] == {
        "state": "current",
        "publication_age_days": 19,
        "reference_age_days": 43,
    }
    assert sk["revisions"] == 0
    assert sk["schema_version"] == 1
    assert sk["parse_warnings"] == []
    nato = spending["nato"]
    assert nato["latest_reference"]["label"] == "2026"
    assert set(nato["statuses"]) == {"actual", "estimate"}
    assert set(nato["countries"]) >= {"SE", "US", "TR"}
    json.dumps(diagnostics)  # serialisable

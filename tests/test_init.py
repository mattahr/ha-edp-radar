"""Tests for config entry setup, unload and removal."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.const import CONF_SELECTED_COUNTRY, DOMAIN
from custom_components.edp_radar.storage import SCHEMA_VERSION


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.radar.data is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_remove_entry_deletes_storage(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    prefix = f"{DOMAIN}.{config_entry.entry_id}"
    hass_storage[f"{prefix}.index"] = {
        "version": 1,
        "key": f"{prefix}.index",
        "data": {"schema_version": SCHEMA_VERSION, "partitions": ["2026-09"]},
    }
    hass_storage[f"{prefix}.notices.2026-09"] = {
        "version": 1,
        "key": f"{prefix}.notices.2026-09",
        "data": {"schema_version": SCHEMA_VERSION, "month": "2026-09", "notices": []},
    }
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert not [k for k in hass_storage if k.startswith(prefix)]


async def test_migration_derives_my_country_from_home_assistant(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker
) -> None:
    """Version 1 entries get My country from the instance country (Phase 2 §35.6)."""
    hass.config.country = "SE"
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, version=1, data={}, options={}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.version == 2
    assert entry.options[CONF_SELECTED_COUNTRY] == "SE"
    assert entry.runtime_data.radar.config.metrics.selected_country == "SE"


async def test_migration_keeps_an_existing_choice_and_skips_unsupported(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker
) -> None:
    hass.config.country = "US"
    chosen = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        version=1,
        data={},
        options={CONF_SELECTED_COUNTRY: "FI"},
    )
    chosen.add_to_hass(hass)
    assert await hass.config_entries.async_setup(chosen.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert chosen.version == 2
    assert chosen.options[CONF_SELECTED_COUNTRY] == "FI"


async def test_migration_without_a_supported_country_leaves_it_unset(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker
) -> None:
    hass.config.country = "US"
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, version=1, data={}, options={}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.version == 2
    assert CONF_SELECTED_COUNTRY not in entry.options
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.spending_live
async def test_spending_layer_is_wired(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    from custom_components.edp_radar.spending.models import ProviderState
    from custom_components.edp_radar.spending.store import storage_key

    from .spending.mocks import mock_spending_sources

    mock_spending_sources(mock_backend)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    runtime = config_entry.runtime_data
    assert runtime.radar.data is not None
    snapshot = runtime.spending.data
    assert snapshot is not None
    for source_id in ("statskontoret", "eurostat", "nato", "eda", "sipri"):
        series = snapshot.get(source_id)
        assert series.health.state is ProviderState.AVAILABLE, (
            source_id,
            series.health,
        )
        assert series.datapoints
    assert any(
        p.metric_id == "materiel_outturn"
        for p in snapshot.get("statskontoret").datapoints
    )

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert storage_key(config_entry.entry_id, "nato") in hass_storage

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert not [k for k in hass_storage if ".spending." in k]

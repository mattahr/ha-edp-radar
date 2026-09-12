"""Tests for config entry setup, unload and removal."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.const import DOMAIN
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
    assert config_entry.runtime_data.data is not None

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

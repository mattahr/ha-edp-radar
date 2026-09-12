"""Sensor platform (entities land with Task 4)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EdpRadarConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EdpRadarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

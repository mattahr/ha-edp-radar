"""Event entities for new notice versions (plan §23–24, §42).

The coordinator dispatches ``(event_type, attributes)`` on two signals; the
entities only relay them. Attributes are hard facts about the notice.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EdpRadarConfigEntry, EdpRadarCoordinator
from .entity import DeviceKind, EdpRadarEntity

EVENT_TYPES = ["new_competition", "change", "result", "contract_modification"]

ACTIVITY = EventEntityDescription(
    key="procurement_activity",
    translation_key="procurement_activity",
    event_types=EVENT_TYPES,
)
WATCHLIST = EventEntityDescription(
    key="watchlist_activity",
    translation_key="watchlist_activity",
    event_types=EVENT_TYPES,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EdpRadarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Always create the activity entity; the watchlist one only when configured."""
    coordinator = entry.runtime_data
    entities = [EdpRadarEvent(coordinator, ACTIVITY, coordinator.signal_activity)]
    if not coordinator.config.metrics.watchlist.is_empty:
        entities.append(
            EdpRadarEvent(coordinator, WATCHLIST, coordinator.signal_watchlist)
        )
    async_add_entities(entities)


class EdpRadarEvent(EdpRadarEntity, EventEntity):
    """Relays one dispatcher signal as Home Assistant events."""

    entity_description: EventEntityDescription

    def __init__(
        self,
        coordinator: EdpRadarCoordinator,
        description: EventEntityDescription,
        signal: str,
    ) -> None:
        super().__init__(coordinator, description, DeviceKind.MARKET)
        self._signal = signal

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._async_handle)
        )

    @callback
    def _async_handle(self, event_type: str, attributes: dict[str, Any]) -> None:
        if event_type not in self.event_types:
            return
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()

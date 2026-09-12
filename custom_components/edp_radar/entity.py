"""Base entity and service devices (plan §21, addendum D16)."""

from __future__ import annotations

from enum import StrEnum

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import EdpRadarCoordinator
from .metrics import RadarSnapshot

CONFIGURATION_URL = "https://ted.europa.eu/"


class DeviceKind(StrEnum):
    MARKET = "market"
    EXTERNAL = "external"
    ORGANISATION = "organisation"
    PEERS = "peers"
    SUPPLIERS = "suppliers"
    CATEGORY = "category"


DEVICE_NAMES: dict[DeviceKind, str] = {
    DeviceKind.MARKET: "European Defence Market",
    DeviceKind.EXTERNAL: "External Radar",
    DeviceKind.ORGANISATION: "Selected Organisation",
    DeviceKind.PEERS: "Peer Comparison",
    DeviceKind.SUPPLIERS: "Supplier Landscape",
}


def device_info(
    entry_id: str,
    kind: DeviceKind,
    *,
    category_id: str | None = None,
    category_label: str | None = None,
) -> DeviceInfo:
    """One service device per analytics group; pinned categories get their own."""
    if kind is DeviceKind.CATEGORY:
        key = f"{kind.value}_{category_id}"
        name = f"Pinned Category: {category_label or category_id}"
    else:
        key = kind.value
        name = DEVICE_NAMES[kind]
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{key}")},
        name=name,
        manufacturer=MANUFACTURER,
        model=MODEL,
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=CONFIGURATION_URL,
    )


class EdpRadarEntity(CoordinatorEntity[EdpRadarCoordinator]):
    """An entity that reads the latest ``RadarSnapshot``; never talks to TED."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EdpRadarCoordinator,
        description: EntityDescription,
        kind: DeviceKind,
        *,
        category_id: str | None = None,
        category_label: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry_id = coordinator.entry.entry_id
        if category_id is not None:
            self._attr_unique_id = f"{entry_id}_cat_{category_id}_{description.key}"
        else:
            self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = device_info(
            entry_id, kind, category_id=category_id, category_label=category_label
        )

    @property
    def snapshot(self) -> RadarSnapshot | None:
        """The complete snapshot, or None while the bootstrap is still running."""
        data = self.coordinator.data
        if data is None or not data.bootstrap_complete:
            return None
        return data

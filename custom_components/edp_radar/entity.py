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
    RAW = "raw"
    # Phase 2: country purchasing
    MY_COUNTRY = "my_country"
    PURCHASING = "purchasing"
    RANKING = "ranking"


DEVICE_NAMES: dict[DeviceKind, str] = {
    DeviceKind.MARKET: "European Defence Market",
    DeviceKind.EXTERNAL: "External Radar",
    DeviceKind.ORGANISATION: "Selected Organisation",
    DeviceKind.PEERS: "Peer Comparison",
    DeviceKind.SUPPLIERS: "Supplier Landscape",
    DeviceKind.PURCHASING: "European Purchasing",
    DeviceKind.RANKING: "Country Ranking",
}


def device_info(
    entry_id: str,
    kind: DeviceKind,
    *,
    suffix: str | None = None,
    label: str | None = None,
) -> DeviceInfo:
    """One service device per analytics group; categories and raw-data countries
    get one device each, keyed by ``suffix`` (category id or country code). The
    My Country device keeps one identifier and is renamed when the country
    changes."""
    if kind is DeviceKind.CATEGORY:
        key = f"{kind.value}_{suffix}"
        name = f"Pinned Category: {label or suffix}"
    elif kind is DeviceKind.RAW:
        key = f"{kind.value}_{suffix}"
        name = f"Raw Data: {label or suffix}"
    elif kind is DeviceKind.MY_COUNTRY:
        key = kind.value
        name = f"My Country: {label or suffix}"
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
        suffix: str | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry_id = coordinator.entry.entry_id
        if kind is DeviceKind.CATEGORY:
            self._attr_unique_id = f"{entry_id}_cat_{suffix}_{description.key}"
        elif kind is DeviceKind.RAW:
            self._attr_unique_id = f"{entry_id}_raw_{suffix}_{description.key}"
        else:
            self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = device_info(entry_id, kind, suffix=suffix, label=label)

    @property
    def snapshot(self) -> RadarSnapshot | None:
        """The complete snapshot, or None while the bootstrap is still running."""
        data = self.coordinator.data
        if data is None or not data.bootstrap_complete:
            return None
        return data

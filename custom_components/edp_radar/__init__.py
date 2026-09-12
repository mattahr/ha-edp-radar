"""European Defence Procurement Radar for Home Assistant."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TedApiClient
from .config import RadarConfig
from .coordinator import EdpRadarConfigEntry, EdpRadarCoordinator
from .fx import EcbFxClient
from .storage import RadarStore
from .taxonomy import Taxonomy

PLATFORMS = [Platform.SENSOR, Platform.EVENT]


async def async_setup_entry(hass: HomeAssistant, entry: EdpRadarConfigEntry) -> bool:
    """Set up the radar from a config entry."""
    session = async_get_clientsession(hass)
    config = RadarConfig.from_options(entry.options)
    coordinator = EdpRadarCoordinator(
        hass,
        entry,
        client=TedApiClient(session),
        fx_client=EcbFxClient(session),
        store=RadarStore(hass, entry.entry_id, retention_days=config.retention_days),
        taxonomy=Taxonomy.load(),
    )
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: EdpRadarConfigEntry
) -> None:
    """Options changed: reload so devices and entities follow the new configuration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: EdpRadarConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: EdpRadarConfigEntry) -> None:
    """Delete stored notices when the integration is removed."""
    store = RadarStore(hass, entry.entry_id)
    await store.async_load()
    await store.async_remove()

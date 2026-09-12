"""European Defence Procurement Radar for Home Assistant."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import TedApiClient
from .config import RadarConfig
from .const import DOMAIN
from .coordinator import EdpRadarConfigEntry, EdpRadarCoordinator
from .fx import EcbFxClient
from .services import async_setup_services
from .storage import RadarStore
from .taxonomy import Taxonomy

PLATFORMS = [Platform.SENSOR, Platform.EVENT]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register actions; everything else lives in the config entry."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EdpRadarConfigEntry) -> bool:
    """Set up the radar from a config entry."""
    session = async_get_clientsession(hass)
    config = RadarConfig.from_options(entry.options)
    taxonomy = await hass.async_add_executor_job(Taxonomy.load)
    coordinator = EdpRadarCoordinator(
        hass,
        entry,
        client=TedApiClient(session),
        fx_client=EcbFxClient(session),
        store=RadarStore(
            hass,
            entry.entry_id,
            retention_days=config.retention_days,
            bootstrap_days=config.bootstrap_days,
        ),
        taxonomy=taxonomy,
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

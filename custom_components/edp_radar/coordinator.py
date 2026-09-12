"""DataUpdateCoordinator: ingestion, storage, metrics (plan §33, D8, D9, D11)."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import TedApiClient
from .config import RadarConfig
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .fx import EcbFxClient
from .metrics import RadarSnapshot, compute_snapshot
from .storage import RadarStore
from .taxonomy import Taxonomy

_LOGGER = logging.getLogger(__name__)

type EdpRadarConfigEntry = ConfigEntry[EdpRadarCoordinator]


class EdpRadarCoordinator(DataUpdateCoordinator[RadarSnapshot]):
    """Owns the store and the clients; entities only read ``self.data``."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: EdpRadarConfigEntry,
        *,
        client: TedApiClient,
        fx_client: EcbFxClient,
        store: RadarStore,
        taxonomy: Taxonomy,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.entry = entry
        self.client = client
        self.fx_client = fx_client
        self.store = store
        self.taxonomy = taxonomy
        self.config = RadarConfig.from_options(entry.options)
        self.last_ted_error: str | None = None
        self.last_fx_error: str | None = None

    async def async_setup(self) -> None:
        """Load stored data before the first refresh."""
        await self.store.async_load()

    async def async_shutdown(self) -> None:
        """Persist immediately and stop scheduling refreshes."""
        await self.store.async_save(immediate=True)
        await super().async_shutdown()

    async def _async_compute(self, *, bootstrap_complete: bool) -> RadarSnapshot:
        """Compute the snapshot in the executor from a stable copy of the store."""
        notices = list(self.store.notices.values())
        today = dt_util.now().date()
        return await self.hass.async_add_executor_job(
            lambda: compute_snapshot(
                notices,
                self.store.fx,
                self.config.metrics,
                today,
                taxonomy=self.taxonomy,
                parse_errors=self.store.index.parse_errors,
                bootstrap_complete=bootstrap_complete,
                computed_at=datetime.now(tz=dt_util.UTC),
            )
        )

    async def _async_update_data(self) -> RadarSnapshot:
        return await self._async_compute(
            bootstrap_complete=self.store.index.bootstrap_complete
        )

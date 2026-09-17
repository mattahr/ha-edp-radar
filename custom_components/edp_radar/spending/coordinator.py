"""SpendingCoordinator (S14; plan §64, §65, §86, §87).

Ticks every ``SPENDING_UPDATE_INTERVAL`` and runs only the providers whose
``next_check_at`` has passed. Discovery is cheap; a download happens only when
the release id changed. Failures are recorded per provider and never affect
the others; a failed source is due again at the next tick; ``UpdateFailed`` is
raised only when no configured source has any data.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from aiohttp import ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, SPENDING_UPDATE_INTERVAL
from .models import ProviderHealth, ProviderState, SourceSeries
from .providers.base import SchemaChangedError, SourceUnavailableError, SpendingProvider
from .store import SpendingStore

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SpendingSnapshot:
    """What entities and diagnostics read: one series per source."""

    series: Mapping[str, SourceSeries]
    refreshed_at: datetime

    def get(self, source_id: str) -> SourceSeries:
        return self.series[source_id]


class SpendingCoordinator(DataUpdateCoordinator[SpendingSnapshot]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        *,
        session: ClientSession,
        store: SpendingStore,
        providers: Sequence[SpendingProvider],
        clock: Callable[[], datetime] = dt_util.utcnow,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_spending",
            update_interval=SPENDING_UPDATE_INTERVAL,
        )
        self.entry = entry
        self.store = store
        self.providers = tuple(providers)
        self._session = session
        self._clock = clock

    async def async_setup(self) -> None:
        await self.store.async_load()
        self.data = self._snapshot(self._clock())

    async def async_shutdown(self) -> None:
        await self.store.async_save(immediate=True)
        await super().async_shutdown()

    def _snapshot(self, now: datetime) -> SpendingSnapshot:
        return SpendingSnapshot(dict(self.store.series), now)

    async def _async_update_data(self) -> SpendingSnapshot:
        now = self._clock()
        for provider in self.providers:
            health = self.store.get(provider.spec.source_id).health
            if health.next_check_at is not None and now < health.next_check_at:
                continue
            await self._async_refresh_provider(provider, now)
        await self.store.async_save()
        configured = [provider.spec.source_id for provider in self.providers]
        stored = {source_id: self.store.get(source_id) for source_id in configured}
        if configured and not any(series.datapoints for series in stored.values()):
            errors = {
                source_id: series.health.last_error
                for source_id, series in stored.items()
                if series.health.last_error
            }
            raise UpdateFailed(f"No spending source available: {errors}")
        return self._snapshot(now)

    async def async_refresh_source(self, source_id: str) -> None:
        """Run one provider now regardless of its cadence (diagnostics/scripts)."""
        provider = next(
            (p for p in self.providers if p.spec.source_id == source_id), None
        )
        if provider is None:
            raise ValueError(f"unknown spending source {source_id!r}")
        now = self._clock()
        await self._async_refresh_provider(provider, now)
        await self.store.async_save()
        self.async_set_updated_data(self._snapshot(now))

    async def _async_refresh_provider(
        self, provider: SpendingProvider, now: datetime
    ) -> None:
        source_id = provider.spec.source_id
        series = self.store.get(source_id)
        try:
            release = await provider.async_discover_latest(self._session)
            if (
                series.release is not None
                and series.release.release_id == release.release_id
                and series.datapoints
            ):
                self._set_health(
                    source_id,
                    now,
                    state=ProviderState.AVAILABLE,
                    next_check_at=now + provider.spec.check_interval,
                    skip_reason="unchanged_release",
                )
                return
            fetched, payload = await provider.async_fetch_release(
                self._session, release
            )
            if (
                series.release is not None
                and series.datapoints
                and fetched.checksum is not None
                and fetched.checksum == series.release.checksum
            ):
                fetched = dataclasses.replace(
                    fetched, layout_fingerprint=series.release.layout_fingerprint
                )
                self.store.refresh_release(source_id, fetched, now=now)
                self._set_health(
                    source_id,
                    now,
                    state=ProviderState.AVAILABLE,
                    next_check_at=now + provider.spec.check_interval,
                    skip_reason="unchanged_checksum",
                )
                return
            result = await self.hass.async_add_executor_job(
                provider.parse_release, payload, fetched
            )
            fetched = dataclasses.replace(
                fetched, layout_fingerprint=result.layout_fingerprint
            )
            applied = self.store.apply_release(
                source_id, fetched, result.datapoints, now=now, warnings=result.warnings
            )
            self._set_health(
                source_id,
                now,
                state=ProviderState.AVAILABLE,
                next_check_at=now + provider.spec.check_interval,
                skip_reason=None,
            )
            _LOGGER.debug(
                "%s: release %s → +%d ~%d =%d (carried %d, revisions %d)",
                source_id,
                fetched.release_id,
                applied.added,
                applied.updated,
                applied.unchanged,
                applied.carried_over,
                len(applied.revisions),
            )
        except SourceUnavailableError as err:
            state = (
                ProviderState.STALE_BUT_CACHED
                if series.datapoints
                else ProviderState.TEMPORARILY_UNAVAILABLE
            )
            _LOGGER.warning("%s unavailable: %s", source_id, err)
            self._set_health(
                source_id,
                now,
                state=state,
                next_check_at=now,  # S44: due at the next tick
                error=str(err),
            )
        except SchemaChangedError as err:
            _LOGGER.error("%s layout changed, keeping stored data: %s", source_id, err)
            self._set_health(
                source_id,
                now,
                state=ProviderState.SCHEMA_CHANGED,
                next_check_at=now + provider.spec.check_interval,
                error=str(err),
            )
        except Exception as err:
            _LOGGER.exception("%s failed, keeping stored data", source_id)
            self._set_health(
                source_id,
                now,
                state=ProviderState.PARSER_ERROR,
                next_check_at=now + provider.spec.check_interval,
                error=str(err),
            )

    def _set_health(
        self,
        source_id: str,
        now: datetime,
        *,
        state: ProviderState,
        next_check_at: datetime,
        skip_reason: str | None = None,
        error: str | None = None,
    ) -> None:
        current = self.store.get(source_id).health
        self.store.set_health(
            source_id,
            ProviderHealth(
                state=state,
                last_check_at=now,
                next_check_at=next_check_at,
                last_success_at=now
                if state is ProviderState.AVAILABLE
                else current.last_success_at,
                last_error=error,
                warnings=current.warnings,
                skip_reason=skip_reason,
            ),
        )

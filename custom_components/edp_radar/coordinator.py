"""DataUpdateCoordinator: ingestion, storage, metrics (plan §33, D8, D9, D11, D25).

The coordinator owns the store and both clients. A background task performs the
400-day bootstrap once; afterwards every scheduled refresh fetches the notices
published since the last known publication date (with overlap), refreshes FX,
prunes, persists, recomputes the ``RadarSnapshot`` and dispatches events for
notice versions that are new to the store.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import TedApiClient, TedApiError
from .config import RadarConfig
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, INCREMENTAL_OVERLAP_DAYS
from .fx import EcbFxClient, EcbFxError
from .metrics import (
    RadarSnapshot,
    compute_snapshot,
    event_type_for,
    is_central_purchasing_only,
    notice_event_attributes,
    watchlist_matches,
)
from .models import ProcurementNotice
from .normalizer import REQUESTED_FIELDS, normalize_many
from .storage import FX_RETENTION_MARGIN, RadarStore
from .taxonomy import Taxonomy

_LOGGER = logging.getLogger(__name__)

SIGNAL_ACTIVITY = f"{DOMAIN}_activity_{{}}"
SIGNAL_WATCHLIST = f"{DOMAIN}_watchlist_{{}}"
BOOTSTRAP_RETRY_SECONDS = 900
SAVE_EVERY_PAGES = 10
PAGE_BATCH = 200

type EdpRadarConfigEntry = ConfigEntry[EdpRadarCoordinator]
type ProgressCallback = Callable[[int, int | None], None]


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
        self.bootstrap_progress: tuple[int, int | None] | None = None
        self._bootstrap_task: asyncio.Task[None] | None = None
        self._bootstrap_retry: CALLBACK_TYPE | None = None

    @property
    def signal_activity(self) -> str:
        return SIGNAL_ACTIVITY.format(self.entry.entry_id)

    @property
    def signal_watchlist(self) -> str:
        return SIGNAL_WATCHLIST.format(self.entry.entry_id)

    # ------------------------------------------------------------- lifecycle

    async def async_setup(self) -> None:
        """Load stored data; the first refresh starts the bootstrap if needed (D8)."""
        await self.store.async_load()
        self.store.index.retention_days = self.config.retention_days

    async def async_shutdown(self) -> None:
        """Cancel background work, persist immediately, stop scheduling."""
        if self._bootstrap_retry is not None:
            self._bootstrap_retry()
            self._bootstrap_retry = None
        if self._bootstrap_task is not None and not self._bootstrap_task.done():
            self._bootstrap_task.cancel()
        self._bootstrap_task = None
        await self.store.async_save(immediate=True)
        await super().async_shutdown()

    def _ensure_bootstrap(self) -> None:
        if self.store.index.bootstrap_complete:
            return
        if self._bootstrap_task is not None and not self._bootstrap_task.done():
            return
        self._bootstrap_task = self.entry.async_create_background_task(
            self.hass, self._async_bootstrap(), f"{DOMAIN} bootstrap"
        )

    @callback
    def _async_retry_bootstrap(self, _now: datetime) -> None:
        self._bootstrap_retry = None
        self._ensure_bootstrap()

    # ------------------------------------------------------------- ingestion

    async def _async_ingest(
        self, query: str, *, progress: ProgressCallback | None = None
    ) -> list[ProcurementNotice]:
        """Fetch, normalize and store; return the notice versions that were new."""
        new: list[ProcurementNotice] = []
        batch: list[dict[str, Any]] = []
        pages = 0
        async for raw in self.client.async_search_notices(
            query, REQUESTED_FIELDS, progress=progress
        ):
            batch.append(raw)
            if len(batch) < PAGE_BATCH:
                continue
            new.extend(await self._async_store_batch(batch))
            batch = []
            pages += 1
            if pages % SAVE_EVERY_PAGES == 0:
                await self.store.async_save()
                self.async_update_listeners()
        if batch:
            new.extend(await self._async_store_batch(batch))
        return new

    async def _async_store_batch(
        self, batch: list[dict[str, Any]]
    ) -> list[ProcurementNotice]:
        notices, errors = await self.hass.async_add_executor_job(
            normalize_many, batch, self.taxonomy
        )
        self.store.index.parse_errors += errors
        return [n for n in notices if self.store.upsert(n)]

    async def _async_refresh_fx(self, *, history: bool, today: date) -> None:
        """Merge ECB rates inside the retention window; failures are non-fatal."""
        try:
            rates = await (
                self.fx_client.async_fetch_history()
                if history
                else self.fx_client.async_fetch_recent()
            )
        except EcbFxError as err:
            self.last_fx_error = str(err)
            _LOGGER.warning(
                "ECB rates unavailable (%s); EUR conversion may be incomplete", err
            )
            return
        self.last_fx_error = None
        cutoff = today - timedelta(days=self.config.retention_days)
        cutoff -= FX_RETENTION_MARGIN
        self.store.update_fx({d: r for d, r in rates.items() if d >= cutoff})

    def _finish_refresh(self, today: date) -> None:
        """Prune, then record what the store now knows (index bookkeeping)."""
        removed = self.store.prune(today)
        if removed:
            _LOGGER.debug("Pruned %s notice versions outside retention", removed)
        self.store.index.last_successful_update = datetime.now(tz=UTC)
        self.store.index.last_publication_date = max(
            (n.publication_date for n in self.store.notices.values()), default=None
        )
        self.store.index.taxonomy_version = self.taxonomy.version

    # ------------------------------------------------------------- bootstrap

    @callback
    def _on_progress(self, fetched: int, total: int | None) -> None:
        self.bootstrap_progress = (fetched, total)

    async def _async_bootstrap(self) -> None:
        """Fetch the whole retention window once (D8); retry later on TED errors."""
        today = dt_util.now().date()
        self.bootstrap_progress = (0, None)
        try:
            await self._async_refresh_fx(history=True, today=today)
            since = today - timedelta(days=self.config.bootstrap_days)
            query = self.config.universe_query(self.taxonomy, since)
            _LOGGER.info(
                "Bootstrapping %s days of TED notices", self.config.bootstrap_days
            )
            await self._async_ingest(query, progress=self._on_progress)
        except TedApiError as err:
            _LOGGER.warning(
                "Bootstrap failed (%s); retrying in %s s", err, BOOTSTRAP_RETRY_SECONDS
            )
            self.last_ted_error = str(err)
            self.bootstrap_progress = None
            self._bootstrap_retry = async_call_later(
                self.hass, BOOTSTRAP_RETRY_SECONDS, self._async_retry_bootstrap
            )
            return
        self.last_ted_error = None
        # Nothing ingested during bootstrap is an event (plan §42).
        self.store.mark_events_emitted(self._version_keys_oldest_first())
        self._finish_refresh(today)
        self.store.index.bootstrap_complete = True
        await self.store.async_save(immediate=True)
        self.bootstrap_progress = None
        _LOGGER.info("Bootstrap complete: %s notice versions", len(self.store.notices))
        self.async_set_updated_data(await self._async_compute(bootstrap_complete=True))

    def _version_keys_oldest_first(self) -> Iterable[str]:
        ordered = sorted(
            self.store.notices.values(),
            key=lambda n: (n.publication_date, n.notice_version),
        )
        return (n.version_key for n in ordered)

    # ------------------------------------------------------------- refresh

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
                computed_at=datetime.now(tz=UTC),
            )
        )

    def _is_bootstrapped(self) -> bool:
        # A method rather than an attribute read: the flag flips in another task
        # while this one awaits, so it must be re-read without type narrowing.
        return self.store.index.bootstrap_complete

    async def _async_update_data(self) -> RadarSnapshot:
        if self._is_bootstrapped():
            return await self._async_incremental_refresh()
        self._ensure_bootstrap()
        snapshot = await self._async_compute(bootstrap_complete=False)
        if not self._is_bootstrapped():
            return snapshot
        # The bootstrap finished while we were computing: never publish a
        # stale partial snapshot over its complete one.
        return await self._async_compute(bootstrap_complete=True)

    async def _async_incremental_refresh(self) -> RadarSnapshot:
        today = dt_util.now().date()
        floor = today - timedelta(days=self.config.bootstrap_days)
        last = self.store.index.last_publication_date or floor
        since = max(floor, last - timedelta(days=INCREMENTAL_OVERLAP_DAYS))
        query = self.config.universe_query(self.taxonomy, since)
        try:
            new = await self._async_ingest(query)
        except TedApiError as err:
            self.last_ted_error = str(err)
            if not self.store.notices:
                raise UpdateFailed(
                    f"TED unavailable and nothing stored: {err}"
                ) from err
            # D25: stale data beats unavailable entities.
            _LOGGER.warning("TED refresh failed (%s); serving stored data", err)
            return await self._async_compute(bootstrap_complete=True)
        self.last_ted_error = None
        await self._async_refresh_fx(history=False, today=today)
        self._finish_refresh(today)
        self._emit_events(new)
        await self.store.async_save()
        return await self._async_compute(bootstrap_complete=True)

    # ------------------------------------------------------------- events

    def _emit_events(self, new: list[ProcurementNotice]) -> None:
        emitted: list[str] = []
        for notice in new:
            if self.store.was_event_emitted(notice.version_key):
                continue
            self._emit(notice)
            emitted.append(notice.version_key)
        if emitted:
            self.store.mark_events_emitted(emitted)

    def _emit(self, notice: ProcurementNotice) -> None:
        """Dispatch activity and watchlist signals for one new notice version."""
        metrics = self.config.metrics
        if not self.taxonomy.is_relevant(notice.match_reasons, metrics.relevance_mode):
            return
        if is_central_purchasing_only(notice):
            return
        event_type = event_type_for(notice)
        if event_type is None:
            return
        own = metrics.own_organisation
        is_own = own is not None and own.matches(notice)
        attributes = notice_event_attributes(notice, self.store.fx)
        attributes["own_organisation"] = is_own
        in_market = (
            not metrics.market_countries
            or notice.buyer.country in metrics.market_countries
        )
        if in_market or is_own:
            async_dispatcher_send(
                self.hass, self.signal_activity, event_type, attributes
            )
        if watchlist_matches(notice, metrics.watchlist, self.store.fx):
            async_dispatcher_send(
                self.hass, self.signal_watchlist, event_type, attributes
            )

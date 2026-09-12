"""Local persistence: monthly notice partitions over Home Assistant's Store.

Layout (plan §31–32, addendum D12): ``edp_radar.<entry>.index``,
``edp_radar.<entry>.notices.<YYYY-MM>``, ``edp_radar.<entry>.fx`` and
``edp_radar.<entry>.events``. Only dirty partitions are written.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DEFAULT_RETENTION_DAYS, DOMAIN, EMITTED_EVENT_KEYS_LIMIT
from .fx_rates import FxRateTable
from .models import ProcurementNotice

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SCHEMA_VERSION = 1
SAVE_DELAY_SECONDS = 30
FX_RETENTION_MARGIN = timedelta(days=30)


@dataclass
class StoreIndex:
    schema_version: int = SCHEMA_VERSION
    partitions: list[str] = field(default_factory=list)
    last_successful_update: datetime | None = None
    last_publication_date: date | None = None
    bootstrap_complete: bool = False
    retention_days: int = DEFAULT_RETENTION_DAYS
    taxonomy_version: str | None = None
    parse_errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "partitions": sorted(self.partitions),
            "last_successful_update": (
                self.last_successful_update.isoformat()
                if self.last_successful_update
                else None
            ),
            "last_publication_date": (
                self.last_publication_date.isoformat()
                if self.last_publication_date
                else None
            ),
            "bootstrap_complete": self.bootstrap_complete,
            "retention_days": self.retention_days,
            "taxonomy_version": self.taxonomy_version,
            "parse_errors": self.parse_errors,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StoreIndex:
        return cls(
            schema_version=int(data.get("schema_version", 0)),
            partitions=sorted(data.get("partitions") or []),
            last_successful_update=(
                datetime.fromisoformat(data["last_successful_update"])
                if data.get("last_successful_update")
                else None
            ),
            last_publication_date=(
                date.fromisoformat(data["last_publication_date"])
                if data.get("last_publication_date")
                else None
            ),
            bootstrap_complete=bool(data.get("bootstrap_complete", False)),
            retention_days=int(data.get("retention_days", DEFAULT_RETENTION_DAYS)),
            taxonomy_version=data.get("taxonomy_version"),
            parse_errors=int(data.get("parse_errors", 0)),
        )


def _deserialize(items: list[dict[str, Any]]) -> list[ProcurementNotice]:
    """Executor job: dataclass construction for thousands of notices is slow."""
    return [ProcurementNotice.from_dict(item) for item in items]


def _serialize(notices: list[ProcurementNotice]) -> list[dict[str, Any]]:
    """Executor job: ``asdict`` deep-copies; notices are frozen so this is safe."""
    return [n.to_dict() for n in notices]


class RadarStore:
    """Normalized notices partitioned by publication month, plus index/FX/events."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        *,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> None:
        self._hass = hass
        self._prefix = f"{DOMAIN}.{entry_id}"
        self.index = StoreIndex(retention_days=retention_days)
        self.notices: dict[str, ProcurementNotice] = {}
        self.fx = FxRateTable()
        self.emitted_event_keys: dict[str, None] = {}
        self._index_store = self._store("index")
        self._fx_store = self._store("fx")
        self._events_store = self._store("events")
        self._partition_stores: dict[str, Store[dict[str, Any]]] = {}
        self._dirty_partitions: set[str] = set()
        self._fx_dirty = False
        self._events_dirty = False

    @staticmethod
    def partition_key(day: date) -> str:
        return day.strftime("%Y-%m")

    def _store(self, suffix: str) -> Store[dict[str, Any]]:
        return Store(self._hass, STORAGE_VERSION, f"{self._prefix}.{suffix}")

    def _partition_store(self, month: str) -> Store[dict[str, Any]]:
        if month not in self._partition_stores:
            self._partition_stores[month] = self._store(f"notices.{month}")
        return self._partition_stores[month]

    async def async_load(self) -> None:
        retention = self.index.retention_days
        raw_index = await self._index_store.async_load()
        loaded = StoreIndex.from_dict(raw_index) if raw_index else StoreIndex()
        if loaded.schema_version != SCHEMA_VERSION:
            _LOGGER.warning(
                "Discarding stored radar data with schema %s (current %s)",
                loaded.schema_version,
                SCHEMA_VERSION,
            )
            for month in loaded.partitions:
                await self._partition_store(month).async_remove()
            loaded = StoreIndex()
        loaded.retention_days = retention
        self.index = loaded

        kept: list[str] = []
        for month in list(self.index.partitions):
            data = await self._partition_store(month).async_load()
            if not data or data.get("schema_version") != SCHEMA_VERSION:
                _LOGGER.warning(
                    "Partition %s missing or incompatible; bootstrap required", month
                )
                self.index.bootstrap_complete = False
                continue
            notices = await self._hass.async_add_executor_job(
                _deserialize, data.get("notices") or []
            )
            for notice in notices:
                self.notices[notice.version_key] = notice
            kept.append(month)
        self.index.partitions = sorted(kept)

        raw_fx = await self._fx_store.async_load()
        if raw_fx and raw_fx.get("schema_version") == SCHEMA_VERSION:
            self.fx = FxRateTable.from_dict(raw_fx.get("rates") or {})
        raw_events = await self._events_store.async_load()
        if raw_events:
            self.emitted_event_keys = dict.fromkeys(raw_events.get("keys") or [])

    def upsert(self, notice: ProcurementNotice) -> bool:
        """Store a notice version; return True when the version key is new."""
        key = notice.version_key
        is_new = key not in self.notices
        if is_new or self.notices[key] != notice:
            self.notices[key] = notice
            month = self.partition_key(notice.publication_date)
            self._dirty_partitions.add(month)
            if month not in self.index.partitions:
                self.index.partitions = sorted([*self.index.partitions, month])
        return is_new

    def upsert_many(self, notices: Iterable[ProcurementNotice]) -> int:
        return sum(1 for notice in notices if self.upsert(notice))

    def prune(self, today: date) -> int:
        """Drop notices older than the retention window; return how many."""
        cutoff = today - timedelta(days=self.index.retention_days)
        removed = [
            key for key, n in self.notices.items() if n.publication_date < cutoff
        ]
        for key in removed:
            self._dirty_partitions.add(
                self.partition_key(self.notices[key].publication_date)
            )
            del self.notices[key]
        self.fx.prune_before(cutoff - FX_RETENTION_MARGIN)
        self._fx_dirty = True
        return len(removed)

    def mark_events_emitted(self, keys: Iterable[str]) -> None:
        for key in keys:
            self.emitted_event_keys.pop(key, None)
            self.emitted_event_keys[key] = None
        while len(self.emitted_event_keys) > EMITTED_EVENT_KEYS_LIMIT:
            del self.emitted_event_keys[next(iter(self.emitted_event_keys))]
        self._events_dirty = True

    def was_event_emitted(self, key: str) -> bool:
        return key in self.emitted_event_keys

    def update_fx(self, rates: Mapping[date, Mapping[str, Decimal]]) -> int:
        added = self.fx.update(rates)
        self._fx_dirty = True
        return added

    def _partition_notices(self, month: str) -> list[ProcurementNotice]:
        return [
            n
            for n in self.notices.values()
            if self.partition_key(n.publication_date) == month
        ]

    async def _async_write(
        self, store: Store[dict[str, Any]], payload: dict[str, Any], immediate: bool
    ) -> None:
        if immediate:
            await store.async_save(payload)
        else:
            store.async_delay_save(lambda: payload, SAVE_DELAY_SECONDS)

    async def async_save(self, *, immediate: bool = False) -> None:
        """Write dirty partitions, FX, events and the index (delayed by default).

        The dirty flags are taken before the first await so that changes made
        while a partition is being serialized (in the executor) stay dirty.
        """
        dirty = sorted(self._dirty_partitions)
        self._dirty_partitions.clear()
        fx_dirty, self._fx_dirty = self._fx_dirty, False
        events_dirty, self._events_dirty = self._events_dirty, False
        for month in dirty:
            notices = self._partition_notices(month)
            store = self._partition_store(month)
            if not notices:
                await store.async_remove()
                self.index.partitions = [m for m in self.index.partitions if m != month]
                continue
            serialized = await self._hass.async_add_executor_job(_serialize, notices)
            payload = {
                "schema_version": SCHEMA_VERSION,
                "month": month,
                "notices": serialized,
            }
            await self._async_write(store, payload, immediate)
        if fx_dirty:
            fx_payload = {"schema_version": SCHEMA_VERSION, "rates": self.fx.to_dict()}
            await self._async_write(self._fx_store, fx_payload, immediate)
        if events_dirty:
            events_payload = {"keys": list(self.emitted_event_keys)}
            await self._async_write(self._events_store, events_payload, immediate)
        await self._async_write(self._index_store, self.index.to_dict(), immediate)

    async def async_remove(self) -> None:
        for month in list(self.index.partitions):
            await self._partition_store(month).async_remove()
        await self._fx_store.async_remove()
        await self._events_store.async_remove()
        await self._index_store.async_remove()
        self.notices.clear()
        self.index = StoreIndex(retention_days=self.index.retention_days)

"""Per-source persistence of spending series (S13; plan §62, §66, §67).

Every release replaces the series: datapoints present in the new release are
added or updated (a changed value records a ``Revision``), datapoints absent
from it are carried over with their original provenance so history survives
sources that drop old years. A datapoint whose key differs from a new one
only in ``unit`` is superseded (S39).
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..const import DOMAIN
from .models import (
    DatapointKey,
    ProviderHealth,
    ProviderState,
    Revision,
    SourceRelease,
    SourceSeries,
    SpendingDataPoint,
)
from .registry import SOURCE_ORDER

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SCHEMA_VERSION = 1
SAVE_DELAY_SECONDS = 30

# Newest revisions kept per source; older ones are dropped (plan §62 keeps the
# previous value of a change, not an unbounded audit log).
MAX_REVISIONS = 1000


def storage_key(entry_id: str, source_id: str) -> str:
    return f"{DOMAIN}.{entry_id}.spending.{source_id}"


def health_storage_key(entry_id: str) -> str:
    """One small store for every source's health (S40): written on every tick."""
    return f"{DOMAIN}.{entry_id}.spending.health"


def _constant(payload: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    """A zero-argument callable for ``Store.async_delay_save`` that always
    returns the same, already-computed payload."""
    return lambda: payload


@dataclass(frozen=True, slots=True)
class ApplyResult:
    added: int
    updated: int
    unchanged: int
    carried_over: int
    revisions: tuple[Revision, ...]
    superseded: int = 0


@dataclass(frozen=True, slots=True)
class _ReleaseDiff:
    """Pure result of merging one release's datapoints into the existing ones."""

    merged: dict[DatapointKey, SpendingDataPoint]
    added: int
    updated: int
    unchanged: int
    superseded: int
    revisions: tuple[Revision, ...]
    unit_changes: dict[tuple[str, str], int]


def _diff_release(
    existing: dict[DatapointKey, SpendingDataPoint],
    incoming: dict[DatapointKey, SpendingDataPoint],
    now: datetime,
) -> _ReleaseDiff:
    # S39: a datapoint whose key differs from a new one only in ``unit``
    # (constant-price base year moved) is replaced, not kept beside it.
    by_base: dict[tuple[str, ...], list[DatapointKey]] = {}
    for key in existing:
        by_base.setdefault(key[:5], []).append(key)
    merged = dict(existing)
    added = updated = unchanged = superseded = 0
    revisions: list[Revision] = []
    unit_changes: dict[tuple[str, str], int] = {}
    for key, point in incoming.items():
        previous = existing.get(key)
        if previous is None:
            old_keys = [
                k for k in by_base.get(key[:5], ()) if k not in incoming and k in merged
            ]
            if not old_keys:
                added += 1
            else:
                for old_key in old_keys:
                    old = merged.pop(old_key)
                    superseded += 1
                    change = (old.unit, point.unit)
                    unit_changes[change] = unit_changes.get(change, 0) + 1
                    revisions.append(
                        Revision(
                            key=point.key,
                            previous_value=old.value,
                            previous_release_id=old.release_id,
                            new_value=point.value,
                            release_id=point.release_id,
                            detected_at=now,
                        )
                    )
        elif previous.value != point.value:
            updated += 1
            revisions.append(
                Revision(
                    key=point.key,
                    previous_value=previous.value,
                    previous_release_id=previous.release_id,
                    new_value=point.value,
                    release_id=point.release_id,
                    detected_at=now,
                )
            )
        else:
            unchanged += 1
        merged[key] = point
    return _ReleaseDiff(
        merged=merged,
        added=added,
        updated=updated,
        unchanged=unchanged,
        superseded=superseded,
        revisions=tuple(revisions),
        unit_changes=unit_changes,
    )


class SpendingStore:
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._hass = hass
        self._entry_id = entry_id
        self._stores: dict[str, Store[dict[str, Any]]] = {
            source_id: Store(hass, STORAGE_VERSION, storage_key(entry_id, source_id))
            for source_id in SOURCE_ORDER
        }
        self._health_store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, health_storage_key(entry_id)
        )
        self.series: dict[str, SourceSeries] = {
            source_id: SourceSeries.empty(source_id) for source_id in SOURCE_ORDER
        }
        self._dirty: set[str] = set()
        self._pending: set[str] = set()
        self._health_dirty = False
        self._health_pending = False

    async def async_load(self) -> None:
        for source_id, store in self._stores.items():
            data = await store.async_load()
            if (
                not isinstance(data, dict)
                or data.get("schema_version") != SCHEMA_VERSION
            ):
                if data:
                    _LOGGER.warning(
                        "Discarding %s: %s",
                        source_id,
                        f"schema {data.get('schema_version')}"
                        if isinstance(data, dict)
                        else f"unexpected {type(data).__name__}",
                    )
                continue
            try:
                # Series files written before S40 still carry ``health``; it is
                # the fallback until the health store exists.
                self.series[source_id] = SourceSeries.from_dict(data["series"])
            except (KeyError, ValueError, TypeError) as err:
                _LOGGER.warning("Discarding stored %s series: %s", source_id, err)
        # Typed as ``object``: like the series files, whatever is actually on
        # disk is not guaranteed to match the ``Store``'s declared type.
        health: object = await self._health_store.async_load()
        if not isinstance(health, dict):
            if health:
                _LOGGER.warning(
                    "Discarding health store: unexpected %s", type(health).__name__
                )
            return
        for source_id, raw in (health.get("health") or {}).items():
            if source_id not in self.series:
                continue  # an unknown source id is not corruption
            if not isinstance(raw, dict):
                _LOGGER.warning(
                    "Discarding stored %s health: unexpected %s",
                    source_id,
                    type(raw).__name__,
                )
                continue
            try:
                self.series[source_id] = dataclasses.replace(
                    self.series[source_id], health=ProviderHealth.from_dict(raw)
                )
            except (KeyError, ValueError, TypeError) as err:
                _LOGGER.warning("Discarding stored %s health: %s", source_id, err)

    def refresh_release(
        self, source_id: str, release: SourceRelease, *, now: datetime
    ) -> None:
        """A release whose payload matched the stored checksum: new metadata,
        same datapoints."""
        self.series[source_id] = dataclasses.replace(
            self.series[source_id], release=release, retrieved_at=now
        )
        self._dirty.add(source_id)

    def get(self, source_id: str) -> SourceSeries:
        return self.series[source_id]

    def apply_release(
        self,
        source_id: str,
        release: SourceRelease,
        datapoints: Iterable[SpendingDataPoint],
        *,
        now: datetime,
        warnings: tuple[str, ...] = (),
    ) -> ApplyResult:
        current = self.series[source_id]
        existing = {point.key: point for point in current.datapoints}
        incoming: dict[DatapointKey, SpendingDataPoint] = {}
        duplicates = 0
        for point in datapoints:
            if point.key in incoming:
                duplicates += 1
            incoming[point.key] = point
        diff = _diff_release(existing, incoming, now)
        carried_over = len(diff.merged) - len(incoming)
        notes = list(warnings)
        if duplicates:
            notes.append(
                f"{duplicates} duplicate keys within release {release.release_id} "
                "(last value kept)"
            )
        for (old_unit, new_unit), count in sorted(diff.unit_changes.items()):
            notes.append(f"unit changed {old_unit} → {new_unit} for {count} datapoints")
        health = dataclasses.replace(
            current.health,
            state=ProviderState.AVAILABLE,
            last_check_at=now,
            last_success_at=now,
            last_error=None,
            warnings=tuple(notes),
            skip_reason=None,
        )
        self.series[source_id] = SourceSeries(
            source_id=source_id,
            release=release,
            health=health,
            datapoints=tuple(diff.merged[key] for key in sorted(diff.merged)),
            revisions=(*current.revisions, *diff.revisions)[-MAX_REVISIONS:],
            retrieved_at=now,
        )
        self._dirty.add(source_id)
        self._health_dirty = True
        return ApplyResult(
            diff.added,
            diff.updated,
            diff.unchanged,
            carried_over,
            diff.revisions,
            diff.superseded,
        )

    def set_health(self, source_id: str, health: ProviderHealth) -> None:
        self.series[source_id] = dataclasses.replace(
            self.series[source_id], health=health
        )
        self._health_dirty = True

    def _payload(self, source_id: str) -> dict[str, Any]:
        series = self.series[source_id].to_dict()
        series.pop("health", None)  # S40: health has its own store
        return {"schema_version": SCHEMA_VERSION, "series": series}

    def _health_payload(self) -> dict[str, Any]:
        return {
            "health": {
                source_id: series.health.to_dict()
                for source_id, series in self.series.items()
            }
        }

    async def async_save(self, *, immediate: bool = False) -> None:
        """Write changed sources (delayed by default, as D12).

        Series payloads are serialised in the executor; the health payload is
        small and built inline. Sources with a delayed write still pending
        are rewritten by an immediate save (shutdown), so an unload never
        loses the last release. Health is written whenever it changed,
        without touching the series files (S40).
        """
        dirty = sorted(self._dirty | (self._pending if immediate else set()))
        self._dirty.clear()
        for source_id in dirty:
            payload = await self._hass.async_add_executor_job(self._payload, source_id)
            store = self._stores[source_id]
            if immediate:
                self._pending.discard(source_id)
                await store.async_save(payload)
            else:
                self._pending.add(source_id)
                store.async_delay_save(_constant(payload), SAVE_DELAY_SECONDS)
        if self._health_dirty or (immediate and self._health_pending):
            self._health_dirty = False
            health = self._health_payload()
            if immediate:
                self._health_pending = False
                await self._health_store.async_save(health)
            else:
                self._health_pending = True
                self._health_store.async_delay_save(
                    _constant(health), SAVE_DELAY_SECONDS
                )

    async def async_remove(self) -> None:
        for store in self._stores.values():
            await store.async_remove()
        await self._health_store.async_remove()
        self.series = {
            source_id: SourceSeries.empty(source_id) for source_id in SOURCE_ORDER
        }
        self._dirty.clear()
        self._pending.clear()
        self._health_dirty = False
        self._health_pending = False

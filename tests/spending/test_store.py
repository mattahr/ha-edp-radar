"""SpendingStore: per-source Store files, diff, revisions, removal (S13, S5)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.edp_radar.const import DOMAIN
from custom_components.edp_radar.spending.models import (
    DatapointStatus,
    ProviderHealth,
    ProviderState,
    ReferencePeriod,
    SourceRelease,
    SpendingDataPoint,
)
from custom_components.edp_radar.spending.store import (
    SAVE_DELAY_SECONDS,
    SCHEMA_VERSION,
    SpendingStore,
    storage_key,
)

ENTRY = "entry1"
NOW = datetime(2026, 9, 12, 21, 0, tzinfo=UTC)


def _release(release_id: str, published: date) -> SourceRelease:
    return SourceRelease(
        "statskontoret", release_id, published, "d", "c", "csv", checksum=release_id
    )


def _point(
    metric: str,
    year: int,
    month: int,
    value: str,
    release: SourceRelease,
    status: DatapointStatus = DatapointStatus.ACTUAL,
) -> SpendingDataPoint:
    return SpendingDataPoint(
        "statskontoret",
        metric,
        "SE",
        ReferencePeriod.month(year, month),
        Decimal(value),
        "SEK_MILLION",
        status,
        release.release_id,
        release.published_at,
        "u",
    )


async def test_fresh_store_has_empty_series_for_every_source(
    hass: HomeAssistant,
) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    assert sorted(store.series) == ["eda", "eurostat", "nato", "sipri", "statskontoret"]
    assert store.get("nato").health.state is ProviderState.NEVER_LOADED
    assert storage_key(ENTRY, "nato") == f"{DOMAIN}.{ENTRY}.spending.nato"


async def test_apply_release_persists_and_reloads(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    first = _release("2025-12-preliminar-2026-01-28", date(2026, 1, 28))
    result = store.apply_release(
        "statskontoret",
        first,
        [
            _point("materiel_outturn", 2025, 11, "3638.46181911", first),
            _point(
                "materiel_outturn",
                2025,
                12,
                "19729.43332150",
                first,
                DatapointStatus.PRELIMINARY,
            ),
        ],
        now=NOW,
        warnings=("w1",),
    )
    assert (result.added, result.updated, result.unchanged, result.carried_over) == (
        2,
        0,
        0,
        0,
    )
    assert result.revisions == ()
    series = store.get("statskontoret")
    assert series.release == first
    assert series.retrieved_at == NOW
    assert series.health.state is ProviderState.AVAILABLE
    assert series.health.last_success_at == NOW
    assert series.health.warnings == ("w1",)
    await store.async_save(immediate=True)
    stored = hass_storage[storage_key(ENTRY, "statskontoret")]["data"]
    assert stored["schema_version"] == SCHEMA_VERSION
    assert len(stored["series"]["datapoints"]) == 2

    reloaded = SpendingStore(hass, ENTRY)
    await reloaded.async_load()
    assert reloaded.get("statskontoret") == series


async def test_second_release_updates_records_revision_and_carries_over(
    hass: HomeAssistant,
) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    first = _release("2025-12-preliminar-2026-01-28", date(2026, 1, 28))
    store.apply_release(
        "statskontoret",
        first,
        [
            _point("materiel_outturn", 2025, 11, "3638.46181911", first),
            _point(
                "materiel_outturn",
                2025,
                12,
                "19729.43332150",
                first,
                DatapointStatus.PRELIMINARY,
            ),
            _point(
                "uo6_total_outturn",
                2025,
                12,
                "34786.38436460",
                first,
                DatapointStatus.PRELIMINARY,
            ),
        ],
        now=NOW,
    )
    second = _release("2025-12-definitiv-2026-03-24", date(2026, 3, 24))
    result = store.apply_release(
        "statskontoret",
        second,
        [
            _point("materiel_outturn", 2025, 11, "3638.46181911", second),
            _point("materiel_outturn", 2025, 12, "23327.02469578", second),
        ],
        now=NOW,
    )
    assert (result.added, result.updated, result.unchanged, result.carried_over) == (
        0,
        1,
        1,
        1,
    )
    assert len(result.revisions) == 1
    revision = result.revisions[0]
    assert revision.previous_value == Decimal("19729.43332150")
    assert revision.new_value == Decimal("23327.02469578")
    assert revision.previous_release_id == first.release_id
    assert revision.release_id == second.release_id
    assert revision.detected_at == NOW
    series = store.get("statskontoret")
    by_key = {p.key: p for p in series.datapoints}
    december = by_key[
        (
            "statskontoret",
            "materiel_outturn",
            "SE",
            "2025-12-01",
            "2025-12-31",
            "SEK_MILLION",
        )
    ]
    assert december.value == Decimal("23327.02469578")
    assert december.status is DatapointStatus.ACTUAL
    assert december.release_id == second.release_id
    november = by_key[
        (
            "statskontoret",
            "materiel_outturn",
            "SE",
            "2025-11-01",
            "2025-11-30",
            "SEK_MILLION",
        )
    ]
    assert (
        november.release_id == second.release_id
    )  # unchanged value, newest provenance
    carried = by_key[
        (
            "statskontoret",
            "uo6_total_outturn",
            "SE",
            "2025-12-01",
            "2025-12-31",
            "SEK_MILLION",
        )
    ]
    assert carried.release_id == first.release_id
    assert series.revisions == result.revisions
    assert [p.key for p in series.datapoints] == sorted(
        p.key for p in series.datapoints
    )


async def test_set_health_and_remove(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    store.set_health(
        "nato",
        ProviderHealth(
            state=ProviderState.TEMPORARILY_UNAVAILABLE, last_error="HTTP 503"
        ),
    )
    await store.async_save(immediate=True)
    assert (
        hass_storage[storage_key(ENTRY, "nato")]["data"]["series"]["health"][
            "last_error"
        ]
        == "HTTP 503"
    )
    assert (
        storage_key(ENTRY, "eda") not in hass_storage
    )  # untouched sources are not written
    await store.async_remove()
    assert not [k for k in hass_storage if ".spending." in k]


async def test_delayed_save_writes_after_the_delay(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    first = _release("2025-12-preliminar-2026-01-28", date(2026, 1, 28))
    store.apply_release(
        "statskontoret",
        first,
        [_point("materiel_outturn", 2025, 11, "3638.46181911", first)],
        now=NOW,
    )
    await store.async_save()
    assert storage_key(ENTRY, "statskontoret") not in hass_storage

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=SAVE_DELAY_SECONDS + 1)
    )
    await hass.async_block_till_done()
    stored = hass_storage[storage_key(ENTRY, "statskontoret")]["data"]
    assert len(stored["series"]["datapoints"]) == 1


async def test_immediate_save_flushes_a_pending_delayed_write(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    first = _release("2025-12-preliminar-2026-01-28", date(2026, 1, 28))
    store.apply_release(
        "statskontoret",
        first,
        [_point("materiel_outturn", 2025, 11, "3638.46181911", first)],
        now=NOW,
    )
    await store.async_save()
    assert storage_key(ENTRY, "statskontoret") not in hass_storage

    await store.async_save(immediate=True)
    stored = hass_storage[storage_key(ENTRY, "statskontoret")]["data"]
    assert len(stored["series"]["datapoints"]) == 1

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=SAVE_DELAY_SECONDS + 1)
    )
    await hass.async_block_till_done()
    assert hass_storage[storage_key(ENTRY, "statskontoret")]["data"] == stored

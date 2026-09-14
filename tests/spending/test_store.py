"""SpendingStore: per-source Store files, diff, revisions, removal (S13, S5)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.edp_radar.const import DOMAIN
from custom_components.edp_radar.spending import store as store_module
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
    health_storage_key,
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
        hass_storage[health_storage_key(ENTRY)]["data"]["health"]["nato"]["last_error"]
        == "HTTP 503"
    )
    assert (
        storage_key(ENTRY, "nato") not in hass_storage
    )  # a health-only change never writes the series file (S40)
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


async def test_health_lives_in_its_own_store(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    release = _release("r1", date(2026, 8, 24))
    store.apply_release(
        "statskontoret",
        release,
        [_point("materiel_outturn", 2026, 7, "1", release)],
        now=NOW,
    )
    await store.async_save(immediate=True)
    series_key = storage_key(ENTRY, "statskontoret")
    health_key = health_storage_key(ENTRY)
    assert "health" not in hass_storage[series_key]["data"]["series"]
    stored_health = hass_storage[health_key]["data"]["health"]
    assert stored_health["statskontoret"]["state"] == "available"
    assert stored_health["nato"]["state"] == "never_loaded"

    # A health-only change rewrites the health store, never the series file.
    hass_storage[series_key]["data"]["marker"] = True
    store.set_health(
        "statskontoret",
        ProviderHealth(state=ProviderState.STALE_BUT_CACHED, last_check_at=NOW),
    )
    await store.async_save(immediate=True)
    assert hass_storage[series_key]["data"]["marker"] is True
    assert (
        hass_storage[health_key]["data"]["health"]["statskontoret"]["state"]
        == "stale_but_cached"
    )

    reloaded = SpendingStore(hass, ENTRY)
    await reloaded.async_load()
    assert reloaded.get("statskontoret").health.state is ProviderState.STALE_BUT_CACHED
    assert len(reloaded.get("statskontoret").datapoints) == 1


async def test_health_falls_back_to_the_old_series_file(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    hass_storage[storage_key(ENTRY, "nato")] = {
        "version": 1,
        "key": storage_key(ENTRY, "nato"),
        "data": {
            "schema_version": SCHEMA_VERSION,
            "series": {
                "source_id": "nato",
                "release": None,
                "health": {"state": "parser_error", "last_error": "boom"},
                "datapoints": [],
                "revisions": [],
                "retrieved_at": None,
            },
        },
    }
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    assert store.get("nato").health.state is ProviderState.PARSER_ERROR
    assert store.get("nato").health.last_error == "boom"


async def test_corrupt_series_file_is_discarded(
    hass: HomeAssistant, hass_storage: dict[str, Any], caplog: Any
) -> None:
    hass_storage[storage_key(ENTRY, "nato")] = {
        "version": 1,
        "key": storage_key(ENTRY, "nato"),
        "data": ["not", "a", "dict"],
    }
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    assert store.get("nato").datapoints == ()
    assert "Discarding nato" in caplog.text


async def test_corrupt_health_store_is_discarded(
    hass: HomeAssistant, hass_storage: dict[str, Any], caplog: Any
) -> None:
    hass_storage[health_storage_key(ENTRY)] = {
        "version": 1,
        "key": health_storage_key(ENTRY),
        "data": ["not", "a", "dict"],
    }
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    assert all(
        series.health.state is ProviderState.NEVER_LOADED
        for series in store.series.values()
    )
    assert "Discarding health store" in caplog.text


async def test_malformed_per_source_health_is_discarded(
    hass: HomeAssistant, hass_storage: dict[str, Any], caplog: Any
) -> None:
    hass_storage[health_storage_key(ENTRY)] = {
        "version": 1,
        "key": health_storage_key(ENTRY),
        "data": {"health": {"nato": "garbage"}},
    }
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    assert store.get("nato").health.state is ProviderState.NEVER_LOADED
    assert "Discarding stored nato health" in caplog.text


async def test_refresh_release_replaces_release_only(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    first = _release("r1", date(2026, 8, 24))
    store.apply_release(
        "statskontoret",
        first,
        [_point("materiel_outturn", 2026, 7, "1", first)],
        now=NOW,
    )
    await store.async_save(immediate=True)
    later = NOW + timedelta(hours=6)
    store.refresh_release("statskontoret", _release("r2", date(2026, 8, 25)), now=later)
    await store.async_save(immediate=True)
    series = hass_storage[storage_key(ENTRY, "statskontoret")]["data"]["series"]
    assert series["release"]["release_id"] == "r2"
    assert series["retrieved_at"] == later.isoformat()
    assert len(series["datapoints"]) == 1
    assert series["datapoints"][0]["release_id"] == "r1"


async def test_remove_deletes_the_health_store(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    store.set_health("eda", ProviderHealth(state=ProviderState.AVAILABLE))
    await store.async_save(immediate=True)
    assert health_storage_key(ENTRY) in hass_storage
    await store.async_remove()
    assert health_storage_key(ENTRY) not in hass_storage
    assert store.get("eda").health.state is ProviderState.NEVER_LOADED


async def test_unit_change_supersedes_the_old_series(hass: HomeAssistant) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    v1 = SourceRelease(
        "sipri", "v1", date(2026, 4, 27), "d", "c", "xlsx", checksum="v1"
    )
    old = SpendingDataPoint(
        "sipri",
        "military_expenditure_usd_constant",
        "SE",
        ReferencePeriod.year(2024),
        Decimal("12046"),
        "USD_MILLION_CONSTANT_2024",
        DatapointStatus.ACTUAL,
        "v1",
        v1.published_at,
        "u",
    )
    store.apply_release("sipri", v1, [old], now=NOW)
    v2 = SourceRelease(
        "sipri", "v2", date(2027, 4, 26), "d", "c", "xlsx", checksum="v2"
    )
    new = dataclasses.replace(
        old, value=Decimal("12400"), unit="USD_MILLION_CONSTANT_2025", release_id="v2"
    )
    result = store.apply_release("sipri", v2, [new], now=NOW + timedelta(days=365))
    assert (result.added, result.updated, result.superseded, result.carried_over) == (
        0,
        0,
        1,
        0,
    )
    series = store.get("sipri")
    assert [p.unit for p in series.datapoints] == ["USD_MILLION_CONSTANT_2025"]
    revision = series.revisions[-1]
    assert revision.key == new.key
    assert revision.previous_value == Decimal("12046")
    assert revision.previous_release_id == "v1"
    assert series.health.warnings == (
        "unit changed USD_MILLION_CONSTANT_2024 → USD_MILLION_CONSTANT_2025 "
        "for 1 datapoints",
    )


async def test_duplicate_keys_within_a_release_are_counted(hass: HomeAssistant) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    release = _release("r1", date(2026, 8, 24))
    first = _point("materiel_outturn", 2026, 7, "1", release)
    second = _point("materiel_outturn", 2026, 7, "2", release)
    result = store.apply_release("statskontoret", release, [first, second], now=NOW)
    assert result.added == 1
    series = store.get("statskontoret")
    assert series.datapoints[0].value == Decimal("2")
    assert series.health.warnings == (
        "1 duplicate keys within release r1 (last value kept)",
    )


async def test_revisions_are_capped(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(store_module, "MAX_REVISIONS", 3)
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    for number in range(1, 7):
        release = _release(f"r{number}", date(2026, 8, number))
        store.apply_release(
            "statskontoret",
            release,
            [_point("materiel_outturn", 2026, 7, str(number), release)],
            now=NOW + timedelta(days=number),
        )
    revisions = store.get("statskontoret").revisions
    assert [r.release_id for r in revisions] == ["r4", "r5", "r6"]


async def test_two_new_units_in_one_release_never_orphan_the_old_series(
    hass: HomeAssistant,
) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    v1 = SourceRelease(
        "sipri", "v1", date(2026, 4, 27), "d", "c", "xlsx", checksum="v1"
    )
    p2024 = SpendingDataPoint(
        "sipri",
        "military_expenditure_usd_constant",
        "SE",
        ReferencePeriod.year(2024),
        Decimal("12046"),
        "USD_MILLION_CONSTANT_2024",
        DatapointStatus.ACTUAL,
        "v1",
        v1.published_at,
        "u",
    )
    store.apply_release("sipri", v1, [p2024], now=NOW)

    v2 = SourceRelease(
        "sipri", "v2", date(2027, 4, 26), "d", "c", "xlsx", checksum="v2"
    )
    p2025 = dataclasses.replace(
        p2024, value=Decimal("12400"), unit="USD_MILLION_CONSTANT_2025", release_id="v2"
    )
    p2026 = dataclasses.replace(
        p2024, value=Decimal("12500"), unit="USD_MILLION_CONSTANT_2026", release_id="v2"
    )
    result_v2 = store.apply_release(
        "sipri", v2, [p2025, p2026], now=NOW + timedelta(days=365)
    )
    assert result_v2.added == 1
    assert result_v2.superseded == 1
    assert len(result_v2.revisions) == 1
    series_v2 = store.get("sipri")
    assert {p.unit for p in series_v2.datapoints} == {
        "USD_MILLION_CONSTANT_2025",
        "USD_MILLION_CONSTANT_2026",
    }
    assert series_v2.health.warnings == (
        "unit changed USD_MILLION_CONSTANT_2024 → USD_MILLION_CONSTANT_2025 "
        "for 1 datapoints",
    )

    v3 = SourceRelease(
        "sipri", "v3", date(2028, 4, 25), "d", "c", "xlsx", checksum="v3"
    )
    p2027 = dataclasses.replace(
        p2024, value=Decimal("12600"), unit="USD_MILLION_CONSTANT_2027", release_id="v3"
    )
    result_v3 = store.apply_release("sipri", v3, [p2027], now=NOW + timedelta(days=730))
    assert result_v3.superseded == 2
    series_v3 = store.get("sipri")
    assert {p.unit for p in series_v3.datapoints} == {"USD_MILLION_CONSTANT_2027"}
    assert len(result_v3.revisions) == 2
    assert {revision.previous_value for revision in result_v3.revisions} == {
        Decimal("12400"),
        Decimal("12500"),
    }
    assert series_v3.health.warnings == (
        "unit changed USD_MILLION_CONSTANT_2025 → USD_MILLION_CONSTANT_2027 "
        "for 1 datapoints",
        "unit changed USD_MILLION_CONSTANT_2026 → USD_MILLION_CONSTANT_2027 "
        "for 1 datapoints",
    )


async def test_old_unit_present_in_the_release_is_not_superseded(
    hass: HomeAssistant,
) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    v1 = SourceRelease(
        "sipri", "v1", date(2026, 4, 27), "d", "c", "xlsx", checksum="v1"
    )
    p2024 = SpendingDataPoint(
        "sipri",
        "military_expenditure_usd_constant",
        "SE",
        ReferencePeriod.year(2024),
        Decimal("12046"),
        "USD_MILLION_CONSTANT_2024",
        DatapointStatus.ACTUAL,
        "v1",
        v1.published_at,
        "u",
    )
    store.apply_release("sipri", v1, [p2024], now=NOW)

    v2 = SourceRelease(
        "sipri", "v2", date(2027, 4, 26), "d", "c", "xlsx", checksum="v2"
    )
    same_2024 = dataclasses.replace(p2024, release_id="v2")
    new_2025 = dataclasses.replace(
        p2024, value=Decimal("12400"), unit="USD_MILLION_CONSTANT_2025", release_id="v2"
    )
    result = store.apply_release(
        "sipri", v2, [same_2024, new_2025], now=NOW + timedelta(days=365)
    )
    assert result.superseded == 0
    assert result.unchanged == 1
    assert result.added == 1
    series = store.get("sipri")
    assert {p.unit for p in series.datapoints} == {
        "USD_MILLION_CONSTANT_2024",
        "USD_MILLION_CONSTANT_2025",
    }
    assert series.health.warnings == ()

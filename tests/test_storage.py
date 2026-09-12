from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.edp_radar.const import DOMAIN, EMITTED_EVENT_KEYS_LIMIT
from custom_components.edp_radar.storage import SCHEMA_VERSION, RadarStore, StoreIndex

from .factories import competition, make_notice

TODAY = date(2026, 9, 12)
ENTRY = "entry1"


def _key(suffix: str) -> str:
    return f"{DOMAIN}.{ENTRY}.{suffix}"


async def test_fresh_store_is_empty_and_not_bootstrapped(hass: HomeAssistant) -> None:
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    assert store.index == StoreIndex()
    assert store.notices == {}
    assert len(store.fx) == 0
    assert store.index.bootstrap_complete is False


async def test_save_writes_partitions_index_fx_and_events(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    assert store.upsert(competition("a", "p1", date(2026, 9, 1))) is True
    assert store.upsert(competition("b", "p2", date(2026, 8, 15))) is True
    assert store.upsert(competition("a", "p1", date(2026, 9, 1))) is False
    v2 = make_notice(notice_id="a", notice_version=2, publication_date=date(2026, 9, 3))
    assert store.upsert_many([v2]) == 1
    store.update_fx({date(2026, 9, 11): {"SEK": Decimal("11.2373")}})
    store.mark_events_emitted(["a:1"])
    store.index.bootstrap_complete = True
    store.index.last_successful_update = datetime(2026, 9, 12, 8, tzinfo=UTC)
    store.index.last_publication_date = date(2026, 9, 3)
    await store.async_save(immediate=True)

    assert sorted(store.index.partitions) == ["2026-08", "2026-09"]
    index = hass_storage[_key("index")]["data"]
    assert index["partitions"] == ["2026-08", "2026-09"]
    assert index["bootstrap_complete"] is True
    assert index["last_publication_date"] == "2026-09-03"
    september = hass_storage[_key("notices.2026-09")]["data"]
    assert september["schema_version"] == SCHEMA_VERSION
    assert sorted(n["notice_version"] for n in september["notices"]) == [1, 2]
    assert len(hass_storage[_key("notices.2026-08")]["data"]["notices"]) == 1
    assert hass_storage[_key("fx")]["data"]["rates"]["2026-09-11"]["SEK"] == "11.2373"
    assert hass_storage[_key("events")]["data"]["keys"] == ["a:1"]


async def test_restart_reloads_everything(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    first = RadarStore(hass, ENTRY)
    await first.async_load()
    first.upsert(competition("a", "p1", date(2026, 9, 1)))
    first.update_fx({date(2026, 9, 11): {"SEK": Decimal("11.2373")}})
    first.mark_events_emitted(["a:1"])
    first.index.bootstrap_complete = True
    first.index.bootstrap_days = first.bootstrap_days
    await first.async_save(immediate=True)

    second = RadarStore(hass, ENTRY)
    await second.async_load()
    assert second.index.bootstrap_complete is True
    assert list(second.notices) == ["a:1"]
    assert second.notices["a:1"] == first.notices["a:1"]
    rate = second.fx.rate_for("SEK", date(2026, 9, 11))
    assert rate == (Decimal("11.2373"), date(2026, 9, 11))
    assert second.was_event_emitted("a:1") is True
    assert second.was_event_emitted("b:1") is False


async def test_wider_bootstrap_window_requires_a_new_bootstrap(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Upgrading from 400 to 760 days re-fetches history without discarding data."""
    first = RadarStore(hass, ENTRY, retention_days=400, bootstrap_days=400)
    await first.async_load()
    first.upsert(competition("a", "p1", date(2026, 9, 1)))
    first.index.bootstrap_complete = True
    first.index.bootstrap_days = 400
    await first.async_save(immediate=True)
    assert hass_storage[f"{DOMAIN}.{ENTRY}.index"]["data"]["bootstrap_days"] == 400

    same = RadarStore(hass, ENTRY, retention_days=400, bootstrap_days=400)
    await same.async_load()
    assert same.index.bootstrap_complete is True

    wider = RadarStore(hass, ENTRY, retention_days=760, bootstrap_days=760)
    await wider.async_load()
    assert wider.index.bootstrap_complete is False
    assert list(wider.notices) == ["a:1"]

    # Stores written before Phase 2 carry no bootstrap_days: treat as too narrow.
    del hass_storage[f"{DOMAIN}.{ENTRY}.index"]["data"]["bootstrap_days"]
    legacy = RadarStore(hass, ENTRY, retention_days=400, bootstrap_days=400)
    await legacy.async_load()
    assert legacy.index.bootstrap_days is None
    assert legacy.index.bootstrap_complete is False


async def test_only_dirty_partitions_are_rewritten(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    store.upsert(competition("a", "p1", date(2026, 9, 1)))
    store.upsert(competition("b", "p2", date(2026, 8, 1)))
    await store.async_save(immediate=True)
    del hass_storage[_key("notices.2026-08")]  # nothing should touch August again
    store.upsert(competition("c", "p3", date(2026, 9, 2)))
    await store.async_save(immediate=True)
    assert _key("notices.2026-08") not in hass_storage
    assert len(hass_storage[_key("notices.2026-09")]["data"]["notices"]) == 2


async def test_prune_drops_old_notices_and_whole_partitions(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    store = RadarStore(hass, ENTRY, retention_days=400)
    await store.async_load()
    store.upsert(competition("old", "p0", date(2025, 7, 1)))  # 438 days before TODAY
    store.upsert(competition("edge", "p1", date(2025, 8, 9)))  # 399 days: kept
    store.upsert(competition("new", "p2", date(2026, 9, 1)))
    await store.async_save(immediate=True)
    assert store.prune(TODAY) == 1
    await store.async_save(immediate=True)
    assert set(store.notices) == {"edge:1", "new:1"}
    assert store.index.partitions == ["2025-08", "2026-09"]
    assert _key("notices.2025-07") not in hass_storage


async def test_foreign_schema_version_is_discarded(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    stale = StoreIndex(bootstrap_complete=True, partitions=["2026-09"]).to_dict()
    hass_storage[_key("index")] = {
        "version": 1,
        "key": _key("index"),
        "data": {**stale, "schema_version": 0},
    }
    hass_storage[_key("notices.2026-09")] = {
        "version": 1,
        "key": _key("notices.2026-09"),
        "data": {"schema_version": 0, "month": "2026-09", "notices": [{"x": 1}]},
    }
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    assert store.notices == {}
    assert store.index.bootstrap_complete is False
    assert store.index.partitions == []


async def test_missing_partition_resets_bootstrap(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    hass_storage[_key("index")] = {
        "version": 1,
        "key": _key("index"),
        "data": StoreIndex(bootstrap_complete=True, partitions=["2026-09"]).to_dict(),
    }
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    assert store.index.bootstrap_complete is False


async def test_event_keys_are_bounded(hass: HomeAssistant) -> None:
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    store.mark_events_emitted(f"n{i}:1" for i in range(EMITTED_EVENT_KEYS_LIMIT + 10))
    assert len(store.emitted_event_keys) == EMITTED_EVENT_KEYS_LIMIT
    assert store.was_event_emitted("n0:1") is False
    assert store.was_event_emitted(f"n{EMITTED_EVENT_KEYS_LIMIT + 9}:1") is True


async def test_remove_deletes_all_keys(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    store = RadarStore(hass, ENTRY)
    await store.async_load()
    store.upsert(competition("a", "p1", date(2026, 9, 1)))
    await store.async_save(immediate=True)
    await store.async_remove()
    assert not [k for k in hass_storage if k.startswith(f"{DOMAIN}.{ENTRY}.")]


def test_partition_key() -> None:
    assert RadarStore.partition_key(date(2026, 9, 1)) == "2026-09"


def test_fx_retention_covers_decision_date_lag() -> None:
    """A result published at the retention cutoff may have been decided a year
    earlier; its award-date rate must survive pruning (Phase 2 P4)."""
    from custom_components.edp_radar.const import MAX_DECISION_LAG_DAYS
    from custom_components.edp_radar.storage import FX_RETENTION_MARGIN

    assert timedelta(days=MAX_DECISION_LAG_DAYS) <= FX_RETENTION_MARGIN

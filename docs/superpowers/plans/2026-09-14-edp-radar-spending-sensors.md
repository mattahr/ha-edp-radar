# Phase 3 Plan 2 — Spending Sensors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the five defence-spending sources (Statskontoret, Eurostat, NATO, EDA, SIPRI) as 27 Home Assistant sensors on five source devices, after hardening the data layer they read from.

**Architecture:** The data layer (`custom_components/edp_radar/spending/`) already fetches, parses and stores every source; this plan first fixes the deferred minors and the owner decisions S26–S29 in that layer (Tasks 1–10), then adds pure calculation/attribute/text helpers (Tasks 11–13), then the entities themselves in `spending/sensors.py` with one hook line in `sensor.py` (Tasks 14–19), then docs and version (Tasks 20–21). Sweden is the fixed focus country; rankings never cross sources.

**Tech Stack:** Python 3.14, Home Assistant 2026.9 (`DataUpdateCoordinator`, `CoordinatorEntity`, `SensorEntity`, `Store`), openpyxl, pytest + pytest-homeassistant-custom-component, ruff, mypy strict, `uv`.

**Spec:** `docs/superpowers/specs/2026-09-14-edp-radar-spending-sensors-design.md` (decisions S30–S44; earlier decisions S1–S29 in `docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md` §7; plan paragraphs `§n` refer to `docs/ha-edp-radar_PHASE3_SWEDEN_DEFENCE_SPENDING.md`).

## Global Constraints

- Quality gate before every commit: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components` — all green (currently 281 tests).
- Work directly on `main`, one conventional commit per task, message body ends with `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`. Never push.
- Code, docstrings, `strings.json`, README in English; `translations/sv.json` in Swedish with å/ä/ö. `strings.json` must equal `translations/en.json` byte for byte (test-enforced); `sv.json` must have the same key set.
- `FOCUS_COUNTRY = "SE"` (`spending/registry.py`) is the only focus country (S2).
- `custom_components/edp_radar/sensor.py` and `metrics.py` do not grow beyond the one hook line of Task 14 (S1, S43).
- `spending/calculations.py`, `spending/attrs.py`, `spending/text.py`, `spending/freshness.py` import nothing from Home Assistant.
- Money states are whole currency units (`MSEK` × 1 000 000 → `SEK`), `device_class=MONETARY` (S32).
- Scripts run as `PYTHONPATH=. uv run python scripts/<name>.py …`.
- Run tests with `uv run pytest <path> -q`; a single test with `uv run pytest <path>::<name> -q`.

## File structure

| File | Responsibility |
| --- | --- |
| `spending/store.py` | per-source series stores + one health store (S40); `refresh_release`; unit-supersedes diff (S39); caps |
| `spending/coordinator.py` | tick, cadence gating, isolation; `ValueError` on unknown source; configured-only `UpdateFailed` |
| `spending/freshness.py` | ages, release deadline, `expected_reference_end`, `reference_overdue`, `reference_period_complete` (S42) |
| `spending/providers/base.py` | HTTP helpers without conditional GET (S41); payload size cap |
| `spending/providers/statskontoret.py` | December-window status (S38); short-row warning; injected `today` |
| `spending/providers/eurostat.py` | `freq` guard |
| `spending/providers/nato.py`, `sipri.py`, `spending/xlsx.py` | constant-price base year from sheet/subtitle (S39) |
| `spending/providers/eda.py`, `spending/countries.py` | dedupe, `is_skipped_label`, `-` cells, per-year fixtures |
| `spending/calculations.py` | annual series, YTD/month change, coverage, zero-excluded ranking, Nordic summary |
| `spending/attrs.py` | NEW — provenance, ranking, series attribute builders |
| `spending/text.py` | NEW — `format_amount`, two text sensors |
| `spending/sensors.py` | NEW — description dataclass, entity class, 27 descriptions, setup hook |
| `entity.py` | `spending_device_info(entry_id, source_id)` |
| `sensor.py` | one call to `async_setup_spending_sensors` |
| `diagnostics.py`, `scripts/spending_profile.py` | S17 field names, fingerprint, overdue |
| `strings.json`, `translations/{en,sv}.json` | 27 sensor names |
| `README.md`, `docs/dashboard-example.yaml`, addendum §7.4, `NEXT-SESSION.md`, `manifest.json` | docs and 0.3.0 |

Deviation from the spec noted up front: devices are keyed by `source_id` through `spending_device_info(entry_id, source_id)` instead of five new `DeviceKind` members — same identifiers, names and URLs as S30, less enum plumbing.

---

## Part A — data-layer prerequisites

### Task 1: Health store, `refresh_release`, tolerant load (S40)

**Files:**
- Modify: `custom_components/edp_radar/spending/store.py`
- Test: `tests/spending/test_store.py`

**Interfaces:**
- Consumes: `SourceSeries`, `ProviderHealth` from `spending/models.py`.
- Produces: `health_storage_key(entry_id) -> str`; `SpendingStore.refresh_release(source_id, release, *, now) -> None`; series files no longer carry a `health` key; `edp_radar.<entry_id>.spending.health` holds `{"health": {source_id: ProviderHealth.to_dict()}}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/spending/test_store.py` (add `health_storage_key` to the existing `from custom_components.edp_radar.spending.store import (...)`):

```python
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
    store.refresh_release(
        "statskontoret", _release("r2", date(2026, 8, 25)), now=later
    )
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_store.py -q`
Expected: 5 failures — `ImportError: cannot import name 'health_storage_key'`.

- [ ] **Step 3: Implement the health store**

In `custom_components/edp_radar/spending/store.py`:

Add after `storage_key`:

```python
def health_storage_key(entry_id: str) -> str:
    """One small store for every source's health (S40): written on every tick."""
    return f"{DOMAIN}.{entry_id}.spending.health"
```

Replace `__init__`, `async_load`, `set_health`, `_payload`, `async_save` and `async_remove` with:

```python
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
            if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
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
        health = await self._health_store.async_load()
        if not isinstance(health, dict):
            return
        for source_id, raw in (health.get("health") or {}).items():
            if source_id not in self.series or not isinstance(raw, dict):
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

        Serialisation runs in the executor. Sources with a delayed write still
        pending are rewritten by an immediate save (shutdown), so an unload
        never loses the last release. Health is small and written whenever it
        changed, without touching the series files (S40).
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

                def _static(payload: dict[str, Any] = payload) -> dict[str, Any]:
                    return payload

                store.async_delay_save(_static, SAVE_DELAY_SECONDS)
        if self._health_dirty or (immediate and self._health_pending):
            self._health_dirty = False
            health = self._health_payload()
            if immediate:
                self._health_pending = False
                await self._health_store.async_save(health)
            else:
                self._health_pending = True

                def _static_health(
                    payload: dict[str, Any] = health,
                ) -> dict[str, Any]:
                    return payload

                self._health_store.async_delay_save(_static_health, SAVE_DELAY_SECONDS)

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
```

In `apply_release`, replace the final `self._dirty.add(source_id)` with:

```python
        self._dirty.add(source_id)
        self._health_dirty = True
```

Add `SourceRelease` to the `from .models import (...)` list if it is not already there (it is).

- [ ] **Step 4: Run the store tests and the wiring test**

Run: `uv run pytest tests/spending/test_store.py tests/test_init.py -q`
Expected: all pass (`test_spending_layer_is_wired` still finds no `.spending.` keys after removal because the health store is removed too).

- [ ] **Step 5: Quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/store.py tests/spending/test_store.py
git commit -m "feat(spending): keep provider health in its own store (S40)

Health changes on every tick; series files are now written only when a
release actually changed. Old series files still seed health until the
health store exists. Adds refresh_release for the unchanged-checksum path
and discards non-dict store payloads instead of crashing.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 2: Unit supersedes, duplicate-key warning, revisions cap (S39 store half)

**Files:**
- Modify: `custom_components/edp_radar/spending/store.py`
- Test: `tests/spending/test_store.py`

**Interfaces:**
- Produces: `MAX_REVISIONS = 1000`; `ApplyResult.superseded: int`; health warnings `"unit changed <old> → <new> for <n> datapoints"` and `"<n> duplicate keys within release <id> (last value kept)"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/spending/test_store.py` (add `import dataclasses` and `import pytest` at the top, and `from custom_components.edp_radar.spending import store as store_module`):

```python
async def test_unit_change_supersedes_the_old_series(hass: HomeAssistant) -> None:
    store = SpendingStore(hass, ENTRY)
    await store.async_load()
    v1 = SourceRelease("sipri", "v1", date(2026, 4, 27), "d", "c", "xlsx", checksum="v1")
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
    v2 = SourceRelease("sipri", "v2", date(2027, 4, 26), "d", "c", "xlsx", checksum="v2")
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_store.py -q`
Expected: 3 failures (`AttributeError: 'ApplyResult' object has no attribute 'superseded'`, warnings mismatch, cap missing).

- [ ] **Step 3: Implement the diff changes**

In `store.py` add after `SAVE_DELAY_SECONDS`:

```python
# Newest revisions kept per source; older ones are dropped (plan §62 keeps the
# previous value of a change, not an unbounded audit log).
MAX_REVISIONS = 1000
```

Change `ApplyResult` to:

```python
@dataclass(frozen=True, slots=True)
class ApplyResult:
    added: int
    updated: int
    unchanged: int
    carried_over: int
    revisions: tuple[Revision, ...]
    superseded: int = 0
```

Replace the body of `apply_release` from `current = self.series[source_id]` up to and including `revisions=(*current.revisions, *revisions),` with:

```python
        current = self.series[source_id]
        existing = {point.key: point for point in current.datapoints}
        # S39: a datapoint whose key differs from a new one only in ``unit``
        # (constant-price base year moved) is replaced, not kept beside it.
        by_base: dict[tuple[str, ...], DatapointKey] = {
            key[:5]: key for key in existing
        }
        incoming: dict[DatapointKey, SpendingDataPoint] = {}
        duplicates = 0
        for point in datapoints:
            if point.key in incoming:
                duplicates += 1
            incoming[point.key] = point
        merged = dict(existing)
        added = updated = unchanged = superseded = 0
        revisions: list[Revision] = []
        unit_changes: dict[tuple[str, str], int] = {}
        for key, point in incoming.items():
            previous = existing.get(key)
            if previous is None:
                old_key = by_base.get(key[:5])
                old = (
                    merged.pop(old_key, None)
                    if old_key is not None and old_key not in incoming
                    else None
                )
                if old is None:
                    added += 1
                else:
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
        carried_over = len(merged) - len(incoming)
        notes = list(warnings)
        if duplicates:
            notes.append(
                f"{duplicates} duplicate keys within release {release.release_id} "
                "(last value kept)"
            )
        for (old_unit, new_unit), count in sorted(unit_changes.items()):
            notes.append(
                f"unit changed {old_unit} → {new_unit} for {count} datapoints"
            )
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
            datapoints=tuple(merged[key] for key in sorted(merged)),
            revisions=(*current.revisions, *revisions)[-MAX_REVISIONS:],
```

and change the `return` to `return ApplyResult(added, updated, unchanged, carried_over, tuple(revisions), superseded)`.

Update the module docstring's second paragraph to end with: "A datapoint whose key differs from a new one only in ``unit`` is superseded (S39)."

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending/test_store.py tests/spending/test_coordinator.py -q`
Expected: all pass (`test_second_release_updates_records_revision_and_carries_over` is unaffected: its keys share units).

- [ ] **Step 5: Quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/store.py tests/spending/test_store.py
git commit -m "feat(spending): supersede a series when only its unit changed (S39)

Also counts duplicate keys inside one release as a warning instead of a
silent collapse, and caps stored revisions at MAX_REVISIONS.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 3: Coordinator — unknown source, configured-only `UpdateFailed`, no retry constant (S44)

**Files:**
- Modify: `custom_components/edp_radar/spending/coordinator.py`, `custom_components/edp_radar/const.py`
- Test: `tests/spending/test_coordinator.py`

**Interfaces:**
- Consumes: `SpendingStore.refresh_release` (Task 1).
- Produces: `async_refresh_source` raises `ValueError` for an unknown id; `SPENDING_RETRY_INTERVAL` no longer exists; a failed source has `next_check_at == now` (due at the next tick).

- [ ] **Step 1: Update and add tests**

In `tests/spending/test_coordinator.py`:

Remove `SPENDING_RETRY_INTERVAL` from the `from custom_components.edp_radar.const import (...)` block (keep `DOMAIN`). Replace `test_failures_are_isolated_and_retry_sooner` with:

```python
async def test_failures_are_isolated_and_retry_next_tick(hass: HomeAssistant) -> None:
    clock = Clock(NOW)
    broken = FakeProvider("eurostat")
    broken.discover_error = SourceUnavailableError("HTTP 503 for x")
    fine = FakeProvider("statskontoret")
    coordinator = await _coordinator(hass, [broken, fine], clock)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    eurostat = coordinator.data.get("eurostat")
    assert eurostat.health.state is ProviderState.TEMPORARILY_UNAVAILABLE
    assert eurostat.health.last_error == "HTTP 503 for x"
    # S44: due again at the next 6-hour tick, not on a separate retry clock.
    assert eurostat.health.next_check_at == NOW
    assert len(coordinator.data.get("statskontoret").datapoints) == 1
    # Recover, then fail again: data stays, state says stale.
    broken.discover_error = None
    clock.now = NOW + timedelta(hours=6)
    await coordinator.async_refresh()
    assert broken.calls["discover"] == 2
    assert coordinator.data.get("eurostat").health.state is ProviderState.AVAILABLE
    broken.fetch_error = SourceUnavailableError("timeout")
    broken.release_id = "r2"
    clock.now += timedelta(days=1, minutes=1)
    await coordinator.async_refresh()
    eurostat = coordinator.data.get("eurostat")
    assert eurostat.health.state is ProviderState.STALE_BUT_CACHED
    assert len(eurostat.datapoints) == 1
```

Append:

```python
async def test_update_failed_ignores_sources_without_a_provider(
    hass: HomeAssistant,
) -> None:
    clock = Clock(NOW)
    # NATO data exists in the store from an earlier configuration…
    seeded = SpendingStore(hass, "test-entry")
    await seeded.async_load()
    release = SourceRelease("nato", "r1", date(2026, 9, 1), "d", "c", "x")
    seeded.apply_release(
        "nato",
        release,
        [
            SpendingDataPoint(
                "nato",
                "m",
                "SE",
                ReferencePeriod.year(2025),
                Decimal(1),
                "U",
                DatapointStatus.ACTUAL,
                "r1",
                release.published_at,
                "c",
            )
        ],
        now=NOW,
    )
    await seeded.async_save(immediate=True)
    # …but only EDA is configured now, and it is down.
    provider = FakeProvider("eda")
    provider.discover_error = SourceUnavailableError("down")
    coordinator = await _coordinator(hass, [provider], clock)
    assert coordinator.store.get("nato").datapoints  # loaded, yet not configured
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_refresh_source_rejects_unknown_ids(hass: HomeAssistant) -> None:
    coordinator = await _coordinator(hass, [FakeProvider("nato")], Clock(NOW))
    with pytest.raises(ValueError, match="unknown spending source 'sipri'"):
        await coordinator.async_refresh_source("sipri")


async def test_unchanged_checksum_refreshes_release_metadata(
    hass: HomeAssistant,
) -> None:
    clock = Clock(NOW)
    provider = FakeProvider("nato")
    coordinator = await _coordinator(hass, [provider], clock)
    await coordinator.async_refresh()
    # New release id, identical payload checksum: no parse, metadata refreshed.
    provider.release_id = "r2"
    provider.checksum = "r1"
    clock.now = NOW + timedelta(days=7, minutes=1)
    await coordinator.async_refresh()
    series = coordinator.data.get("nato")
    assert provider.calls == {"discover": 2, "fetch": 2, "parse": 1}
    assert series.release is not None and series.release.release_id == "r2"
    assert series.retrieved_at == clock.now
    assert series.health.skip_reason == "unchanged_checksum"
```

Give `FakeProvider` a `checksum` attribute: in `__init__` add `self.checksum: str | None = None`, and in `_release` use `checksum=self.checksum or self.release_id`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_coordinator.py -q`
Expected: `test_failures_are_isolated_and_retry_next_tick` fails on `next_check_at`, `test_update_failed_ignores_sources_without_a_provider` fails (no `UpdateFailed` raised), `test_refresh_source_rejects_unknown_ids` fails with `StopIteration`.

- [ ] **Step 3: Implement**

`const.py`: delete the line `SPENDING_RETRY_INTERVAL = timedelta(hours=1)` and change the comment above `SPENDING_UPDATE_INTERVAL` to `# Phase 3 spending layer (S14, S44): coordinator tick; a failed source retries at the next tick.`

`coordinator.py`:

- Import line: `from ..const import DOMAIN, SPENDING_UPDATE_INTERVAL`.
- In `_async_update_data`, replace the `if self.providers and not any(...)` block with:

```python
        configured = [provider.spec.source_id for provider in self.providers]
        if configured and not any(
            self.store.get(source_id).datapoints for source_id in configured
        ):
            errors = {
                source_id: self.store.get(source_id).health.last_error
                for source_id in configured
                if self.store.get(source_id).health.last_error
            }
            raise UpdateFailed(f"No spending source available: {errors}")
```

- In `async_refresh_source`, replace the first line with:

```python
        provider = next(
            (p for p in self.providers if p.spec.source_id == source_id), None
        )
        if provider is None:
            raise ValueError(f"unknown spending source {source_id!r}")
```

- In `_async_refresh_provider`, replace `self.store.series[source_id] = dataclasses.replace(series, release=fetched)` with `self.store.refresh_release(source_id, fetched, now=now)`; and in the `except SourceUnavailableError` branch replace `next_check_at=now + SPENDING_RETRY_INTERVAL,` with `next_check_at=now,  # S44: due at the next tick`.
- Remove `import dataclasses` if nothing else in the module uses it (mypy/ruff will tell you).
- Update the module docstring's last sentence: "Failures are recorded per provider and never affect the others; a failed source is due again at the next tick; ``UpdateFailed`` is raised only when no configured source has any data."

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending -q`
Expected: all pass.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/coordinator.py custom_components/edp_radar/const.py tests/spending/test_coordinator.py
git commit -m "fix(spending): coordinator edge cases and retry semantics (S44)

async_refresh_source raises ValueError for an unknown id, UpdateFailed
looks only at configured providers, the ineffective retry interval is
gone, and the unchanged-checksum path goes through the store.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 4: Freshness — reference overdue and period completeness (S42)

**Files:**
- Modify: `custom_components/edp_radar/spending/freshness.py`, `custom_components/edp_radar/diagnostics.py`
- Test: `tests/spending/test_freshness.py`, `tests/test_diagnostics.py`

**Interfaces:**
- Produces: `expected_reference_end(spec, today) -> date`, `reference_overdue(spec, latest_reference_end, today) -> bool`, `reference_period_complete(reference_end, today) -> bool`; `freshness_state` returns `LATE` when the reference is overdue beyond the grace period; diagnostics `freshness` gains `reference_overdue` and `next_release_expected`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/spending/test_freshness.py` (extend its import from `freshness` with `expected_reference_end, reference_overdue, reference_period_complete, next_release_deadline` — keep what is already imported):

```python
def test_expected_reference_end_follows_the_lag() -> None:
    statskontoret = source_spec("statskontoret")  # monthly, lag 31 d
    assert expected_reference_end(statskontoret, date(2026, 9, 14)) == date(2026, 7, 31)
    assert expected_reference_end(statskontoret, date(2026, 10, 2)) == date(2026, 8, 31)
    eurostat = source_spec("eurostat")  # twice-yearly release, annual data, lag 120 d
    assert expected_reference_end(eurostat, date(2026, 9, 14)) == date(2025, 12, 31)
    assert expected_reference_end(eurostat, date(2026, 4, 1)) == date(2024, 12, 31)
    nato = source_spec("nato")  # annual, lag 200 d
    assert expected_reference_end(nato, date(2026, 7, 1)) == date(2024, 12, 31)
    assert expected_reference_end(nato, date(2026, 7, 20)) == date(2025, 12, 31)


def test_reference_overdue_and_period_complete() -> None:
    statskontoret = source_spec("statskontoret")
    assert not reference_overdue(statskontoret, date(2026, 7, 31), date(2026, 9, 14))
    assert reference_overdue(statskontoret, date(2026, 7, 31), date(2026, 10, 2))
    assert reference_overdue(statskontoret, None, date(2026, 9, 14))
    assert reference_period_complete(date(2025, 12, 31), date(2026, 9, 14))
    assert not reference_period_complete(date(2026, 12, 31), date(2026, 9, 14))
    assert reference_period_complete(date(2026, 9, 14), date(2026, 9, 14))


def test_reference_overdue_makes_the_state_late() -> None:
    eurostat = source_spec("eurostat")
    # Re-published in October 2026 while 2025 is still the newest year: fine.
    assert (
        freshness_state(eurostat, date(2025, 12, 31), date(2026, 10, 20), date(2026, 11, 1))
        is FreshnessState.CURRENT
    )
    # A fresh April 2027 release that still stops at 2025: the 2026 data
    # (due 30 April 2027 + grace) is overdue although the release is recent.
    assert (
        freshness_state(eurostat, date(2025, 12, 31), date(2027, 4, 20), date(2027, 6, 1))
        is FreshnessState.LATE
    )
    # Inside the grace period the overdue reference is still only "expected".
    assert (
        freshness_state(eurostat, date(2025, 12, 31), date(2027, 4, 20), date(2027, 5, 3))
        is FreshnessState.CURRENT
    )
```

In `tests/test_diagnostics.py::test_spending_diagnostics` replace the `assert sk["freshness"] == {...}` block with:

```python
    assert sk["freshness"] == {
        "state": "current",
        "publication_age_days": 19,
        "reference_age_days": 43,
        "reference_overdue": False,
        "next_release_expected": "2026-09-30",
    }
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_freshness.py tests/test_diagnostics.py -q`
Expected: `ImportError` for the new names; diagnostics assertion fails on the missing keys.

- [ ] **Step 3: Implement**

In `freshness.py` add after `_add_months`:

```python
def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def expected_reference_end(spec: SourceSpec, today: date) -> date:
    """Newest period end whose figures should already be published (S42).

    Monthly sources: the newest month end at least ``expected_lag_days`` ago.
    Annual data (also Eurostat's twice-yearly dissemination): the newest
    31 December at least ``expected_lag_days`` ago.
    """
    lag = timedelta(days=spec.expected_lag_days)
    if spec.cadence is Cadence.MONTHLY:
        year, month = _add_months(today, -1)
        candidate = _month_end(year, month)
        while candidate + lag > today:
            year, month = _add_months(candidate, -1)
            candidate = _month_end(year, month)
        return candidate
    candidate = date(today.year - 1, 12, 31)
    while candidate + lag > today:
        candidate = date(candidate.year - 1, 12, 31)
    return candidate


def reference_overdue(
    spec: SourceSpec, latest_reference_end: date | None, today: date
) -> bool:
    """True when a period that should be published is not in the data."""
    return latest_reference_end is None or latest_reference_end < expected_reference_end(
        spec, today
    )


def reference_period_complete(reference_end: date, today: date) -> bool:
    """False for a reference year still running (NATO estimates, S24c)."""
    return reference_end <= today
```

Replace `freshness_state` with:

```python
def freshness_state(
    spec: SourceSpec,
    latest_reference_end: date | None,
    published_at: date | None,
    today: date,
    *,
    grace_days: int = GRACE_DAYS,
) -> FreshnessState:
    deadline = next_release_deadline(spec, latest_reference_end, published_at)
    if deadline is None or latest_reference_end is None:
        return FreshnessState.UNKNOWN
    grace = timedelta(days=grace_days)
    if reference_overdue(spec, latest_reference_end, today - grace):
        return FreshnessState.LATE
    if today <= deadline:
        return FreshnessState.CURRENT
    if today <= deadline + grace:
        return FreshnessState.EXPECTED
    return FreshnessState.LATE
```

Extend the module docstring with: "``late`` also covers a reference period that should have been published (``expected_lag_days`` after its end) but is missing, so a source that keeps re-publishing old data is not reported as current."

In `diagnostics.py`, extend the freshness import to `freshness_state, next_release_deadline, publication_age_days, reference_age_days, reference_overdue`, and add to the `"freshness"` dict after `"reference_age_days"`:

```python
            "reference_overdue": reference_overdue(
                source_spec(series.source_id), latest.end if latest else None, today
            ),
            "next_release_expected": _plain(
                next_release_deadline(
                    source_spec(series.source_id),
                    latest.end if latest else None,
                    published,
                )
            ),
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending/test_freshness.py tests/test_diagnostics.py -q`
Expected: all pass, including the pre-existing `test_monthly_deadline_and_states` and `test_annual_and_twice_yearly_states`.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/freshness.py custom_components/edp_radar/diagnostics.py tests/spending/test_freshness.py tests/test_diagnostics.py
git commit -m "feat(spending): reference-overdue freshness signal (S42)

expected_lag_days now drives a second signal: a period that should have
been published but is missing makes the source late even when the
release itself is recent. Diagnostics expose it with the next deadline.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 5: HTTP base — drop conditional GET, cap payload size (S41)

**Files:**
- Modify: `custom_components/edp_radar/spending/providers/base.py`, `custom_components/edp_radar/spending/providers/statskontoret.py`
- Test: `tests/spending/test_base.py`, `tests/spending/test_statskontoret.py`

**Interfaces:**
- Produces: `async_fetch_bytes(session, url, *, request_timeout=DEFAULT_TIMEOUT) -> FetchResult` (no `previous`), `FetchResult` without `not_modified`, `MAX_PAYLOAD_BYTES = 50 * 1024 * 1024`; oversized responses and zip members raise `SourceUnavailableError`.

- [ ] **Step 1: Rewrite the base tests**

In `tests/spending/test_base.py`: delete `test_fetch_sends_conditional_headers_and_handles_304`, `test_conditional_headers_only_for_the_same_url` and the `_release` helper (and the now-unused `SourceRelease`/`date` imports). In `test_fetch_returns_payload_headers_and_checksum` delete the line `assert result.not_modified is False`. Update the module docstring to `"""HTTP helper: payload cap, errors, checksums, HEAD metadata (S12, S41)."""`. Append:

```python
async def test_oversized_payload_is_unavailable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.edp_radar.spending.providers import base

    monkeypatch.setattr(base, "MAX_PAYLOAD_BYTES", 4)
    aioclient_mock.get(URL, content=b"12345")
    with pytest.raises(SourceUnavailableError, match="larger than 4 bytes"):
        await async_fetch_bytes(async_get_clientsession(hass), URL)
    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, content=b"123", headers={"Content-Length": "999"})
    with pytest.raises(SourceUnavailableError, match="larger than 4 bytes"):
        await async_fetch_bytes(async_get_clientsession(hass), URL)


async def test_head_metadata_client_error_returns_nothing(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.head(URL, exc=ClientError("boom"))
    assert await async_head_metadata(async_get_clientsession(hass), URL) == (None, None)
```

Append to `tests/spending/test_statskontoret.py`:

```python
def test_oversized_zip_member_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from custom_components.edp_radar.spending.providers import base
    from custom_components.edp_radar.spending.providers.base import (
        SourceUnavailableError,
    )

    monkeypatch.setattr(base, "MAX_PAYLOAD_BYTES", 10)
    release = release_from(
        select_latest(parse_discovery_page(_page(2026), PAGE_2026)), PAGE_2026
    )
    with pytest.raises(SourceUnavailableError, match="larger than 10 bytes"):
        parse_outturn_csv(_zip("utfall.csv", b"x" * 11), release)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_base.py tests/spending/test_statskontoret.py -q`
Expected: the two new base tests and the zip test fail (`MAX_PAYLOAD_BYTES` missing / no error raised).

- [ ] **Step 3: Implement**

In `base.py`:

- Add after `DEFAULT_TIMEOUT`: 

```python
# Largest response (and zip member) a provider accepts; the biggest real
# source is the 10 MB Statskontoret CSV.
MAX_PAYLOAD_BYTES = 50 * 1024 * 1024
```

- Remove the `not_modified` field from `FetchResult`.
- Delete `_conditional_headers`.
- Replace `async_fetch_bytes` with (the header is read as text so the test mocker, which has no ``content_length`` property, behaves like aiohttp):

```python
def _declared_length(header: str | None) -> int | None:
    try:
        return None if header is None else int(header)
    except ValueError:
        return None


async def async_fetch_bytes(
    session: ClientSession,
    url: str,
    *,
    request_timeout: float = DEFAULT_TIMEOUT,
) -> FetchResult:
    """GET ``url``; re-download avoidance lives in discovery (S14, S41)."""
    try:
        async with asyncio.timeout(request_timeout):
            async with session.get(
                url, headers={"User-Agent": USER_AGENT}, allow_redirects=True
            ) as response:
                if response.status != 200:
                    raise SourceUnavailableError(f"HTTP {response.status} for {url}")
                declared = _declared_length(response.headers.get("Content-Length"))
                if declared is not None and declared > MAX_PAYLOAD_BYTES:
                    raise SourceUnavailableError(
                        f"{url} is larger than {MAX_PAYLOAD_BYTES} bytes ({declared})"
                    )
                payload = await response.read()
                if len(payload) > MAX_PAYLOAD_BYTES:
                    raise SourceUnavailableError(
                        f"{url} is larger than {MAX_PAYLOAD_BYTES} bytes ({len(payload)})"
                    )
                return FetchResult(
                    payload=payload,
                    etag=response.headers.get("ETag"),
                    last_modified=response.headers.get("Last-Modified"),
                    checksum=sha256_hex(payload),
                )
    except TimeoutError as err:
        raise SourceUnavailableError(f"Timeout fetching {url}") from err
    except ClientError as err:
        raise SourceUnavailableError(f"Error fetching {url}: {err}") from err
```

- Update the module docstring: replace "conditional" wording with "Discovery decides whether a download is needed; the fetch helper only caps size and wraps errors."

In `statskontoret.py` `_csv_text`, replace `payload = archive.read(names[0])` with:

```python
        info = archive.getinfo(names[0])
        if info.file_size > MAX_PAYLOAD_BYTES:
            raise SourceUnavailableError(
                f"{names[0]} is larger than {MAX_PAYLOAD_BYTES} bytes "
                f"({info.file_size})"
            )
        payload = archive.read(names[0])
```

and add `MAX_PAYLOAD_BYTES, SourceUnavailableError` to its `from .base import (...)`.

Search for any other `previous=` caller: `grep -rn "previous=" custom_components/edp_radar/spending` must return nothing.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending -q`
Expected: all pass.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/providers/base.py custom_components/edp_radar/spending/providers/statskontoret.py tests/spending/test_base.py tests/spending/test_statskontoret.py
git commit -m "refactor(spending): remove unused conditional GET, cap payload size (S41)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 6: Statskontoret — December window (S38), short rows, injected `today`

**Files:**
- Modify: `custom_components/edp_radar/spending/providers/statskontoret.py`, `custom_components/edp_radar/spending/providers/__init__.py`, `custom_components/edp_radar/__init__.py`
- Test: `tests/spending/test_statskontoret.py`, `tests/spending/mocks.py`

**Interfaces:**
- Produces: `december_is_definitive(releases, year) -> bool`; `parse_outturn_csv(payload, release, *, previous_december_definitive=True)`; `DiscoveredRelease` without `heading`; `all_providers(*, today: Callable[[], date] | None = None)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/spending/test_statskontoret.py` (add `december_is_definitive` to the provider import list):

```python
def test_december_is_definitive_reads_the_previous_year_page() -> None:
    releases = parse_discovery_page(_page(2025), PAGE_2025)
    assert december_is_definitive(releases, 2025)
    assert not december_is_definitive(releases, 2024)
    only_preliminary = [
        r for r in releases if not (r.month == 12 and r.is_definitive)
    ]
    assert not december_is_definitive(only_preliminary, 2025)


def test_previous_december_is_preliminary_until_definitive() -> None:
    release = release_from(
        select_latest(parse_discovery_page(_page(2026), PAGE_2026)), PAGE_2026
    )
    payload = _csv("utgifter-2026-07.csv")
    pending = parse_outturn_csv(payload, release, previous_december_definitive=False)
    by_month = {
        (p.metric_id, p.reference.start.year, p.reference.start.month): p
        for p in pending.datapoints
    }
    assert by_month[("materiel_outturn", 2025, 12)].status is DatapointStatus.PRELIMINARY
    assert by_month[("materiel_outturn", 2025, 11)].status is DatapointStatus.ACTUAL
    assert by_month[("materiel_outturn", 2026, 7)].status is DatapointStatus.ACTUAL
    settled = parse_outturn_csv(payload, release, previous_december_definitive=True)
    assert all(p.status is DatapointStatus.ACTUAL for p in settled.datapoints)


async def test_provider_labels_december_from_the_previous_year_page(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    page_2025 = _page(2025)
    without_definitive = page_2025[
        : page_2025.index("Utgifter december 2025 &#x2014; definitiv")
    ]
    aioclient_mock.get(PAGE_2026, text=_page(2026))
    aioclient_mock.get(PAGE_2025, text=without_definitive)
    csv_url = release_from(
        select_latest(parse_discovery_page(_page(2026), PAGE_2026)), PAGE_2026
    ).download_url
    aioclient_mock.get(csv_url, content=_csv("utgifter-2026-07.csv"))
    provider = StatskontoretProvider(today=lambda: date(2026, 9, 14))
    session = async_get_clientsession(hass)
    release = await provider.async_discover_latest(session)
    fetched, payload = await provider.async_fetch_release(session, release)
    result = provider.parse_release(payload, fetched)
    december = next(
        p
        for p in result.datapoints
        if p.metric_id == "materiel_outturn" and p.reference.start == date(2025, 12, 1)
    )
    assert december.status is DatapointStatus.PRELIMINARY
    assert [str(call[1]) for call in aioclient_mock.mock_calls[:2]] == [
        PAGE_2026,
        PAGE_2025,
    ]


def test_short_rows_are_counted_as_a_warning() -> None:
    release = release_from(
        select_latest(parse_discovery_page(_page(2026), PAGE_2026)), PAGE_2026
    )
    text = _csv("utgifter-2026-07.csv").decode("utf-8-sig")
    lines = text.splitlines()
    lines.insert(2, "06;Försvar;0601003;kort rad")
    result = parse_outturn_csv("\n".join(lines).encode("utf-8"), release)
    assert result.warnings == ("1 rows shorter than the header were skipped",)
```

Discovery now reads the previous year's page as well, so the three existing provider tests must mock it: add `aioclient_mock.get(PAGE_2025, text=_page(2025))` next to the `PAGE_2026` registration in `test_provider_discovers_and_fetches`, `test_provider_fetches_zipped_csv` and `test_provider_falls_back_to_previous_year_in_january` (in the last one the release found on the 2026 page is July 2026, so its previous year is 2025).

In `tests/spending/mocks.py`, the previous-year page must be the real 2025 fixture (its definitive December keeps December 2025 `actual` in the HA tests). The mocker answers with the *first* registration for a URL, so register 2025 before the loop and exclude it from the loop:

```python
    page_2025 = (FIXTURES / "statskontoret" / "discovery-2025.html").read_text(
        encoding="utf-8"
    )
    aioclient_mock.get(f"{DISCOVERY_URL}?year=2025", text=page_2025)
    for year in {today.year, today.year - 1, 2026} - {2025}:
        aioclient_mock.get(f"{DISCOVERY_URL}?year={year}", text=page)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_statskontoret.py -q`
Expected: `ImportError: cannot import name 'december_is_definitive'`.

- [ ] **Step 3: Implement**

In `statskontoret.py`:

- Remove `heading: str` from `DiscoveredRelease`; in `_DiscoveryParser` drop the `h2` capture (`_heading` list, the `elif self._in_entry and tag == "h2"` branch, the `if self._capture == "h2"` branch) and make `entries` a list of `tuple[str | None, list[str]]` (`updated, links`); in `parse_discovery_page` iterate `for updated, links in parser.entries:` and drop `heading=heading`.
- Add after `select_latest`:

```python
def december_is_definitive(releases: list[DiscoveredRelease], year: int) -> bool:
    """Whether the page lists a definitive December for ``year`` (S38)."""
    return any(r.year == year and r.month == 12 and r.is_definitive for r in releases)
```

- Change `parse_outturn_csv` signature to `def parse_outturn_csv(payload: bytes, release: SourceRelease, *, previous_december_definitive: bool = True) -> ParseResult:` and its docstring to: `"""Sum the three metrics per (year, month) from the appropriation rows.

    December of the year before the release stays ``preliminary`` until the
    source lists a definitive December for it (S38): between the January
    release (February) and the definitive December release (March) its value
    is still the preliminary one.
    """`
- Replace the row loop's `if len(row) < len(header): continue` with

```python
    short_rows = 0
    for row in reader:
        if len(row) < len(header):
            short_rows += 1
            continue
```

(declare `short_rows = 0` before the loop, not inside it), and the status expression with:

```python
            status=_month_status(
                year,
                month,
                release_year,
                release_month,
                release_status,
                previous_december_definitive,
            ),
```

plus, before `parse_outturn_csv`:

```python
def _month_status(
    year: int,
    month: int,
    release_year: int,
    release_month: int,
    release_status: DatapointStatus,
    previous_december_definitive: bool,
) -> DatapointStatus:
    if (year, month) == (release_year, release_month):
        return release_status
    if (year, month) == (release_year - 1, 12) and not previous_december_definitive:
        return DatapointStatus.PRELIMINARY
    return DatapointStatus.ACTUAL
```

- Build the warnings tuple: `warnings = (f"{short_rows} rows shorter than the header were skipped",) if short_rows else ()` and return `ParseResult(datapoints, warnings, ";".join(header))`.
- In `StatskontoretProvider.__init__` add `self._previous_december_definitive = True`. Replace `async_discover_latest` with:

```python
    async def async_discover_latest(self, session: ClientSession) -> SourceRelease:
        year = self._today().year
        for candidate in (year, year - 1):
            page_url = f"{DISCOVERY_URL}?year={candidate}"
            releases = await self._async_releases(session, page_url)
            if releases:
                latest = select_latest(releases)
                previous_url = f"{DISCOVERY_URL}?year={latest.year - 1}"
                previous = await self._async_releases(session, previous_url)
                self._previous_december_definitive = december_is_definitive(
                    previous, latest.year - 1
                )
                return release_from(latest, page_url)
        raise SchemaChangedError(
            "Statskontoret lists no Utgifter releases for this or last year"
        )

    async def _async_releases(
        self, session: ClientSession, page_url: str
    ) -> list[DiscoveredRelease]:
        page = await async_fetch_bytes(session, page_url)
        return parse_discovery_page(page.payload.decode("utf-8", "replace"), page_url)
```

and `parse_release` returns `parse_outturn_csv(payload, release, previous_december_definitive=self._previous_december_definitive)`.

In `providers/__init__.py`:

```python
"""Spending providers in plan order (plan §69)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from .base import SpendingProvider
from .eda import EdaProvider
from .eurostat import EurostatProvider
from .nato import NatoProvider
from .sipri import SipriProvider
from .statskontoret import StatskontoretProvider


def all_providers(
    *, today: Callable[[], date] | None = None
) -> tuple[SpendingProvider, ...]:
    """Statskontoret, Eurostat, NATO, EDA, SIPRI (registry.SOURCE_ORDER).

    ``today`` lets Home Assistant supply its own clock (``dt_util``); scripts
    fall back to ``date.today``.
    """
    return (
        StatskontoretProvider(today=today or date.today),
        EurostatProvider(),
        NatoProvider(),
        EdaProvider(),
        SipriProvider(),
    )
```

In `custom_components/edp_radar/__init__.py` change `providers=all_providers(),` to `providers=all_providers(today=lambda: dt_util.now().date()),` and add `from homeassistant.util import dt as dt_util` to the imports if it is not there yet.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending tests/test_init.py tests/test_diagnostics.py -q`
Expected: all pass. (`tests/conftest.py` patches `custom_components.edp_radar.all_providers` with `return_value=()`; the keyword argument is accepted by the mock.)

- [ ] **Step 5: Quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/providers/statskontoret.py custom_components/edp_radar/spending/providers/__init__.py custom_components/edp_radar/__init__.py tests/spending/test_statskontoret.py tests/spending/mocks.py
git commit -m "feat(spending): Statskontoret December stays preliminary until definitive (S38)

Discovery also reads the previous year's page. Short CSV rows are
counted as a warning, the unused heading is gone, and Home Assistant
supplies the clock instead of date.today().

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 7: Eurostat — the `freq` dimension must be annual

**Files:**
- Modify: `custom_components/edp_radar/spending/providers/eurostat.py`
- Test: `tests/spending/test_eurostat.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/spending/test_eurostat.py`:

```python
def test_non_annual_frequency_is_a_schema_change() -> None:
    payload = (FIXTURES / "gov_ev-defence.json").read_bytes()
    data = json.loads(payload)
    data["dimension"]["freq"]["category"]["index"] = {"Q": 0}
    data["dimension"]["freq"]["category"]["label"] = {"Q": "Quarterly"}
    quarterly = json.dumps(data).encode()
    with pytest.raises(SchemaChangedError, match="freq"):
        parse_jsonstat(quarterly, release_from_payload(payload))
```

(`FIXTURES`, `json`, `pytest`, `parse_jsonstat`, `release_from_payload`, `SchemaChangedError` are already imported in that file; add any that are missing.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/spending/test_eurostat.py::test_non_annual_frequency_is_a_schema_change -q`
Expected: FAIL — no exception raised.

- [ ] **Step 3: Implement**

In `parse_jsonstat`, after the `for required in (...)` check add:

```python
    if "freq" in ids and set(_index(data, "freq")) != {"A"}:
        raise SchemaChangedError(
            f"Eurostat freq dimension is {sorted(_index(data, 'freq'))}, expected ['A']"
        )
```

and in the `fixed` loop replace `code = EXPEND if dim == "expend" else next(iter(index))` with:

```python
        code = {"expend": EXPEND, "freq": "A"}.get(dim) or next(iter(index))
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending/test_eurostat.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/providers/eurostat.py tests/spending/test_eurostat.py
git commit -m "fix(spending): Eurostat requires the annual frequency code

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 8: NATO and SIPRI — constant-price base year from the workbook (S39 parser half)

**Files:**
- Modify: `custom_components/edp_radar/spending/xlsx.py`, `custom_components/edp_radar/spending/providers/nato.py`, `custom_components/edp_radar/spending/providers/sipri.py`, `custom_components/edp_radar/spending/registry.py`, `scripts/fetch_spending_fixtures.py`
- Regenerate: `tests/fixtures/spending/sipri/milex-trimmed.xlsx`
- Test: `tests/spending/test_xlsx.py`, `tests/spending/test_nato.py`, `tests/spending/test_sipri.py`, `tests/spending/test_registry.py`

**Interfaces:**
- Produces: `xlsx.constant_base_year(label) -> int` (raises `SchemaChangedError`), `xlsx.sheet_by_prefix(book, prefix) -> str`; unit `USD_MILLION_CONSTANT_<year>` derived per workbook; `MetricSpec.unit == "USD_MILLION_CONSTANT"` for `nato/defence_expenditure_usd_constant` and `sipri/military_expenditure_usd_constant`; SIPRI fixture contains Libya (red-font 2022–2023).

- [ ] **Step 1: Write the failing tests**

Append to `tests/spending/test_xlsx.py`:

```python
def test_constant_base_year_and_sheet_prefix() -> None:
    from openpyxl import Workbook

    from custom_components.edp_radar.spending.xlsx import (
        constant_base_year,
        sheet_by_prefix,
    )

    assert constant_base_year("Constant (2024) US$") == 2024
    assert constant_base_year("constant 2021 prices and exchange rates") == 2021
    with pytest.raises(SchemaChangedError, match="base year"):
        constant_base_year("Current US$")
    book = Workbook()
    book.active.title = "Constant (2025) US$"
    assert sheet_by_prefix(book, "Constant (") == "Constant (2025) US$"
    with pytest.raises(SchemaChangedError, match="Share of"):
        sheet_by_prefix(book, "Share of")
```

In `tests/spending/test_nato.py::test_parse_2026_workbook_sweden_and_status` add after the `usd_constant` value assertion:

```python
    assert (
        points[("defence_expenditure_usd_constant", "SE", 2026)].unit
        == "USD_MILLION_CONSTANT_2021"
    )
```

Append to `tests/spending/test_sipri.py` (the tests below load the real fixture with openpyxl and rename one sheet; no synthetic workbook is needed):

```python
def test_base_year_comes_from_the_sheet_name() -> None:
    import io

    from openpyxl import load_workbook

    payload = (FIXTURES / "milex-trimmed.xlsx").read_bytes()
    book = load_workbook(io.BytesIO(payload))
    book["Constant (2024) US$"].title = "Constant (2025) US$"
    buffer = io.BytesIO()
    book.save(buffer)
    result = parse_sipri_workbook(buffer.getvalue(), _release())
    units = {p.unit for p in result.datapoints if p.metric_id == "military_expenditure_usd_constant"}
    assert units == {"USD_MILLION_CONSTANT_2025"}


def test_red_font_in_the_real_workbook_is_highly_uncertain() -> None:
    result = parse_sipri_workbook((FIXTURES / "milex-trimmed.xlsx").read_bytes(), _release())
    points = {(p.metric_id, p.country, p.reference.start.year): p for p in result.datapoints}
    libya_2023 = points[("military_expenditure_usd_constant", "LY", 2023)]
    assert "highly_uncertain" in libya_2023.flags
    assert "highly_uncertain" not in points[("military_expenditure_usd_constant", "SE", 2023)].flags
```

(`_release()` is the module-level helper `tests/spending/test_sipri.py` already defines; use `_release()` wherever `RELEASE` appears above.) In `test_parse_sweden_estimates_and_notes`, change the country count assertion from `== 59` to `== 60` and the constant unit assertion (if any) to `"USD_MILLION_CONSTANT_2024"` (unchanged value; it is derived now).

In `tests/spending/test_registry.py` add:

```python
def test_constant_price_metrics_carry_no_base_year() -> None:
    assert metric_spec("nato", "defence_expenditure_usd_constant").unit == (
        "USD_MILLION_CONSTANT"
    )
    assert metric_spec("sipri", "military_expenditure_usd_constant").unit == (
        "USD_MILLION_CONSTANT"
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_xlsx.py tests/spending/test_nato.py tests/spending/test_sipri.py tests/spending/test_registry.py -q`
Expected: `ImportError` (xlsx helpers), `KeyError: ('military_expenditure_usd_constant', 'LY', 2023)`, registry unit mismatch.

- [ ] **Step 3: Regenerate the SIPRI fixture with one red-font country**

In `scripts/fetch_spending_fixtures.py`, replace `trim_sipri_workbook` with:

```python
KEEP_FROM = "Europe"
KEEP_ROW = "Libya"  # a red-font (highly uncertain) row outside Europe


def trim_sipri_workbook(data: bytes) -> bytes:
    """Keep three data sheets, the rows from 'Europe' on, and one African row
    with red-font cells so the highly-uncertain marker is tested against real
    data (colours survive)."""
    book = openpyxl.load_workbook(io.BytesIO(data))
    for name in list(book.sheetnames):
        if name not in SIPRI_SHEETS:
            book.remove(book[name])
    for name in SIPRI_SHEETS:
        sheet = book[name]
        header = next(
            i for i in range(1, 15) if str(sheet.cell(i, 1).value).strip() == "Country"
        )
        rows = {
            str(sheet.cell(i, 1).value).strip(): i
            for i in range(header + 1, sheet.max_row + 1)
        }
        europe, keep = rows[KEEP_FROM], rows[KEEP_ROW]
        # Delete from the bottom up so earlier indexes stay valid.
        sheet.delete_rows(keep + 1, europe - (keep + 1))
        sheet.delete_rows(header + 2, keep - (header + 2))
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()
```

Run `PYTHONPATH=. uv run python scripts/fetch_spending_fixtures.py sipri` (uses `.cache/spending/fixtures/sipri-milex.xlsx`; no network). Then `git diff --stat tests/fixtures/spending/sipri/` shows the workbook changed.

- [ ] **Step 4: Implement the parsers and registry**

`xlsx.py` — add after `year_header`:

```python
_BASE_YEAR = re.compile(r"constant\D{0,3}(\d{4})", re.IGNORECASE)


def constant_base_year(label: str) -> int:
    """``2024`` from ``"Constant (2024) US$"`` or ``"constant 2021 prices"``."""
    match = _BASE_YEAR.search(label)
    if match is None:
        raise SchemaChangedError(f"no constant-price base year in {label!r}")
    return int(match.group(1))


def sheet_by_prefix(book: Workbook, prefix: str) -> str:
    for name in book.sheetnames:
        if str(name).startswith(prefix):
            return str(name)
    raise SchemaChangedError(f"no sheet starting with {prefix!r}; found {book.sheetnames}")
```

`registry.py` — change the two constant-price metrics to `unit="USD_MILLION_CONSTANT"`, display names `"Defence expenditure (USD, constant prices)"` and `"Military expenditure (USD, constant prices)"`, and definitions ending with "; the base year is read from the workbook and appended to the datapoint unit (S39)".

`nato.py` — in `TABLES` change the constant entry to `TableSpec("Table 2", 1, "constant", "defence_expenditure_usd_constant", "USD_MILLION_CONSTANT")`. In `_parse_table`, after the subtitle check add:

```python
    unit = spec.unit
    if unit == "USD_MILLION_CONSTANT":
        unit = f"{unit}_{constant_base_year(subtitle)}"
```

and use `unit=unit` in the `SpendingDataPoint(...)`. Import `constant_base_year` from `..xlsx`.

`sipri.py` — change `SHEETS` to use a prefix for the constant sheet: `("Constant (", "military_expenditure_usd_constant", "USD_MILLION_CONSTANT", False)`. In `parse_sipri_workbook`:

```python
    for prefix, metric_id, unit, pct in SHEETS:
        sheet = sheet_by_prefix(book, prefix)
        if unit == "USD_MILLION_CONSTANT":
            unit = f"{unit}_{constant_base_year(sheet)}"
        rows = rows_of(book[sheet])
        sheet_points, fingerprint = _parse_sheet(
            rows, sheet, metric_id, unit, pct, release, warnings
        )
```

Import `constant_base_year, sheet_by_prefix` from `..xlsx` (drop `require_sheet` if unused). Update the module docstring: "The constant-price base year is read from the sheet name (S39)."

Check `scripts/spending_profile.py` for the literal `USD_MILLION_CONSTANT_2024` / `_2021` (grep): if a rank line passes a hard-coded unit, take the unit from Sweden's datapoint instead: `unit = next(p.unit for p in points if p.metric_id == metric_id and p.country == "SE")`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/spending -q`
Expected: all pass, SIPRI country count 60.

- [ ] **Step 6: Quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/xlsx.py custom_components/edp_radar/spending/providers/nato.py custom_components/edp_radar/spending/providers/sipri.py custom_components/edp_radar/spending/registry.py scripts/fetch_spending_fixtures.py scripts/spending_profile.py tests/fixtures/spending/sipri/milex-trimmed.xlsx tests/spending/
git commit -m "feat(spending): read constant-price base years from the workbooks (S39)

NATO and SIPRI no longer hard-code 2021/2024; the next SIPRI edition will
supersede the old series instead of raising schema_changed. The SIPRI
fixture keeps Libya so the red-font marker is tested on real data.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 9: EDA — skipped labels, duplicated columns, `-` cells, per-year fixtures

**Files:**
- Modify: `custom_components/edp_radar/spending/countries.py`, `custom_components/edp_radar/spending/providers/eda.py`, `scripts/fetch_spending_fixtures.py`, `tests/spending/mocks.py`
- Create: `tests/fixtures/spending/eda/defence-data-2023.xlsx`, `tests/fixtures/spending/eda/defence-data-2024.xlsx` (downloaded; ≈80 kB each)
- Test: `tests/spending/test_countries.py`, `tests/spending/test_eda.py`

**Interfaces:**
- Produces: `countries.is_skipped_label(label) -> bool`; EDA emits no warning for `SKIP_LABELS` rows and no datapoint for `-` cells.

- [ ] **Step 1: Write the failing tests**

Append to `tests/spending/test_countries.py`:

```python
def test_skipped_labels_are_distinguishable_from_unknown_ones() -> None:
    from custom_components.edp_radar.spending.countries import (
        is_skipped_label,
        resolve_country,
    )

    assert is_skipped_label("European Union")
    assert is_skipped_label("NATO Total*")
    assert not is_skipped_label("Atlantis")
    assert resolve_country("European Union") is None
    assert resolve_country("Atlantis") is None
```

Append to `tests/spending/test_eda.py` (reuse the file's existing synthetic-workbook helper if it has one; otherwise build the sheet inline as below):

```python
def test_skip_labels_and_dash_cells_are_silent() -> None:
    import io

    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "Member States 2025"
    sheet.append(
        [
            "Member State",
            "Year",
            "Total Defence Expenditure",
            "Defence Investment",
            "Total Defence Expenditure as % of GDP",
            "Total Defence Expenditure as % of Government Expenditure",
            "Total Defence Expenditure per capita",
        ]
    )
    sheet.append(["Sweden", 2025, 14788, "-", 0.0248, 0.057, 1386])
    sheet.append(["European Union", 2025, 343000, 106000, 0.019, 0.04, 760])
    billions = book.create_sheet("Billions")
    billions.append(
        [
            "Member State",
            "Year",
            "Total Defence Expenditure",
            "Defence Equipment Procurement Expenditure",
            "Defence R&D Expenditure",
            "Defence Investment",
            "Total Defence Expenditure as % of GDP",
        ]
    )
    billions.append(["Sweden", 2021, 7000, 1500, 88.2, 1588.2, 0.013])
    buffer = io.BytesIO()
    book.save(buffer)
    release = SourceRelease("eda", "2025:x", date(2026, 9, 4), "d", "c", "xlsx")
    result = parse_eda_workbooks({"2025": buffer.getvalue()}, release)
    assert result.warnings == ()
    metrics = {(p.metric_id, p.country) for p in result.datapoints}
    assert ("defence_investment", "SE") not in metrics
    assert ("defence_expenditure", "SE") in metrics
    assert not any(p.country == "EU" for p in result.datapoints)
```

In `test_provider_discovers_and_fetches_every_recent_workbook`, the mock loop already prefers `FIXTURES / f"defence-data-{year}.xlsx"` when it exists (falling back to 2022); once the 2023/2024 files exist every year is served from its own workbook. Replace its last line `assert any(p.reference.start.year == 2025 for p in result.datapoints)` with:

```python
    by_year = {
        year: {p.country: p.value for p in result.datapoints if p.reference.start.year == year and p.metric_id == "defence_expenditure" and "sheet:billions" not in p.flags}
        for year in (2022, 2023, 2024, 2025)
    }
    assert all(len(by_year[year]) >= 26 for year in by_year)
    sweden = [by_year[year]["SE"] for year in (2022, 2023, 2024, 2025)]
    assert len(set(sweden)) == 4  # four workbooks, four different figures
```

- [ ] **Step 2: Fetch the missing fixtures**

In `scripts/fetch_spending_fixtures.py::fetch_eda` change `for year in (2025, 2022):` to `for year in (2025, 2024, 2023, 2022):`. Run `PYTHONPATH=. uv run python scripts/fetch_spending_fixtures.py eda` (network: downloads the 2023 and 2024 workbooks into `.cache/spending/fixtures/` and writes the two new fixture files; the 2022/2025 files are byte-identical). In `tests/spending/mocks.py` replace the `name = ...` line with:

```python
        name = f"defence-data-{min(max(year, 2022), 2025)}.xlsx"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_countries.py tests/spending/test_eda.py -q`
Expected: `ImportError: cannot import name 'is_skipped_label'`; the synthetic test fails with a warning about `'European Union'`.

- [ ] **Step 4: Implement**

`countries.py` — add after `normalise_label`:

```python
def is_skipped_label(label: str) -> bool:
    """Aggregates and dissolved states that are deliberately not countries."""
    return normalise_label(label) in SKIP_LABELS
```

and change `resolve_country`'s docstring to `"""Alpha-2 code for a source label; ``None`` when unknown or skipped (see ``is_skipped_label`` to tell the two apart)."""`.

`eda.py`:

- Replace the two column tuples with shared rows:

```python
Column = tuple[str, str, str, bool]  # (normalised header, metric_id, unit, ×100)
_EXPENDITURE: Column = ("total defence expenditure", "defence_expenditure", "EUR_MILLION", False)
_INVESTMENT: Column = ("defence investment", "defence_investment", "EUR_MILLION", False)
_PCT_GDP: Column = (
    "total defence expenditure as % of gdp",
    "defence_expenditure_pct_gdp",
    "PCT_GDP",
    True,
)
MEMBER_STATE_COLUMNS: tuple[Column, ...] = (
    _EXPENDITURE,
    _INVESTMENT,
    _PCT_GDP,
    (
        "total defence expenditure as % of government expenditure",
        "defence_expenditure_pct_government",
        "PCT",
        True,
    ),
    ("total defence expenditure per capita", "defence_expenditure_per_capita", "EUR", False),
)
BILLIONS_COLUMNS: tuple[Column, ...] = (
    _EXPENDITURE,
    ("defence equipment procurement expenditure", "equipment_procurement", "EUR_MILLION", False),
    ("defence r&d expenditure", "defence_rnd", "EUR_MILLION", False),
    _INVESTMENT,
    _PCT_GDP,
)
```

- `_columns`: replace the `for label in ("year",):` loop with

```python
    if "year" not in names:
        raise SchemaChangedError(f"{sheet}: column 'Year' missing")
    columns: dict[str, int] = {"year": names.index("year")}
```

and the `pretty = ...` line with `pretty = header.title().replace("Gdp", "GDP")`.

- `_emit`: after `if not label or label.startswith("*"): continue` add `if is_skipped_label(label): continue`; import `is_skipped_label` next to `resolve_country`. (`number("-")` already returns `None`, so the `-` cell needs no code — the test documents it.)

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/spending -q`
Expected: all pass.

- [ ] **Step 6: Quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/countries.py custom_components/edp_radar/spending/providers/eda.py scripts/fetch_spending_fixtures.py tests/fixtures/spending/eda/ tests/spending/
git commit -m "fix(spending): EDA skips aggregates silently, real 2023/2024 fixtures

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 10: Diagnostics field names, layout fingerprint, profile script

**Files:**
- Modify: `custom_components/edp_radar/spending/models.py`, `custom_components/edp_radar/spending/coordinator.py`, `custom_components/edp_radar/diagnostics.py`, `scripts/spending_profile.py`
- Test: `tests/spending/test_models.py`, `tests/test_diagnostics.py`, `tests/spending/test_coordinator.py`

**Interfaces:**
- Produces: `SourceRelease.layout_fingerprint: str | None = None` (round-trips through `to_dict`/`from_dict`); diagnostics keys `datapoints_count`, `revision_count`; release dict includes `layout_fingerprint`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/spending/test_models.py`:

```python
def test_release_round_trips_the_layout_fingerprint() -> None:
    from custom_components.edp_radar.spending.models import SourceRelease

    release = SourceRelease(
        "nato", "2026:x", date(2026, 7, 10), "d", "c", "xlsx", layout_fingerprint="Table 1 | Table 2"
    )
    assert SourceRelease.from_dict(release.to_dict()) == release
    assert SourceRelease.from_dict({**release.to_dict(), "layout_fingerprint": None}).layout_fingerprint is None
```

In `tests/test_diagnostics.py::test_spending_diagnostics` change `sk["datapoints"] == 57` to `sk["datapoints_count"] == 57`, `sk["revisions"] == 0` to `sk["revision_count"] == 0`, and add `assert sk["release"]["layout_fingerprint"].startswith("Utgiftsområde;")`.

In `tests/spending/test_coordinator.py::test_first_refresh_loads_every_provider` add inside the `for provider in providers:` loop: `assert series.release is not None and series.release.layout_fingerprint == "fp"`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_models.py tests/test_diagnostics.py tests/spending/test_coordinator.py -q`
Expected: `TypeError: unexpected keyword argument 'layout_fingerprint'`, `KeyError: 'datapoints_count'`, fingerprint `None`.

- [ ] **Step 3: Implement**

`models.py` — add `layout_fingerprint: str | None = None` as the last field of `SourceRelease`; include `"layout_fingerprint": self.layout_fingerprint` in `to_dict` and `layout_fingerprint=data.get("layout_fingerprint")` in `from_dict`.

`coordinator.py` — in `_async_refresh_provider`, after `result = await self.hass.async_add_executor_job(...)`:

```python
            fetched = dataclasses.replace(
                fetched, layout_fingerprint=result.layout_fingerprint
            )
```

(re-add `import dataclasses` if Task 3 removed it).

`diagnostics.py::_spending_series` — rename the keys `"datapoints"` → `"datapoints_count"` and `"revisions"` → `"revision_count"` (S17). The release dict already serialises the new field.

`scripts/spending_profile.py`:
- In the "freshness today" row, replace the reference-age fragment with:

```python
            f"{_reference_age_text(latest_end, today)})",
```

and add near `_fmt`:

```python
def _reference_age_text(latest_end: date | None, today: date) -> str:
    if latest_end is None:
        return "reference age n/a"
    age = reference_age_days(latest_end, today)
    if age < 0:
        return f"reference age {age} d (reference period ends {latest_end}, not yet complete)"
    return f"reference age {age} d"
```

- In `_table`, render empty cells as an em dash: `"| " + " | ".join(str(c) if str(c) else "—" for c in row) + " |"`.

Regenerate `docs/phase3-source-profile.md` with `PYTHONPATH=. uv run python scripts/spending_profile.py --no-fetch --today 2026-09-13` and commit the regenerated file only if the diff is limited to the freshness/dash wording.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending tests/test_diagnostics.py -q`
Expected: all pass.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/models.py custom_components/edp_radar/spending/coordinator.py custom_components/edp_radar/diagnostics.py scripts/spending_profile.py docs/phase3-source-profile.md tests/
git commit -m "fix(spending): S17 diagnostics field names, stored layout fingerprint

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Part B — pure helpers

### Task 11: Calculations for the sensors (§7 of the spec)

**Files:**
- Modify: `custom_components/edp_radar/spending/calculations.py`
- Test: `tests/spending/test_calculations.py`

**Interfaces:**
- Produces (all pure, `points: Iterable[SpendingDataPoint]`):
  - `annual_series(points, metric_id, country, *, unit=None) -> dict[int, SpendingDataPoint]`
  - `latest_year(points, metric_id, country, *, unit=None) -> SpendingDataPoint | None`
  - `YtdChange(current, previous, change, pct, months)`; `ytd_change(points, metric_id, country, year, through_month) -> YtdChange | None`
  - `MonthChange(current, previous, pct)`; `month_change(points, metric_id, country, year, month) -> MonthChange | None`
  - `value_at(points, metric_id, country, reference, *, unit=None) -> Decimal | None`
  - `Coverage(present, ever_seen, missing)`; `coverage(points, metric_id, reference, *, unit) -> Coverage` — `ever_seen` spans every metric of the points given (pass the whole series)
  - `change_over_years(series, year, years_back) -> tuple[Decimal, Decimal | None] | None`
  - `Ranking.excluded_zero: tuple[str, ...]` (zero values leave `entries`)
  - `NordicSummary(entries, median)`; `nordic_summary(ranking) -> NordicSummary` (import `NordicSummary` in the test too)

- [ ] **Step 1: Write the failing tests**

Append to `tests/spending/test_calculations.py` (extend the import from `calculations` with the new names; `_monthly` and `_annual` helpers and the `ANNUAL` list already exist in the file):

```python
MONTHLY_TWO_YEARS = [
    *(_monthly("materiel_outturn", 2025, m, str(100 * m)) for m in range(1, 13)),
    *(_monthly("materiel_outturn", 2026, m, str(150 * m)) for m in range(1, 8)),
]


def test_ytd_change_and_month_change() -> None:
    change = ytd_change(MONTHLY_TWO_YEARS, "materiel_outturn", "SE", 2026, 7)
    assert change is not None
    assert change.current == Decimal(150 * 28)  # 150 × (1+…+7)
    assert change.previous == Decimal(100 * 28)
    assert change.change == Decimal(50 * 28)
    assert change.pct == Decimal(50)
    assert change.months == 7
    # A missing month in either year gives no YTD figure.
    assert ytd_change(MONTHLY_TWO_YEARS, "materiel_outturn", "SE", 2026, 9) is None
    first_year_only = [p for p in MONTHLY_TWO_YEARS if p.reference.start.year == 2026]
    partial = ytd_change(first_year_only, "materiel_outturn", "SE", 2026, 7)
    assert partial is not None and partial.previous is None and partial.pct is None
    month = month_change(MONTHLY_TWO_YEARS, "materiel_outturn", "SE", 2026, 7)
    assert month is not None
    assert month.current.value == Decimal(1050)
    assert month.previous is not None and month.previous.value == Decimal(700)
    assert month.pct == Decimal(50)
    assert month_change(MONTHLY_TWO_YEARS, "materiel_outturn", "SE", 2024, 1) is None


def test_annual_series_latest_year_and_value_at() -> None:
    points = [
        _annual("sipri", "milex", "SE", 2023, "10", unit="USD_MILLION_CONSTANT_2024"),
        _annual("sipri", "milex", "SE", 2025, "12", unit="USD_MILLION_CONSTANT_2024"),
        _annual("sipri", "milex", "SE", 2025, "13", unit="USD_MILLION_CONSTANT_2025"),
        _annual("sipri", "milex_pct", "SE", 2025, "2.4", unit="PCT_GDP"),
        _monthly("milex", 2025, 1, "1"),  # monthly reference: not a year
    ]
    series = annual_series(points, "milex", "SE", unit="USD_MILLION_CONSTANT_2024")
    assert sorted(series) == [2023, 2025]
    assert latest_year(points, "milex", "SE", unit="USD_MILLION_CONSTANT_2024").value == Decimal(12)
    assert latest_year(points, "milex", "SE").value in {Decimal(12), Decimal(13)}
    assert latest_year(points, "milex", "FI") is None
    assert value_at(points, "milex_pct", "SE", ReferencePeriod.year(2025)) == Decimal("2.4")
    assert value_at(points, "milex_pct", "SE", ReferencePeriod.year(2024)) is None
    assert change_over_years(series, 2025, 2) == (Decimal(10), Decimal(20))
    assert change_over_years(series, 2025, 10) is None


def test_coverage_reports_missing_reporters() -> None:
    points = [
        *ANNUAL,
        _annual("eurostat", "defence_expenditure", "IT", 2024, "30000"),
        # Cyprus only ever reports investment: still part of the source's population.
        _annual("eurostat", "defence_investment", "CY", 2025, "50"),
    ]
    cov = coverage(points, "defence_expenditure", ReferencePeriod.year(2025), unit="EUR_MILLION")
    assert cov.present == ("DE", "DK", "FI", "FR", "PL", "SE")
    assert cov.ever_seen == ("CY", "DE", "DK", "FI", "FR", "IT", "PL", "SE")
    assert cov.missing == ("CY", "IT")


def test_rank_excludes_true_zeros_and_nordic_summary_ignores_them() -> None:
    points = [
        *ANNUAL,
        _annual("eurostat", "defence_expenditure", "IS", 2025, "0"),
        _annual("eurostat", "defence_expenditure", "NO", 2025, "9000"),
    ]
    ranking = rank(
        points,
        metric_id="defence_expenditure",
        unit="EUR_MILLION",
        reference=ReferencePeriod.year(2025),
    )
    assert ranking is not None
    assert ranking.excluded_zero == ("IS",)
    assert "IS" not in [e.country for e in ranking.entries]
    assert ranking.population == 7
    nordic = nordic_summary(ranking)
    # SE 17196.9, NO 9000, DK 8997.7, FI 7000 → median of the middle two.
    assert [e.country for e in nordic.entries] == ["SE", "NO", "DK", "FI"]
    assert nordic.median == (Decimal("9000") + Decimal("8997.7")) / 2
    germany_only = rank(
        ANNUAL[:2],
        metric_id="defence_expenditure",
        unit="EUR_MILLION",
        reference=ReferencePeriod.year(2025),
        focus="DE",
    )
    assert germany_only is not None
    assert nordic_summary(germany_only) == NordicSummary((), None)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_calculations.py -q`
Expected: `ImportError` for the new names.

- [ ] **Step 3: Implement**

Add to `calculations.py` (keep the existing functions; `rank` is modified in place):

```python
@dataclass(frozen=True, slots=True)
class YtdChange:
    """January..month of one year against the same months a year earlier."""

    current: Decimal
    previous: Decimal | None
    change: Decimal | None
    pct: Decimal | None
    months: int


@dataclass(frozen=True, slots=True)
class MonthChange:
    current: SpendingDataPoint
    previous: SpendingDataPoint | None
    pct: Decimal | None


@dataclass(frozen=True, slots=True)
class Coverage:
    """Which countries a reference period covers for one metric, against every
    country the source reports at all (S37): Eurostat's 22 of 27 (S24b)."""

    present: tuple[str, ...]
    ever_seen: tuple[str, ...]
    missing: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NordicSummary:
    entries: tuple[RankEntry, ...]
    median: Decimal | None


def _is_year(reference: ReferencePeriod) -> bool:
    start, end = reference.start, reference.end
    return (start.month, start.day, end.month, end.day) == (1, 1, 12, 31) and (
        start.year == end.year
    )


def annual_series(
    points: Iterable[SpendingDataPoint],
    metric_id: str,
    country: str,
    *,
    unit: str | None = None,
) -> dict[int, SpendingDataPoint]:
    """``{year: point}`` for calendar-year references of one metric/country."""
    series: dict[int, SpendingDataPoint] = {}
    for point in points:
        if point.metric_id != metric_id or point.country != country:
            continue
        if unit is not None and point.unit != unit:
            continue
        if _is_year(point.reference):
            series[point.reference.start.year] = point
    return series


def latest_year(
    points: Iterable[SpendingDataPoint],
    metric_id: str,
    country: str,
    *,
    unit: str | None = None,
) -> SpendingDataPoint | None:
    series = annual_series(points, metric_id, country, unit=unit)
    return series[max(series)] if series else None


def ytd_change(
    points: Iterable[SpendingDataPoint],
    metric_id: str,
    country: str,
    year: int,
    through_month: int,
) -> YtdChange | None:
    """YTD of ``year`` and the same months of ``year - 1`` (plan §52, §54)."""
    snapshot = list(points)
    current = ytd(snapshot, metric_id, country, year, through_month)
    if current is None:
        return None
    previous = ytd(snapshot, metric_id, country, year - 1, through_month)
    change = None if previous is None else current - previous
    return YtdChange(
        current, previous, change, nominal_change_pct(current, previous), through_month
    )


def month_change(
    points: Iterable[SpendingDataPoint],
    metric_id: str,
    country: str,
    year: int,
    month: int,
) -> MonthChange | None:
    series = monthly_series(points, metric_id, country)
    current = series.get((year, month))
    if current is None:
        return None
    previous = series.get((year - 1, month))
    return MonthChange(
        current,
        previous,
        nominal_change_pct(current.value, previous.value if previous else None),
    )


def value_at(
    points: Iterable[SpendingDataPoint],
    metric_id: str,
    country: str,
    reference: ReferencePeriod,
    *,
    unit: str | None = None,
) -> Decimal | None:
    """The value of one metric for one country and reference period."""
    for point in points:
        if (
            point.metric_id == metric_id
            and point.country == country
            and (point.reference.start, point.reference.end)
            == (reference.start, reference.end)
            and (unit is None or point.unit == unit)
        ):
            return point.value
    return None


def coverage(
    points: Iterable[SpendingDataPoint],
    metric_id: str,
    reference: ReferencePeriod,
    *,
    unit: str,
) -> Coverage:
    present: set[str] = set()
    ever_seen: set[str] = set()
    for point in points:
        ever_seen.add(point.country)
        if point.metric_id != metric_id or point.unit != unit:
            continue
        if (point.reference.start, point.reference.end) == (
            reference.start,
            reference.end,
        ):
            present.add(point.country)
    return Coverage(
        tuple(sorted(present)),
        tuple(sorted(ever_seen)),
        tuple(sorted(ever_seen - present)),
    )


def change_over_years(
    series: dict[int, SpendingDataPoint], year: int, years_back: int
) -> tuple[Decimal, Decimal | None] | None:
    """``(value years_back ago, change %)`` or ``None`` when that year is absent."""
    then = series.get(year - years_back)
    now = series.get(year)
    if then is None or now is None:
        return None
    return then.value, nominal_change_pct(now.value, then.value)


def nordic_summary(ranking: Ranking) -> NordicSummary:
    """Nordic entries of a ranking and their median (plan §51).

    Only countries in the ranking count, so a true zero excluded by ``rank``
    (Iceland, S24d) never enters the median.
    """
    entries = nordic_subset(ranking)
    median = Decimal(_median(e.value for e in entries)) if entries else None
    return NordicSummary(entries, median)
```

Modify `Ranking` and `rank`:

- Add `excluded_zero: tuple[str, ...] = ()` as the last field of `Ranking`.
- In `rank`, after the loop and the single-source check, before `if focus not in selected`:

```python
    excluded_zero = tuple(sorted(c for c, p in selected.items() if p.value == 0))
    for country in excluded_zero:
        del selected[country]
```

and pass `excluded_zero=excluded_zero` to the `Ranking(...)` constructor. Add to the `rank` docstring: "Values of exactly zero are listed in ``excluded_zero`` instead of ranked (S35)."

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending/test_calculations.py tests/spending -q`
Expected: all pass.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/calculations.py tests/spending/test_calculations.py
git commit -m "feat(spending): calculations for the sensor layer (S35, S37)

Annual series, YTD and month changes, coverage, zero-excluded rankings
and a Nordic summary without Iceland.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 12: `spending/attrs.py` — provenance, ranking and series attributes

**Files:**
- Create: `custom_components/edp_radar/spending/attrs.py`
- Test: `tests/spending/test_attrs.py`

**Interfaces:**
- Consumes: `Ranking`, `Coverage`, `NordicSummary`, `nordic_summary`, `RankEntry` (Task 11); `publication_age_days`, `reference_age_days`, `reference_period_complete` (Task 4).
- Produces:
  - `MILLION = 1_000_000`, `RANKING_ROWS = 40`
  - `iso(value: date | datetime | None) -> str | None`
  - `scaled(value: Decimal | None, scale: int = 1) -> float | None`
  - `price_base_year(unit: str) -> int | None`
  - `provenance_attrs(point, *, spec, metric, retrieved_at, today, reference=None, status=None) -> dict[str, Any]`
  - `Companion = tuple[Callable[[str], Decimal | None], int]`
  - `ranking_attrs(ranking, cov, *, value_key, scale, companions=None) -> dict[str, Any]`
  - `monthly_series_attrs(series: dict[tuple[int, int], SpendingDataPoint], year, value_key, scale) -> list[dict[str, Any]]`
  - `annual_series_attrs(series: dict[int, SpendingDataPoint], value_key, scale) -> list[dict[str, Any]]`

- [ ] **Step 1: Write the failing tests**

Create `tests/spending/test_attrs.py`:

```python
"""Attribute builders shared by every spending sensor (spec §6)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from custom_components.edp_radar.spending.attrs import (
    MILLION,
    RANKING_ROWS,
    annual_series_attrs,
    monthly_series_attrs,
    price_base_year,
    provenance_attrs,
    ranking_attrs,
    scaled,
)
from custom_components.edp_radar.spending.calculations import coverage, rank
from custom_components.edp_radar.spending.models import (
    DatapointStatus,
    ReferencePeriod,
    SpendingDataPoint,
)
from custom_components.edp_radar.spending.registry import metric_spec, source_spec

TODAY = date(2026, 9, 14)
NOW = datetime(2026, 9, 14, 13, 40, 21, tzinfo=UTC)


def _point(
    country: str,
    year: int,
    value: str,
    *,
    metric: str = "military_expenditure_usd_constant",
    unit: str = "USD_MILLION_CONSTANT_2024",
    status: DatapointStatus = DatapointStatus.ACTUAL,
) -> SpendingDataPoint:
    return SpendingDataPoint(
        "sipri",
        metric,
        country,
        ReferencePeriod.year(year),
        Decimal(value),
        unit,
        status,
        "milex:2026-04-27",
        date(2026, 4, 27),
        "https://www.sipri.org/databases/milex",
    )


def test_provenance_attrs_are_the_shared_set() -> None:
    point = _point("SE", 2025, "14954.07")
    attrs = provenance_attrs(
        point,
        spec=source_spec("sipri"),
        metric=metric_spec("sipri", "military_expenditure_usd_constant"),
        retrieved_at=NOW,
        today=TODAY,
    )
    assert attrs == {
        "source": "SIPRI Military Expenditure Database",
        "source_id": "sipri",
        "source_url": "https://www.sipri.org/databases/milex",
        "reference_label": "2025",
        "reference_start": "2025-01-01",
        "reference_end": "2025-12-31",
        "reference_period_complete": True,
        "status": "actual",
        "published_at": "2026-04-27",
        "publication_age_days": 140,
        "reference_age_days": 257,
        "retrieved_at": "2026-09-14T13:40:21+00:00",
        "release_id": "milex:2026-04-27",
        "unit_definition": metric_spec(
            "sipri", "military_expenditure_usd_constant"
        ).definition,
    }
    # An unfinished reference year has no age and can override label/status.
    running = provenance_attrs(
        _point("SE", 2026, "1", status=DatapointStatus.ESTIMATE),
        spec=source_spec("nato"),
        metric=metric_spec("nato", "defence_expenditure_usd_current"),
        retrieved_at=None,
        today=TODAY,
        reference=ReferencePeriod(date(2026, 1, 1), date(2026, 7, 31), "Jan–Jul 2026"),
        status=DatapointStatus.PRELIMINARY,
    )
    assert running["reference_label"] == "Jan–Jul 2026"
    assert running["status"] == "preliminary"
    assert running["retrieved_at"] is None
    full_year = provenance_attrs(
        _point("SE", 2026, "1", status=DatapointStatus.ESTIMATE),
        spec=source_spec("nato"),
        metric=metric_spec("nato", "defence_expenditure_usd_current"),
        retrieved_at=None,
        today=TODAY,
    )
    assert full_year["reference_period_complete"] is False
    assert full_year["reference_age_days"] is None


def test_ranking_attrs_rows_coverage_and_nordic() -> None:
    points = [
        *(_point(country, 2025, str(value)) for country, value in {
            "US": 900000, "RU": 158236, "DE": 88000, "NO": 16085, "SE": 14954,
            "DK": 14082, "FI": 7614, "IS": 0,
        }.items()),
        _point("SE", 2025, "2.47", metric="military_expenditure_pct_gdp", unit="PCT_GDP"),
        _point("US", 2024, "880000"),
        _point("CH", 2024, "6000"),
    ]
    ranking = rank(points, metric_id="military_expenditure_usd_constant", unit="USD_MILLION_CONSTANT_2024", reference=ReferencePeriod.year(2025))
    assert ranking is not None
    cov = coverage(points, "military_expenditure_usd_constant", ReferencePeriod.year(2025), unit="USD_MILLION_CONSTANT_2024")
    attrs = ranking_attrs(
        ranking,
        cov,
        value_key="usd",
        scale=MILLION,
        companions={
            "pct_gdp": (
                lambda country: Decimal("2.47") if country == "SE" else None,
                1,
            )
        },
    )
    assert attrs["ranking"][0] == {"rank": 1, "country": "US", "usd": 900000.0 * MILLION, "pct_gdp": None}
    assert attrs["ranking"][4] == {"rank": 5, "country": "SE", "usd": 14954.0 * MILLION, "pct_gdp": 2.47}
    assert attrs["population"] == 7
    assert attrs["population_total"] == 9
    assert attrs["missing"] == ["CH"]
    assert attrs["excluded_zero"] == ["IS"]
    assert attrs["top"] == {"country": "US", "usd": 900000.0 * MILLION}
    assert attrs["median_usd"] == 16085.0 * MILLION
    assert [row["country"] for row in attrs["nordic"]] == ["NO", "SE", "DK", "FI"]
    assert attrs["nordic_median_usd"] == (14954 + 14082) / 2 * MILLION  # SE, DK are the middle two
    assert attrs["sweden"] == {"rank": 5, "usd": 14954.0 * MILLION}
    assert attrs["statuses"] == ["actual"]


def test_ranking_rows_are_capped_with_sweden_appended() -> None:
    points = [_point(f"C{i:02d}", 2025, str(1000 - i)) for i in range(RANKING_ROWS + 5)]
    points.append(_point("SE", 2025, "1"))
    ranking = rank(points, metric_id="military_expenditure_usd_constant", unit="USD_MILLION_CONSTANT_2024", reference=ReferencePeriod.year(2025))
    assert ranking is not None
    cov = coverage(points, "military_expenditure_usd_constant", ReferencePeriod.year(2025), unit="USD_MILLION_CONSTANT_2024")
    rows = ranking_attrs(ranking, cov, value_key="usd", scale=MILLION)["ranking"]
    assert len(rows) == RANKING_ROWS + 1
    assert rows[-1]["country"] == "SE" and rows[-1]["rank"] == RANKING_ROWS + 6


def test_series_attrs_and_helpers() -> None:
    monthly = {
        (2026, 1): SpendingDataPoint("statskontoret", "materiel_outturn", "SE", ReferencePeriod.month(2026, 1), Decimal("2000.5"), "SEK_MILLION", DatapointStatus.ACTUAL, "r", None, "u"),
        (2026, 2): SpendingDataPoint("statskontoret", "materiel_outturn", "SE", ReferencePeriod.month(2026, 2), Decimal("3000"), "SEK_MILLION", DatapointStatus.ACTUAL, "r", None, "u"),
        (2025, 12): SpendingDataPoint("statskontoret", "materiel_outturn", "SE", ReferencePeriod.month(2025, 12), Decimal("9000"), "SEK_MILLION", DatapointStatus.PRELIMINARY, "r", None, "u"),
    }
    assert monthly_series_attrs(monthly, 2026, "sek", MILLION) == [
        {"month": "Jan", "sek": 2000.5 * MILLION, "status": "actual"},
        {"month": "Feb", "sek": 3000.0 * MILLION, "status": "actual"},
    ]
    annual = {2025: _point("SE", 2025, "12"), 2024: _point("SE", 2024, "11")}
    assert annual_series_attrs(annual, "usd", MILLION) == [
        {"year": 2024, "usd": 11.0 * MILLION, "status": "actual"},
        {"year": 2025, "usd": 12.0 * MILLION, "status": "actual"},
    ]
    assert scaled(None) is None and scaled(Decimal("1.5"), 2) == 3.0
    assert price_base_year("USD_MILLION_CONSTANT_2024") == 2024
    assert price_base_year("USD_MILLION") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_attrs.py -q`
Expected: `ModuleNotFoundError: custom_components.edp_radar.spending.attrs`.

- [ ] **Step 3: Implement**

Create `custom_components/edp_radar/spending/attrs.py`:

```python
"""Attribute builders for the spending sensors (spec §6; S36, S37).

Pure functions: they turn datapoints and rankings into the JSON-friendly
dicts entities expose. Money is scaled from the source's millions to whole
currency units here so the entity code never touches units.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from .calculations import Coverage, RankEntry, Ranking, nordic_summary
from .freshness import (
    publication_age_days,
    reference_age_days,
    reference_period_complete,
)
from .models import (
    DatapointStatus,
    MetricSpec,
    ReferencePeriod,
    SourceSpec,
    SpendingDataPoint,
)
from .registry import FOCUS_COUNTRY

MILLION = 1_000_000
# Eurostat (27), NATO (31) and EDA (27) fit; SIPRI shows the top 40 + Sweden.
RANKING_ROWS = 40
_BASE_YEAR = re.compile(r"_CONSTANT_(\d{4})$")

type Companion = tuple[Callable[[str], Decimal | None], int]


def iso(value: date | datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def scaled(value: Decimal | None, scale: int = 1) -> float | None:
    return None if value is None else float(value * scale)


def price_base_year(unit: str) -> int | None:
    match = _BASE_YEAR.search(unit)
    return int(match.group(1)) if match else None


def provenance_attrs(
    point: SpendingDataPoint,
    *,
    spec: SourceSpec,
    metric: MetricSpec,
    retrieved_at: datetime | None,
    today: date,
    reference: ReferencePeriod | None = None,
    status: DatapointStatus | None = None,
) -> dict[str, Any]:
    """The shared provenance set (plan §78). ``reference``/``status`` override
    the datapoint's own for composite figures such as a YTD sum."""
    period = reference or point.reference
    complete = reference_period_complete(period.end, today)
    return {
        "source": spec.display_name,
        "source_id": point.source_id,
        "source_url": point.source_url,
        "reference_label": period.label,
        "reference_start": iso(period.start),
        "reference_end": iso(period.end),
        "reference_period_complete": complete,
        "status": (status or point.status).value,
        "published_at": iso(point.published_at),
        "publication_age_days": publication_age_days(point.published_at, today),
        "reference_age_days": reference_age_days(period.end, today)
        if complete
        else None,
        "retrieved_at": iso(retrieved_at),
        "release_id": point.release_id,
        "unit_definition": metric.definition,
    }


def _row(
    entry: RankEntry,
    value_key: str,
    scale: int,
    companions: Mapping[str, Companion] | None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "rank": entry.rank,
        "country": entry.country,
        value_key: scaled(entry.value, scale),
    }
    for name, (lookup, companion_scale) in (companions or {}).items():
        row[name] = scaled(lookup(entry.country), companion_scale)
    return row


def ranking_attrs(
    ranking: Ranking,
    cov: Coverage,
    *,
    value_key: str,
    scale: int,
    companions: Mapping[str, Companion] | None = None,
) -> dict[str, Any]:
    """Rows (capped, Sweden always present), coverage, top, medians, Nordic."""
    entries = list(ranking.entries[:RANKING_ROWS])
    if all(e.country != FOCUS_COUNTRY for e in entries):
        entries.append(next(e for e in ranking.entries if e.country == FOCUS_COUNTRY))
    nordic = nordic_summary(ranking)
    return {
        "ranking": [_row(e, value_key, scale, companions) for e in entries],
        "population": ranking.population,
        "population_total": len(cov.ever_seen),
        "missing": list(cov.missing),
        "excluded_zero": list(ranking.excluded_zero),
        "top": {"country": ranking.top.country, value_key: scaled(ranking.top.value, scale)},
        f"median_{value_key}": scaled(ranking.median, scale),
        "nordic": [
            {"country": e.country, "rank": e.rank, value_key: scaled(e.value, scale)}
            for e in nordic.entries
        ],
        f"nordic_median_{value_key}": scaled(nordic.median, scale),
        "sweden": {"rank": ranking.focus_rank, value_key: scaled(ranking.focus_value, scale)},
        "statuses": list(ranking.statuses),
    }


def monthly_series_attrs(
    series: Mapping[tuple[int, int], SpendingDataPoint],
    year: int,
    value_key: str,
    scale: int,
) -> list[dict[str, Any]]:
    """One row per stored month of ``year`` (plan §52 chart), January first."""
    return [
        {
            "month": point.reference.label.split(" ")[0],
            value_key: scaled(point.value, scale),
            "status": point.status.value,
        }
        for (point_year, _month), point in sorted(series.items())
        if point_year == year
    ]


def annual_series_attrs(
    series: Mapping[int, SpendingDataPoint], value_key: str, scale: int
) -> list[dict[str, Any]]:
    return [
        {"year": year, value_key: scaled(point.value, scale), "status": point.status.value}
        for year, point in sorted(series.items())
    ]
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending/test_attrs.py -q`
Expected: all pass. If the `provenance` ages differ by one, recount: 2026-04-27 → 2026-09-14 is 140 days; 2025-12-31 → 2026-09-14 is 257 days.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/attrs.py tests/spending/test_attrs.py
git commit -m "feat(spending): attribute builders for provenance, rankings and series

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 13: `spending/text.py` — amount formatting and the two text sensors

**Files:**
- Create: `custom_components/edp_radar/spending/text.py`
- Test: `tests/spending/test_text.py`

**Interfaces:**
- Consumes: `YtdChange` (Task 11), `Ranking`.
- Produces: `format_amount(currency, amount: Decimal | None) -> str` (whole units in, `"SEK 48.2bn"` out); `statskontoret_snapshot_text(ytd: YtdChange | None, through_label: str | None) -> str | None`; `nato_position_text(ranking: Ranking | None, usd: Decimal | None, pct_gdp: Decimal | None, reference_year: int | None, status: DatapointStatus | None) -> str | None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/spending/test_text.py`:

```python
"""Compact factual text sensors (plan §76): facts, source, period — no verdicts."""

from __future__ import annotations

from decimal import Decimal

from custom_components.edp_radar.spending.calculations import YtdChange, rank
from custom_components.edp_radar.spending.models import (
    DatapointStatus,
    ReferencePeriod,
    SpendingDataPoint,
)
from custom_components.edp_radar.spending.text import (
    format_amount,
    nato_position_text,
    statskontoret_snapshot_text,
)


def test_format_amount_thresholds() -> None:
    assert format_amount("SEK", Decimal("48200000000")) == "SEK 48.2bn"
    assert format_amount("EUR", Decimal("850000000")) == "EUR 850m"
    assert format_amount("USD", Decimal("2400000")) == "USD 2.4m"
    assert format_amount("SEK", Decimal("12500")) == "SEK 13k"
    assert format_amount("SEK", Decimal("999")) == "SEK 999"
    assert format_amount("SEK", None) == "SEK n/a"


def test_statskontoret_snapshot_text() -> None:
    ytd = YtdChange(Decimal("25876.95768163"), Decimal("19905.38365486"), Decimal("5971.57"), Decimal("30.0"), 7)
    assert (
        statskontoret_snapshot_text(ytd, "Jul 2026")
        == "Materiel YTD SEK 25.9bn · +30.0% YoY · Statskontoret · through Jul 2026"
    )
    no_base = YtdChange(Decimal("100"), None, None, None, 1)
    assert (
        statskontoret_snapshot_text(no_base, "Jan 2027")
        == "Materiel YTD SEK 100m · YoY n/a · Statskontoret · through Jan 2027"
    )
    assert statskontoret_snapshot_text(None, None) is None


def test_nato_position_text() -> None:
    points = [
        SpendingDataPoint("nato", "defence_expenditure_pct_gdp", c, ReferencePeriod.year(2026), Decimal(v), "PCT_GDP", DatapointStatus.ESTIMATE, "r", None, "u")
        for c, v in (("LT", "5.33"), ("SE", "3.22"), ("US", "3.2"))
    ]
    ranking = rank(points, metric_id="defence_expenditure_pct_gdp", unit="PCT_GDP", reference=ReferencePeriod.year(2026))
    assert (
        nato_position_text(ranking, Decimal("24186000000"), Decimal("3.22"), 2026, DatapointStatus.ESTIMATE)
        == "SE #2 of 3 · USD 24.2bn · 3.2% GDP · NATO 2026 estimate"
    )
    assert nato_position_text(None, None, None, None, None) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/spending/test_text.py -q`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `custom_components/edp_radar/spending/text.py`:

```python
"""Compact factual text for the two spending text sensors (plan §76).

Facts, source and period only — no interpretation. ``format_amount`` takes
whole currency units (what the entities expose), not source millions.
"""

from __future__ import annotations

from decimal import Decimal

from .calculations import Ranking, YtdChange
from .models import DatapointStatus


def format_amount(currency: str, amount: Decimal | None) -> str:
    """``"SEK 48.2bn"`` — the thresholds of ``periods.format_eur``, any currency."""
    if amount is None:
        return f"{currency} n/a"
    value = float(amount)
    if value >= 1e9:
        return f"{currency} {value / 1e9:.1f}bn"
    if value >= 1e7:
        return f"{currency} {value / 1e6:.0f}m"
    if value >= 1e6:
        return f"{currency} {value / 1e6:.1f}m"
    if value >= 1e3:
        return f"{currency} {value / 1e3:.0f}k"
    return f"{currency} {value:.0f}"


def _pct(value: Decimal | None) -> str:
    return "n/a" if value is None else f"{float(value):+.1f}%"


def statskontoret_snapshot_text(
    ytd: YtdChange | None, through_label: str | None
) -> str | None:
    """``Materiel YTD SEK 48.2bn · +31% YoY · Statskontoret · through Aug 2026``."""
    if ytd is None or through_label is None:
        return None
    amount = format_amount("SEK", ytd.current * 1_000_000)
    return f"Materiel YTD {amount} · {_pct(ytd.pct)} YoY · Statskontoret · through {through_label}"


def nato_position_text(
    ranking: Ranking | None,
    usd: Decimal | None,
    pct_gdp: Decimal | None,
    reference_year: int | None,
    status: DatapointStatus | None,
) -> str | None:
    """``SE #7 of 31 · USD 24.2bn · 3.2% GDP · NATO 2026 estimate``."""
    if ranking is None or reference_year is None or status is None:
        return None
    share = "n/a" if pct_gdp is None else f"{float(pct_gdp):.1f}%"
    return (
        f"SE #{ranking.focus_rank} of {ranking.population} · "
        f"{format_amount('USD', usd)} · {share} GDP · NATO {reference_year} {status.value}"
    )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/spending/test_text.py -q`
Expected: all pass.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/text.py tests/spending/test_text.py
git commit -m "feat(spending): text formatting for the snapshot and NATO position sensors

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Part C — entities

### Task 14: `spending/sensors.py`, source devices, Statskontoret sensors, platform hook

**Files:**
- Create: `custom_components/edp_radar/spending/sensors.py`, `tests/test_spending_sensors.py`
- Modify: `custom_components/edp_radar/entity.py`, `custom_components/edp_radar/sensor.py`, `custom_components/edp_radar/strings.json`, `custom_components/edp_radar/translations/en.json`, `custom_components/edp_radar/translations/sv.json`

**Interfaces:**
- Consumes: Tasks 11–13; `SpendingCoordinator`, `SpendingSnapshot.get(source_id)`; `mock_spending_sources` (`tests/spending/mocks.py`).
- Produces:
  - `entity.spending_device_info(entry_id, source_id) -> DeviceInfo`
  - `sensors.SpendingSensorEntityDescription(key, source_id, value_fn, attributes_fn=None, …)` with `ValueFn = Callable[[SourceSeries, date], StateType]`, `AttributesFn = Callable[[SourceSeries, date, datetime], dict[str, Any]]`
  - `sensors.SpendingSensor`, `sensors.SPENDING_SENSORS: tuple[SpendingSensorEntityDescription, ...]`, `sensors.async_setup_spending_sensors(entry, async_add_entities)`
  - builders `_money`, `_pct`, `_rank`, `_text`, `_age` reused by Tasks 15–19
  - unique ids `f"{entry_id}_spending_{key}"`; entity ids `sensor.statskontoret_materiel_acquisition_ytd` etc.

- [ ] **Step 1: Write the failing HA test**

Create `tests/test_spending_sensors.py`:

```python
"""Spending sensors: five source devices, Sweden focus (Phase 3 Plan 2)."""

from __future__ import annotations

from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.const import DOMAIN

from .spending.mocks import mock_spending_sources
from .test_coordinator import NOW

ENTRY = "test-entry"
MILLION = 1_000_000

SPENDING_KEYS = {
    "statskontoret": [
        "statskontoret_materiel_ytd",
        "statskontoret_materiel_latest_month",
        "statskontoret_materiel_ytd_change_pct",
        "statskontoret_defence_ytd",
        "statskontoret_defence_latest_month",
        "statskontoret_defence_ytd_change_pct",
        "statskontoret_snapshot_text",
        "statskontoret_data_age",
    ],
    "eurostat": [
        "eurostat_defence_expenditure",
        "eurostat_defence_expenditure_rank",
        "eurostat_defence_investment",
        "eurostat_defence_investment_rank",
        "eurostat_data_age",
    ],
    "nato": [
        "nato_defence_expenditure",
        "nato_defence_expenditure_pct_gdp",
        "nato_defence_expenditure_pct_gdp_rank",
        "nato_equipment_share_pct",
        "nato_position_text",
        "nato_data_age",
    ],
    "eda": [
        "eda_defence_expenditure",
        "eda_defence_expenditure_rank",
        "eda_defence_investment_rank",
        "eda_data_age",
    ],
    "sipri": [
        "sipri_military_expenditure",
        "sipri_military_expenditure_rank",
        "sipri_military_expenditure_pct_gdp",
        "sipri_data_age",
    ],
}
DATA_AGE_KEYS = [k for keys in SPENDING_KEYS.values() for k in keys if k.endswith("_data_age")]


async def setup_spending(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker
) -> MockConfigEntry:
    mock_spending_sources(mock_backend)
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id=ENTRY, unique_id=DOMAIN, data={}, options={}, version=2
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def entity_id(hass: HomeAssistant, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{ENTRY}_spending_{key}"
    )


def get_state(hass: HomeAssistant, key: str) -> State:
    eid = entity_id(hass, key)
    assert eid is not None, f"spending sensor {key} not registered"
    state = hass.states.get(eid)
    assert state is not None, f"{eid} has no state"
    return state


def provenance(attrs: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "source", "source_id", "source_url", "reference_label", "reference_start",
        "reference_end", "reference_period_complete", "status", "published_at",
        "publication_age_days", "reference_age_days", "retrieved_at", "release_id",
        "unit_definition",
    )
    missing = [k for k in keys if k not in attrs]
    assert not missing, f"provenance keys missing: {missing}"
    return {k: attrs[k] for k in keys}


@pytest.mark.spending_live
async def test_source_devices_and_every_sensor_exist(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)
    await setup_spending(hass, mock_backend)
    devices = dr.async_get(hass)
    registry = er.async_get(hass)
    for source_id, keys in SPENDING_KEYS.items():
        device = devices.async_get_device({(DOMAIN, f"{ENTRY}_spending_{source_id}")})
        assert device is not None, source_id
        assert device.name in {"Statskontoret", "Eurostat", "NATO", "EDA", "SIPRI"}
        assert device.configuration_url
        for key in keys:
            eid = entity_id(hass, key)
            assert eid is not None, key
            assert registry.async_get(eid).device_id == device.id
    for key in DATA_AGE_KEYS:
        entry = registry.async_get(entity_id(hass, key))
        assert entry is not None and entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entity_id(hass, "statskontoret_materiel_ytd") == "sensor.statskontoret_materiel_acquisition_ytd"
    assert entity_id(hass, "eurostat_defence_expenditure") == "sensor.eurostat_defence_expenditure"


@pytest.mark.spending_live
async def test_statskontoret_sensors(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)
    await setup_spending(hass, mock_backend)

    ytd = get_state(hass, "statskontoret_materiel_ytd")
    assert float(ytd.state) == pytest.approx(25876.95768163 * MILLION)
    assert ytd.attributes["unit_of_measurement"] == "SEK"
    assert ytd.attributes["device_class"] == "monetary"
    assert ytd.attributes["months_included"] == 7
    assert ytd.attributes["previous_year_ytd_sek"] == pytest.approx(19905.38365486 * MILLION)
    assert ytd.attributes["change_pct"] == pytest.approx(30.0, abs=0.05)
    assert [row["month"] for row in ytd.attributes["monthly_current_year"]] == [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
    ]
    assert len(ytd.attributes["monthly_previous_year"]) == 12
    assert ytd.attributes["monthly_previous_year"][11]["status"] == "actual"
    prov = provenance(ytd.attributes)
    assert prov["source"] == "Statskontoret"
    assert prov["reference_label"] == "Jan–Jul 2026"
    assert prov["reference_start"] == "2026-01-01"
    assert prov["reference_end"] == "2026-07-31"
    assert prov["status"] == "actual"
    assert prov["published_at"] == "2026-08-24"
    assert prov["publication_age_days"] == 19
    assert prov["reference_age_days"] == 43
    assert prov["release_id"] == "2026-07-definitiv-2026-08-24"

    latest = get_state(hass, "statskontoret_materiel_latest_month")
    assert float(latest.state) == pytest.approx(3753.54717975 * MILLION)
    assert latest.attributes["month_label"] == "Jul 2026"
    assert latest.attributes["same_month_previous_year_sek"] == pytest.approx(2939.12460557 * MILLION)
    assert latest.attributes["change_pct"] == pytest.approx(27.7, abs=0.05)
    assert provenance(latest.attributes)["reference_label"] == "Jul 2026"

    change = get_state(hass, "statskontoret_materiel_ytd_change_pct")
    assert float(change.state) == pytest.approx(30.0, abs=0.05)
    assert change.attributes["unit_of_measurement"] == "%"
    assert change.attributes["current_sek"] == pytest.approx(25876.95768163 * MILLION)

    defence = get_state(hass, "statskontoret_defence_ytd")
    assert float(defence.state) == pytest.approx(81422.36229634 * MILLION)
    assert defence.attributes["uo6_total_ytd_sek"] == pytest.approx(87336.30036421 * MILLION)
    defence_month = get_state(hass, "statskontoret_defence_latest_month")
    assert float(defence_month.state) == pytest.approx(DEFENCE_JUL_2026 * MILLION)
    assert defence_month.attributes["same_month_previous_year_sek"] == pytest.approx(9041.86392863 * MILLION)
    assert float(get_state(hass, "statskontoret_defence_ytd_change_pct").state) == pytest.approx(21.6, abs=0.05)

    text = get_state(hass, "statskontoret_snapshot_text")
    assert text.state == "Materiel YTD SEK 25.9bn · +30.0% YoY · Statskontoret · through Jul 2026"


async def test_sensors_are_unknown_before_the_first_refresh(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker
) -> None:
    """Without providers (conftest stubs them) every value sensor is unknown."""
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id=ENTRY, unique_id=DOMAIN, data={}, options={}, version=2
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert get_state(hass, "statskontoret_materiel_ytd").state == STATE_UNKNOWN
    assert get_state(hass, "statskontoret_snapshot_text").state == STATE_UNKNOWN
```

Add the module constant `DEFENCE_JUL_2026 = 10267.82747284` (the July 2026 `uo6_defence_outturn` figure in the fixture, MSEK) next to `MILLION`. The 2025 July figure is `9041.86392863`; the 2026 YTD is `81422.36229634` and the 2025 YTD `66946.64818113`, so the YTD change is +21.6 %.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_spending_sensors.py -q`
Expected: `test_source_devices_and_every_sensor_exist` fails (`device is None`), the others fail on missing entities.

- [ ] **Step 3: Device info in `entity.py`**

Add to `custom_components/edp_radar/entity.py` (import `source_spec` from `.spending.registry`):

```python
SPENDING_DEVICE_NAMES: dict[str, str] = {
    "statskontoret": "Statskontoret",
    "eurostat": "Eurostat",
    "nato": "NATO",
    "eda": "EDA",
    "sipri": "SIPRI",
}


def spending_device_info(entry_id: str, source_id: str) -> DeviceInfo:
    """One service device per spending source (S30); the source's own page is
    the configuration URL."""
    spec = source_spec(source_id)
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_spending_{source_id}")},
        name=SPENDING_DEVICE_NAMES[source_id],
        manufacturer=spec.publisher,
        model=spec.display_name,
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=spec.canonical_url,
    )
```

- [ ] **Step 4: Create `spending/sensors.py` with the Statskontoret block**

```python
"""Spending sensors (Phase 3 Plan 2; spec S30–S37, S43).

One ``SpendingSensor`` per description; each reads one source's
``SourceSeries`` from the ``SpendingCoordinator`` snapshot and never fetches
anything itself. Money is exposed in whole currency units (S32); Sweden is
the fixed focus (S2); rankings never cross sources (S8).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from ..entity import spending_device_info
from .attrs import (
    MILLION,
    Companion,
    annual_series_attrs,
    monthly_series_attrs,
    price_base_year,
    provenance_attrs,
    ranking_attrs,
    scaled,
)
from .calculations import (
    MonthChange,
    Ranking,
    YtdChange,
    annual_series,
    change_over_years,
    coverage,
    latest_month,
    latest_year,
    month_change,
    monthly_series,
    nominal_change_pct,
    rank,
    value_at,
    ytd_change,
)
from .coordinator import SpendingCoordinator
from .models import DatapointStatus, ReferencePeriod, SourceSeries, SpendingDataPoint
from .registry import (
    EDA,
    EUROSTAT,
    FOCUS_COUNTRY,
    NATO,
    SIPRI,
    STATSKONTORET,
    metric_spec,
    source_spec,
)
from .text import nato_position_text, statskontoret_snapshot_text

if TYPE_CHECKING:
    from ..coordinator import EdpRadarConfigEntry

type ValueFn = Callable[[SourceSeries, date], StateType]
type AttributesFn = Callable[[SourceSeries, date, datetime], dict[str, Any]]


@dataclass(frozen=True, kw_only=True)
class SpendingSensorEntityDescription(SensorEntityDescription):
    """A sensor bound to one source device and one reader of its series."""

    source_id: str
    value_fn: ValueFn
    attributes_fn: AttributesFn | None = None


# ----------------------------------------------------------------- builders


def _money(
    key: str,
    source_id: str,
    currency: str,
    value_fn: ValueFn,
    attributes_fn: AttributesFn | None = None,
) -> SpendingSensorEntityDescription:
    return SpendingSensorEntityDescription(
        key=key,
        translation_key=key,
        source_id=source_id,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=currency,
        suggested_display_precision=0,
        value_fn=value_fn,
        attributes_fn=attributes_fn,
    )


def _pct(
    key: str,
    source_id: str,
    value_fn: ValueFn,
    attributes_fn: AttributesFn | None = None,
) -> SpendingSensorEntityDescription:
    return SpendingSensorEntityDescription(
        key=key,
        translation_key=key,
        source_id=source_id,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=value_fn,
        attributes_fn=attributes_fn,
    )


def _rank(
    key: str,
    source_id: str,
    value_fn: ValueFn,
    attributes_fn: AttributesFn,
) -> SpendingSensorEntityDescription:
    return SpendingSensorEntityDescription(
        key=key,
        translation_key=key,
        source_id=source_id,
        value_fn=value_fn,
        attributes_fn=attributes_fn,
    )


def _text(key: str, source_id: str, value_fn: ValueFn) -> SpendingSensorEntityDescription:
    return SpendingSensorEntityDescription(
        key=key, translation_key=key, source_id=source_id, value_fn=value_fn
    )


def _age(
    key: str, source_id: str, value_fn: ValueFn, attributes_fn: AttributesFn
) -> SpendingSensorEntityDescription:
    return SpendingSensorEntityDescription(
        key=key,
        translation_key=key,
        source_id=source_id,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=value_fn,
        attributes_fn=attributes_fn,
    )


def _provenance(
    point: SpendingDataPoint,
    series: SourceSeries,
    today: date,
    *,
    reference: ReferencePeriod | None = None,
    status: DatapointStatus | None = None,
) -> dict[str, Any]:
    return provenance_attrs(
        point,
        spec=source_spec(point.source_id),
        metric=metric_spec(point.source_id, point.metric_id),
        retrieved_at=series.retrieved_at,
        today=today,
        reference=reference,
        status=status,
    )


def _pct_value(value: Decimal | None) -> float | None:
    return scaled(value, 1)


# ------------------------------------------------------------ Statskontoret

MATERIEL = "materiel_outturn"
DEFENCE = "uo6_defence_outturn"
UO6_TOTAL = "uo6_total_outturn"


def _sk_ytd(series: SourceSeries, metric_id: str) -> tuple[SpendingDataPoint, YtdChange] | None:
    latest = latest_month(series.datapoints, metric_id, FOCUS_COUNTRY)
    if latest is None:
        return None
    change = ytd_change(
        series.datapoints,
        metric_id,
        FOCUS_COUNTRY,
        latest.reference.start.year,
        latest.reference.start.month,
    )
    return None if change is None else (latest, change)


def _ytd_reference(latest: SpendingDataPoint) -> ReferencePeriod:
    end = latest.reference.end
    return ReferencePeriod(date(end.year, 1, 1), end, f"Jan–{latest.reference.label}")


def _sk_ytd_value(metric_id: str) -> ValueFn:
    return lambda series, today: (
        scaled(pair[1].current, MILLION) if (pair := _sk_ytd(series, metric_id)) else None
    )


def _sk_ytd_attrs(metric_id: str) -> AttributesFn:
    def attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
        pair = _sk_ytd(series, metric_id)
        if pair is None:
            return {}
        latest, change = pair
        year = latest.reference.start.year
        months = monthly_series(series.datapoints, metric_id, FOCUS_COUNTRY)
        out = _provenance(latest, series, today, reference=_ytd_reference(latest))
        out.update(
            {
                "months_included": change.months,
                "previous_year_ytd_sek": scaled(change.previous, MILLION),
                "change_pct": _pct_value(change.pct),
                "monthly_current_year": monthly_series_attrs(months, year, "sek", MILLION),
                "monthly_previous_year": monthly_series_attrs(
                    months, year - 1, "sek", MILLION
                ),
            }
        )
        if metric_id == DEFENCE:
            total = _sk_ytd(series, UO6_TOTAL)
            out["uo6_total_ytd_sek"] = scaled(total[1].current, MILLION) if total else None
        return out

    return attrs


def _sk_month(series: SourceSeries, metric_id: str) -> MonthChange | None:
    latest = latest_month(series.datapoints, metric_id, FOCUS_COUNTRY)
    if latest is None:
        return None
    return month_change(
        series.datapoints,
        metric_id,
        FOCUS_COUNTRY,
        latest.reference.start.year,
        latest.reference.start.month,
    )


def _sk_month_value(metric_id: str) -> ValueFn:
    return lambda series, today: (
        scaled(m.current.value, MILLION) if (m := _sk_month(series, metric_id)) else None
    )


def _sk_month_attrs(metric_id: str) -> AttributesFn:
    def attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
        change = _sk_month(series, metric_id)
        if change is None:
            return {}
        out = _provenance(change.current, series, today)
        out.update(
            {
                "month_label": change.current.reference.label,
                "same_month_previous_year_sek": scaled(
                    change.previous.value if change.previous else None, MILLION
                ),
                "change_pct": _pct_value(change.pct),
            }
        )
        return out

    return attrs


def _sk_change_value(metric_id: str) -> ValueFn:
    return lambda series, today: (
        _pct_value(pair[1].pct) if (pair := _sk_ytd(series, metric_id)) else None
    )


def _sk_change_attrs(metric_id: str) -> AttributesFn:
    def attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
        pair = _sk_ytd(series, metric_id)
        if pair is None:
            return {}
        latest, change = pair
        out = _provenance(latest, series, today, reference=_ytd_reference(latest))
        out.update(
            {
                "current_sek": scaled(change.current, MILLION),
                "previous_sek": scaled(change.previous, MILLION),
                "change_sek": scaled(change.change, MILLION),
            }
        )
        return out

    return attrs


def _sk_snapshot(series: SourceSeries, today: date) -> StateType:
    pair = _sk_ytd(series, MATERIEL)
    if pair is None:
        return None
    return statskontoret_snapshot_text(pair[1], pair[0].reference.label)


STATSKONTORET_SENSORS: tuple[SpendingSensorEntityDescription, ...] = (
    _money("statskontoret_materiel_ytd", STATSKONTORET, "SEK", _sk_ytd_value(MATERIEL), _sk_ytd_attrs(MATERIEL)),
    _money("statskontoret_materiel_latest_month", STATSKONTORET, "SEK", _sk_month_value(MATERIEL), _sk_month_attrs(MATERIEL)),
    _pct("statskontoret_materiel_ytd_change_pct", STATSKONTORET, _sk_change_value(MATERIEL), _sk_change_attrs(MATERIEL)),
    _money("statskontoret_defence_ytd", STATSKONTORET, "SEK", _sk_ytd_value(DEFENCE), _sk_ytd_attrs(DEFENCE)),
    _money("statskontoret_defence_latest_month", STATSKONTORET, "SEK", _sk_month_value(DEFENCE), _sk_month_attrs(DEFENCE)),
    _pct("statskontoret_defence_ytd_change_pct", STATSKONTORET, _sk_change_value(DEFENCE), _sk_change_attrs(DEFENCE)),
    _text("statskontoret_snapshot_text", STATSKONTORET, _sk_snapshot),
)


# ------------------------------------------------------------------ catalogue

SPENDING_SENSORS: tuple[SpendingSensorEntityDescription, ...] = (
    *STATSKONTORET_SENSORS,
)


# ------------------------------------------------------------------- entity


class SpendingSensor(CoordinatorEntity[SpendingCoordinator], SensorEntity):
    """A sensor reading one source's series from the spending snapshot."""

    _attr_has_entity_name = True
    entity_description: SpendingSensorEntityDescription

    def __init__(
        self,
        coordinator: SpendingCoordinator,
        description: SpendingSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry_id = coordinator.entry.entry_id
        self._attr_unique_id = f"{entry_id}_spending_{description.key}"
        self._attr_device_info = spending_device_info(entry_id, description.source_id)

    @property
    def _series(self) -> SourceSeries | None:
        data = self.coordinator.data
        return None if data is None else data.get(self.entity_description.source_id)

    @property
    def native_value(self) -> StateType:
        series = self._series
        if series is None:
            return None
        return self.entity_description.value_fn(series, dt_util.now().date())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        series = self._series
        builder = self.entity_description.attributes_fn
        if series is None or builder is None:
            return None
        return builder(series, dt_util.now().date(), dt_util.utcnow())


def async_setup_spending_sensors(
    entry: EdpRadarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Every spending sensor exists whenever the integration is set up."""
    coordinator = entry.runtime_data.spending
    async_add_entities(
        SpendingSensor(coordinator, description) for description in SPENDING_SENSORS
    )
```

Ruff will ask for the long `_money(...)` lines in `STATSKONTORET_SENSORS` to be wrapped — let `uv run ruff format .` do it. Unused imports (`Ranking`, `annual_series`, …) are used by Tasks 15–19; if ruff flags them now, keep the import lines and add the sensors of Task 15 before committing, or commit Tasks 14 and 15 together.

Hook in `custom_components/edp_radar/sensor.py`: add `from .spending.sensors import async_setup_spending_sensors` to the imports and, as the last line of `async_setup_entry`, after `async_add_entities(entities)`:

```python
    async_setup_spending_sensors(entry, async_add_entities)
```

- [ ] **Step 5: Translations**

Add to the `"entity" → "sensor"` object of `custom_components/edp_radar/strings.json` (and identically to `translations/en.json`), after `"ted_data_last_updated"`:

```json
      "statskontoret_materiel_ytd": { "name": "Materiel acquisition YTD" },
      "statskontoret_materiel_latest_month": { "name": "Materiel acquisition latest month" },
      "statskontoret_materiel_ytd_change_pct": { "name": "Materiel acquisition YTD change" },
      "statskontoret_defence_ytd": { "name": "Defence appropriations YTD" },
      "statskontoret_defence_latest_month": { "name": "Defence appropriations latest month" },
      "statskontoret_defence_ytd_change_pct": { "name": "Defence appropriations YTD change" },
      "statskontoret_snapshot_text": { "name": "Spending snapshot" },
      "statskontoret_data_age": { "name": "Statskontoret data age" },
      "eurostat_defence_expenditure": { "name": "Defence expenditure" },
      "eurostat_defence_expenditure_rank": { "name": "Defence expenditure rank" },
      "eurostat_defence_investment": { "name": "Defence investment" },
      "eurostat_defence_investment_rank": { "name": "Defence investment rank" },
      "eurostat_data_age": { "name": "Eurostat data age" },
      "nato_defence_expenditure": { "name": "Defence expenditure" },
      "nato_defence_expenditure_pct_gdp": { "name": "Defence expenditure share of GDP" },
      "nato_defence_expenditure_pct_gdp_rank": { "name": "Defence expenditure share of GDP rank" },
      "nato_equipment_share_pct": { "name": "Equipment share of defence expenditure" },
      "nato_position_text": { "name": "NATO position" },
      "nato_data_age": { "name": "NATO data age" },
      "eda_defence_expenditure": { "name": "Defence expenditure" },
      "eda_defence_expenditure_rank": { "name": "Defence expenditure rank" },
      "eda_defence_investment_rank": { "name": "Defence investment rank" },
      "eda_data_age": { "name": "EDA data age" },
      "sipri_military_expenditure": { "name": "Military expenditure" },
      "sipri_military_expenditure_rank": { "name": "Military expenditure rank" },
      "sipri_military_expenditure_pct_gdp": { "name": "Military expenditure share of GDP" },
      "sipri_data_age": { "name": "SIPRI data age" }
```

and the Swedish names to `translations/sv.json` under the same keys:

```json
      "statskontoret_materiel_ytd": { "name": "Materielanskaffning hittills i år" },
      "statskontoret_materiel_latest_month": { "name": "Materielanskaffning senaste månad" },
      "statskontoret_materiel_ytd_change_pct": { "name": "Materielanskaffning förändring hittills i år" },
      "statskontoret_defence_ytd": { "name": "Försvarsanslag hittills i år" },
      "statskontoret_defence_latest_month": { "name": "Försvarsanslag senaste månad" },
      "statskontoret_defence_ytd_change_pct": { "name": "Försvarsanslag förändring hittills i år" },
      "statskontoret_snapshot_text": { "name": "Utgiftsöversikt" },
      "statskontoret_data_age": { "name": "Statskontoret dataålder" },
      "eurostat_defence_expenditure": { "name": "Försvarsutgifter" },
      "eurostat_defence_expenditure_rank": { "name": "Rangordning försvarsutgifter" },
      "eurostat_defence_investment": { "name": "Försvarsinvesteringar" },
      "eurostat_defence_investment_rank": { "name": "Rangordning försvarsinvesteringar" },
      "eurostat_data_age": { "name": "Eurostat dataålder" },
      "nato_defence_expenditure": { "name": "Försvarsutgifter" },
      "nato_defence_expenditure_pct_gdp": { "name": "Försvarsutgifter andel av BNP" },
      "nato_defence_expenditure_pct_gdp_rank": { "name": "Rangordning försvarsutgifter andel av BNP" },
      "nato_equipment_share_pct": { "name": "Materielandel av försvarsutgifter" },
      "nato_position_text": { "name": "NATO-position" },
      "nato_data_age": { "name": "NATO dataålder" },
      "eda_defence_expenditure": { "name": "Försvarsutgifter" },
      "eda_defence_expenditure_rank": { "name": "Rangordning försvarsutgifter" },
      "eda_defence_investment_rank": { "name": "Rangordning försvarsinvesteringar" },
      "eda_data_age": { "name": "EDA dataålder" },
      "sipri_military_expenditure": { "name": "Militärutgifter" },
      "sipri_military_expenditure_rank": { "name": "Rangordning militärutgifter" },
      "sipri_military_expenditure_pct_gdp": { "name": "Militärutgifter andel av BNP" },
      "sipri_data_age": { "name": "SIPRI dataålder" }
```

Match the files' existing formatting (one key per line, two-space indent); run `uv run pytest tests/test_translations.py -q` to confirm `strings.json == en.json` and the sv/en key sets match. All 27 keys go in now so the translation test stays green while Tasks 15–19 add the sensors.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_spending_sensors.py tests/test_translations.py tests/test_sensor.py -q`
Expected: `test_statskontoret_sensors` and `test_sensors_are_unknown_before_the_first_refresh` pass; `test_source_devices_and_every_sensor_exist` still fails for the keys of Tasks 15–19 (it passes at the end of Task 19). `tests/test_sensor.py` stays green untouched: its `DISABLED_BY_DEFAULT` list is keyed by the TED layer's `f"{ENTRY}_{key}"` unique ids and only iterates its own entries, so the spending diagnostics (unique ids `…_spending_…`) are asserted in `tests/test_spending_sensors.py` alone.

- [ ] **Step 7: Quality gate and commit**

```bash
uv run ruff format . && uv run pytest -q --deselect tests/test_spending_sensors.py::test_source_devices_and_every_sensor_exist && uv run ruff check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/sensors.py custom_components/edp_radar/entity.py custom_components/edp_radar/sensor.py custom_components/edp_radar/strings.json custom_components/edp_radar/translations/ tests/test_spending_sensors.py
git commit -m "feat(spending): sensor platform, source devices and Statskontoret sensors

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 15: Eurostat sensors

**Files:**
- Modify: `custom_components/edp_radar/spending/sensors.py`
- Test: `tests/test_spending_sensors.py`

**Interfaces:**
- Consumes: builders and helpers of Task 14; `annual_series`, `latest_year`, `rank`, `coverage`, `value_at`, `nominal_change_pct` (Task 11); `ranking_attrs` (Task 12).
- Produces: shared annual-source helpers `_latest(series, metric_id, unit=None)`, `_ranking(series, point)`, `_companion(series, metric_id, reference, scale)`, `_annual_value_attrs(...)`, `_rank_attrs(...)`; `EUROSTAT_SENSORS`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_spending_sensors.py`:

```python
@pytest.mark.spending_live
async def test_eurostat_sensors(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)
    await setup_spending(hass, mock_backend)

    value = get_state(hass, "eurostat_defence_expenditure")
    assert float(value.state) == pytest.approx(17196.9 * MILLION)
    assert value.attributes["unit_of_measurement"] == "EUR"
    assert value.attributes["reference_year"] == 2025
    assert value.attributes["pct_gdp"] == pytest.approx(2.9)
    assert value.attributes["nac_million"] == pytest.approx(190306.0)
    assert value.attributes["previous_year_eur"] == pytest.approx(11093.8 * MILLION)
    assert value.attributes["change_pct"] == pytest.approx(55.0, abs=0.05)
    assert value.attributes["rank"] == 4
    assert value.attributes["pct_gdp_rank"] == 4
    assert value.attributes["population"] == 22
    prov = provenance(value.attributes)
    assert prov["source"] == "Eurostat"
    assert prov["reference_label"] == "2025"
    assert prov["status"] == "actual"
    assert prov["published_at"] == "2026-04-27"

    ranking = get_state(hass, "eurostat_defence_expenditure_rank")
    assert ranking.state == "4"
    attrs = ranking.attributes
    assert attrs["population"] == 22
    assert attrs["population_total"] == 27
    assert attrs["missing"] == ["CY", "ES", "IE", "IT", "NL"]
    assert attrs["excluded_zero"] == []
    assert attrs["top"] == {"country": "DE", "eur": pytest.approx(68824.0 * MILLION)}
    assert attrs["ranking"][0]["country"] == "DE"
    assert attrs["ranking"][3] == {
        "rank": 4,
        "country": "SE",
        "eur": pytest.approx(17196.9 * MILLION),
        "pct_gdp": pytest.approx(2.9),
    }
    assert len(attrs["ranking"]) == 22
    assert [row["country"] for row in attrs["nordic"]] == ["SE", "DK", "FI"]
    assert attrs["sweden"] == {"rank": 4, "eur": pytest.approx(17196.9 * MILLION)}
    assert attrs["statuses"] == ["actual"]
    assert attrs["median_eur"] == pytest.approx(3808.3 * MILLION)
    assert provenance(attrs)["reference_label"] == "2025"

    investment = get_state(hass, "eurostat_defence_investment")
    assert float(investment.state) == pytest.approx(4864.3 * MILLION)
    assert investment.attributes["rank"] == 5
    inv_rank = get_state(hass, "eurostat_defence_investment_rank")
    assert inv_rank.state == "5"
    assert inv_rank.attributes["population"] == 27
    assert inv_rank.attributes["missing"] == []
    assert inv_rank.attributes["top"]["country"] == "PL"
```

The Eurostat "% GDP" companion appears in the expenditure ranking rows only; the investment ranking rows carry `rank`, `country`, `eur` (assert `set(inv_rank.attributes["ranking"][0]) == {"rank", "country", "eur"}`).

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_spending_sensors.py::test_eurostat_sensors -q`
Expected: FAIL — `spending sensor eurostat_defence_expenditure not registered`.

- [ ] **Step 3: Implement**

Add to `sensors.py` after the Statskontoret block (the annual helpers are shared with Tasks 16–18):

```python
# ------------------------------------------------------- annual sources


def _latest(
    series: SourceSeries, metric_id: str, unit: str | None = None
) -> SpendingDataPoint | None:
    return latest_year(series.datapoints, metric_id, FOCUS_COUNTRY, unit=unit)


def _ranking(series: SourceSeries, point: SpendingDataPoint) -> Ranking | None:
    """Rank Sweden's datapoint within its own metric, reference and unit."""
    return rank(
        series.datapoints,
        metric_id=point.metric_id,
        unit=point.unit,
        reference=point.reference,
    )


def _companion(
    series: SourceSeries, metric_id: str, reference: ReferencePeriod, scale: int
) -> Companion:
    return (
        lambda country: value_at(series.datapoints, metric_id, country, reference),
        scale,
    )


def _focus_value(
    series: SourceSeries, metric_id: str, reference: ReferencePeriod
) -> Decimal | None:
    return value_at(series.datapoints, metric_id, FOCUS_COUNTRY, reference)


def _focus_rank(
    series: SourceSeries, metric_id: str, unit: str, reference: ReferencePeriod
) -> int | None:
    ranking = rank(series.datapoints, metric_id=metric_id, unit=unit, reference=reference)
    return None if ranking is None else ranking.focus_rank


def _year_over_year(
    series: SourceSeries, point: SpendingDataPoint
) -> tuple[Decimal | None, Decimal | None]:
    """``(previous year's value, change %)`` for the focus country."""
    annual = annual_series(series.datapoints, point.metric_id, FOCUS_COUNTRY, unit=point.unit)
    previous = annual.get(point.reference.start.year - 1)
    if previous is None:
        return None, None
    return previous.value, nominal_change_pct(point.value, previous.value)


def _annual_value(metric_id: str, scale: int = MILLION) -> ValueFn:
    return lambda series, today: (
        scaled(p.value, scale) if (p := _latest(series, metric_id)) else None
    )


def _rank_value(metric_id: str) -> ValueFn:
    def value(series: SourceSeries, today: date) -> StateType:
        point = _latest(series, metric_id)
        ranking = _ranking(series, point) if point else None
        return None if ranking is None else ranking.focus_rank

    return value


def _rank_attrs(
    metric_id: str,
    value_key: str,
    scale: int,
    companions: dict[str, tuple[str, int]] | None = None,
) -> AttributesFn:
    """Ranking attributes; ``companions`` maps attribute name → (metric id, scale)."""

    def attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
        point = _latest(series, metric_id)
        ranking = _ranking(series, point) if point else None
        if point is None or ranking is None:
            return {}
        cov = coverage(series.datapoints, metric_id, point.reference, unit=point.unit)
        out = _provenance(point, series, today)
        out.update(
            ranking_attrs(
                ranking,
                cov,
                value_key=value_key,
                scale=scale,
                companions={
                    name: _companion(series, other, point.reference, other_scale)
                    for name, (other, other_scale) in (companions or {}).items()
                },
            )
        )
        return out

    return attrs


# ---------------------------------------------------------------- Eurostat

EU_EXPENDITURE = "defence_expenditure"
EU_INVESTMENT = "defence_investment"


def _eurostat_value_attrs(metric_id: str) -> AttributesFn:
    def attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
        point = _latest(series, metric_id)
        if point is None:
            return {}
        reference = point.reference
        previous, change = _year_over_year(series, point)
        ranking = _ranking(series, point)
        out = _provenance(point, series, today)
        out.update(
            {
                "reference_year": reference.start.year,
                "pct_gdp": _pct_value(_focus_value(series, f"{metric_id}_pct_gdp", reference)),
                "nac_million": scaled(_focus_value(series, f"{metric_id}_nac", reference)),
                "previous_year_eur": scaled(previous, MILLION),
                "change_pct": _pct_value(change),
                "rank": None if ranking is None else ranking.focus_rank,
                "pct_gdp_rank": _focus_rank(series, f"{metric_id}_pct_gdp", "PCT_GDP", reference),
                "population": None if ranking is None else ranking.population,
            }
        )
        return out

    return attrs


EUROSTAT_SENSORS: tuple[SpendingSensorEntityDescription, ...] = (
    _money("eurostat_defence_expenditure", EUROSTAT, "EUR", _annual_value(EU_EXPENDITURE), _eurostat_value_attrs(EU_EXPENDITURE)),
    _rank("eurostat_defence_expenditure_rank", EUROSTAT, _rank_value(EU_EXPENDITURE), _rank_attrs(EU_EXPENDITURE, "eur", MILLION, {"pct_gdp": (f"{EU_EXPENDITURE}_pct_gdp", 1)})),
    _money("eurostat_defence_investment", EUROSTAT, "EUR", _annual_value(EU_INVESTMENT), _eurostat_value_attrs(EU_INVESTMENT)),
    _rank("eurostat_defence_investment_rank", EUROSTAT, _rank_value(EU_INVESTMENT), _rank_attrs(EU_INVESTMENT, "eur", MILLION)),
)
```

and extend the catalogue: `SPENDING_SENSORS = (*STATSKONTORET_SENSORS, *EUROSTAT_SENSORS)`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_spending_sensors.py -q --deselect tests/test_spending_sensors.py::test_source_devices_and_every_sensor_exist`
Expected: pass. If `median_eur` differs, the fixture median over 22 countries is `3808.3` MSEK-equivalent (mean of the 11th and 12th values); recompute from the fixture if the number was trimmed differently.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run ruff format . && uv run pytest -q --deselect tests/test_spending_sensors.py::test_source_devices_and_every_sensor_exist && uv run ruff check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/sensors.py tests/test_spending_sensors.py
git commit -m "feat(spending): Eurostat sensors with coverage-aware rankings (S37)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 16: NATO sensors

**Files:**
- Modify: `custom_components/edp_radar/spending/sensors.py`
- Test: `tests/test_spending_sensors.py`

**Interfaces:**
- Consumes: annual helpers (Task 15), `nato_position_text` (Task 13), `price_base_year` (Task 12).
- Produces: `NATO_SENSORS`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_spending_sensors.py`:

```python
@pytest.mark.spending_live
async def test_nato_sensors(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)
    await setup_spending(hass, mock_backend)

    value = get_state(hass, "nato_defence_expenditure")
    assert float(value.state) == pytest.approx(24186 * MILLION)
    assert value.attributes["unit_of_measurement"] == "USD"
    assert value.attributes["reference_year"] == 2026
    assert value.attributes["nac_million"] == pytest.approx(217902)
    assert value.attributes["usd_constant"] == pytest.approx(21538 * MILLION)
    assert value.attributes["price_base_year"] == 2021
    assert value.attributes["pct_gdp"] == pytest.approx(3.22)
    assert value.attributes["latest_actual"] == {"year": 2024, "usd": pytest.approx(13300 * MILLION)}
    assert value.attributes["previous_year_usd"] == pytest.approx(19122 * MILLION)
    assert value.attributes["change_pct"] == pytest.approx(26.5, abs=0.05)
    assert value.attributes["rank"] == 11
    assert value.attributes["population"] == 31
    prov = provenance(value.attributes)
    assert prov["status"] == "estimate"
    assert prov["reference_period_complete"] is False
    assert prov["reference_age_days"] is None
    assert prov["published_at"] == "2026-07-10"

    share = get_state(hass, "nato_defence_expenditure_pct_gdp")
    assert float(share.state) == pytest.approx(3.22)
    assert share.attributes["rank"] == 7
    assert share.attributes["population"] == 31
    assert share.attributes["alliance_median_pct_gdp"] == pytest.approx(2.22)

    ranking = get_state(hass, "nato_defence_expenditure_pct_gdp_rank")
    assert ranking.state == "7"
    assert ranking.attributes["top"] == {"country": "LT", "pct_gdp": pytest.approx(5.33)}
    assert ranking.attributes["ranking"][6] == {
        "rank": 7,
        "country": "SE",
        "pct_gdp": pytest.approx(3.22),
        "usd": pytest.approx(24186 * MILLION),
    }
    assert [row["country"] for row in ranking.attributes["nordic"]] == ["DK", "SE", "NO", "FI"]
    assert ranking.attributes["statuses"] == ["estimate"]
    assert ranking.attributes["population_total"] == 31

    equipment = get_state(hass, "nato_equipment_share_pct")
    assert float(equipment.state) == pytest.approx(25.41)
    assert equipment.attributes["equipment_usd"] == pytest.approx(6145.6626 * MILLION)
    assert equipment.attributes["rank"] == 25

    text = get_state(hass, "nato_position_text")
    assert text.state == "SE #7 of 31 · USD 24.2bn · 3.2% GDP · NATO 2026 estimate"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_spending_sensors.py::test_nato_sensors -q`
Expected: FAIL — `nato_defence_expenditure not registered`.

- [ ] **Step 3: Implement**

Add to `sensors.py` after the Eurostat block:

```python
# -------------------------------------------------------------------- NATO

NATO_USD = "defence_expenditure_usd_current"
NATO_NAC = "defence_expenditure_nac"
NATO_USD_CONSTANT = "defence_expenditure_usd_constant"
NATO_PCT_GDP = "defence_expenditure_pct_gdp"
NATO_EQUIPMENT_SHARE = "equipment_share_pct"
NATO_EQUIPMENT_USD = "equipment_expenditure_usd_current"


def _latest_actual(series: SourceSeries, metric_id: str) -> SpendingDataPoint | None:
    annual = annual_series(series.datapoints, metric_id, FOCUS_COUNTRY)
    actual = [p for p in annual.values() if p.status is DatapointStatus.ACTUAL]
    return max(actual, key=lambda p: p.reference.start) if actual else None


def _nato_value_attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
    point = _latest(series, NATO_USD)
    if point is None:
        return {}
    reference = point.reference
    previous, change = _year_over_year(series, point)
    ranking = _ranking(series, point)
    constant = latest_year(series.datapoints, NATO_USD_CONSTANT, FOCUS_COUNTRY)
    constant_value = (
        constant.value
        if constant is not None and constant.reference == reference
        else None
    )
    actual = _latest_actual(series, NATO_USD)
    out = _provenance(point, series, today)
    out.update(
        {
            "reference_year": reference.start.year,
            "nac_million": scaled(_focus_value(series, NATO_NAC, reference)),
            "usd_constant": scaled(constant_value, MILLION),
            "price_base_year": price_base_year(constant.unit) if constant else None,
            "pct_gdp": _pct_value(_focus_value(series, NATO_PCT_GDP, reference)),
            "latest_actual": None
            if actual is None
            else {"year": actual.reference.start.year, "usd": scaled(actual.value, MILLION)},
            "previous_year_usd": scaled(previous, MILLION),
            "change_pct": _pct_value(change),
            "rank": None if ranking is None else ranking.focus_rank,
            "population": None if ranking is None else ranking.population,
        }
    )
    return out


def _nato_pct_attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
    point = _latest(series, NATO_PCT_GDP)
    ranking = _ranking(series, point) if point else None
    if point is None or ranking is None:
        return {}
    out = _provenance(point, series, today)
    out.update(
        {
            "reference_year": point.reference.start.year,
            "rank": ranking.focus_rank,
            "population": ranking.population,
            "alliance_median_pct_gdp": _pct_value(ranking.median),
        }
    )
    return out


def _nato_equipment_attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
    point = _latest(series, NATO_EQUIPMENT_SHARE)
    ranking = _ranking(series, point) if point else None
    if point is None or ranking is None:
        return {}
    out = _provenance(point, series, today)
    out.update(
        {
            "reference_year": point.reference.start.year,
            "equipment_usd": scaled(
                _focus_value(series, NATO_EQUIPMENT_USD, point.reference), MILLION
            ),
            "rank": ranking.focus_rank,
            "population": ranking.population,
        }
    )
    return out


def _nato_position(series: SourceSeries, today: date) -> StateType:
    pct = _latest(series, NATO_PCT_GDP)
    ranking = _ranking(series, pct) if pct else None
    if pct is None or ranking is None:
        return None
    usd = _focus_value(series, NATO_USD, pct.reference)
    return nato_position_text(
        ranking,
        None if usd is None else usd * MILLION,
        pct.value,
        pct.reference.start.year,
        pct.status,
    )


NATO_SENSORS: tuple[SpendingSensorEntityDescription, ...] = (
    _money("nato_defence_expenditure", NATO, "USD", _annual_value(NATO_USD), _nato_value_attrs),
    _pct("nato_defence_expenditure_pct_gdp", NATO, _annual_value(NATO_PCT_GDP, 1), _nato_pct_attrs),
    _rank("nato_defence_expenditure_pct_gdp_rank", NATO, _rank_value(NATO_PCT_GDP), _rank_attrs(NATO_PCT_GDP, "pct_gdp", 1, {"usd": (NATO_USD, MILLION)})),
    _pct("nato_equipment_share_pct", NATO, _annual_value(NATO_EQUIPMENT_SHARE, 1), _nato_equipment_attrs),
    _text("nato_position_text", NATO, _nato_position),
)
```

Extend the catalogue with `*NATO_SENSORS`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_spending_sensors.py -q --deselect tests/test_spending_sensors.py::test_source_devices_and_every_sensor_exist`
Expected: pass.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run ruff format . && uv run pytest -q --deselect tests/test_spending_sensors.py::test_source_devices_and_every_sensor_exist && uv run ruff check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/sensors.py tests/test_spending_sensors.py
git commit -m "feat(spending): NATO sensors with estimate labelling (S34)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 17: EDA sensors

**Files:**
- Modify: `custom_components/edp_radar/spending/sensors.py`
- Test: `tests/test_spending_sensors.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_spending_sensors.py`:

```python
@pytest.mark.spending_live
async def test_eda_sensors(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)
    await setup_spending(hass, mock_backend)

    value = get_state(hass, "eda_defence_expenditure")
    assert float(value.state) == pytest.approx(14788.962566848055 * MILLION)
    assert value.attributes["reference_year"] == 2025
    assert value.attributes["pct_gdp"] == pytest.approx(2.488, abs=0.001)
    assert value.attributes["pct_government"] == pytest.approx(5.697, abs=0.001)
    assert value.attributes["per_capita_eur"] == pytest.approx(1386.96, abs=0.01)
    assert value.attributes["investment_eur"] == pytest.approx(4227.901618627983 * MILLION)
    assert value.attributes["previous_year_eur"] is not None  # 2024 workbook (Task 9)
    assert value.attributes["rank"] == 7
    assert value.attributes["population"] == 27
    assert provenance(value.attributes)["published_at"] == "2026-09-04"

    ranking = get_state(hass, "eda_defence_expenditure_rank")
    assert ranking.state == "7"
    assert ranking.attributes["top"]["country"] == "DE"
    assert set(ranking.attributes["ranking"][6]) == {"rank", "country", "eur", "pct_gdp", "per_capita_eur"}
    assert ranking.attributes["ranking"][6]["country"] == "SE"
    assert [row["country"] for row in ranking.attributes["nordic"]] == ["SE", "DK", "FI"]
    assert ranking.attributes["statuses"] == ["actual", "estimate"]
    assert ranking.attributes["population_total"] == 27

    investment = get_state(hass, "eda_defence_investment_rank")
    assert investment.state == "7"
    assert investment.attributes["sweden"] == {"rank": 7, "eur": pytest.approx(4227.901618627983 * MILLION)}
    assert set(investment.attributes["ranking"][0]) == {"rank", "country", "eur"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_spending_sensors.py::test_eda_sensors -q`
Expected: FAIL — not registered.

- [ ] **Step 3: Implement**

Add to `sensors.py` after the NATO block:

```python
# --------------------------------------------------------------------- EDA

EDA_EXPENDITURE = "defence_expenditure"
EDA_INVESTMENT = "defence_investment"
EDA_PCT_GDP = "defence_expenditure_pct_gdp"
EDA_PCT_GOVERNMENT = "defence_expenditure_pct_government"
EDA_PER_CAPITA = "defence_expenditure_per_capita"


def _eda_value_attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
    point = _latest(series, EDA_EXPENDITURE)
    if point is None:
        return {}
    reference = point.reference
    previous, change = _year_over_year(series, point)
    ranking = _ranking(series, point)
    out = _provenance(point, series, today)
    out.update(
        {
            "reference_year": reference.start.year,
            "pct_gdp": _pct_value(_focus_value(series, EDA_PCT_GDP, reference)),
            "pct_government": _pct_value(_focus_value(series, EDA_PCT_GOVERNMENT, reference)),
            "per_capita_eur": scaled(_focus_value(series, EDA_PER_CAPITA, reference)),
            "investment_eur": scaled(_focus_value(series, EDA_INVESTMENT, reference), MILLION),
            "previous_year_eur": scaled(previous, MILLION),
            "change_pct": _pct_value(change),
            "rank": None if ranking is None else ranking.focus_rank,
            "population": None if ranking is None else ranking.population,
        }
    )
    return out


EDA_SENSORS: tuple[SpendingSensorEntityDescription, ...] = (
    _money("eda_defence_expenditure", EDA, "EUR", _annual_value(EDA_EXPENDITURE), _eda_value_attrs),
    _rank("eda_defence_expenditure_rank", EDA, _rank_value(EDA_EXPENDITURE), _rank_attrs(EDA_EXPENDITURE, "eur", MILLION, {"pct_gdp": (EDA_PCT_GDP, 1), "per_capita_eur": (EDA_PER_CAPITA, 1)})),
    _rank("eda_defence_investment_rank", EDA, _rank_value(EDA_INVESTMENT), _rank_attrs(EDA_INVESTMENT, "eur", MILLION)),
)
```

Extend the catalogue with `*EDA_SENSORS`.

A subtlety: the EDA `Billions` sheet stores `defence_expenditure` for 2005–2021 with the same unit; `_latest` picks 2025 from the Member States sheets because `latest_year` takes the maximum year. `_year_over_year` finds 2024 from the 2024 workbook fixture added in Task 9.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_spending_sensors.py -q --deselect tests/test_spending_sensors.py::test_source_devices_and_every_sensor_exist`
Expected: pass.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run ruff format . && uv run pytest -q --deselect tests/test_spending_sensors.py::test_source_devices_and_every_sensor_exist && uv run ruff check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/sensors.py tests/test_spending_sensors.py
git commit -m "feat(spending): EDA sensors

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 18: SIPRI sensors

**Files:**
- Modify: `custom_components/edp_radar/spending/sensors.py`
- Test: `tests/test_spending_sensors.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_spending_sensors.py`:

```python
@pytest.mark.spending_live
async def test_sipri_sensors(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)
    await setup_spending(hass, mock_backend)

    value = get_state(hass, "sipri_military_expenditure")
    assert float(value.state) == pytest.approx(14954.07135864315 * MILLION)
    assert value.attributes["unit_of_measurement"] == "USD"
    assert value.attributes["reference_year"] == 2025
    assert value.attributes["price_base_year"] == 2024
    assert value.attributes["flags"] == []
    assert value.attributes["pct_gdp"] == pytest.approx(2.471, abs=0.001)
    assert value.attributes["previous_year_usd"] == pytest.approx(12046.97008544414 * MILLION)
    assert value.attributes["change_pct"] == pytest.approx(24.1, abs=0.05)
    assert value.attributes["value_10y_ago_usd"] == pytest.approx(5696.73409992092 * MILLION)
    assert value.attributes["change_10y_pct"] == pytest.approx(162.5, abs=0.1)
    series = value.attributes["annual_series"]
    assert series[0] == {"year": 1990, "usd": pytest.approx(6900.298751312625 * MILLION), "status": "actual"}
    assert series[-1]["year"] == 2025 and len(series) == 36
    assert value.attributes["rank"] == 14
    assert value.attributes["population"] == 54  # 55 countries report 2025, minus Iceland's zero
    assert provenance(value.attributes)["published_at"] == "2026-04-27"

    ranking = get_state(hass, "sipri_military_expenditure_rank")
    assert ranking.state == "14"
    assert ranking.attributes["excluded_zero"] == ["IS"]
    assert ranking.attributes["top"]["country"] == "RU"
    assert len(ranking.attributes["ranking"]) == 40
    assert [row["country"] for row in ranking.attributes["nordic"]] == ["NO", "SE", "DK", "FI"]
    assert ranking.attributes["ranking"][13] == {
        "rank": 14,
        "country": "SE",
        "usd": pytest.approx(14954.07135864315 * MILLION),
        "pct_gdp": pytest.approx(2.471, abs=0.001),
    }
    assert set(ranking.attributes["statuses"]) == {"actual", "budget", "estimate"}
    assert len(str(ranking.attributes)) < 16_000

    pct = get_state(hass, "sipri_military_expenditure_pct_gdp")
    assert float(pct.state) == pytest.approx(2.471, abs=0.001)
    assert pct.attributes["rank"] == 21
    assert pct.attributes["population"] == 54
```

The fixture holds 60 countries after Task 8, of which 55 report a 2025 value (Libya stops at 2023); S35 removes Iceland's zero, hence 54. The `annual_series` has 36 rows (1990–2025).

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_spending_sensors.py::test_sipri_sensors -q`
Expected: FAIL — not registered.

- [ ] **Step 3: Implement**

Add to `sensors.py` after the EDA block:

```python
# ------------------------------------------------------------------- SIPRI

SIPRI_CONSTANT = "military_expenditure_usd_constant"
SIPRI_PCT_GDP = "military_expenditure_pct_gdp"
TEN_YEARS = 10


def _sipri_value_attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
    point = _latest(series, SIPRI_CONSTANT)
    if point is None:
        return {}
    reference = point.reference
    year = reference.start.year
    annual = annual_series(series.datapoints, SIPRI_CONSTANT, FOCUS_COUNTRY, unit=point.unit)
    previous, change = _year_over_year(series, point)
    decade = change_over_years(annual, year, TEN_YEARS)
    ranking = _ranking(series, point)
    out = _provenance(point, series, today)
    out.update(
        {
            "reference_year": year,
            "price_base_year": price_base_year(point.unit),
            "flags": list(point.flags),
            "pct_gdp": _pct_value(_focus_value(series, SIPRI_PCT_GDP, reference)),
            "previous_year_usd": scaled(previous, MILLION),
            "change_pct": _pct_value(change),
            "value_10y_ago_usd": None if decade is None else scaled(decade[0], MILLION),
            "change_10y_pct": None if decade is None else _pct_value(decade[1]),
            "annual_series": annual_series_attrs(annual, "usd", MILLION),
            "rank": None if ranking is None else ranking.focus_rank,
            "population": None if ranking is None else ranking.population,
        }
    )
    return out


def _sipri_pct_attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
    point = _latest(series, SIPRI_PCT_GDP)
    ranking = _ranking(series, point) if point else None
    if point is None or ranking is None:
        return {}
    out = _provenance(point, series, today)
    out.update(
        {
            "reference_year": point.reference.start.year,
            "rank": ranking.focus_rank,
            "population": ranking.population,
        }
    )
    return out


SIPRI_SENSORS: tuple[SpendingSensorEntityDescription, ...] = (
    _money("sipri_military_expenditure", SIPRI, "USD", _annual_value(SIPRI_CONSTANT), _sipri_value_attrs),
    _rank("sipri_military_expenditure_rank", SIPRI, _rank_value(SIPRI_CONSTANT), _rank_attrs(SIPRI_CONSTANT, "usd", MILLION, {"pct_gdp": (SIPRI_PCT_GDP, 1)})),
    _pct("sipri_military_expenditure_pct_gdp", SIPRI, _annual_value(SIPRI_PCT_GDP, 1), _sipri_pct_attrs),
)
```

Extend the catalogue with `*SIPRI_SENSORS`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_spending_sensors.py -q --deselect tests/test_spending_sensors.py::test_source_devices_and_every_sensor_exist`
Expected: pass.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run ruff format . && uv run pytest -q --deselect tests/test_spending_sensors.py::test_source_devices_and_every_sensor_exist && uv run ruff check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/sensors.py tests/test_spending_sensors.py
git commit -m "feat(spending): SIPRI sensors with zero-excluded world ranking (S35, S36)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 19: Data-age diagnostics sensors and the complete catalogue

**Files:**
- Modify: `custom_components/edp_radar/spending/sensors.py`
- Test: `tests/test_spending_sensors.py`

**Interfaces:**
- Consumes: `freshness_state`, `next_release_deadline`, `publication_age_days`, `reference_age_days`, `reference_overdue` (Task 4).
- Produces: `<source>_data_age` for all five sources; `SPENDING_SENSORS` complete (27).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_spending_sensors.py`:

```python
@pytest.mark.spending_live
async def test_data_age_sensors_are_diagnostic_and_survive_source_failures(
    hass: HomeAssistant, mock_backend: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(NOW)
    registry = er.async_get(hass)
    # Enable the five diagnostics before setup so they get states.
    await setup_spending(hass, mock_backend)
    for key in DATA_AGE_KEYS:
        registry.async_update_entity(entity_id(hass, key), disabled_by=None)
    await hass.config_entries.async_reload(ENTRY)
    await hass.async_block_till_done(wait_background_tasks=True)

    age = get_state(hass, "statskontoret_data_age")
    assert age.state == "19"
    assert age.attributes["unit_of_measurement"] == "d"
    assert age.attributes["freshness_state"] == "current"
    assert age.attributes["reference_overdue"] is False
    assert age.attributes["next_release_expected"] == "2026-09-30"
    assert age.attributes["latest_reference_end"] == "2026-07-31"
    assert age.attributes["reference_age_days"] == 43
    assert age.attributes["published_at"] == "2026-08-24"
    assert age.attributes["release_id"] == "2026-07-definitiv-2026-08-24"
    assert age.attributes["health_state"] == "available"
    assert age.attributes["last_error"] is None
    assert age.attributes["datapoints"] == 57
    assert age.attributes["revisions"] == 0

    nato = get_state(hass, "nato_data_age")
    assert nato.state == "64"
    assert nato.attributes["latest_reference_end"] == "2026-12-31"
    assert nato.attributes["reference_age_days"] == -110  # 2026-09-12 → 2026-12-31

    # A source that fails on the next tick keeps its values; the age sensor says why.
    # The mocker answers with the first registration per URL, so clear and
    # register the failure before the healthy sources.
    from custom_components.edp_radar.spending.providers.eurostat import API_URL

    mock_backend.clear_requests()
    mock_backend.get(API_URL, status=503)
    mock_spending_sources(mock_backend)
    entry = hass.config_entries.async_get_entry(ENTRY)
    assert entry is not None
    await entry.runtime_data.spending.async_refresh_source("eurostat")
    await hass.async_block_till_done()
    assert float(get_state(hass, "eurostat_defence_expenditure").state) == pytest.approx(17196.9 * MILLION)
    failed = get_state(hass, "eurostat_data_age")
    assert failed.attributes["health_state"] == "stale_but_cached"
    assert "HTTP 503" in failed.attributes["last_error"]
```

`clear_requests()` also drops the TED/ECB handlers of the `mock_backend` fixture; that is fine here because only the Eurostat provider is refreshed afterwards.

`tests/test_sensor.py` is not touched: its `DISABLED_BY_DEFAULT` loop only visits the TED layer's own keys.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_spending_sensors.py -q`
Expected: the new test fails (`statskontoret_data_age not registered`); `test_source_devices_and_every_sensor_exist` still fails on the data-age keys.

- [ ] **Step 3: Implement**

Add to `sensors.py` imports: `from .freshness import freshness_state, next_release_deadline, publication_age_days, reference_age_days, reference_overdue` and `from .attrs import iso` (extend the existing `.attrs` import). Then after the SIPRI block:

```python
# ---------------------------------------------------------------- data age


def _latest_reference_end(series: SourceSeries) -> date | None:
    ends = [p.reference.end for p in series.datapoints]
    return max(ends) if ends else None


def _published(series: SourceSeries) -> date | None:
    return series.release.published_at if series.release else None


def _age_value(series: SourceSeries, today: date) -> StateType:
    return publication_age_days(_published(series), today)


def _age_attrs(source_id: str) -> AttributesFn:
    spec = source_spec(source_id)

    def attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
        latest = _latest_reference_end(series)
        published = _published(series)
        health = series.health
        return {
            "freshness_state": freshness_state(spec, latest, published, today).value,
            "reference_overdue": reference_overdue(spec, latest, today),
            "next_release_expected": iso(next_release_deadline(spec, latest, published)),
            "latest_reference_end": iso(latest),
            "reference_age_days": None if latest is None else reference_age_days(latest, today),
            "published_at": iso(published),
            "retrieved_at": iso(series.retrieved_at),
            "release_id": series.release.release_id if series.release else None,
            "health_state": health.state.value,
            "last_check_at": iso(health.last_check_at),
            "last_success_at": iso(health.last_success_at),
            "last_error": health.last_error,
            "datapoints": len(series.datapoints),
            "revisions": len(series.revisions),
        }

    return attrs


DATA_AGE_SENSORS: tuple[SpendingSensorEntityDescription, ...] = tuple(
    _age(f"{source_id}_data_age", source_id, _age_value, _age_attrs(source_id))
    for source_id in (STATSKONTORET, EUROSTAT, NATO, EDA, SIPRI)
)
```

Final catalogue:

```python
SPENDING_SENSORS: tuple[SpendingSensorEntityDescription, ...] = (
    *STATSKONTORET_SENSORS,
    *EUROSTAT_SENSORS,
    *NATO_SENSORS,
    *EDA_SENSORS,
    *SIPRI_SENSORS,
    *DATA_AGE_SENSORS,
)
```

Move the `SPENDING_SENSORS` definition below `DATA_AGE_SENSORS` (it must come after every block it spreads). `assert len(SPENDING_SENSORS) == 27` belongs in the test file, not the module: add `from custom_components.edp_radar.spending.sensors import SPENDING_SENSORS` and `def test_catalogue_has_27_sensors(): assert len(SPENDING_SENSORS) == 27 and len({d.key for d in SPENDING_SENSORS}) == 27` to `tests/test_spending_sensors.py`.

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest -q`
Expected: all pass, including `test_source_devices_and_every_sensor_exist` and `tests/test_sensor.py`.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run ruff format . && uv run pytest -q && uv run ruff check . && uv run mypy custom_components
git add custom_components/edp_radar/spending/sensors.py tests/test_spending_sensors.py
git commit -m "feat(spending): per-source data-age diagnostics complete the 27 sensors

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Part D — documentation, version, live check

### Task 20: README, dashboard example, addendum §7.4, NEXT-SESSION, version 0.3.0

**Files:**
- Modify: `README.md`, `docs/dashboard-example.yaml`, `docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md`, `docs/superpowers/NEXT-SESSION.md`, `custom_components/edp_radar/manifest.json`
- Test: none new — `manifest.json` is validated by the Home Assistant loader in every `tests/test_init.py` setup.

- [ ] **Step 1: README**

Replace the section `## Defence spending data layer (Phase 3, data only)` (one paragraph) with a `## Defence spending` section placed before `## Dashboard examples`, in the style of the `### My Country: …` subsections:

````markdown
## Defence spending

Version 0.3.0 adds five devices that read official spending statistics —
one device per source, because the sources define "defence expenditure"
differently and are never ranked against each other. Sweden is the focus
country of every sensor. Every value sensor carries the same provenance
attributes: `source`, `source_id`, `source_url`, `reference_label`,
`reference_start`, `reference_end`, `reference_period_complete`, `status`
(`actual`, `preliminary`, `provisional`, `estimate`, `projection`, `budget`),
`published_at`, `publication_age_days`, `reference_age_days` (empty while the
reference year is still running), `retrieved_at`, `release_id` and
`unit_definition`. Money is exposed in whole currency units of the source
(`SEK`, `EUR`, `USD`); nothing is converted.

Ranking sensors show Sweden's rank as the state and expose `ranking` (at most
40 rows, Sweden always included), `population` (countries ranked),
`population_total` (countries the source reports at all), `missing`,
`excluded_zero` (a true zero such as Iceland's is not a rank), `top`,
`median_*`, `nordic` with `nordic_median_*`, `sweden` and `statuses`.

Sources refresh on their own cadence — Statskontoret and Eurostat daily,
NATO, EDA and SIPRI weekly — inside a 6-hour tick; a source that fails is
retried at the next tick and its sensors keep the last stored values.

### Statskontoret

Monthly Swedish budget outturn (SEK) from the open-data page: appropriation
6:1:3 *Anskaffning av materiel och anläggningar* and all defence
appropriations 6:1:1–6:1:14. `Materiel acquisition YTD` and
`Defence appropriations YTD` sum January to the latest month and carry
`monthly_current_year` / `monthly_previous_year` for a month-by-month
chart; `… latest month` and `… YTD change` give the newest month and the
year-on-year change. December of the previous year stays `preliminary`
until Statskontoret publishes the definitive December file (late March).
`Spending snapshot` is a one-line text.

### Eurostat

`gov_ev` general government defence expenditure and investment (EUR,
ESA 2010) for EU member states. The latest year usually has fewer reporters
than the year before; the rank sensors say how many (`population` of
`population_total`, with `missing`).

### NATO

Defence expenditure at current prices (USD), share of GDP and the equipment
share, for all 31 allies; the newest year is an estimate and the sensors say
so (`status: estimate`, `reference_period_complete: false`,
`latest_actual`). `NATO position` is a one-line text.

### EDA

Total defence expenditure and defence investment (EUR) at member-state
level from the annual Defence Data workbooks (2022 onwards); equipment
procurement is not exposed because EDA stopped publishing it per country
after 2021.

### SIPRI

Military expenditure at constant prices (USD, base year in
`price_base_year`) and share of GDP, stored from 1990 (`annual_series`),
with a world ranking (top 40 plus Sweden) and a ten-year change.

### Data age

Each device has a default-disabled diagnostic `… data age` sensor: days
since the source's publication, with `freshness_state` (`current`,
`expected`, `late`, `unknown`), `reference_overdue`, `next_release_expected`,
the provider's health and its last error.
````

Update `## What you get` to mention the spending devices, and any entity count in the README (`grep -n "sensors" README.md`).

- [ ] **Step 2: Dashboard example**

Append a view to `docs/dashboard-example.yaml` after the existing Phase 2 view (keep the file's comment style):

```yaml
  # Phase 3: Sweden's defence spending, one line per source (plan §77).
  - title: Spending
    path: spending
    cards:
      - type: entities
        title: Sweden — defence spending
        entities:
          - entity: sensor.statskontoret_materiel_acquisition_ytd
            name: Materiel outturn YTD (Statskontoret, actual)
          - entity: sensor.statskontoret_materiel_acquisition_ytd_change
            name: … change vs previous year
          - entity: sensor.my_country_sweden_awarded_value_12_m
            name: Awarded contract value 12 m (TED)
          - entity: sensor.eurostat_defence_expenditure
            name: Defence expenditure (Eurostat)
          - entity: sensor.eurostat_defence_expenditure_rank
            name: … rank among reporting EU states
          - entity: sensor.eda_defence_expenditure
            name: Defence expenditure (EDA)
          - entity: sensor.nato_defence_expenditure_share_of_gdp
            name: Share of GDP (NATO, estimate)
          - entity: sensor.nato_defence_expenditure_share_of_gdp_rank
            name: … rank among allies
          - entity: sensor.sipri_military_expenditure
            name: Military expenditure (SIPRI, constant prices)
      - type: markdown
        title: Snapshot
        content: >-
          {{ states('sensor.statskontoret_spending_snapshot') }}

          {{ states('sensor.nato_nato_position') }}
      - type: history-graph
        title: Materiel acquisition, latest month
        hours_to_show: 8760
        entities:
          - sensor.statskontoret_materiel_acquisition_latest_month
```

Verify each entity id against the registry output of Task 21 and correct any that differ (Home Assistant slugifies `has_entity_name` names as `<device>_<name>`).

- [ ] **Step 3: Addendum §7.4 and NEXT-SESSION**

Append to `docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md` a `### 7.4 Phase 3 Plan 2 — sensors (2026-09-14)` section: one paragraph pointing at the spec file, then `S30`–`S44` copied verbatim from spec §2, then a line "S26 → S38, S27 → S39, S28 → S40, S29 → S41 (implemented)". Update §7's opening paragraph: "Devices and sensors (plan §72–79) are specified in §7.4."

Rewrite `docs/superpowers/NEXT-SESSION.md` "Läge" to 2026-09-14: Plan 2 implemented (27 sensors, five devices, 0.3.0), the data-layer fixes done, quality gate count updated; "Nästa steg": the Phase 2 owner decisions (consumables domain cap, Infrastructure category) and GitHub workflows/issue templates now that the repository goes public; remove the "Småsaker" and "Ägarbeslut S26/S27" sections (done); keep "Så här arbetar du".

- [ ] **Step 4: Version**

`custom_components/edp_radar/manifest.json`: `"version": "0.3.0"`.

- [ ] **Step 5: Quality gate and commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components
git add README.md docs/dashboard-example.yaml docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md docs/superpowers/NEXT-SESSION.md custom_components/edp_radar/manifest.json
git commit -m "docs: defence spending devices, dashboard view, addendum §7.4; version 0.3.0

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

### Task 21: Live check in the dev container

**Files:** none (verification only; fix-ups become their own commits).

- [ ] **Step 1: Restart the dev container on the new code**

```bash
docker compose -f /Users/mattias/source/ha-edp-radar/docker-compose.yml restart homeassistant
```

(`docker-compose.yml` bind-mounts `./custom_components` into the container, so a restart picks up the new code; `dev/ha.sh restart` does the same with the port checks.) Wait until `dev/config/home-assistant.log` shows `Finished fetching edp_radar_spending data` after the restart:

```bash
sleep 90; grep -E 'edp_radar_spending|edp_radar.*(ERROR|WARNING|Traceback)' /Users/mattias/source/ha-edp-radar/dev/config/home-assistant.log | tail -20
```

Expected: one `Finished fetching edp_radar_spending data … (success: True)` line after the restart timestamp, no `ERROR`/`Traceback` lines mentioning `edp_radar`. (The `SyncWorker` "custom integration" warning is normal.)

- [ ] **Step 2: Read the entities through the REST API**

Read `HA_PORT`, `HA_USER`, `HA_PASSWORD` from `/Users/mattias/source/ha-edp-radar/.env` (never print the password). Create a long-lived token in the dev UI once if `dev/config/.token` does not exist (Profile → Security → Long-lived access tokens) and store it in `dev/config/.token` (git-ignored). Then:

```bash
TOKEN=$(cat /Users/mattias/source/ha-edp-radar/dev/config/.token); PORT=$(grep '^HA_PORT=' /Users/mattias/source/ha-edp-radar/.env | cut -d= -f2)
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:$PORT/api/states" \
  | python3 -c 'import json,sys; [print(s["entity_id"], "=", s["state"], s["attributes"].get("unit_of_measurement",""), "|", s["attributes"].get("reference_label",""), s["attributes"].get("status","")) for s in json.load(sys.stdin) if s["entity_id"].startswith(("sensor.statskontoret_","sensor.eurostat_","sensor.nato_","sensor.eda_","sensor.sipri_"))]'
```

Expected: 22 non-diagnostic sensors with numeric or text states (no `unknown`, no `unavailable`), `reference_label` and `status` filled; the Statskontoret YTD shows the live month (August 2026 if Statskontoret has published it by now — the test fixtures stop at July). Copy the entity ids into `docs/dashboard-example.yaml` if any differ from Task 20's guesses and commit that as `docs: dashboard entity ids from the live registry`.

- [ ] **Step 3: Enable one data-age sensor and check it**

In the dev UI enable `sensor.statskontoret_statskontoret_data_age` (Settings → Devices → Statskontoret → +1 entity not shown), wait for the state, and confirm `freshness_state`, `next_release_expected` and `health_state: available` in the attributes.

- [ ] **Step 4: Report**

Say what the live check showed — entity count, the reference labels per source, any warning in the log — before calling the plan done. If anything failed, fix it in a commit named for the failure and repeat Steps 1–3.

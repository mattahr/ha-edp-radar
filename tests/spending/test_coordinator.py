"""SpendingCoordinator: cadence, unchanged skip, isolation, revisions (S14)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edp_radar.const import DOMAIN
from custom_components.edp_radar.spending.coordinator import SpendingCoordinator
from custom_components.edp_radar.spending.models import (
    DatapointStatus,
    ProviderState,
    ReferencePeriod,
    SourceRelease,
    SpendingDataPoint,
)
from custom_components.edp_radar.spending.providers.base import (
    ParseResult,
    Payload,
    SchemaChangedError,
    SourceUnavailableError,
)
from custom_components.edp_radar.spending.registry import source_spec
from custom_components.edp_radar.spending.store import SpendingStore

NOW = datetime(2026, 9, 12, 21, 0, tzinfo=UTC)


class FakeProvider:
    """A provider whose behaviour is scripted per test."""

    def __init__(
        self, source_id: str, release_id: str = "r1", value: str = "1"
    ) -> None:
        self.spec = source_spec(source_id)
        self.release_id = release_id
        self.value = value
        self.checksum: str | None = None
        self.discover_error: Exception | None = None
        self.fetch_error: Exception | None = None
        self.parse_error: Exception | None = None
        self.calls = {"discover": 0, "fetch": 0, "parse": 0}

    def _release(self) -> SourceRelease:
        return SourceRelease(
            self.spec.source_id,
            self.release_id,
            date(2026, 9, 1),
            "d",
            "c",
            "x",
            checksum=self.checksum or self.release_id,
        )

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease:
        self.calls["discover"] += 1
        if self.discover_error:
            raise self.discover_error
        return self._release()

    async def async_fetch_release(
        self, session: ClientSession, release: SourceRelease
    ) -> tuple[SourceRelease, Payload]:
        self.calls["fetch"] += 1
        if self.fetch_error:
            raise self.fetch_error
        return release, b"payload"

    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult:
        self.calls["parse"] += 1
        if self.parse_error:
            raise self.parse_error
        point = SpendingDataPoint(
            self.spec.source_id,
            "m",
            "SE",
            ReferencePeriod.year(2025),
            Decimal(self.value),
            "U",
            DatapointStatus.ACTUAL,
            release.release_id,
            release.published_at,
            "c",
        )
        return ParseResult((point,), ("note",), "fp")


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


async def _coordinator(
    hass: HomeAssistant, providers: list[FakeProvider], clock: Clock
) -> SpendingCoordinator:
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test-entry",
        unique_id=DOMAIN,
        data={},
        options={},
        version=2,
    )
    entry.add_to_hass(hass)
    store = SpendingStore(hass, entry.entry_id)
    coordinator = SpendingCoordinator(
        hass,
        entry,
        session=async_get_clientsession(hass),
        store=store,
        providers=providers,
        clock=clock,
    )
    await coordinator.async_setup()
    return coordinator


async def test_first_refresh_loads_every_provider(hass: HomeAssistant) -> None:
    clock = Clock(NOW)
    providers = [FakeProvider("statskontoret"), FakeProvider("nato")]
    coordinator = await _coordinator(hass, providers, clock)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    snapshot = coordinator.data
    assert snapshot is not None and snapshot.refreshed_at == NOW
    for provider in providers:
        series = snapshot.get(provider.spec.source_id)
        assert provider.calls == {"discover": 1, "fetch": 1, "parse": 1}
        assert len(series.datapoints) == 1
        assert series.health.state is ProviderState.AVAILABLE
        assert series.health.warnings == ("note",)
        assert series.health.next_check_at == NOW + provider.spec.check_interval
        assert series.release is not None and series.release.layout_fingerprint == "fp"
    assert snapshot.get("eurostat").health.state is ProviderState.NEVER_LOADED


async def test_not_due_providers_are_skipped_and_unchanged_releases_not_fetched(
    hass: HomeAssistant,
) -> None:
    clock = Clock(NOW)
    provider = FakeProvider("nato")
    coordinator = await _coordinator(hass, [provider], clock)
    await coordinator.async_refresh()
    clock.now = NOW + timedelta(hours=6)
    await coordinator.async_refresh()
    assert provider.calls["discover"] == 1  # weekly cadence: not due yet
    clock.now = NOW + timedelta(days=7, minutes=1)
    await coordinator.async_refresh()
    assert provider.calls == {"discover": 2, "fetch": 1, "parse": 1}
    health = coordinator.data.get("nato").health
    assert health.skip_reason == "unchanged_release"
    assert health.last_check_at == clock.now
    assert health.next_check_at == clock.now + provider.spec.check_interval
    provider.release_id, provider.value = "r2", "2"
    clock.now += timedelta(days=7, minutes=1)
    await coordinator.async_refresh()
    assert provider.calls == {"discover": 3, "fetch": 2, "parse": 2}
    series = coordinator.data.get("nato")
    assert series.datapoints[0].value == Decimal("2")
    assert len(series.revisions) == 1


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


async def test_unexpected_provider_exception_is_isolated(hass: HomeAssistant) -> None:
    clock = Clock(NOW)
    broken = FakeProvider("nato")
    fine = FakeProvider("statskontoret")
    coordinator = await _coordinator(hass, [broken, fine], clock)
    await coordinator.async_refresh()
    broken.release_id = "r2"
    broken.parse_error = RuntimeError("boom")
    fine.release_id, fine.value = "r2", "9"
    clock.now = NOW + timedelta(days=7, minutes=1)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    nato = coordinator.data.get("nato")
    assert nato.health.state is ProviderState.PARSER_ERROR
    assert nato.health.last_error == "boom"
    assert len(nato.datapoints) == 1
    assert nato.datapoints[0].value == Decimal("1")
    assert fine.calls == {"discover": 2, "fetch": 2, "parse": 2}
    statskontoret = coordinator.data.get("statskontoret")
    assert len(statskontoret.datapoints) == 1
    assert statskontoret.datapoints[0].value == Decimal("9")


async def test_schema_change_and_parser_error_keep_old_data(
    hass: HomeAssistant,
) -> None:
    clock = Clock(NOW)
    provider = FakeProvider("sipri")
    coordinator = await _coordinator(hass, [provider], clock)
    await coordinator.async_refresh()
    provider.release_id = "r2"
    provider.parse_error = SchemaChangedError("sheet missing")
    clock.now = NOW + timedelta(days=7, minutes=1)
    await coordinator.async_refresh()
    series = coordinator.data.get("sipri")
    assert series.health.state is ProviderState.SCHEMA_CHANGED
    assert series.health.last_error == "sheet missing"
    assert series.release is not None and series.release.release_id == "r1"
    assert len(series.datapoints) == 1
    provider.parse_error = ValueError("bad number")
    clock.now += timedelta(days=7, minutes=1)
    await coordinator.async_refresh()
    assert coordinator.data.get("sipri").health.state is ProviderState.PARSER_ERROR


async def test_update_failed_only_when_nothing_is_available(
    hass: HomeAssistant,
) -> None:
    clock = Clock(NOW)
    provider = FakeProvider("eda")
    provider.discover_error = SourceUnavailableError("down")
    coordinator = await _coordinator(hass, [provider], clock)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_force_refresh_one_source(hass: HomeAssistant) -> None:
    clock = Clock(NOW)
    provider = FakeProvider("nato")
    coordinator = await _coordinator(hass, [provider], clock)
    await coordinator.async_refresh()
    provider.release_id = "r2"
    await coordinator.async_refresh_source("nato")
    assert provider.calls["fetch"] == 2
    assert coordinator.data.get("nato").release.release_id == "r2"


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


async def test_setup_seeds_data_from_the_loaded_store(hass: HomeAssistant) -> None:
    # NATO data exists in the store from before a restart…
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
    # …so entities must see it immediately after setup, before any refresh.
    coordinator = await _coordinator(hass, [FakeProvider("nato")], Clock(NOW))
    assert coordinator.data is not None
    assert coordinator.data.get("nato").datapoints


async def test_setup_seeds_empty_series_from_an_empty_store(
    hass: HomeAssistant,
) -> None:
    coordinator = await _coordinator(hass, [FakeProvider("nato")], Clock(NOW))
    assert coordinator.data is not None
    assert coordinator.data.get("nato").datapoints == ()


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
    assert series.release.layout_fingerprint == "fp"

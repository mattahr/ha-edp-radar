"""Spending models: construction, keys and JSON round-trips (S4, S5)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from custom_components.edp_radar.spending.models import (
    DatapointStatus,
    ProviderHealth,
    ProviderState,
    ReferencePeriod,
    Revision,
    SourceRelease,
    SourceSeries,
    SpendingDataPoint,
)


def test_reference_period_year_and_month_labels() -> None:
    year = ReferencePeriod.year(2025)
    assert (year.start, year.end, year.label) == (
        date(2025, 1, 1),
        date(2025, 12, 31),
        "2025",
    )
    month = ReferencePeriod.month(2026, 7)
    assert (month.start, month.end, month.label) == (
        date(2026, 7, 1),
        date(2026, 7, 31),
        "Jul 2026",
    )
    assert ReferencePeriod.month(2024, 2).end == date(2024, 2, 29)
    assert ReferencePeriod.from_dict(month.to_dict()) == month


def _point(**overrides: object) -> SpendingDataPoint:
    base: dict[str, object] = {
        "source_id": "statskontoret",
        "metric_id": "materiel_outturn",
        "country": "SE",
        "reference": ReferencePeriod.month(2026, 7),
        "value": Decimal("3753.54717975"),
        "unit": "SEK_MILLION",
        "status": DatapointStatus.ACTUAL,
        "release_id": "2026-07-definitiv-2026-08-24",
        "published_at": date(2026, 8, 24),
        "source_url": "https://www.statskontoret.se/analys-och-statistik/oppna-data/manadsutfall/?year=2026",
        "flags": ("agency:2021000340",),
    }
    base.update(overrides)
    return SpendingDataPoint(**base)  # type: ignore[arg-type]


def test_datapoint_key_and_round_trip() -> None:
    point = _point()
    assert point.key == (
        "statskontoret",
        "materiel_outturn",
        "SE",
        "2026-07-01",
        "2026-07-31",
        "SEK_MILLION",
    )
    data = point.to_dict()
    assert data["value"] == "3753.54717975"
    assert data["status"] == "actual"
    assert SpendingDataPoint.from_dict(data) == point
    assert (
        SpendingDataPoint.from_dict(
            _point(published_at=None, flags=()).to_dict()
        ).published_at
        is None
    )


def test_release_round_trip_keeps_optional_fields() -> None:
    release = SourceRelease(
        source_id="nato",
        release_id="2026:0x8DEDE695735E099",
        published_at=date(2026, 7, 10),
        download_url="https://www.nato.int/content/dam/nato/webready/documents/finance/def-exp-2026-en.xlsx",
        canonical_url="https://www.nato.int/en/what-we-do/introduction-to-nato/defence-expenditures-and-natos-5-commitment",
        format="xlsx",
        etag='"0x8DEDE695735E099"',
        last_modified="Fri, 10 Jul 2026 09:55:14 GMT",
        checksum="abc",
    )
    assert SourceRelease.from_dict(release.to_dict()) == release
    minimal = SourceRelease("sipri", "v1.2", None, "u", "c", "xlsx")
    assert SourceRelease.from_dict(minimal.to_dict()) == minimal


def test_series_round_trip_with_health_and_revisions() -> None:
    now = datetime(2026, 9, 12, 21, 0, tzinfo=UTC)
    point = _point()
    revision = Revision(
        key=point.key,
        previous_value=Decimal("3700"),
        previous_release_id="2026-07-preliminar-2026-08-20",
        new_value=point.value,
        release_id=point.release_id,
        detected_at=now,
    )
    health = ProviderHealth(
        state=ProviderState.AVAILABLE,
        last_check_at=now,
        next_check_at=now,
        last_success_at=now,
        last_error=None,
        warnings=("unknown country label 'Kosovo'",),
        skip_reason=None,
    )
    series = SourceSeries(
        source_id="statskontoret",
        release=None,
        health=health,
        datapoints=(point,),
        revisions=(revision,),
        retrieved_at=now,
    )
    restored = SourceSeries.from_dict(series.to_dict())
    assert restored == series
    assert restored.health.state is ProviderState.AVAILABLE
    assert restored.revisions[0].detected_at == now


def test_empty_series_default() -> None:
    series = SourceSeries.empty("eda")
    assert series.health.state is ProviderState.NEVER_LOADED
    assert series.datapoints == ()
    assert series.release is None
    assert SourceSeries.from_dict(series.to_dict()) == series


def test_release_round_trips_the_layout_fingerprint() -> None:
    from custom_components.edp_radar.spending.models import SourceRelease

    release = SourceRelease(
        "nato",
        "2026:x",
        date(2026, 7, 10),
        "d",
        "c",
        "xlsx",
        layout_fingerprint="Table 1 | Table 2",
    )
    assert SourceRelease.from_dict(release.to_dict()) == release
    assert (
        SourceRelease.from_dict(
            {**release.to_dict(), "layout_fingerprint": None}
        ).layout_fingerprint
        is None
    )

"""Ages and cadence-aware freshness (S15; plan §14, §56–§58)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from custom_components.edp_radar.spending.freshness import (
    FreshnessState,
    freshness_state,
    last_business_day,
    next_release_deadline,
    publication_age_days,
    reference_age_days,
    retrieval_age_days,
)
from custom_components.edp_radar.spending.registry import source_spec

TODAY = date(2026, 9, 12)


def test_ages() -> None:
    assert publication_age_days(date(2026, 8, 24), TODAY) == 19
    assert publication_age_days(None, TODAY) is None
    assert reference_age_days(date(2026, 7, 31), TODAY) == 43
    assert (
        retrieval_age_days(
            datetime(2026, 9, 11, 22, 0, tzinfo=UTC),
            datetime(2026, 9, 12, 21, 0, tzinfo=UTC),
        )
        == 0
    )
    assert (
        retrieval_age_days(
            datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 9, 12, tzinfo=UTC)
        )
        == 11
    )
    assert retrieval_age_days(None, datetime(2026, 9, 12, tzinfo=UTC)) is None


def test_last_business_day() -> None:
    assert last_business_day(2026, 8) == date(2026, 8, 31)  # Monday
    assert last_business_day(2026, 5) == date(2026, 5, 29)  # 31st is a Sunday
    assert last_business_day(2026, 1) == date(2026, 1, 30)


def test_monthly_deadline_and_states() -> None:
    spec = source_spec("statskontoret")
    # Reference July 2026 → August due last business day of September.
    assert next_release_deadline(spec, date(2026, 7, 31), date(2026, 8, 24)) == date(
        2026, 9, 30
    )
    assert (
        freshness_state(spec, date(2026, 7, 31), date(2026, 8, 24), TODAY)
        is FreshnessState.CURRENT
    )
    assert (
        freshness_state(spec, date(2026, 7, 31), date(2026, 8, 24), date(2026, 10, 3))
        is FreshnessState.EXPECTED
    )
    assert (
        freshness_state(spec, date(2026, 7, 31), date(2026, 8, 24), date(2026, 10, 8))
        is FreshnessState.LATE
    )
    assert freshness_state(spec, None, None, TODAY) is FreshnessState.UNKNOWN


def test_annual_and_twice_yearly_states() -> None:
    nato = source_spec("nato")
    assert next_release_deadline(nato, date(2026, 12, 31), date(2026, 7, 10)) == date(
        2027, 7, 10
    )
    assert (
        freshness_state(nato, date(2026, 12, 31), date(2026, 7, 10), TODAY)
        is FreshnessState.CURRENT
    )
    assert (
        freshness_state(nato, date(2026, 12, 31), date(2026, 7, 10), date(2027, 7, 15))
        is FreshnessState.EXPECTED
    )
    assert (
        freshness_state(nato, date(2026, 12, 31), date(2026, 7, 10), date(2027, 8, 1))
        is FreshnessState.LATE
    )
    assert (
        freshness_state(nato, date(2026, 12, 31), None, TODAY) is FreshnessState.UNKNOWN
    )
    eurostat = source_spec("eurostat")
    assert next_release_deadline(
        eurostat, date(2025, 12, 31), date(2026, 4, 27)
    ) == date(2026, 10, 27)
    assert (
        freshness_state(eurostat, date(2025, 12, 31), date(2026, 4, 27), TODAY)
        is FreshnessState.CURRENT
    )
    assert (
        freshness_state(
            eurostat, date(2025, 12, 31), date(2026, 4, 27), date(2026, 11, 15)
        )
        is FreshnessState.LATE
    )

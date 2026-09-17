"""Publication, reference and retrieval ages plus a cadence-aware state (S15).

``current``  – the next release is not yet due.
``expected`` – due, but within the grace period.
``late``     – past due and grace.
``unknown``  – not enough metadata.

Statskontoret publishes "senast sista vardagen i månaden efter aktuell
utfallsmånad" (plan §14): the month after the latest reference month is due
on the last business day of the month after that. Business days ignore
Swedish public holidays (a documented simplification). Annual sources are due
365 days after their last publication, twice-yearly sources after 183 days.

``late`` also covers a reference period that should have been published
(``expected_lag_days`` after its end) but is missing, so a source that keeps
re-publishing old data is not reported as current.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from enum import StrEnum

from .models import Cadence, SourceSpec

GRACE_DAYS = 7
_ANNUAL = timedelta(days=365)
_TWICE_YEARLY = timedelta(days=183)


class FreshnessState(StrEnum):
    CURRENT = "current"
    EXPECTED = "expected"
    LATE = "late"
    UNKNOWN = "unknown"


def publication_age_days(published_at: date | None, today: date) -> int | None:
    return None if published_at is None else (today - published_at).days


def reference_age_days(reference_end: date, today: date) -> int:
    return (today - reference_end).days


def retrieval_age_days(retrieved_at: datetime | None, now: datetime) -> int | None:
    return None if retrieved_at is None else (now - retrieved_at).days


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def last_business_day(year: int, month: int) -> date:
    day = _month_end(year, month)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _add_months(day: date, months: int) -> tuple[int, int]:
    index = day.year * 12 + (day.month - 1) + months
    return index // 12, index % 12 + 1


def expected_reference_end(spec: SourceSpec, today: date) -> date:
    """Newest period end whose figures should already be published (S42).

    Monthly sources: the newest month end at least ``expected_lag_days`` ago.
    Annual data (also Eurostat's twice-yearly dissemination): the newest
    31 December at least ``expected_lag_days`` ago.
    """
    lag = timedelta(days=spec.expected_lag_days)
    if spec.cadence is Cadence.MONTHLY:
        candidate = _month_end(today.year, today.month)
        while candidate + lag > today:
            year, month = _add_months(candidate, -1)
            candidate = _month_end(year, month)
        return candidate
    candidate = date(today.year, 12, 31)
    while candidate + lag > today:
        candidate = date(candidate.year - 1, 12, 31)
    return candidate


def reference_overdue(
    spec: SourceSpec, latest_reference_end: date | None, today: date
) -> bool:
    """True when a period that should be published is not in the data."""
    return (
        latest_reference_end is None
        or latest_reference_end < expected_reference_end(spec, today)
    )


def reference_period_complete(reference_end: date, today: date) -> bool:
    """False for a reference year still running (NATO estimates, S24c)."""
    return reference_end <= today


def next_release_deadline(
    spec: SourceSpec, latest_reference_end: date | None, published_at: date | None
) -> date | None:
    """When the next release is due, or ``None`` when it cannot be known."""
    if spec.cadence is Cadence.MONTHLY:
        if latest_reference_end is None:
            return None
        year, month = _add_months(latest_reference_end, 2)
        return last_business_day(year, month)
    if published_at is None:
        return None
    if spec.cadence is Cadence.TWICE_YEARLY:
        return published_at + _TWICE_YEARLY
    return published_at + _ANNUAL


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

"""Pure calculations over datapoints (S16; plan §48–§55).

Nothing here converts currencies or mixes sources: ``rank`` refuses more than
one ``source_id`` and works on exactly one metric, reference period and unit.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from statistics import median as _median

from .countries import NORDIC
from .models import DatapointStatus, ReferencePeriod, SpendingDataPoint
from .registry import FOCUS_COUNTRY


def monthly_series(
    points: Iterable[SpendingDataPoint], metric_id: str, country: str
) -> dict[tuple[int, int], SpendingDataPoint]:
    """``{(year, month): point}`` for one monthly metric of one country."""
    series: dict[tuple[int, int], SpendingDataPoint] = {}
    for point in points:
        if point.metric_id != metric_id or point.country != country:
            continue
        start, end = point.reference.start, point.reference.end
        if start.year == end.year and start.month == end.month and start.day == 1:
            series[(start.year, start.month)] = point
    return series


def latest_month(
    points: Iterable[SpendingDataPoint], metric_id: str, country: str
) -> SpendingDataPoint | None:
    series = monthly_series(points, metric_id, country)
    if not series:
        return None
    return series[max(series)]


def ytd(
    points: Iterable[SpendingDataPoint],
    metric_id: str,
    country: str,
    year: int,
    through_month: int,
) -> Decimal | None:
    """Sum of January..``through_month``; ``None`` when any month is missing."""
    series = monthly_series(points, metric_id, country)
    total = Decimal(0)
    for month in range(1, through_month + 1):
        point = series.get((year, month))
        if point is None:
            return None
        total += point.value
    return total


def nominal_change_pct(
    current: Decimal | None, previous: Decimal | None
) -> Decimal | None:
    """Nominal change in percent (plan §54); ``None`` without a usable base."""
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / previous * Decimal(100)


@dataclass(frozen=True, slots=True)
class RankEntry:
    rank: int
    country: str
    value: Decimal
    status: DatapointStatus
    flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Ranking:
    source_id: str
    metric_id: str
    unit: str
    reference: ReferencePeriod
    entries: tuple[RankEntry, ...]
    focus_rank: int
    focus_value: Decimal
    population: int
    top: RankEntry
    median: Decimal
    statuses: tuple[str, ...]
    excluded_zero: tuple[str, ...] = ()


def rank(
    points: Iterable[SpendingDataPoint],
    *,
    metric_id: str,
    unit: str,
    reference: ReferencePeriod,
    focus: str = FOCUS_COUNTRY,
    statuses: set[DatapointStatus] | None = None,
) -> Ranking | None:
    """Descending ranking of one source/metric/reference/unit (plan §48, §50).

    Values of exactly zero are listed in ``excluded_zero`` instead of ranked
    (S35).
    """
    selected: dict[str, SpendingDataPoint] = {}
    sources: set[str] = set()
    for point in points:
        if point.metric_id != metric_id or point.unit != unit:
            continue
        if (point.reference.start, point.reference.end) != (
            reference.start,
            reference.end,
        ):
            continue
        sources.add(point.source_id)
        if statuses is not None and point.status not in statuses:
            continue
        selected[point.country] = point
    if len(sources) > 1:
        raise ValueError(f"ranking must use one source, got {sorted(sources)}")
    excluded_zero = tuple(sorted(c for c, p in selected.items() if p.value == 0))
    for country in excluded_zero:
        del selected[country]
    if focus not in selected:
        return None
    ordered = sorted(selected.values(), key=lambda p: (-p.value, p.country))
    entries = tuple(
        RankEntry(index, p.country, p.value, p.status, p.flags)
        for index, p in enumerate(ordered, start=1)
    )
    focus_entry = next(e for e in entries if e.country == focus)
    return Ranking(
        source_id=next(iter(sources)),
        metric_id=metric_id,
        unit=unit,
        reference=reference,
        entries=entries,
        focus_rank=focus_entry.rank,
        focus_value=focus_entry.value,
        population=len(entries),
        top=entries[0],
        median=Decimal(_median(e.value for e in entries)),
        statuses=tuple(sorted({e.status.value for e in entries})),
        excluded_zero=excluded_zero,
    )


def latest_reference(
    points: Iterable[SpendingDataPoint], metric_id: str, *, min_countries: int = 2
) -> ReferencePeriod | None:
    """Newest reference period of a metric with at least ``min_countries``."""
    by_period: dict[tuple[str, str], tuple[ReferencePeriod, set[str]]] = {}
    for point in points:
        if point.metric_id != metric_id:
            continue
        key = (point.reference.start.isoformat(), point.reference.end.isoformat())
        entry = by_period.setdefault(key, (point.reference, set()))
        entry[1].add(point.country)
    candidates = [
        ref for ref, countries in by_period.values() if len(countries) >= min_countries
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: (r.end, r.start))


def nordic_subset(ranking: Ranking) -> tuple[RankEntry, ...]:
    """Nordic entries in ranking order; Iceland only when present (plan §51)."""
    return tuple(e for e in ranking.entries if e.country in NORDIC)


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

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


def rank(
    points: Iterable[SpendingDataPoint],
    *,
    metric_id: str,
    unit: str,
    reference: ReferencePeriod,
    focus: str = FOCUS_COUNTRY,
    statuses: set[DatapointStatus] | None = None,
) -> Ranking | None:
    """Descending ranking of one source/metric/reference/unit (plan §48, §50)."""
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

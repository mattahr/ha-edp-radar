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
        "top": {
            "country": ranking.top.country,
            value_key: scaled(ranking.top.value, scale),
        },
        f"median_{value_key}": scaled(ranking.median, scale),
        "nordic": [
            {"country": e.country, "rank": e.rank, value_key: scaled(e.value, scale)}
            for e in nordic.entries
        ],
        f"nordic_median_{value_key}": scaled(nordic.median, scale),
        "sweden": {
            "rank": ranking.focus_rank,
            value_key: scaled(ranking.focus_value, scale),
        },
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
        {
            "year": year,
            value_key: scaled(point.value, scale),
            "status": point.status.value,
        }
        for year, point in sorted(series.items())
    ]

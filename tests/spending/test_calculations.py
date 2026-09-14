"""Pure calculations on datapoints (S16; plan §48–§55)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from custom_components.edp_radar.spending.calculations import (
    NordicSummary,
    annual_series,
    change_over_years,
    coverage,
    latest_month,
    latest_reference,
    latest_year,
    month_change,
    monthly_series,
    nominal_change_pct,
    nordic_subset,
    nordic_summary,
    rank,
    value_at,
    ytd,
    ytd_change,
)
from custom_components.edp_radar.spending.models import (
    DatapointStatus,
    ReferencePeriod,
    SpendingDataPoint,
)


def _monthly(metric: str, year: int, month: int, value: str) -> SpendingDataPoint:
    return SpendingDataPoint(
        "statskontoret",
        metric,
        "SE",
        ReferencePeriod.month(year, month),
        Decimal(value),
        "SEK_MILLION",
        DatapointStatus.ACTUAL,
        "r",
        date(2026, 8, 24),
        "u",
    )


def _annual(
    source: str,
    metric: str,
    country: str,
    year: int,
    value: str,
    status: DatapointStatus = DatapointStatus.ACTUAL,
    unit: str = "EUR_MILLION",
) -> SpendingDataPoint:
    return SpendingDataPoint(
        source,
        metric,
        country,
        ReferencePeriod.year(year),
        Decimal(value),
        unit,
        status,
        "r",
        None,
        "u",
    )


MONTHLY = [
    *[
        _monthly("materiel_outturn", 2025, m, v)
        for m, v in enumerate(
            [
                "1249.91904794",
                "1761.37533405",
                "3924.46838279",
                "1992.49195545",
                "3023.46969568",
                "5014.53463338",
                "2939.12460557",
                "1795.37738032",
                "5249.30849248",
                "4913.77616522",
                "3638.46181911",
                "23327.02469578",
            ],
            start=1,
        )
    ],
    *[
        _monthly("materiel_outturn", 2026, m, v)
        for m, v in enumerate(
            [
                "1413.08686370",
                "3525.41360338",
                "5470.01853783",
                "2779.98873985",
                "3349.14200332",
                "5585.76075380",
                "3753.54717975",
            ],
            start=1,
        )
    ],
    _monthly("uo6_total_outturn", 2026, 7, "11050.09591378"),
]


def test_monthly_series_latest_and_ytd() -> None:
    series = monthly_series(MONTHLY, "materiel_outturn", "SE")
    assert sorted(series)[-1] == (2026, 7)
    latest = latest_month(MONTHLY, "materiel_outturn", "SE")
    assert latest is not None and latest.reference.label == "Jul 2026"
    assert ytd(MONTHLY, "materiel_outturn", "SE", 2026, 7) == Decimal("25876.95768163")
    assert ytd(MONTHLY, "materiel_outturn", "SE", 2025, 7) == Decimal("19905.38365486")
    assert ytd(MONTHLY, "materiel_outturn", "SE", 2026, 8) is None  # August missing
    assert (
        ytd(MONTHLY, "uo6_total_outturn", "SE", 2026, 7) is None
    )  # January–June missing
    assert latest_month(MONTHLY, "nope", "SE") is None


def test_nominal_change_pct() -> None:
    assert nominal_change_pct(
        Decimal("25876.95768163"), Decimal("19905.38365486")
    ) == pytest.approx(Decimal("30.0"), abs=Decimal("0.1"))
    assert nominal_change_pct(Decimal("10"), Decimal("0")) is None
    assert nominal_change_pct(Decimal("10"), None) is None
    assert nominal_change_pct(None, Decimal("5")) is None
    assert nominal_change_pct(Decimal("90"), Decimal("100")) == Decimal("-10")


ANNUAL = [
    _annual("eurostat", "defence_expenditure", "DE", 2025, "68824.0"),
    _annual("eurostat", "defence_expenditure", "FR", 2025, "56638.0"),
    _annual("eurostat", "defence_expenditure", "PL", 2025, "31637.9"),
    _annual("eurostat", "defence_expenditure", "SE", 2025, "17196.9"),
    _annual("eurostat", "defence_expenditure", "DK", 2025, "8997.7"),
    _annual("eurostat", "defence_expenditure", "FI", 2025, "7000.0"),
    _annual("eurostat", "defence_expenditure", "SE", 2024, "11093.8"),
    _annual("eurostat", "defence_expenditure", "DE", 2024, "60000"),
    _annual(
        "eurostat", "defence_expenditure_pct_gdp", "SE", 2025, "2.9", unit="PCT_GDP"
    ),
    _annual(
        "nato",
        "defence_expenditure_usd_current",
        "SE",
        2025,
        "19122",
        DatapointStatus.ESTIMATE,
        "USD_MILLION",
    ),
]


def test_rank_within_one_source_metric_reference_unit() -> None:
    ranking = rank(
        ANNUAL,
        metric_id="defence_expenditure",
        unit="EUR_MILLION",
        reference=ReferencePeriod.year(2025),
    )
    assert ranking is not None
    assert ranking.source_id == "eurostat"
    assert [e.country for e in ranking.entries] == ["DE", "FR", "PL", "SE", "DK", "FI"]
    assert ranking.entries[0].rank == 1
    assert ranking.focus_rank == 4
    assert ranking.focus_value == Decimal("17196.9")
    assert ranking.population == 6
    assert ranking.top.country == "DE"
    assert ranking.median == (Decimal("31637.9") + Decimal("17196.9")) / 2
    assert ranking.statuses == ("actual",)
    assert [e.country for e in nordic_subset(ranking)] == ["SE", "DK", "FI"]


def test_rank_requires_focus_and_rejects_mixed_sources() -> None:
    without_sweden = [p for p in ANNUAL if p.country != "SE"]
    assert (
        rank(
            without_sweden,
            metric_id="defence_expenditure",
            unit="EUR_MILLION",
            reference=ReferencePeriod.year(2025),
        )
        is None
    )
    assert (
        rank(
            ANNUAL,
            metric_id="defence_expenditure",
            unit="EUR_MILLION",
            reference=ReferencePeriod.year(2030),
        )
        is None
    )
    mixed = [
        *ANNUAL,
        _annual("nato", "defence_expenditure", "NO", 2025, "1", unit="EUR_MILLION"),
    ]
    with pytest.raises(ValueError, match="one source"):
        rank(
            mixed,
            metric_id="defence_expenditure",
            unit="EUR_MILLION",
            reference=ReferencePeriod.year(2025),
        )
    only_actual = rank(
        ANNUAL,
        metric_id="defence_expenditure",
        unit="EUR_MILLION",
        reference=ReferencePeriod.year(2025),
        statuses={DatapointStatus.ESTIMATE},
    )
    assert only_actual is None


def test_latest_reference_with_enough_countries() -> None:
    assert latest_reference(ANNUAL, "defence_expenditure") == ReferencePeriod.year(2025)
    assert latest_reference(ANNUAL, "defence_expenditure", min_countries=7) is None
    assert latest_reference(
        ANNUAL, "defence_expenditure", min_countries=2
    ) == ReferencePeriod.year(2025)
    assert latest_reference([], "defence_expenditure") is None


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
    assert latest_year(
        points, "milex", "SE", unit="USD_MILLION_CONSTANT_2024"
    ).value == Decimal(12)
    assert latest_year(points, "milex", "SE").value in {Decimal(12), Decimal(13)}
    assert latest_year(points, "milex", "FI") is None
    assert value_at(points, "milex_pct", "SE", ReferencePeriod.year(2025)) == Decimal(
        "2.4"
    )
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
    cov = coverage(
        points, "defence_expenditure", ReferencePeriod.year(2025), unit="EUR_MILLION"
    )
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

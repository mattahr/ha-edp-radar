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
        "source": "SIPRI military expenditure database",
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
        *(
            _point(country, 2025, str(value))
            for country, value in {
                "US": 900000,
                "RU": 158236,
                "DE": 88000,
                "NO": 16085,
                "SE": 14954,
                "DK": 14082,
                "FI": 7614,
                "IS": 0,
            }.items()
        ),
        _point(
            "SE", 2025, "2.47", metric="military_expenditure_pct_gdp", unit="PCT_GDP"
        ),
        _point("US", 2024, "880000"),
        _point("CH", 2024, "6000"),
    ]
    ranking = rank(
        points,
        metric_id="military_expenditure_usd_constant",
        unit="USD_MILLION_CONSTANT_2024",
        reference=ReferencePeriod.year(2025),
    )
    assert ranking is not None
    cov = coverage(
        points,
        "military_expenditure_usd_constant",
        ReferencePeriod.year(2025),
        unit="USD_MILLION_CONSTANT_2024",
    )
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
    assert attrs["ranking"][0] == {
        "rank": 1,
        "country": "US",
        "usd": 900000.0 * MILLION,
        "pct_gdp": None,
    }
    assert attrs["ranking"][4] == {
        "rank": 5,
        "country": "SE",
        "usd": 14954.0 * MILLION,
        "pct_gdp": 2.47,
    }
    assert attrs["population"] == 7
    assert attrs["population_total"] == 9
    assert attrs["missing"] == ["CH"]
    assert attrs["excluded_zero"] == ["IS"]
    assert attrs["top"] == {"country": "US", "usd": 900000.0 * MILLION}
    assert attrs["median_usd"] == 16085.0 * MILLION
    assert [row["country"] for row in attrs["nordic"]] == ["NO", "SE", "DK", "FI"]
    assert (
        attrs["nordic_median_usd"] == (14954 + 14082) / 2 * MILLION
    )  # SE, DK are the middle two
    assert attrs["sweden"] == {"rank": 5, "usd": 14954.0 * MILLION}
    assert attrs["statuses"] == ["actual"]


def test_ranking_rows_are_capped_with_sweden_appended() -> None:
    points = [_point(f"C{i:02d}", 2025, str(1000 - i)) for i in range(RANKING_ROWS + 5)]
    points.append(_point("SE", 2025, "1"))
    ranking = rank(
        points,
        metric_id="military_expenditure_usd_constant",
        unit="USD_MILLION_CONSTANT_2024",
        reference=ReferencePeriod.year(2025),
    )
    assert ranking is not None
    cov = coverage(
        points,
        "military_expenditure_usd_constant",
        ReferencePeriod.year(2025),
        unit="USD_MILLION_CONSTANT_2024",
    )
    rows = ranking_attrs(ranking, cov, value_key="usd", scale=MILLION)["ranking"]
    assert len(rows) == RANKING_ROWS + 1
    assert rows[-1]["country"] == "SE" and rows[-1]["rank"] == RANKING_ROWS + 6


def test_series_attrs_and_helpers() -> None:
    monthly = {
        (2026, 1): SpendingDataPoint(
            "statskontoret",
            "materiel_outturn",
            "SE",
            ReferencePeriod.month(2026, 1),
            Decimal("2000.5"),
            "SEK_MILLION",
            DatapointStatus.ACTUAL,
            "r",
            None,
            "u",
        ),
        (2026, 2): SpendingDataPoint(
            "statskontoret",
            "materiel_outturn",
            "SE",
            ReferencePeriod.month(2026, 2),
            Decimal("3000"),
            "SEK_MILLION",
            DatapointStatus.ACTUAL,
            "r",
            None,
            "u",
        ),
        (2025, 12): SpendingDataPoint(
            "statskontoret",
            "materiel_outturn",
            "SE",
            ReferencePeriod.month(2025, 12),
            Decimal("9000"),
            "SEK_MILLION",
            DatapointStatus.PRELIMINARY,
            "r",
            None,
            "u",
        ),
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

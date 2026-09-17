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
    assert format_amount("SEK", Decimal("-48200000000")) == "SEK -48.2bn"
    assert format_amount("EUR", Decimal("-999")) == "EUR -999"


def test_statskontoret_snapshot_text() -> None:
    ytd = YtdChange(
        Decimal("25876.95768163"),
        Decimal("19905.38365486"),
        Decimal("5971.57"),
        Decimal("30.0"),
        7,
    )
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
    tie = YtdChange(Decimal("100"), Decimal("50"), Decimal("50"), Decimal("30.15"), 7)
    tie_text = statskontoret_snapshot_text(tie, "Jul 2026")
    assert tie_text is not None
    assert "+30.2% YoY" in tie_text
    rounds_to_zero = YtdChange(
        Decimal("100"), Decimal("100"), Decimal("0"), Decimal("-0.04"), 7
    )
    rounds_to_zero_text = statskontoret_snapshot_text(rounds_to_zero, "Jul 2026")
    assert rounds_to_zero_text is not None
    assert "+0.0% YoY" in rounds_to_zero_text
    small_negative = YtdChange(
        Decimal("100"), Decimal("100"), Decimal("0"), Decimal("-0.06"), 7
    )
    small_negative_text = statskontoret_snapshot_text(small_negative, "Jul 2026")
    assert small_negative_text is not None
    assert "-0.1% YoY" in small_negative_text


def test_nato_position_text() -> None:
    points = [
        SpendingDataPoint(
            "nato",
            "defence_expenditure_pct_gdp",
            c,
            ReferencePeriod.year(2026),
            Decimal(v),
            "PCT_GDP",
            DatapointStatus.ESTIMATE,
            "r",
            None,
            "u",
        )
        for c, v in (("LT", "5.33"), ("SE", "3.22"), ("US", "3.2"))
    ]
    ranking = rank(
        points,
        metric_id="defence_expenditure_pct_gdp",
        unit="PCT_GDP",
        reference=ReferencePeriod.year(2026),
    )
    assert (
        nato_position_text(
            ranking,
            Decimal("24186000000"),
            Decimal("3.22"),
            2026,
            DatapointStatus.ESTIMATE,
        )
        == "SE #2 of 3 · USD 24.2bn · 3.2% GDP · NATO 2026 estimate"
    )
    assert nato_position_text(None, None, None, None, None) is None
    tie_pct = nato_position_text(
        ranking, Decimal("24186000000"), Decimal("3.25"), 2026, DatapointStatus.ESTIMATE
    )
    assert tie_pct is not None
    assert "3.3% GDP" in tie_pct

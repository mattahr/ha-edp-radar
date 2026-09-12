from datetime import date
from decimal import Decimal

import pytest

from custom_components.edp_radar.const import RelevanceMode
from custom_components.edp_radar.metrics import (
    CountMetric,
    Coverage,
    MetricsConfig,
    OwnOrganisation,
    ValueMetric,
    WatchlistConfig,
    Window,
    current_window,
    format_eur,
    is_central_purchasing_only,
    median,
    pct,
    pct_change,
    previous_window,
    relevant_notices,
    value_in_eur,
)
from custom_components.edp_radar.models import Money
from custom_components.edp_radar.taxonomy import Taxonomy

from .factories import buyer, flat_fx, make_notice

TODAY = date(2026, 9, 12)


@pytest.fixture
def taxonomy() -> Taxonomy:
    return Taxonomy.load()


def test_windows_are_half_open() -> None:
    w = current_window(TODAY, 30)
    assert w == Window(date(2026, 8, 13), TODAY)
    assert w.days == 30
    assert w.contains(TODAY) and w.contains(date(2026, 8, 14))
    assert not w.contains(date(2026, 8, 13))
    p = previous_window(TODAY, 30)
    assert p == Window(date(2026, 7, 14), date(2026, 8, 13))
    assert p.contains(date(2026, 8, 13))


def test_helpers() -> None:
    assert pct_change(142, 100) == 42.0
    assert pct_change(50, 100) == -50.0
    assert pct_change(5, 0) is None
    assert pct_change(5, None) is None
    assert pct_change(Decimal("3"), Decimal("2")) == 50.0
    assert pct(1, 4) == 25.0
    assert pct(0, 0) is None
    assert median([]) is None
    assert median([3, 1, 2]) == 2
    assert median([1, 2, 3, 4]) == 2.5
    assert format_eur(None) == "EUR n/a"
    assert format_eur(Decimal("31400000000")) == "EUR 31.4bn"
    assert format_eur(Decimal("640000000")) == "EUR 640m"
    assert format_eur(Decimal("8400000")) == "EUR 8.4m"
    assert format_eur(Decimal("85000")) == "EUR 85k"
    assert format_eur(Decimal("950")) == "EUR 950"


def test_value_in_eur_uses_event_date_rate() -> None:
    fx = flat_fx({"SEK": "10"}, date(2026, 1, 1), date(2026, 12, 31))
    sek = Money(Decimal("100"), "SEK")
    assert value_in_eur(sek, date(2026, 3, 1), fx) == Decimal("10.00")
    eur = Money(Decimal("100"), "EUR")
    assert value_in_eur(eur, date(2026, 3, 1), fx) == Decimal("100.00")
    assert value_in_eur(Money(Decimal("100"), "XXX"), date(2026, 3, 1), fx) is None
    assert value_in_eur(None, date(2026, 3, 1), fx) is None


def test_metric_types() -> None:
    assert Coverage(211, 328).pct == 64.3
    assert Coverage(0, 0).pct is None
    count = CountMetric(173, 142, 30)
    assert count.change == 31 and count.change_pct == 21.8
    assert CountMetric(5, None, 30).change is None
    value = ValueMetric(Decimal("8400000000"), Decimal("7000000000"), 328, 211, 90)
    assert value.coverage_pct == 64.3
    assert value.change_pct == 20.0
    assert ValueMetric(None, None, 0, 0, 90).coverage_pct is None


def test_own_organisation_matching() -> None:
    own = OwnOrganisation.from_options(
        ["202100-0340"], "SE", "FMV", ["Försvarets materielverk"]
    )
    assert own.matches(make_notice()) is True
    assert own.matches(make_notice(buyer=buyer("Saab", "SE", "556036-0793"))) is False
    assert own.matches(make_notice(buyer=buyer("Försvarets Materielverk", "SE")))
    assert not own.matches(make_notice(buyer=buyer("Försvarets Materielverk", "FI")))
    anywhere = OwnOrganisation.from_options([], None, "FMV", [])
    assert anywhere.matches(make_notice(buyer=buyer("fmv", "NO"))) is True


def test_watchlist_is_empty_by_default() -> None:
    assert WatchlistConfig().is_empty is True
    assert WatchlistConfig(countries=frozenset({"PL"})).is_empty is False
    assert MetricsConfig().relevance_mode is RelevanceMode.STRICT


def test_relevant_notices_apply_mode_and_central_purchasing_rule(
    taxonomy: Taxonomy,
) -> None:
    strict = make_notice(notice_id="a", match_reasons=frozenset({"defence_buyer"}))
    cpv_only = make_notice(notice_id="b", match_reasons=frozenset({"defence_cpv"}))
    cpb = make_notice(
        notice_id="c",
        buyer=buyer("CPB", "HR", "1", count=537),
        match_reasons=frozenset({"defence_buyer"}),
    )
    cpb_with_cpv = make_notice(
        notice_id="d",
        buyer=buyer("CPB", "HR", "1", count=537),
        match_reasons=frozenset({"defence_buyer", "defence_cpv"}),
    )
    none = make_notice(notice_id="e", match_reasons=frozenset())
    assert is_central_purchasing_only(cpb) is True
    assert is_central_purchasing_only(cpb_with_cpv) is False
    assert is_central_purchasing_only(strict) is False

    everything = [strict, cpv_only, cpb, cpb_with_cpv, none]
    kept, excluded = relevant_notices(everything, MetricsConfig(), taxonomy)
    assert [n.notice_id for n in kept] == ["a", "d"]
    assert excluded == 1
    broad = MetricsConfig(relevance_mode=RelevanceMode.BROAD)
    kept, excluded = relevant_notices(everything, broad, taxonomy)
    assert [n.notice_id for n in kept] == ["a", "b", "d"]

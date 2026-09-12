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


# --- Task 12: market metrics -------------------------------------------------
from custom_components.edp_radar.lifecycle import ProcedureIndex  # noqa: E402
from custom_components.edp_radar.metrics import (  # noqa: E402
    award_value,
    awards_count,
    estimated_value,
    growth_ranking,
    largest_change,
    market_metrics,
    new_competitions,
    process_metrics,
    rank_by,
    top_ranking,
)
from custom_components.edp_radar.models import ProcurementNotice, Winner  # noqa: E402

from .factories import change_of, competition, days_ago, result  # noqa: E402

FX = flat_fx({"SEK": "10", "PLN": "4"}, date(2025, 1, 1), date(2026, 12, 31))


def _market_notices() -> list[ProcurementNotice]:
    """Hand-built dataset. today = 2026-09-12; 30d window = (Aug 13, Sep 12]."""
    se1 = competition(
        "se1",
        "p-se1",
        days_ago(TODAY, 5),
        estimated_value=Money(Decimal("2000000"), "SEK"),
    )
    return [
        # SE: two competitions in current 30d, one in previous 30d (Jul 20)
        se1,
        competition("se2", "p-se2", days_ago(TODAY, 20), estimated_value=None),
        competition("se3", "p-se3", days_ago(TODAY, 54)),
        # version 2 + change of se1 in window: must not add a competition
        make_notice(
            notice_id="se1",
            notice_version=2,
            procedure_id="p-se1",
            publication_date=days_ago(TODAY, 3),
            estimated_value=Money(Decimal("2500000"), "SEK"),
        ),
        change_of(se1, published=days_ago(TODAY, 1), notice_id="se1-chg"),
        # DE: one big competition now, none before; PL: 1 now, 1 before (EUR 1m each)
        competition(
            "de1",
            "p-de1",
            days_ago(TODAY, 10),
            buyer=buyer("BAAINBw", "DE", "de-1"),
            estimated_value=Money(Decimal("60000000"), "EUR"),
            categories=("air_missile_defence", "air_systems"),
        ),
        competition(
            "pl1",
            "p-pl1",
            days_ago(TODAY, 15),
            buyer=buyer("AU", "PL", "pl-1"),
            estimated_value=Money(Decimal("4000000"), "PLN"),
        ),
        competition(
            "pl0",
            "p-pl0",
            days_ago(TODAY, 45),
            buyer=buyer("AU", "PL", "pl-1"),
            estimated_value=Money(Decimal("4000000"), "PLN"),
        ),
        # results: one in window with value, one without value, one in previous window
        result(
            "r1",
            "p-se3",
            days_ago(TODAY, 2),
            value=Money(Decimal("900000"), "EUR"),
            tenders=(3,),
            winners=(Winner("Saab", "556036-0793", "SE", "large"),),
        ),
        result(
            "r2",
            "p-pl0",
            days_ago(TODAY, 4),
            value=None,
            tenders=(1, 4),
            statuses=("selec-w", "clos-nw"),
        ),
        result(
            "r0",
            "p-old",
            days_ago(TODAY, 40),
            value=Money(Decimal("100000"), "EUR"),
            tenders=(1,),
        ),
    ]


def test_new_competitions_count_unique_procedures_not_versions_or_changes() -> None:
    index = ProcedureIndex.build(_market_notices())
    metric = new_competitions(index, TODAY, 30)
    assert metric.value == 4  # se1, se2, de1, pl1
    assert metric.previous == 2  # se3, pl0
    assert metric.change_pct == 100.0
    assert new_competitions(index, TODAY, 90).value == 6


def test_estimated_value_uses_latest_version_and_reports_coverage() -> None:
    index = ProcedureIndex.build(_market_notices())
    metric = estimated_value(index, TODAY, 30, FX)
    # se1 latest version 2.5m SEK = 250k EUR; de1 60m; pl1 4m PLN = 1m; se2 unknown
    assert metric.value_eur == Decimal("61250000.00")
    assert metric.sample_size == 4
    assert metric.covered == 3
    assert metric.coverage_pct == 75.0
    assert metric.previous_eur == Decimal("2000000.00")  # se3 1m EUR + pl0 1m


def test_award_value_and_count() -> None:
    index = ProcedureIndex.build(_market_notices())
    value = award_value(index, TODAY, 30, FX)
    assert value.value_eur == Decimal("900000.00")
    assert value.sample_size == 2 and value.covered == 1
    assert value.previous_eur == Decimal("100000.00")
    count = awards_count(index, TODAY, 30)
    assert count.value == 2 and count.previous == 1


def test_rank_by_country_with_ties_and_previous_period() -> None:
    index = ProcedureIndex.build(_market_notices())
    entries = rank_by(index, TODAY, FX, lambda p: [p.country or "??"], str, days=90)
    assert [(e.key, e.rank) for e in entries] == [("DE", 1), ("PL", 2), ("SE", 3)]
    de = entries[0]
    assert de.value_eur == Decimal("60000000.00") and de.procedures == 1
    assert de.previous_value_eur is None and de.change_pct is None
    ranking = top_ranking(entries, "market countries", limit=2)
    assert ranking.population_size == 3 and len(ranking.entries) == 2
    assert ranking.leader is de

    tie_a = competition(
        "a",
        "pa",
        days_ago(TODAY, 1),
        buyer=buyer("A", "AT", "a"),
        estimated_value=Money(Decimal("5"), "EUR"),
    )
    tie_b = competition(
        "b",
        "pb",
        days_ago(TODAY, 1),
        buyer=buyer("B", "BE", "b"),
        estimated_value=Money(Decimal("5"), "EUR"),
    )
    tied_index = ProcedureIndex.build([tie_a, tie_b])
    tied = rank_by(tied_index, TODAY, FX, lambda p: [p.country or "??"], str)
    assert [(e.key, e.rank) for e in tied] == [("AT", 1), ("BE", 1)]


def test_growth_ranking_applies_minimum_activity() -> None:
    today = TODAY
    small = Money(Decimal("100"), "EUR")
    notices = []
    # FI: 6 procedures now (>=5), 3 before -> +100 %
    for i in range(6):
        notices.append(
            competition(
                f"fi{i}",
                f"p-fi{i}",
                days_ago(today, 10),
                buyer=buyer("PV", "FI", "fi"),
                estimated_value=small,
            )
        )
    for i in range(3):
        notices.append(
            competition(
                f"fi-old{i}",
                f"p-fi-old{i}",
                days_ago(today, 100),
                buyer=buyer("PV", "FI", "fi"),
                estimated_value=small,
            )
        )
    # EE: 1 tiny procedure now, 1 before -> +900 % but not eligible
    notices.append(
        competition(
            "ee1",
            "p-ee1",
            days_ago(today, 10),
            buyer=buyer("RKIK", "EE", "ee"),
            estimated_value=Money(Decimal("1000"), "EUR"),
        )
    )
    notices.append(
        competition(
            "ee0",
            "p-ee0",
            days_ago(today, 100),
            buyer=buyer("RKIK", "EE", "ee"),
            estimated_value=small,
        )
    )
    # DE: 1 procedure worth 60m now (eligible by value), 30m before -> +100 %
    notices.append(
        competition(
            "de1",
            "p-de1",
            days_ago(today, 10),
            buyer=buyer("B", "DE", "de"),
            estimated_value=Money(Decimal("60000000"), "EUR"),
        )
    )
    notices.append(
        competition(
            "de0",
            "p-de0",
            days_ago(today, 100),
            buyer=buyer("B", "DE", "de"),
            estimated_value=Money(Decimal("30000000"), "EUR"),
        )
    )
    entries = rank_by(
        ProcedureIndex.build(notices), today, FX, lambda p: [p.country or "??"], str
    )
    growth = growth_ranking(entries, "eligible countries")
    assert [(e.key, e.change_pct, e.rank) for e in growth.entries] == [
        ("DE", 100.0, 1),
        ("FI", 100.0, 2),
    ]
    assert growth.population_size == 2
    change = largest_change(entries)
    assert change is not None
    assert change.key == "DE" and change.change_eur == Decimal("30000000.00")


def test_process_metrics_definitions() -> None:
    notices = [
        competition("c1", "p1", date(2026, 1, 1)),
        result(
            "r1",
            "p1",
            date(2026, 4, 11),
            tenders=(3, 1),
            statuses=("selec-w", "selec-w"),
        ),
        result("r2", "p2", date(2026, 5, 1), tenders=(1,), statuses=("clos-nw",)),
        result("r3", "p3", date(2026, 6, 1)),  # no statistics at all
        result("r4", "p4", date(2025, 1, 1), tenders=(9,)),  # outside 365d
    ]
    process = process_metrics(ProcedureIndex.build(notices), TODAY)
    assert process.median_tenders_365d.value == 1
    assert process.median_tenders_365d.sample_size == 3
    assert process.median_tenders_365d.coverage == Coverage(2, 3)
    assert process.single_bid_share_365d.pct == 66.7
    assert process.single_bid_share_365d.numerator == 2
    assert process.median_time_to_result_365d.value == 100
    assert process.median_time_to_result_365d.coverage == Coverage(1, 3)
    assert process.non_award_share_365d.pct == 33.3
    assert process.non_award_share_365d.denominator == 3


def test_market_metrics_assembles_rankings_and_texts(taxonomy: Taxonomy) -> None:
    market = market_metrics(
        ProcedureIndex.build(_market_notices()), TODAY, FX, taxonomy
    )
    assert market.new_competitions_30d.value == 4
    assert market.country_ranking_90d.leader is not None
    assert market.country_ranking_90d.leader.key == "DE"
    assert market.category_ranking_90d.leader is not None
    assert market.category_ranking_90d.leader.key == "air_missile_defence"
    assert market.category_ranking_90d.leader.label == "Air & missile defence"
    assert market.snapshot_text == "6 competitions / 90d · EUR 63m"
    assert market.country_ranking_text == "DE EUR 60m · PL EUR 2.0m · SE EUR 1.2m"
    assert market.process.median_tenders_365d.sample_size == 4

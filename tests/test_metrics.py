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


# --- Task 13: external radar & own footprint --------------------------------
from custom_components.edp_radar.metrics import (  # noqa: E402
    external_metrics,
    highlight,
    organisation_metrics,
)
from custom_components.edp_radar.models import NoticeStage  # noqa: E402


def test_highlight_uses_estimated_value_for_competitions_and_result_value() -> None:
    comp = competition("c", "p", TODAY, estimated_value=Money(Decimal("100"), "SEK"))
    h = highlight(comp, FX)
    assert (h.original_amount, h.original_currency) == (Decimal("100"), "SEK")
    assert h.value_eur == Decimal("10.00")
    res = result(
        "r",
        "p",
        TODAY,
        value=Money(Decimal("40"), "PLN"),
        decision_dates=(date(2026, 8, 1),),
    )
    assert highlight(res, FX).value_eur == Decimal("10.00")
    assert highlight(res, FX).stage is NoticeStage.RESULT


def test_external_metrics_7d(taxonomy: Taxonomy) -> None:
    notices = [
        competition(
            "a",
            "pa",
            days_ago(TODAY, 1),
            buyer=buyer("A", "DE", "a"),
            estimated_value=Money(Decimal("640000000"), "EUR"),
            categories=("air_missile_defence",),
        ),
        competition(
            "b",
            "pb",
            days_ago(TODAY, 6),
            buyer=buyer("B", "PL", "b"),
            estimated_value=None,
        ),
        competition("c", "pc", days_ago(TODAY, 8), buyer=buyer("C", "FR", "c")),
        result("r", "pc", days_ago(TODAY, 2), value=Money(Decimal("5000000"), "EUR")),
        result(
            "r-old", "px", days_ago(TODAY, 9), value=Money(Decimal("9000000"), "EUR")
        ),
    ]
    external = external_metrics(ProcedureIndex.build(notices), TODAY, FX, taxonomy)
    assert external.new_competitions_7d == 2
    assert [h.notice_id for h in external.recent_competitions] == ["a", "b"]
    assert external.largest_competition_7d is not None
    assert external.largest_competition_7d.notice_id == "a"
    assert external.largest_award_7d is not None
    assert external.largest_award_7d.notice_id == "r"
    published = days_ago(TODAY, 1).isoformat()
    assert external.latest_text == (
        f"DE · Air & missile defence · EUR 640m · published {published}"
    )


def test_external_metrics_without_values_is_unknown(taxonomy: Taxonomy) -> None:
    only = ProcedureIndex.build([competition("b", "pb", TODAY, estimated_value=None)])
    external = external_metrics(only, TODAY, FX, taxonomy)
    assert external.largest_competition_7d is None
    assert external.largest_award_7d is None
    assert external.new_competitions_7d == 1
    assert external.latest_text is not None
    assert external.latest_text.startswith("SE · Land systems · EUR n/a")
    empty = external_metrics(ProcedureIndex.build([]), TODAY, FX, taxonomy)
    assert empty.latest_text is None


def test_organisation_metrics_counts_changes_and_modifications() -> None:
    comp = competition("c1", "p1", days_ago(TODAY, 10))
    notices = [
        comp,
        change_of(comp, published=days_ago(TODAY, 5)),
        change_of(comp, published=days_ago(TODAY, 40), notice_id="c1-chg", version=1),
        result(
            "r1",
            "p1",
            days_ago(TODAY, 3),
            value=Money(Decimal("2000000"), "SEK"),
            tenders=(2,),
        ),
        make_notice(
            notice_id="m1",
            stage=NoticeStage.MODIFICATION,
            publication_date=days_ago(TODAY, 200),
        ),
        make_notice(
            notice_id="m2",
            stage=NoticeStage.MODIFICATION,
            publication_date=days_ago(TODAY, 400),
        ),
    ]
    own = organisation_metrics(ProcedureIndex.build(notices), TODAY, FX)
    assert own.competitions_30d.value == 1
    assert own.estimated_value_30d.value_eur == Decimal("1000000.00")
    assert own.awards_30d.value == 1
    assert own.award_value_30d.value_eur == Decimal("200000.00")
    assert own.changes_30d.value == 1 and own.changes_30d.previous == 1
    assert own.modifications_365d.value == 1 and own.modifications_365d.previous == 1
    assert own.process.median_tenders_365d.value == 2
    assert [h.notice_id for h in own.recent][:2] == ["r1", "c1"]


# --- Task 14: peers, suppliers, categories ----------------------------------
from custom_components.edp_radar.metrics import (  # noqa: E402
    RankingEntry,
    activity_rank,
    category_metrics,
    peer_metrics,
    supplier_metrics,
    value_percentile,
)


def _entries() -> list[RankingEntry]:
    notices = [
        competition(
            "de",
            "p-de",
            days_ago(TODAY, 10),
            buyer=buyer("B", "DE", "de"),
            estimated_value=Money(Decimal("300"), "EUR"),
        ),
        competition(
            "pl",
            "p-pl",
            days_ago(TODAY, 10),
            buyer=buyer("A", "PL", "pl"),
            estimated_value=Money(Decimal("200"), "EUR"),
        ),
        competition(
            "pl2",
            "p-pl2",
            days_ago(TODAY, 11),
            buyer=buyer("A", "PL", "pl"),
            estimated_value=None,
        ),
        competition(
            "se",
            "p-se",
            days_ago(TODAY, 10),
            estimated_value=Money(Decimal("100"), "EUR"),
        ),
        competition(
            "fi",
            "p-fi",
            days_ago(TODAY, 10),
            buyer=buyer("PV", "FI", "fi"),
            estimated_value=None,
        ),
    ]
    index = ProcedureIndex.build(notices)
    return rank_by(index, TODAY, FX, lambda p: [p.country or "??"], str)


def test_ranks_and_percentile() -> None:
    entries = _entries()
    assert [e.key for e in entries] == ["DE", "PL", "SE", "FI"]
    assert activity_rank(entries, "PL") == 1
    assert activity_rank(entries, "SE") == 2  # DE, SE, FI tie on 1 procedure
    assert activity_rank(entries, "XX") is None
    assert value_percentile(entries, "SE") == 50.0  # SE and FI(None→0) are <= SE
    assert value_percentile(entries, "DE") == 100.0
    assert value_percentile(entries, "XX") is None


def test_peer_metrics_by_country_and_deltas() -> None:
    notices = [
        result("r-se", "p-se", days_ago(TODAY, 10), tenders=(1, 1)),
        result(
            "r-fi",
            "p-fi",
            days_ago(TODAY, 10),
            buyer=buyer("PV", "FI", "fi"),
            tenders=(4, 2, 1),
        ),
        result(
            "r-dk",
            "p-dk",
            days_ago(TODAY, 10),
            buyer=buyer("FMI", "DK", "dk"),
            tenders=(3,),
        ),
    ]
    config = MetricsConfig(
        peer_countries=frozenset({"FI", "DK"}), selected_country="SE"
    )
    own = organisation_metrics(ProcedureIndex.build([notices[0]]), TODAY, FX)
    peers = peer_metrics(config, notices, _entries(), own, TODAY, FX)
    assert peers is not None
    assert peers.population == "configured peer countries"
    assert peers.population_size == 2
    assert peers.process.median_tenders_365d.value == 2.5
    assert peers.process.single_bid_share_365d.pct == 25.0
    assert peers.single_bid_delta_pp == 75.0
    assert peers.median_tenders_delta == -1.5
    assert peers.time_to_result_delta_days is None
    assert peers.selected_country == "SE" and peers.value_rank_90d == 3
    assert peers.rank_population_size == 4


def test_peer_metrics_by_organisation_and_none_when_unconfigured() -> None:
    notices = [
        result(
            "r-x",
            "p-x",
            days_ago(TODAY, 10),
            buyer=buyer("X", "NO", "no-1"),
            tenders=(2,),
        )
    ]
    by_org = MetricsConfig(peer_organisation_identifiers=frozenset({"no-1"}))
    peers = peer_metrics(by_org, notices, [], None, TODAY, FX)
    assert peers is not None and peers.population == "configured peer organisations"
    assert peers.process.median_tenders_365d.value == 2
    assert peers.single_bid_delta_pp is None
    assert peer_metrics(MetricsConfig(), notices, [], None, TODAY, FX) is None


def test_supplier_metrics_do_not_double_count_consortia() -> None:
    saab = Winner("Saab AB", "556036-0793", "SE", "large")
    bae = Winner("BAE Systems Hägglunds", "556028-3838", "SE", "large")
    eur = "EUR"
    notices = [
        result(
            "r1",
            "p1",
            days_ago(TODAY, 10),
            value=Money(Decimal("100"), eur),
            winners=(saab,),
        ),
        result(
            "r2",
            "p2",
            days_ago(TODAY, 20),
            value=Money(Decimal("300"), eur),
            winners=(bae, saab),
        ),
        result(
            "r3",
            "p3",
            days_ago(TODAY, 30),
            value=Money(Decimal("50"), eur),
            winners=(bae,),
        ),
        result("r4", "p4", days_ago(TODAY, 30), value=None, winners=(bae,)),
        result(
            "r5",
            "p5",
            days_ago(TODAY, 30),
            value=Money(Decimal("999"), eur),
            winners=(),
        ),
        result(
            "r6",
            "p6",
            days_ago(TODAY, 400),
            value=Money(Decimal("999"), eur),
            winners=(saab,),
        ),
    ]
    suppliers = supplier_metrics(ProcedureIndex.build(notices), TODAY, FX)
    assert [
        (s.name, s.award_value_eur, s.awards, s.rank) for s in suppliers.top_suppliers
    ] == [
        ("BAE Systems Hägglunds + Saab AB", Decimal("300.00"), 1, 1),
        ("Saab AB", Decimal("100.00"), 1, 2),
        ("BAE Systems Hägglunds", Decimal("50.00"), 1, 3),
    ]
    assert suppliers.total_award_value_eur == Decimal("450.00")
    assert suppliers.top5_share_pct == 100.0
    assert suppliers.groups == 3
    assert suppliers.coverage == Coverage(3, 4)
    assert suppliers.top_suppliers[0].country == "SE"


def test_category_metrics_use_procedure_level_membership(taxonomy: Taxonomy) -> None:
    notices = [
        competition(
            "c1",
            "p1",
            days_ago(TODAY, 10),
            categories=("naval_maritime",),
            estimated_value=Money(Decimal("10"), "EUR"),
        ),
        result(
            "r1",
            "p1",
            days_ago(TODAY, 5),
            categories=(),
            value=Money(Decimal("7"), "EUR"),
        ),
        competition("c2", "p2", days_ago(TODAY, 10), categories=("cyber_it",)),
    ]
    index_all = ProcedureIndex.build(notices)
    label = taxonomy.label("naval_maritime")
    naval = category_metrics(index_all, notices, "naval_maritime", label, TODAY, FX)
    assert naval.label == "Naval & maritime"
    assert naval.competitions_30d.value == 1
    assert naval.estimated_value_90d.value_eur == Decimal("10.00")
    assert naval.award_value_90d.value_eur == Decimal(
        "7.00"
    )  # via procedure membership


# --- Task 15: quality, snapshot, events -------------------------------------
from datetime import UTC, datetime  # noqa: E402

from custom_components.edp_radar.metrics import (  # noqa: E402
    compute_snapshot,
    event_type_for,
    notice_event_attributes,
    watchlist_matches,
)


def test_compute_snapshot_end_to_end(taxonomy: Taxonomy) -> None:
    cpb = make_notice(
        notice_id="cpb",
        buyer=buyer("CPB", "HR", "1", count=500),
        publication_date=days_ago(TODAY, 3),
    )
    own_comp = competition("own", "p-own", days_ago(TODAY, 4))
    de = competition(
        "de",
        "p-de",
        days_ago(TODAY, 2),
        buyer=buyer("B", "DE", "de"),
        estimated_value=Money(Decimal("60000000"), "EUR"),
        categories=("air_systems",),
    )
    no = competition("no", "p-no", days_ago(TODAY, 2), buyer=buyer("FMA", "NO", "no"))
    unparsed = competition("x", "p-x", days_ago(TODAY, 2), match_reasons=frozenset())
    config = MetricsConfig(
        market_countries=frozenset({"SE", "DE"}),
        own_organisation=OwnOrganisation.from_options(["202100-0340"], "SE", "FMV", []),
        peer_countries=frozenset({"NO"}),
        selected_country="SE",
        pinned_categories=("air_systems",),
    )
    snapshot = compute_snapshot(
        [cpb, own_comp, de, no, unparsed],
        FX,
        config,
        TODAY,
        taxonomy=taxonomy,
        parse_errors=2,
        computed_at=datetime(2026, 9, 12, 12, tzinfo=UTC),
    )
    assert snapshot.today == TODAY and snapshot.bootstrap_complete is True
    # own + de (NO outside market, cpb excluded, x irrelevant)
    assert snapshot.market.new_competitions_30d.value == 2
    assert snapshot.external.new_competitions_7d == 1  # de only: own excluded
    assert snapshot.own is not None and snapshot.own.competitions_30d.value == 1
    assert snapshot.peers is not None and snapshot.peers.population_size == 1
    assert snapshot.peers.value_rank_90d == 2
    assert set(snapshot.categories) == {"air_systems"}
    assert snapshot.categories["air_systems"].competitions_30d.value == 1
    q = snapshot.quality
    assert q.stored_versions == 5 and q.stored_notices == 5
    assert q.relevant_notices == 3
    assert q.excluded_central_purchasing == 1 and q.parse_errors == 2
    assert q.records_by_stage == {"competition": 5}
    assert q.estimated_value_coverage == Coverage(5, 5)
    assert q.fx_coverage == Coverage(5, 5)
    assert q.unclassified_share_pct == 0.0
    assert q.latest_publication_date == days_ago(TODAY, 2)
    assert q.fx_latest_date == date(2026, 12, 31)
    assert snapshot.suppliers.groups == 0


def test_compute_snapshot_without_own_or_peers(taxonomy: Taxonomy) -> None:
    snapshot = compute_snapshot(
        [], FX, MetricsConfig(), TODAY, taxonomy=taxonomy, bootstrap_complete=False
    )
    assert snapshot.own is None and snapshot.peers is None
    assert snapshot.market.new_competitions_30d.value == 0
    assert snapshot.market.estimated_value_90d.value_eur is None
    assert snapshot.quality.unclassified_share_pct is None
    assert snapshot.bootstrap_complete is False


def test_event_type_and_attributes() -> None:
    comp = competition("c", "p", TODAY, estimated_value=Money(Decimal("100"), "SEK"))
    assert event_type_for(comp) == "new_competition"
    assert event_type_for(change_of(comp, published=TODAY)) == "change"
    assert event_type_for(result("r", "p", TODAY)) == "result"
    modification = make_notice(stage=NoticeStage.MODIFICATION)
    assert event_type_for(modification) == "contract_modification"
    assert event_type_for(make_notice(stage=NoticeStage.PLANNING)) is None
    attrs = notice_event_attributes(comp, FX)
    assert attrs["notice_id"] == "c" and attrs["stage"] == "competition"
    assert attrs["publication_date"] == TODAY.isoformat()
    assert attrs["estimated_value"] == 100.0 and attrs["estimated_currency"] == "SEK"
    assert attrs["estimated_value_eur"] == 10.0
    assert attrs["result_value"] is None
    assert attrs["categories"] == ["land_systems"]
    assert attrs["match_reasons"] == ["defence_buyer"]
    assert attrs["buyer"] == "FMV" and attrs["buyer_country"] == "SE"


def test_watchlist_matching() -> None:
    comp = competition(
        "c",
        "p",
        TODAY,
        buyer=buyer("AU", "PL", "pl"),
        categories=("air_missile_defence",),
        estimated_value=Money(Decimal("600000000"), "EUR"),
    )
    assert watchlist_matches(comp, WatchlistConfig(), FX) is False
    assert watchlist_matches(comp, WatchlistConfig(countries=frozenset({"PL"})), FX)
    assert not watchlist_matches(comp, WatchlistConfig(countries=frozenset({"SE"})), FX)
    by_buyer = WatchlistConfig(buyer_identifiers=frozenset({"pl"}))
    assert watchlist_matches(comp, by_buyer, FX) is True
    by_category = WatchlistConfig(categories=frozenset({"space"}))
    assert watchlist_matches(comp, by_category, FX) is False
    big = WatchlistConfig(
        countries=frozenset({"PL"}), min_estimated_value_eur=Decimal("500000000")
    )
    assert watchlist_matches(comp, big, FX) is True
    bigger = WatchlistConfig(min_estimated_value_eur=Decimal("700000000"))
    assert watchlist_matches(comp, bigger, FX) is False
    awarded = WatchlistConfig(min_award_value_eur=Decimal("1"))
    assert watchlist_matches(comp, awarded, FX) is False

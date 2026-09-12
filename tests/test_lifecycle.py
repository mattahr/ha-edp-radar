from datetime import date
from decimal import Decimal

from custom_components.edp_radar.lifecycle import ProcedureIndex
from custom_components.edp_radar.models import Money, NoticeStage

from .factories import change_of, competition, make_notice, result


def test_competition_change_result_chain() -> None:
    comp = competition("c1", "p1", date(2026, 3, 1))
    change = change_of(comp, published=date(2026, 3, 20))
    res = result("r1", "p1", date(2026, 6, 15), value=Money(Decimal("900000"), "EUR"))
    index = ProcedureIndex.build([comp, change, res])
    assert len(index) == 1
    proc = index.procedures["p1"]
    assert proc.linked is True
    assert proc.first_competition == date(2026, 3, 1)
    assert proc.latest_competition is change  # latest version carries the data
    assert proc.first_result == date(2026, 6, 15)
    assert proc.results == (res,)
    assert proc.changes == (change,)
    assert proc.time_to_result_days == 106
    assert proc.estimated_value == Money(Decimal("1000000"), "EUR")
    assert proc.estimated_value_date == date(2026, 3, 20)
    assert index.competitions() == [change]
    assert index.results() == [res]
    assert index.changes == (change,)


def test_two_versions_of_a_competition_count_once() -> None:
    v1 = competition("c1", "p1", date(2026, 3, 1))
    v2 = make_notice(
        notice_id="c1",
        notice_version=2,
        procedure_id="p1",
        publication_date=date(2026, 3, 5),
    )
    index = ProcedureIndex.build([v2, v1])
    assert [n.notice_version for n in index.notices] == [2]
    proc = index.procedures["p1"]
    assert proc.first_competition == date(2026, 3, 1)
    assert proc.latest_competition is v2


def test_change_published_as_new_id_never_starts_a_competition() -> None:
    comp = competition("c1", "p1", date(2026, 3, 1))
    change = change_of(comp, published=date(2026, 3, 20), notice_id="c1-chg")
    index = ProcedureIndex.build([change])  # original outside the retention window
    proc = index.procedures["p1"]
    assert proc.first_competition is None
    assert proc.latest_competition is None
    assert proc.changes == (change,)
    assert index.originals == ()
    assert index.competitions() == []


def test_planning_competition_result_modification() -> None:
    plan = make_notice(
        notice_id="pl",
        stage=NoticeStage.PLANNING,
        publication_date=date(2026, 1, 10),
        estimated_value=Money(Decimal("5"), "EUR"),
    )
    comp = competition("c1", "p1", date(2026, 2, 1), estimated_value=None)
    res = result("r1", "p1", date(2026, 5, 1))
    mod = make_notice(
        notice_id="m1",
        stage=NoticeStage.MODIFICATION,
        publication_date=date(2026, 8, 1),
    )
    index = ProcedureIndex.build([plan, comp, res, mod])
    proc = index.procedures["p1"]
    assert proc.first_planning == date(2026, 1, 10)
    assert proc.first_competition == date(2026, 2, 1)
    assert proc.first_result == date(2026, 5, 1)
    assert proc.modifications == (mod,)
    assert proc.estimated_value == Money(Decimal("5"), "EUR")  # planning fallback
    assert proc.estimated_value_date == date(2026, 1, 10)


def test_result_without_known_competition_has_no_duration() -> None:
    res = result("r1", "p1", date(2026, 5, 1))
    proc = ProcedureIndex.build([res]).procedures["p1"]
    assert proc.first_competition is None
    assert proc.time_to_result_days is None
    assert proc.buyer.name == "FMV"


def test_missing_procedure_id_creates_unlinked_pseudo_procedures() -> None:
    a = competition("a", None, date(2026, 3, 1))
    b = result("b", None, date(2026, 6, 1))
    index = ProcedureIndex.build([a, b])
    assert set(index.procedures) == {"notice:a", "notice:b"}
    assert index.procedures["notice:a"].linked is False
    assert index.procedures["notice:b"].time_to_result_days is None


def test_union_of_reasons_and_categories_and_buyer_count() -> None:
    comp = competition("c1", "p1", date(2026, 3, 1), categories=("land_systems",))
    res = result(
        "r1",
        "p1",
        date(2026, 5, 1),
        categories=("cyber_it",),
        match_reasons=frozenset({"defence_cpv"}),
    )
    proc = ProcedureIndex.build([comp, res]).procedures["p1"]
    assert proc.categories == frozenset({"land_systems", "cyber_it"})
    assert proc.match_reasons == frozenset({"defence_buyer", "defence_cpv"})
    assert proc.buyer_count == 1
    assert proc.direct_awards == ()

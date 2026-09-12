from datetime import date
from decimal import Decimal
from typing import Any

from custom_components.edp_radar.models import (
    Buyer,
    ChangeInfo,
    Money,
    NoticeStage,
    ProcurementNotice,
    SubmissionStatistic,
    TenderStatistics,
    Winner,
    normalize_name,
)


def test_money_parse_rejects_missing_and_sentinels() -> None:
    assert Money.parse(None, "EUR") is None
    assert Money.parse("100", None) is None
    assert Money.parse("-1", "EUR") is None
    assert Money.parse("0", "EUR") is None
    assert Money.parse("abc", "EUR") is None
    assert Money.parse("1475225.00", "eur") == Money(Decimal("1475225.00"), "EUR")


def test_tender_counts_only_uses_tenders_code() -> None:
    stats = TenderStatistics(
        statistics=(
            SubmissionStatistic("tenders", 3),
            SubmissionStatistic("t-sme", 2),
            SubmissionStatistic("part-req", 7),
            SubmissionStatistic("tenders", 1),
        ),
        selection_statuses=("selec-w", "selec-w"),
        non_award_justifications=(),
        decision_dates=(),
    )
    assert stats.tender_counts == (3, 1)


def test_winner_identity_key_prefers_identifier() -> None:
    assert Winner("Saab AB", "556036-0793", "SE", "large").identity_key == "556036-0793"
    assert Winner("Saab  AB", None, "SE", None).identity_key == "SE:saab ab"
    assert Winner("Saab AB", None, None, None).identity_key == "??:saab ab"


def test_normalize_name() -> None:
    assert normalize_name("  Försvarets  Materielverk, FMV. ") == (
        "försvarets materielverk fmv"
    )


def _notice(**overrides: Any) -> ProcurementNotice:
    base: dict[str, Any] = dict(
        notice_id="n1",
        notice_version=1,
        publication_number="1-2026",
        publication_date=date(2026, 9, 1),
        procedure_id="p1",
        stage=NoticeStage.COMPETITION,
        notice_type="cn-standard",
        notice_subtype="16",
        title="Title",
        buyer=Buyer("FMV", ("202100-0340",), "SE", "cga", ("defence",), 1),
        legal_basis=("32014L0024",),
        cpv_codes=("35300000",),
        match_reasons=frozenset({"defence_buyer"}),
        categories=("other_defence",),
        procedure_type="open",
        contract_nature=("supplies",),
        estimated_value=Money(Decimal("100"), "SEK"),
        result_value=None,
        tender_statistics=None,
        winners=(),
        change=None,
        modification=None,
        source_url="https://ted.europa.eu/en/notice/-/detail/1-2026",
    )
    base.update(overrides)
    return ProcurementNotice(**base)


def test_round_trip_preserves_everything() -> None:
    notice = _notice(
        result_value=Money(Decimal("55600000"), "DKK"),
        tender_statistics=TenderStatistics(
            (SubmissionStatistic("tenders", 3),),
            ("selec-w",),
            ("no-rece",),
            (date(2026, 7, 21),),
        ),
        winners=(Winner("Element Logic", "29847096", "DK", "sme"),),
        change=ChangeInfo("update-add", "Deadline moved", "abc"),
    )
    data = notice.to_dict()
    assert data["publication_date"] == "2026-09-01"
    assert data["estimated_value"] == {"amount": "100", "currency": "SEK"}
    assert ProcurementNotice.from_dict(data) == notice


def test_properties() -> None:
    plain = _notice()
    assert plain.is_change is False
    assert plain.version_key == "n1:1"
    assert plain.award_date == date(2026, 9, 1)
    changed = _notice(change=ChangeInfo("cor-buy", None, None))
    assert changed.is_change is True
    decided = _notice(
        stage=NoticeStage.RESULT,
        tender_statistics=TenderStatistics((), (), (), (date(2026, 7, 21),)),
    )
    assert decided.award_date == date(2026, 7, 21)

"""Builders for deterministic metrics/lifecycle tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from custom_components.edp_radar.fx_rates import FxRateTable
from custom_components.edp_radar.models import (
    Buyer,
    ChangeInfo,
    Money,
    NoticeStage,
    ProcurementNotice,
    SubmissionStatistic,
    TenderStatistics,
    Winner,
)

FMV = Buyer("FMV", ("202100-0340",), "SE", "cga", ("defence",), 1)


def buyer(
    name: str, country: str, identifier: str | None = None, count: int = 1
) -> Buyer:
    identifiers = (identifier,) if identifier else ()
    return Buyer(name, identifiers, country, "cga", ("defence",), count)


def make_notice(**overrides: Any) -> ProcurementNotice:
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
        buyer=FMV,
        legal_basis=("32014L0024",),
        cpv_codes=("35400000",),
        match_reasons=frozenset({"defence_buyer"}),
        categories=("land_systems",),
        procedure_type="open",
        contract_nature=("supplies",),
        estimated_value=Money(Decimal("1000000"), "EUR"),
        result_value=None,
        tender_statistics=None,
        winners=(),
        change=None,
        modification=None,
        source_url=None,
        classification_rule_version="test",
    )
    base.update(overrides)
    if "publication_number" not in overrides:
        base["publication_number"] = f"{base['notice_id']}-{base['notice_version']}"
    return ProcurementNotice(**base)


def competition(
    notice_id: str, procedure_id: str | None, published: date, **overrides: Any
) -> ProcurementNotice:
    return make_notice(
        notice_id=notice_id,
        procedure_id=procedure_id,
        publication_date=published,
        stage=NoticeStage.COMPETITION,
        **overrides,
    )


def result(
    notice_id: str,
    procedure_id: str | None,
    published: date,
    *,
    value: Money | None = None,
    tenders: tuple[int, ...] = (),
    statuses: tuple[str, ...] = (),
    winners: tuple[Winner, ...] = (),
    decision_dates: tuple[date, ...] = (),
    **overrides: Any,
) -> ProcurementNotice:
    stats = None
    if tenders or statuses or decision_dates:
        stats = TenderStatistics(
            tuple(SubmissionStatistic("tenders", t) for t in tenders),
            statuses or tuple("selec-w" for _ in tenders),
            (),
            decision_dates,
        )
    return make_notice(
        notice_id=notice_id,
        procedure_id=procedure_id,
        publication_date=published,
        stage=NoticeStage.RESULT,
        estimated_value=None,
        result_value=value,
        tender_statistics=stats,
        winners=winners,
        **overrides,
    )


def change_of(
    notice: ProcurementNotice,
    *,
    published: date,
    version: int | None = None,
    notice_id: str | None = None,
    reason: str = "update-add",
) -> ProcurementNotice:
    """A change: same id with a higher version, or a new id (D3)."""
    if version is None:
        version = 1 if notice_id else notice.notice_version + 1
    return replace(
        notice,
        notice_id=notice_id or notice.notice_id,
        notice_version=version,
        publication_number=f"{notice_id or notice.notice_id}-chg",
        publication_date=published,
        change=ChangeInfo(reason, "changed", notice.notice_id),
    )


def flat_fx(rates: dict[str, str], start: date, end: date) -> FxRateTable:
    """The same rates on every day of [start, end] (weekends included)."""
    table = FxRateTable()
    day = start
    decimals = {c: Decimal(r) for c, r in rates.items()}
    while day <= end:
        table.add(day, decimals)
        day += timedelta(days=1)
    return table


def days_ago(today: date, days: int) -> date:
    return today - timedelta(days=days)

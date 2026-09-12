"""Procedure lifecycle index (plan §7, §38; addendum D3, D4)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from .models import Buyer, Money, NoticeStage, ProcurementNotice


@dataclass(frozen=True)
class ProcedureSummary:
    key: str
    procedure_id: str | None
    buyer: Buyer
    country: str | None
    match_reasons: frozenset[str]
    categories: frozenset[str]
    first_planning: date | None
    first_competition: date | None
    latest_competition: ProcurementNotice | None
    first_result: date | None
    results: tuple[ProcurementNotice, ...]
    changes: tuple[ProcurementNotice, ...]
    modifications: tuple[ProcurementNotice, ...]
    direct_awards: tuple[ProcurementNotice, ...]
    notices: tuple[ProcurementNotice, ...]

    @property
    def linked(self) -> bool:
        return self.procedure_id is not None

    def _value_source(self) -> ProcurementNotice | None:
        latest = self.latest_competition
        if latest is not None and latest.estimated_value:
            return latest
        for notice in self.notices:
            if notice.stage is NoticeStage.PLANNING and notice.estimated_value:
                return notice
        return None

    @property
    def estimated_value(self) -> Money | None:
        source = self._value_source()
        return source.estimated_value if source else None

    @property
    def estimated_value_date(self) -> date | None:
        source = self._value_source()
        return source.publication_date if source else None

    @property
    def time_to_result_days(self) -> int | None:
        """Days from first original competition to first original result (§17.3)."""
        if (
            not self.linked
            or self.first_competition is None
            or self.first_result is None
        ):
            return None
        return (self.first_result - self.first_competition).days

    @property
    def buyer_count(self) -> int:
        return max((n.buyer.count for n in self.notices), default=1)


def _sort_key(notice: ProcurementNotice) -> tuple[date, int]:
    return (notice.publication_date, notice.notice_version)


class ProcedureIndex:
    """Groups stored notice versions into procedures; O(n) to build."""

    def __init__(
        self,
        procedures: dict[str, ProcedureSummary],
        notices: tuple[ProcurementNotice, ...],
        originals: tuple[ProcurementNotice, ...],
        changes: tuple[ProcurementNotice, ...],
    ) -> None:
        self._procedures = procedures
        self.notices = notices
        self.originals = originals
        self.changes = changes

    def __len__(self) -> int:
        return len(self._procedures)

    @property
    def procedures(self) -> Mapping[str, ProcedureSummary]:
        return self._procedures

    def results(self) -> list[ProcurementNotice]:
        return [n for n in self.originals if n.stage is NoticeStage.RESULT]

    def competitions(self) -> list[ProcurementNotice]:
        return [n for n in self.originals if n.stage is NoticeStage.COMPETITION]

    @classmethod
    def build(cls, notices: Iterable[ProcurementNotice]) -> ProcedureIndex:
        versions_by_id: dict[str, list[ProcurementNotice]] = defaultdict(list)
        for notice in notices:
            versions_by_id[notice.notice_id].append(notice)

        latest: dict[str, ProcurementNotice] = {}
        original_ids: set[str] = set()
        all_changes: list[ProcurementNotice] = []
        for notice_id, versions in versions_by_id.items():
            versions.sort(key=lambda n: n.notice_version)
            latest[notice_id] = versions[-1]
            if any(not v.is_change for v in versions):
                original_ids.add(notice_id)
            all_changes.extend(v for v in versions if v.is_change)

        groups: dict[str, list[ProcurementNotice]] = defaultdict(list)
        for versions in versions_by_id.values():
            for version in versions:
                key = version.procedure_id or f"notice:{version.notice_id}"
                groups[key].append(version)

        procedures: dict[str, ProcedureSummary] = {}
        for key, versions in groups.items():
            latest_notices = sorted(
                {v.notice_id: latest[v.notice_id] for v in versions}.values(),
                key=_sort_key,
            )
            originals = [
                v for v in versions if v.notice_id in original_ids and not v.is_change
            ]
            competitions = [
                n
                for n in latest_notices
                if n.stage is NoticeStage.COMPETITION and n.notice_id in original_ids
            ]
            latest_competition = (
                max(competitions, key=_sort_key) if competitions else None
            )
            anchor = latest_competition or latest_notices[0]
            procedures[key] = ProcedureSummary(
                key=key,
                procedure_id=versions[0].procedure_id,
                buyer=anchor.buyer,
                country=anchor.buyer.country,
                match_reasons=frozenset().union(
                    *(n.match_reasons for n in latest_notices)
                ),
                categories=frozenset(c for n in latest_notices for c in n.categories),
                first_planning=_first_date(originals, NoticeStage.PLANNING),
                first_competition=_first_date(originals, NoticeStage.COMPETITION),
                latest_competition=latest_competition,
                first_result=_first_date(originals, NoticeStage.RESULT),
                results=tuple(
                    n
                    for n in latest_notices
                    if n.stage is NoticeStage.RESULT and n.notice_id in original_ids
                ),
                changes=tuple(
                    sorted((v for v in versions if v.is_change), key=_sort_key)
                ),
                modifications=tuple(
                    n for n in latest_notices if n.stage is NoticeStage.MODIFICATION
                ),
                direct_awards=tuple(
                    n for n in latest_notices if n.stage is NoticeStage.DIRECT_AWARD
                ),
                notices=tuple(latest_notices),
            )

        latest_sorted = tuple(sorted(latest.values(), key=_sort_key))
        originals_sorted = tuple(
            n for n in latest_sorted if n.notice_id in original_ids
        )
        return cls(
            procedures,
            latest_sorted,
            originals_sorted,
            tuple(sorted(all_changes, key=_sort_key)),
        )


def _first_date(originals: list[ProcurementNotice], stage: NoticeStage) -> date | None:
    dates = [n.publication_date for n in originals if n.stage is stage]
    return min(dates) if dates else None

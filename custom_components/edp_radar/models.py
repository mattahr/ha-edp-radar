"""Normalized, Home-Assistant-independent domain models (plan §9, addendum D3/D4)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Self

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_name(name: str) -> str:
    """Casefold, strip punctuation and collapse whitespace for conservative matching."""
    return _WHITESPACE.sub(" ", _PUNCTUATION.sub("", name.casefold())).strip()


class NoticeStage(StrEnum):
    """Lifecycle family derived from the TED ``form-type`` (D3)."""

    PLANNING = "planning"
    COMPETITION = "competition"
    RESULT = "result"
    DIRECT_AWARD = "direct_award"
    MODIFICATION = "modification"
    COMPLETION = "completion"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class Money:
    """An amount in its original currency. EUR normalization happens in metrics."""

    amount: Decimal
    currency: str

    @classmethod
    def parse(
        cls, amount: str | int | float | None, currency: str | None
    ) -> Money | None:
        """Return Money only for a positive amount with a 3-letter currency (D20)."""
        if amount is None or currency is None or len(currency) != 3:
            return None
        try:
            value = Decimal(str(amount))
        except InvalidOperation:
            return None
        if not value.is_finite() or value <= 0:
            return None
        return cls(value, currency.upper())

    def to_dict(self) -> dict[str, str]:
        return {"amount": str(self.amount), "currency": self.currency}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Money:
        return cls(Decimal(data["amount"]), data["currency"])


@dataclass(frozen=True, slots=True)
class Buyer:
    """Primary buyer plus notice-wide buyer facts (arrays are not aligned, D5)."""

    name: str | None
    identifiers: tuple[str, ...]
    country: str | None
    legal_type: str | None
    main_activities: tuple[str, ...]
    count: int


@dataclass(frozen=True, slots=True)
class Winner:
    name: str | None
    identifier: str | None
    country: str | None
    size: str | None

    @property
    def identity_key(self) -> str:
        """Conservative identity: stable identifier, else country + normalized name."""
        if self.identifier:
            return self.identifier
        return f"{self.country or '??'}:{normalize_name(self.name or '')}"


@dataclass(frozen=True, slots=True)
class SubmissionStatistic:
    type_code: str
    value: int


@dataclass(frozen=True, slots=True)
class TenderStatistics:
    statistics: tuple[SubmissionStatistic, ...]
    selection_statuses: tuple[str, ...]
    non_award_justifications: tuple[str, ...]
    decision_dates: tuple[date, ...]

    @property
    def tender_counts(self) -> tuple[int, ...]:
        """One entry per lot result whose code is the total ``tenders`` (D7)."""
        return tuple(s.value for s in self.statistics if s.type_code == "tenders")


@dataclass(frozen=True, slots=True)
class ChangeInfo:
    reason_code: str | None
    description: str | None
    changed_notice_id: str | None


@dataclass(frozen=True, slots=True)
class ModificationInfo:
    description: str | None
    justifications: tuple[str, ...]
    previous_notice_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProcurementNotice:
    """One published notice version, normalized (plan §9)."""

    notice_id: str
    notice_version: int
    publication_number: str
    publication_date: date
    procedure_id: str | None
    stage: NoticeStage
    notice_type: str | None
    notice_subtype: str | None
    title: str | None
    buyer: Buyer
    legal_basis: tuple[str, ...]
    cpv_codes: tuple[str, ...]
    match_reasons: frozenset[str]
    categories: tuple[str, ...]
    procedure_type: str | None
    contract_nature: tuple[str, ...]
    estimated_value: Money | None
    result_value: Money | None
    tender_statistics: TenderStatistics | None
    winners: tuple[Winner, ...]
    change: ChangeInfo | None
    modification: ModificationInfo | None
    source_url: str | None
    classification_rule_version: str | None = field(default=None)

    @property
    def is_change(self) -> bool:
        return self.change is not None

    @property
    def version_key(self) -> str:
        return f"{self.notice_id}:{self.notice_version}"

    @property
    def award_date(self) -> date:
        """Date used for FX normalization of result values (plan §10)."""
        if self.tender_statistics and self.tender_statistics.decision_dates:
            return min(self.tender_statistics.decision_dates)
        return self.publication_date

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["publication_date"] = self.publication_date.isoformat()
        data["stage"] = self.stage.value
        data["match_reasons"] = sorted(self.match_reasons)
        data["estimated_value"] = (
            self.estimated_value.to_dict() if self.estimated_value else None
        )
        data["result_value"] = (
            self.result_value.to_dict() if self.result_value else None
        )
        if self.tender_statistics:
            data["tender_statistics"]["decision_dates"] = [
                d.isoformat() for d in self.tender_statistics.decision_dates
            ]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        kwargs: dict[str, Any] = {f.name: data.get(f.name) for f in fields(cls)}
        kwargs["publication_date"] = date.fromisoformat(data["publication_date"])
        kwargs["stage"] = NoticeStage(data["stage"])
        kwargs["buyer"] = Buyer(
            name=data["buyer"]["name"],
            identifiers=tuple(data["buyer"]["identifiers"]),
            country=data["buyer"]["country"],
            legal_type=data["buyer"]["legal_type"],
            main_activities=tuple(data["buyer"]["main_activities"]),
            count=data["buyer"]["count"],
        )
        kwargs["legal_basis"] = tuple(data["legal_basis"])
        kwargs["cpv_codes"] = tuple(data["cpv_codes"])
        kwargs["match_reasons"] = frozenset(data["match_reasons"])
        kwargs["categories"] = tuple(data["categories"])
        kwargs["contract_nature"] = tuple(data["contract_nature"])
        kwargs["estimated_value"] = (
            Money.from_dict(data["estimated_value"])
            if data.get("estimated_value")
            else None
        )
        kwargs["result_value"] = (
            Money.from_dict(data["result_value"]) if data.get("result_value") else None
        )
        ts = data.get("tender_statistics")
        kwargs["tender_statistics"] = (
            TenderStatistics(
                statistics=tuple(SubmissionStatistic(**s) for s in ts["statistics"]),
                selection_statuses=tuple(ts["selection_statuses"]),
                non_award_justifications=tuple(ts["non_award_justifications"]),
                decision_dates=tuple(
                    date.fromisoformat(d) for d in ts["decision_dates"]
                ),
            )
            if ts
            else None
        )
        kwargs["winners"] = tuple(Winner(**w) for w in data.get("winners") or ())
        change = data.get("change")
        kwargs["change"] = ChangeInfo(**change) if change else None
        modification = data.get("modification")
        kwargs["modification"] = (
            ModificationInfo(
                description=modification["description"],
                justifications=tuple(modification["justifications"]),
                previous_notice_ids=tuple(modification["previous_notice_ids"]),
            )
            if modification
            else None
        )
        return cls(**kwargs)

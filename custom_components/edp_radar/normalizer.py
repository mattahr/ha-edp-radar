"""Raw TED search results → ProcurementNotice (plan §8–9; addendum §1.1, D3, D6, D7)."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any

from .const import TED_NOTICE_URL, TITLE_MAX_LENGTH, to_alpha2
from .models import (
    Buyer,
    ChangeInfo,
    ModificationInfo,
    Money,
    NoticeStage,
    ProcurementNotice,
    SubmissionStatistic,
    TenderStatistics,
    Winner,
)
from .taxonomy import Taxonomy, normalize_cpv

_LOGGER = logging.getLogger(__name__)

REQUESTED_FIELDS: tuple[str, ...] = (
    # identity and lifecycle
    "publication-number",
    "publication-date",
    "notice-identifier",
    "notice-version",
    "notice-type",
    "notice-subtype",
    "form-type",
    "procedure-identifier",
    "previous-notice-id-proc",
    "change-notice-version-identifier",
    # procedure
    "title-proc",
    "internal-identifier-proc",
    "procedure-type",
    "contract-nature",
    # buyer
    "buyer-name",
    "buyer-identifier",
    "buyer-country",
    "buyer-legal-type",
    "authority-main-activity",
    # legal / classification
    "legal-basis",
    "classification-cpv",
    "main-classification-proc",
    "additional-classification-proc",
    "main-classification-lot",
    "additional-classification-lot",
    # estimated value
    "estimated-value-proc",
    "estimated-value-cur-proc",
    "estimated-value-lot",
    "estimated-value-cur-lot",
    # results
    "result-value-notice",
    "result-value-cur-notice",
    "result-value-lot",
    "result-value-cur-lot",
    "winner-name",
    "winner-identifier",
    "winner-country",
    "winner-size",
    "winner-decision-date",
    "winner-selection-status",
    "received-submissions-type-code",
    "received-submissions-type-val",
    "non-award-justification",
    "tender-value",
    "tender-value-cur",
    # changes
    "change-description",
    "change-reason-code",
    "change-reason-description",
    # contract modifications
    "modification-description",
    "modification-justification",
    "modification-reason-description",
    "modification-previous-notice-identifier",
    # deadlines
    "deadline-receipt-tender-date-lot",
)

PREFERRED_LANGUAGES = ("eng", "swe")

_STAGE_BY_FORM_TYPE: dict[str, NoticeStage] = {
    "planning": NoticeStage.PLANNING,
    "competition": NoticeStage.COMPETITION,
    "result": NoticeStage.RESULT,
    "dir-awa-pre": NoticeStage.DIRECT_AWARD,
    "cont-modif": NoticeStage.MODIFICATION,
    "compl": NoticeStage.COMPLETION,
}

_CPV_FIELDS = (
    "classification-cpv",
    "main-classification-proc",
    "additional-classification-proc",
    "main-classification-lot",
    "additional-classification-lot",
)


class NormalizationError(ValueError):
    """The notice lacks the identity fields required by plan §7."""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def as_strings(value: Any) -> tuple[str, ...]:
    """Flatten a scalar-or-list field into non-empty strings."""
    return tuple(str(v) for v in _as_list(value) if v is not None and str(v) != "")


def _language(value: Mapping[str, Any]) -> str | None:
    for lang in PREFERRED_LANGUAGES:
        if lang in value:
            return lang
    return next(iter(value), None)


def first_text(value: Any) -> str | None:
    """First non-empty text of a multilingual, list or scalar field."""
    if isinstance(value, Mapping):
        lang = _language(value)
        return first_text(value[lang]) if lang is not None else None
    if isinstance(value, list):
        return first_text(value[0]) if value else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _texts(value: Any) -> tuple[str, ...]:
    """All texts of a multilingual list field in one language."""
    if isinstance(value, Mapping):
        lang = _language(value)
        return as_strings(value[lang]) if lang is not None else ()
    return as_strings(value)


def parse_ted_date(value: Any) -> date | None:
    """Parse ``2026-09-11+02:00`` / ``2026-07-21Z`` into a date."""
    text = first_text(value)
    if text is None or len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _dates(value: Any) -> tuple[date, ...]:
    return tuple(
        d for d in (parse_ted_date(v) for v in _as_list(value)) if d is not None
    )


def _int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except TypeError, ValueError:
        return None


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _lot_money(values: Sequence[str], currencies: Sequence[str]) -> Money | None:
    """Sum lot values only when the structure is unambiguous (D6)."""
    if not values or not currencies:
        return None
    if len(currencies) == 1:
        pairs = [(v, currencies[0]) for v in values]
    elif len(currencies) == len(values):
        pairs = list(zip(values, currencies, strict=True))
    else:
        return None
    monies: list[Money] = []
    for value, currency in pairs:
        money = Money.parse(value, currency)
        if money is None:
            return None
        monies.append(money)
    currency_set = {m.currency for m in monies}
    if len(currency_set) != 1:
        return None
    total = sum((m.amount for m in monies), start=monies[0].amount * 0)
    return Money(total, currency_set.pop())


def _estimated_value(raw: Mapping[str, Any]) -> Money | None:
    procedure = Money.parse(
        first_text(raw.get("estimated-value-proc")),
        first_text(raw.get("estimated-value-cur-proc")),
    )
    if procedure is not None:
        return procedure
    return _lot_money(
        as_strings(raw.get("estimated-value-lot")),
        as_strings(raw.get("estimated-value-cur-lot")),
    )


def _result_value(raw: Mapping[str, Any]) -> Money | None:
    notice = Money.parse(
        first_text(raw.get("result-value-notice")),
        first_text(raw.get("result-value-cur-notice")),
    )
    if notice is not None:
        return notice
    return _lot_money(
        as_strings(raw.get("result-value-lot")),
        as_strings(raw.get("result-value-cur-lot")),
    )


def _buyer(raw: Mapping[str, Any]) -> Buyer:
    names = _texts(raw.get("buyer-name"))
    countries = as_strings(raw.get("buyer-country"))
    legal_types = as_strings(raw.get("buyer-legal-type"))
    return Buyer(
        name=names[0] if names else None,
        identifiers=_unique(as_strings(raw.get("buyer-identifier"))),
        country=to_alpha2(countries[0]) if countries else None,
        legal_type=legal_types[0] if legal_types else None,
        main_activities=_unique(as_strings(raw.get("authority-main-activity"))),
        count=max(len(names), len(countries), 1),
    )


def _winners(raw: Mapping[str, Any]) -> tuple[Winner, ...]:
    """Unique winners by name; organisation-level arrays are attached conservatively.

    ``winner-name`` is repeated once per winning tender (lot × winner) while
    ``winner-identifier``/``-country``/``-size`` are listed once per organisation
    record, so the arrays only align when their lengths match exactly. A
    single-valued array (all winners from ``POL``) may be collapsed; identifiers
    never are (plan §41).
    """
    names = _unique(_texts(raw.get("winner-name")))
    identifiers = as_strings(raw.get("winner-identifier"))
    countries = as_strings(raw.get("winner-country"))
    sizes = as_strings(raw.get("winner-size"))
    count = len(names)
    if count == 0:
        return ()

    def aligned(values: tuple[str, ...], index: int, *, collapse: bool) -> str | None:
        if len(values) == count:
            return values[index]
        if collapse and values and len(set(values)) == 1:
            return values[0]
        return None

    winners = []
    for index, name in enumerate(names):
        country = aligned(countries, index, collapse=True)
        winners.append(
            Winner(
                name=name,
                identifier=aligned(identifiers, index, collapse=False),
                country=to_alpha2(country) if country else None,
                size=aligned(sizes, index, collapse=True),
            )
        )
    return tuple(winners)


def _tender_statistics(raw: Mapping[str, Any]) -> TenderStatistics | None:
    codes = as_strings(raw.get("received-submissions-type-code"))
    values = as_strings(raw.get("received-submissions-type-val"))
    statistics: tuple[SubmissionStatistic, ...] = ()
    if codes and len(codes) == len(values):
        pairs = zip(codes, values, strict=True)
        parsed = [(code, _int(value)) for code, value in pairs]
        statistics = tuple(
            SubmissionStatistic(code, value)
            for code, value in parsed
            if value is not None and value >= 0
        )
    statuses = as_strings(raw.get("winner-selection-status"))
    justifications = as_strings(raw.get("non-award-justification"))
    decision_dates = _dates(raw.get("winner-decision-date"))
    if not (statistics or statuses or justifications or decision_dates):
        return None
    return TenderStatistics(statistics, statuses, justifications, decision_dates)


def _change(raw: Mapping[str, Any]) -> ChangeInfo | None:
    reason = first_text(raw.get("change-reason-code"))
    description = first_text(raw.get("change-description")) or first_text(
        raw.get("change-reason-description")
    )
    if reason is None and description is None:
        return None
    return ChangeInfo(
        reason, description, first_text(raw.get("change-notice-version-identifier"))
    )


def _modification(raw: Mapping[str, Any]) -> ModificationInfo | None:
    description = first_text(raw.get("modification-description")) or first_text(
        raw.get("modification-reason-description")
    )
    justifications = _unique(as_strings(raw.get("modification-justification")))
    previous = _unique(as_strings(raw.get("modification-previous-notice-identifier")))
    if description is None and not justifications and not previous:
        return None
    return ModificationInfo(description, justifications, previous)


def _cpv_codes(raw: Mapping[str, Any]) -> tuple[str, ...]:
    codes: list[str] = []
    for field in _CPV_FIELDS:
        for value in as_strings(raw.get(field)):
            code = normalize_cpv(value)
            if code is not None:
                codes.append(code)
    return _unique(codes)


def normalize_notice(raw: Mapping[str, Any], taxonomy: Taxonomy) -> ProcurementNotice:
    """Normalize one raw search hit. Raises NormalizationError on missing identity."""
    notice_id = first_text(raw.get("notice-identifier"))
    publication_number = first_text(raw.get("publication-number"))
    publication_date = parse_ted_date(raw.get("publication-date"))
    version = _int(raw.get("notice-version"))
    form_type = first_text(raw.get("form-type"))
    if not (notice_id and publication_number and publication_date and form_type):
        raise NormalizationError(
            f"notice {publication_number or '?'} lacks identity fields"
        )
    if version is None:
        raise NormalizationError(f"notice {publication_number} lacks notice-version")

    buyer = _buyer(raw)
    legal_basis = _unique(as_strings(raw.get("legal-basis")))
    cpv_codes = _cpv_codes(raw)
    title = first_text(raw.get("title-proc"))
    if title is not None and len(title) > TITLE_MAX_LENGTH:
        title = title[: TITLE_MAX_LENGTH - 1] + "…"

    return ProcurementNotice(
        notice_id=notice_id,
        notice_version=version,
        publication_number=publication_number,
        publication_date=publication_date,
        procedure_id=first_text(raw.get("procedure-identifier")),
        stage=_STAGE_BY_FORM_TYPE.get(form_type, NoticeStage.OTHER),
        notice_type=first_text(raw.get("notice-type")),
        notice_subtype=first_text(raw.get("notice-subtype")),
        title=title,
        buyer=buyer,
        legal_basis=legal_basis,
        cpv_codes=cpv_codes,
        match_reasons=taxonomy.match_reasons(
            activities=buyer.main_activities,
            legal_basis=legal_basis,
            cpv_codes=cpv_codes,
        ),
        categories=taxonomy.classify(cpv_codes),
        procedure_type=first_text(raw.get("procedure-type")),
        contract_nature=_unique(as_strings(raw.get("contract-nature"))),
        estimated_value=_estimated_value(raw),
        result_value=_result_value(raw),
        tender_statistics=_tender_statistics(raw),
        winners=_winners(raw),
        change=_change(raw),
        modification=_modification(raw),
        source_url=TED_NOTICE_URL.format(publication_number=publication_number),
        classification_rule_version=taxonomy.version,
    )


def normalize_many(
    raws: Iterable[Mapping[str, Any]], taxonomy: Taxonomy
) -> tuple[list[ProcurementNotice], int]:
    """Normalize a batch, skipping malformed notices and counting them (plan §43)."""
    notices: list[ProcurementNotice] = []
    errors = 0
    for raw in raws:
        try:
            notices.append(normalize_notice(raw, taxonomy))
        except NormalizationError as err:
            errors += 1
            _LOGGER.warning("Skipping malformed TED notice: %s", err)
    return notices, errors

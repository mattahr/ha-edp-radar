"""Country purchasing model: which countries buy the most defence materiel.

Phase 2 plan (docs/ha-edp-radar_PHASE2_COUNTRY_PURCHASING.md). A *purchase* is
the Notice Value (BT-161) of an awarded, non-framework result notice, counted
once per notice and converted to EUR at the award date (§4, §13). Framework
ceilings (§5), estimates, non-awarded procedures (§33) and implausible values
(§14) are never purchases; every exclusion is counted and the excluded records
stay traceable. The purchasing country is the buyer country (§6); a notice
with buyers from several countries is attributed to ``MULTI`` once (§7).

Nothing here imports Home Assistant; every function is deterministic.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from .const import (
    GROWTH_MIN_PROCEDURES,
    GROWTH_MIN_VALUE_EUR,
    PURCHASING_LARGEST_AWARDS_LIMIT,
    PURCHASING_MONTHS,
    PURCHASING_PERIOD_DAYS,
    PURCHASING_SECONDARY_PERIODS,
    SUSPICIOUS_ABSOLUTE_EUR,
    SUSPICIOUS_ESTIMATE_RATIO,
    SUSPICIOUS_REFERENCE_MIN,
    SUSPICIOUS_TENDER_RATIO,
    UNVERIFIED_LARGE_EUR,
)
from .fx_rates import FxRateTable
from .lifecycle import ProcedureIndex
from .models import (
    AWARD_DATE_BASIS_DECISION,
    Money,
    NoticeStage,
    ProcurementNotice,
)
from .periods import (
    Window,
    current_window,
    format_eur,
    pct,
    pct_change,
    previous_window,
    value_in_eur,
)
from .taxonomy import Taxonomy

MULTI_COUNTRY = "MULTI"
UNKNOWN_COUNTRY = "??"
PSEUDO_COUNTRIES = frozenset({MULTI_COUNTRY, UNKNOWN_COUNTRY})
UNCLASSIFIED = "unclassified"
UNCLASSIFIED_LABEL = "Unclassified"
SOURCE_NOTICE_VALUE = "result-value-notice"
STATUS_WINNER_SELECTED = "selec-w"
TEXT_TOP_BUYERS = 5
TEXT_CATEGORIES = 3

FLAG_FRAMEWORK = "framework"
FLAG_UNCONVERTIBLE = "unconvertible_currency"
FLAG_ABOVE_CAP = "above_absolute_cap"
FLAG_EXCEEDS_ESTIMATE = "exceeds_estimate"
FLAG_EXCEEDS_TENDERS = "exceeds_tender_values"
FLAG_DUPLICATE_VALUE = "duplicate_value_in_procedure"
FLAG_UNVERIFIED_LARGE = "unverified_large"
# Internal contradictions quarantine a value; ``unverified_large`` only marks it.
SUSPICIOUS_FLAGS = frozenset(
    {FLAG_ABOVE_CAP, FLAG_EXCEEDS_ESTIMATE, FLAG_EXCEEDS_TENDERS, FLAG_DUPLICATE_VALUE}
)


class ResultKind(StrEnum):
    """What a result notice reports (§33: non-award is EUR 0, not unknown)."""

    AWARDED = "awarded"
    NOT_AWARDED = "not_awarded"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------- per notice


def classify_result(notice: ProcurementNotice) -> ResultKind:
    """Awarded when any lot selected a winner (or winners/value are reported)."""
    if notice.stage is not NoticeStage.RESULT:
        return ResultKind.UNKNOWN
    stats = notice.tender_statistics
    statuses = stats.selection_statuses if stats else ()
    if STATUS_WINNER_SELECTED in statuses or notice.winners:
        return ResultKind.AWARDED
    if statuses:
        return ResultKind.NOT_AWARDED
    if notice.result_value is not None:
        return ResultKind.AWARDED
    return ResultKind.UNKNOWN


def attribute_country(notice: ProcurementNotice) -> str | None:
    """Buyer country (alpha-2), ``MULTI`` for joint procurement, None if missing."""
    countries = notice.buyer.countries
    if not countries:
        return None
    if len(countries) == 1:
        return countries[0]
    return MULTI_COUNTRY


@dataclass(frozen=True)
class AwardedValue:
    """The awarded value of one result notice and how it was derived (§35 step 2)."""

    money: Money | None
    value_eur: Decimal | None
    source: str | None
    date: date
    date_basis: str
    flags: tuple[str, ...]

    @property
    def suspicious(self) -> bool:
        return bool(SUSPICIOUS_FLAGS.intersection(self.flags))

    @property
    def usable(self) -> bool:
        return self.value_eur is not None and not self.suspicious


def extract_awarded_value(
    notice: ProcurementNotice, fx: FxRateTable, *, estimate: Money | None = None
) -> AwardedValue:
    """Notice Value once, in EUR at the award date, with plausibility flags.

    ``estimate`` is the procedure's estimated value. Values entered ×1000 are
    the dominant error in the profiled data, so an award that contradicts its
    own procedure is quarantined: more than ``SUSPICIOUS_ESTIMATE_RATIO`` times
    a real estimate (placeholders such as ``1`` or ``100`` are ignored), or —
    unless a real estimate corroborates it — more than
    ``SUSPICIOUS_TENDER_RATIO`` times the notice's own winning tenders. A large
    award that no real estimate corroborates is kept but marked
    ``unverified_large``.
    """
    on = notice.award_date
    basis = notice.award_date_basis
    if notice.is_framework:
        return AwardedValue(None, None, None, on, basis, (FLAG_FRAMEWORK,))
    money = notice.result_value
    if money is None:
        return AwardedValue(None, None, None, on, basis, ())
    flags: list[str] = []
    eur = value_in_eur(money, on, fx)
    if eur is None:
        flags.append(FLAG_UNCONVERTIBLE)
    elif eur > SUSPICIOUS_ABSOLUTE_EUR:
        flags.append(FLAG_ABOVE_CAP)
    comparable = _comparable(estimate, money)
    corroborated = False
    if comparable and estimate is not None:
        if money.amount > estimate.amount * SUSPICIOUS_ESTIMATE_RATIO:
            flags.append(FLAG_EXCEEDS_ESTIMATE)
        else:
            corroborated = True
    tenders = notice.tender_value_total
    if (
        not corroborated
        and _comparable(tenders, money)
        and tenders is not None
        and money.amount > tenders.amount * SUSPICIOUS_TENDER_RATIO
    ):
        flags.append(FLAG_EXCEEDS_TENDERS)
    if not flags and eur is not None and eur >= UNVERIFIED_LARGE_EUR and not comparable:
        flags.append(FLAG_UNVERIFIED_LARGE)
    return AwardedValue(money, eur, SOURCE_NOTICE_VALUE, on, basis, tuple(flags))


def _comparable(reference: Money | None, money: Money) -> bool:
    """A real (non-placeholder) reference amount in the award's currency."""
    return (
        reference is not None
        and reference.currency == money.currency
        and reference.amount >= SUSPICIOUS_REFERENCE_MIN
    )


def primary_category(notice: ProcurementNotice, taxonomy: Taxonomy) -> str:
    """Category of the main procedure CPV (the first stored code), else unclassified.

    One category per award keeps the country/category split summing to 100 %.
    """
    if notice.cpv_codes:
        categories = taxonomy.classify((notice.cpv_codes[0],))
        if categories:
            return categories[0]
    return UNCLASSIFIED


@dataclass(frozen=True)
class Award:
    """One awarded result, traceable to its TED notice (§22)."""

    publication_number: str
    notice_id: str
    procedure_id: str | None
    title: str | None
    buyer: str | None
    country: str | None
    date: date
    date_basis: str
    amount: Decimal | None
    currency: str | None
    value_eur: Decimal | None
    primary_category: str
    categories: tuple[str, ...]
    source_url: str | None
    flags: tuple[str, ...]


@dataclass(frozen=True)
class _Result:
    notice: ProcurementNotice
    kind: ResultKind
    country: str | None
    value: AwardedValue
    primary_category: str

    @property
    def country_key(self) -> str:
        return self.country or UNKNOWN_COUNTRY

    @property
    def procedure_key(self) -> str:
        return self.notice.procedure_id or f"notice:{self.notice.notice_id}"

    def award(self) -> Award:
        notice, value = self.notice, self.value
        return Award(
            publication_number=notice.publication_number,
            notice_id=notice.notice_id,
            procedure_id=notice.procedure_id,
            title=notice.title,
            buyer=notice.buyer.name,
            country=self.country,
            date=value.date,
            date_basis=value.date_basis,
            amount=value.money.amount if value.money else None,
            currency=value.money.currency if value.money else None,
            value_eur=value.value_eur,
            primary_category=self.primary_category,
            categories=notice.categories,
            source_url=notice.source_url,
            flags=value.flags,
        )


# --------------------------------------------------------------------- summaries


@dataclass(frozen=True)
class CategoryShare:
    category_id: str
    label: str
    value_eur: Decimal
    awards: int
    share_pct: float | None


@dataclass(frozen=True)
class CountryPurchaseSummary:
    """One country (or ``MULTI``/``??``) in one period (§15, §29, §30).

    ``award_value_eur`` is the sum of usable values; ``None`` means the country
    reported awards but none with a usable value (unknown, not zero); ``0``
    means no award was reported in the period.
    """

    country: str
    window: Window
    award_value_eur: Decimal | None
    award_count: int
    valued_awards: int
    framework_results: int
    non_awarded_results: int
    suspicious_results: int
    unconvertible_results: int
    unverified_large_results: int
    unverified_large_value_eur: Decimal | None
    decision_date_awards: int
    previous_value_eur: Decimal | None
    previous_award_count: int
    top_categories: tuple[CategoryShare, ...]
    largest_awards: tuple[Award, ...]

    @property
    def value_coverage_pct(self) -> float | None:
        return pct(self.valued_awards, self.award_count)

    @property
    def change_eur(self) -> Decimal | None:
        if self.award_value_eur is None or self.previous_value_eur is None:
            return None
        return self.award_value_eur - self.previous_value_eur

    @property
    def change_pct(self) -> float | None:
        return pct_change(self.award_value_eur, self.previous_value_eur)

    @property
    def unclassified_share_pct(self) -> float | None:
        if not self.award_value_eur:
            return None
        for share in self.top_categories:
            if share.category_id == UNCLASSIFIED:
                return share.share_pct
        return 0.0


@dataclass(frozen=True)
class CountryRank:
    rank: int
    country: str
    summary: CountryPurchaseSummary
    share_pct: float | None


@dataclass(frozen=True)
class EuropeSummary:
    """The whole ingested market in one period (§16, §19)."""

    window: Window
    total_value_eur: Decimal | None
    attributable_value_eur: Decimal | None
    joint_value_eur: Decimal | None
    unknown_country_value_eur: Decimal | None
    previous_total_value_eur: Decimal | None
    award_count: int
    valued_awards: int
    framework_results: int
    non_awarded_results: int
    suspicious_results: int
    unverified_large_results: int
    countries_with_value: int
    countries_active: int
    largest_buyer: CountryRank | None
    top_categories: tuple[CategoryShare, ...]
    largest_awards: tuple[Award, ...]

    @property
    def change_pct(self) -> float | None:
        return pct_change(self.total_value_eur, self.previous_total_value_eur)

    @property
    def value_coverage_pct(self) -> float | None:
        return pct(self.valued_awards, self.award_count)


@dataclass(frozen=True)
class PurchasingPeriod:
    """Every country summary, the ranking and the European total for one window."""

    window: Window
    countries: Mapping[str, CountryPurchaseSummary]
    ranking: tuple[CountryRank, ...]
    growth: tuple[CountryRank, ...]
    europe: EuropeSummary
    unranked: tuple[str, ...]

    def rank_of(self, country: str) -> CountryRank | None:
        for entry in self.ranking:
            if entry.country == country:
                return entry
        return None


@dataclass(frozen=True)
class MonthlyValue:
    month: str
    value_eur: Decimal | None
    awards: int
    valued_awards: int


@dataclass(frozen=True)
class PurchasingModel:
    today: date
    primary: PurchasingPeriod
    secondary: Mapping[int, PurchasingPeriod]
    quarantined: tuple[Award, ...]
    monthly: Mapping[str, tuple[MonthlyValue, ...]]

    def monthly_series(self, country: str) -> tuple[MonthlyValue, ...]:
        return self.monthly.get(country, ())


# --------------------------------------------------------------------- aggregation


def _share(part: Decimal, total: Decimal | None) -> float | None:
    if not total:
        return None
    return float((part / total * 100).quantize(Decimal("0.1"), ROUND_HALF_UP))


def _sum_usable(results: Iterable[_Result]) -> Decimal | None:
    total = Decimal(0)
    valued = 0
    for r in results:
        if r.value.usable:
            total += r.value.value_eur or Decimal(0)
            valued += 1
    return total if valued else None


def _value_or_zero(awarded: Sequence[_Result]) -> Decimal | None:
    """Sum of usable values; 0 when nothing was awarded; None when unknown (§30)."""
    if not awarded:
        return Decimal(0)
    return _sum_usable(awarded)


def _categories(
    usable: Sequence[_Result], total: Decimal | None, taxonomy: Taxonomy
) -> tuple[CategoryShare, ...]:
    values: dict[str, Decimal] = defaultdict(Decimal)
    counts: dict[str, int] = defaultdict(int)
    for r in usable:
        values[r.primary_category] += r.value.value_eur or Decimal(0)
        counts[r.primary_category] += 1
    ordered = sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))
    return tuple(
        CategoryShare(
            category_id=category,
            label=(
                UNCLASSIFIED_LABEL
                if category == UNCLASSIFIED
                else taxonomy.label(category)
            ),
            value_eur=value,
            awards=counts[category],
            share_pct=_share(value, total),
        )
        for category, value in ordered
    )


def _largest(usable: Iterable[_Result]) -> tuple[Award, ...]:
    ordered = sorted(
        usable,
        key=lambda r: (
            -(r.value.value_eur or Decimal(0)),
            r.notice.publication_number,
        ),
    )
    return tuple(r.award() for r in ordered[:PURCHASING_LARGEST_AWARDS_LIMIT])


def _unverified(usable: Iterable[_Result]) -> list[_Result]:
    return [r for r in usable if FLAG_UNVERIFIED_LARGE in r.value.flags]


def _summarize(
    country: str,
    now: Sequence[_Result],
    before: Sequence[_Result],
    window: Window,
    taxonomy: Taxonomy,
) -> CountryPurchaseSummary:
    awarded = [r for r in now if r.kind is ResultKind.AWARDED]
    usable = [r for r in awarded if r.value.usable]
    value = _value_or_zero(awarded)
    previous_awarded = [r for r in before if r.kind is ResultKind.AWARDED]
    unverified = _unverified(usable)
    return CountryPurchaseSummary(
        country=country,
        window=window,
        award_value_eur=value,
        award_count=len(awarded),
        valued_awards=len(usable),
        framework_results=sum(1 for r in awarded if FLAG_FRAMEWORK in r.value.flags),
        non_awarded_results=sum(1 for r in now if r.kind is ResultKind.NOT_AWARDED),
        suspicious_results=sum(1 for r in awarded if r.value.suspicious),
        unconvertible_results=sum(
            1 for r in awarded if FLAG_UNCONVERTIBLE in r.value.flags
        ),
        unverified_large_results=len(unverified),
        unverified_large_value_eur=_sum_usable(unverified),
        decision_date_awards=sum(
            1 for r in awarded if r.value.date_basis == AWARD_DATE_BASIS_DECISION
        ),
        previous_value_eur=_value_or_zero(previous_awarded),
        previous_award_count=len(previous_awarded),
        top_categories=_categories(usable, value, taxonomy),
        largest_awards=_largest(usable),
    )


def _by_country(results: Iterable[_Result]) -> dict[str, list[_Result]]:
    grouped: dict[str, list[_Result]] = defaultdict(list)
    for r in results:
        grouped[r.country_key].append(r)
    return grouped


def _is_growth_eligible(summary: CountryPurchaseSummary) -> bool:
    """§23: enough current activity to make a growth percentage meaningful."""
    value = summary.award_value_eur
    return summary.valued_awards >= GROWTH_MIN_PROCEDURES or (
        value is not None and value >= GROWTH_MIN_VALUE_EUR
    )


def _optional_sum(values: Iterable[Decimal | None]) -> Decimal | None:
    known = [v for v in values if v is not None]
    return sum(known, Decimal(0)) if known else None


def _period(
    results: Sequence[_Result], window: Window, previous: Window, taxonomy: Taxonomy
) -> PurchasingPeriod:
    now = [r for r in results if window.contains(r.value.date)]
    before = [r for r in results if previous.contains(r.value.date)]
    now_by, before_by = _by_country(now), _by_country(before)
    countries = {
        key: _summarize(
            key, now_by.get(key, []), before_by.get(key, []), window, taxonomy
        )
        for key in sorted(set(now_by) | set(before_by))
    }
    real = {k: s for k, s in countries.items() if k not in PSEUDO_COUNTRIES}
    attributable = _optional_sum(s.award_value_eur for s in real.values())
    joint = countries.get(MULTI_COUNTRY)
    unknown = countries.get(UNKNOWN_COUNTRY)
    joint_value = joint.award_value_eur if joint else None
    unknown_value = unknown.award_value_eur if unknown else None
    total = _optional_sum((attributable, joint_value, unknown_value))
    previous_total = _optional_sum(s.previous_value_eur for s in countries.values())

    ranked = sorted(
        (s for s in real.values() if s.award_value_eur is not None),
        key=lambda s: (-(s.award_value_eur or Decimal(0)), s.country),
    )
    ranking = tuple(
        CountryRank(rank, s.country, s, _share(s.award_value_eur or Decimal(0), total))
        for rank, s in enumerate(ranked, 1)
    )
    eligible = sorted(
        (
            entry
            for entry in ranking
            if _is_growth_eligible(entry.summary)
            and entry.summary.change_pct is not None
        ),
        key=lambda e: (-(e.summary.change_pct or 0), e.country),
    )
    growth = tuple(replace(e, rank=i) for i, e in enumerate(eligible, 1))

    awarded_now = [r for r in now if r.kind is ResultKind.AWARDED]
    usable_now = [r for r in awarded_now if r.value.usable]
    europe = EuropeSummary(
        window=window,
        total_value_eur=total,
        attributable_value_eur=attributable,
        joint_value_eur=joint_value,
        unknown_country_value_eur=unknown_value,
        previous_total_value_eur=previous_total,
        award_count=len(awarded_now),
        valued_awards=len(usable_now),
        framework_results=sum(
            1 for r in awarded_now if FLAG_FRAMEWORK in r.value.flags
        ),
        non_awarded_results=sum(1 for r in now if r.kind is ResultKind.NOT_AWARDED),
        suspicious_results=sum(1 for r in awarded_now if r.value.suspicious),
        unverified_large_results=len(_unverified(usable_now)),
        countries_with_value=sum(1 for s in real.values() if s.award_value_eur),
        countries_active=sum(1 for s in real.values() if s.award_count),
        largest_buyer=(
            ranking[0] if ranking and ranking[0].summary.award_value_eur else None
        ),
        top_categories=_categories(usable_now, total, taxonomy),
        largest_awards=_largest(usable_now),
    )
    unranked = tuple(
        sorted(
            k for k, s in real.items() if s.award_count and s.award_value_eur is None
        )
    )
    return PurchasingPeriod(window, countries, ranking, growth, europe, unranked)


def _months(today: date, count: int) -> list[str]:
    year, month = today.year, today.month
    months: list[str] = []
    for _ in range(count):
        months.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return months[::-1]


def _monthly(
    results: Sequence[_Result], today: date
) -> dict[str, tuple[MonthlyValue, ...]]:
    months = _months(today, PURCHASING_MONTHS)
    wanted = set(months)
    per_country: dict[str, dict[str, list[_Result]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in results:
        if r.kind is not ResultKind.AWARDED:
            continue
        month = r.value.date.strftime("%Y-%m")
        if month in wanted:
            per_country[r.country_key][month].append(r)
    series: dict[str, tuple[MonthlyValue, ...]] = {}
    for country, by_month in per_country.items():
        series[country] = tuple(
            MonthlyValue(
                month,
                _value_or_zero(awarded := by_month.get(month, [])),
                len(awarded),
                sum(1 for r in awarded if r.value.usable),
            )
            for month in months
        )
    return series


def _flag_duplicates(results: list[_Result]) -> list[_Result]:
    """The same Notice Value in several original results of one procedure is a
    republication: keep the earliest, quarantine the rest (§14)."""
    groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for position, r in enumerate(results):
        if r.value.usable and r.value.money is not None:
            key = (r.procedure_key, str(r.value.money.amount), r.value.money.currency)
            groups[key].append(position)
    for positions in groups.values():
        if len(positions) < 2:
            continue
        ordered = sorted(
            positions,
            key=lambda i: (results[i].value.date, results[i].notice.publication_number),
        )
        for i in ordered[1:]:
            r = results[i]
            flagged = replace(r.value, flags=(*r.value.flags, FLAG_DUPLICATE_VALUE))
            results[i] = replace(r, value=flagged)
    return results


def build_purchasing_model(
    notices: Iterable[ProcurementNotice],
    fx: FxRateTable,
    today: date,
    *,
    taxonomy: Taxonomy,
    index: ProcedureIndex | None = None,
) -> PurchasingModel:
    """Compute the country purchasing picture from stored notice versions."""
    if index is None:
        index = ProcedureIndex.build(notices)
    results: list[_Result] = []
    for notice in index.results():
        kind = classify_result(notice)
        if kind is ResultKind.UNKNOWN:
            continue
        if kind is ResultKind.AWARDED:
            summary = index.procedures.get(
                notice.procedure_id or f"notice:{notice.notice_id}"
            )
            estimate = notice.estimated_value or (
                summary.estimated_value if summary else None
            )
            value = extract_awarded_value(notice, fx, estimate=estimate)
        else:
            value = AwardedValue(
                None, None, None, notice.award_date, notice.award_date_basis, ()
            )
        results.append(
            _Result(
                notice,
                kind,
                attribute_country(notice),
                value,
                primary_category(notice, taxonomy),
            )
        )
    results = _flag_duplicates(results)
    primary = _period(
        results,
        current_window(today, PURCHASING_PERIOD_DAYS),
        previous_window(today, PURCHASING_PERIOD_DAYS),
        taxonomy,
    )
    secondary = {
        days: _period(
            results, current_window(today, days), previous_window(today, days), taxonomy
        )
        for days in PURCHASING_SECONDARY_PERIODS
    }
    quarantined = sorted(
        (r for r in results if r.value.suspicious),
        key=lambda r: (
            -(r.value.value_eur or Decimal(0)),
            r.notice.publication_number,
        ),
    )
    return PurchasingModel(
        today=today,
        primary=primary,
        secondary=secondary,
        quarantined=tuple(r.award() for r in quarantined),
        monthly=_monthly(results, today),
    )


# --------------------------------------------------------------------- texts


def period_label(window: Window) -> str:
    return "12m" if window.days == PURCHASING_PERIOD_DAYS else f"{window.days}d"


def my_country_text(period: PurchasingPeriod, country: str) -> str:
    """``SE · EUR 6.1bn / 12m · #5 · 6.0% · +29.8%`` (§25)."""
    label = period_label(period.window)
    summary = period.countries.get(country)
    if summary is None or not summary.award_count:
        return f"{country} · no awards / {label}"
    entry = period.rank_of(country)
    if entry is None or summary.award_value_eur is None:
        return f"{country} · value unknown / {label} · {summary.award_count} awards"
    text = f"{country} · {format_eur(summary.award_value_eur)} / {label}"
    text += f" · #{entry.rank}"
    if entry.share_pct is not None:
        text += f" · {entry.share_pct}%"
    if summary.change_pct is not None:
        text += f" · {summary.change_pct:+.1f}%"
    return text


def top_buyers_text(period: PurchasingPeriod) -> str:
    parts = [
        f"{e.country} {format_eur(e.summary.award_value_eur)}"
        for e in period.ranking[:TEXT_TOP_BUYERS]
        if e.summary.award_value_eur
    ]
    return " · ".join(parts) if parts else "no data"


def categories_text(summary: CountryPurchaseSummary | EuropeSummary) -> str:
    parts = [
        f"{c.label} {format_eur(c.value_eur)}"
        for c in summary.top_categories[:TEXT_CATEGORIES]
    ]
    return " · ".join(parts) if parts else "no data"

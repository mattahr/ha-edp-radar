"""Pure metrics engine: notices + FX + config + date → RadarSnapshot (plan §16–20, §37).

Nothing in this module imports Home Assistant. Every function is deterministic
given its inputs so the statistics can be unit-tested with hand-calculated data.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from .const import (
    CENTRAL_PURCHASING_BUYER_THRESHOLD,
    GROWTH_MIN_PROCEDURES,
    GROWTH_MIN_VALUE_EUR,
    MATCH_DEFENCE_BUYER,
    RANKING_LIMIT,
    RAW_BUYERS_LIMIT,
    RAW_LIST_LIMIT,
    RECENT_ITEMS_LIMIT,
    RelevanceMode,
)
from .fx_rates import FxRateTable
from .lifecycle import ProcedureIndex, ProcedureSummary
from .models import Money, NoticeStage, ProcurementNotice, normalize_name
from .periods import (
    Window,
    current_window,
    format_eur,
    median,
    pct,
    pct_change,
    previous_window,
    value_in_eur,
)
from .taxonomy import Taxonomy

# --------------------------------------------------------------------------- config


@dataclass(frozen=True)
class OwnOrganisation:
    """Public identity of the tracked organisation (plan §12, D17)."""

    identifiers: frozenset[str]
    country: str | None
    names: frozenset[str]

    @classmethod
    def from_options(
        cls,
        identifiers: Iterable[str],
        country: str | None,
        canonical_name: str | None,
        aliases: Iterable[str],
    ) -> OwnOrganisation:
        names = {normalize_name(n) for n in [canonical_name or "", *aliases] if n}
        return cls(frozenset(i for i in identifiers if i), country, frozenset(names))

    def matches(self, notice: ProcurementNotice) -> bool:
        if self.identifiers and self.identifiers & set(notice.buyer.identifiers):
            return True
        if not self.names or not notice.buyer.name:
            return False
        if self.country is not None and notice.buyer.country != self.country:
            return False
        return normalize_name(notice.buyer.name) in self.names


@dataclass(frozen=True)
class WatchlistConfig:
    countries: frozenset[str] = frozenset()
    buyer_identifiers: frozenset[str] = frozenset()
    categories: frozenset[str] = frozenset()
    min_estimated_value_eur: Decimal | None = None
    min_award_value_eur: Decimal | None = None

    @property
    def is_empty(self) -> bool:
        return not (
            self.countries
            or self.buyer_identifiers
            or self.categories
            or self.min_estimated_value_eur is not None
            or self.min_award_value_eur is not None
        )


@dataclass(frozen=True)
class MetricsConfig:
    relevance_mode: RelevanceMode = RelevanceMode.STRICT
    market_countries: frozenset[str] = frozenset()
    own_organisation: OwnOrganisation | None = None
    peer_countries: frozenset[str] = frozenset()
    peer_organisation_identifiers: frozenset[str] = frozenset()
    selected_country: str | None = None
    pinned_categories: tuple[str, ...] = ()
    raw_countries: tuple[str, ...] = ()
    watchlist: WatchlistConfig = field(default_factory=WatchlistConfig)


# --------------------------------------------------------------------------- universe


def is_central_purchasing_only(notice: ProcurementNotice) -> bool:
    """Many buyers and only the defence-buyer signal: a central purchasing body (D5)."""
    return (
        notice.buyer.count > CENTRAL_PURCHASING_BUYER_THRESHOLD
        and notice.match_reasons == frozenset({MATCH_DEFENCE_BUYER})
    )


def relevant_notices(
    notices: Iterable[ProcurementNotice], config: MetricsConfig, taxonomy: Taxonomy
) -> tuple[list[ProcurementNotice], int]:
    """Notices in the configured universe, and how many were excluded as CPB-only."""
    kept: list[ProcurementNotice] = []
    excluded = 0
    for notice in notices:
        if not taxonomy.is_relevant(notice.match_reasons, config.relevance_mode):
            continue
        if is_central_purchasing_only(notice):
            excluded += 1
            continue
        kept.append(notice)
    return kept, excluded


# --------------------------------------------------------------------------- results


@dataclass(frozen=True)
class Coverage:
    covered: int
    population: int

    @property
    def pct(self) -> float | None:
        return pct(self.covered, self.population)


@dataclass(frozen=True)
class CountMetric:
    value: int
    previous: int | None
    period_days: int

    @property
    def change(self) -> int | None:
        return None if self.previous is None else self.value - self.previous

    @property
    def change_pct(self) -> float | None:
        return pct_change(self.value, self.previous)


@dataclass(frozen=True)
class ValueMetric:
    value_eur: Decimal | None
    previous_eur: Decimal | None
    sample_size: int
    covered: int
    period_days: int

    @property
    def coverage_pct(self) -> float | None:
        return pct(self.covered, self.sample_size)

    @property
    def change_pct(self) -> float | None:
        return pct_change(self.value_eur, self.previous_eur)


@dataclass(frozen=True)
class RankingEntry:
    key: str
    label: str
    rank: int
    value_eur: Decimal | None
    procedures: int
    previous_value_eur: Decimal | None
    previous_procedures: int
    change_pct: float | None

    @property
    def change_eur(self) -> Decimal | None:
        if self.value_eur is None or self.previous_value_eur is None:
            return None
        return self.value_eur - self.previous_value_eur


@dataclass(frozen=True)
class Ranking:
    entries: tuple[RankingEntry, ...]
    population: str
    population_size: int

    @property
    def leader(self) -> RankingEntry | None:
        return self.entries[0] if self.entries else None


@dataclass(frozen=True)
class NoticeHighlight:
    notice_id: str
    publication_number: str
    procedure_id: str | None
    title: str | None
    buyer: str | None
    country: str | None
    publication_date: date
    stage: NoticeStage
    original_amount: Decimal | None
    original_currency: str | None
    value_eur: Decimal | None
    categories: tuple[str, ...]
    source_url: str | None


@dataclass(frozen=True)
class MedianMetric:
    value: float | None
    sample_size: int
    coverage: Coverage


@dataclass(frozen=True)
class ShareMetric:
    pct: float | None
    numerator: int
    denominator: int
    coverage: Coverage


@dataclass(frozen=True)
class ProcessMetrics:
    median_tenders_365d: MedianMetric
    single_bid_share_365d: ShareMetric
    median_time_to_result_365d: MedianMetric
    non_award_share_365d: ShareMetric


@dataclass(frozen=True)
class MarketMetrics:
    new_competitions_30d: CountMetric
    new_competitions_90d: CountMetric
    estimated_value_30d: ValueMetric
    estimated_value_90d: ValueMetric
    award_value_30d: ValueMetric
    award_value_90d: ValueMetric
    country_ranking_90d: Ranking
    country_growth_90d: Ranking
    category_ranking_90d: Ranking
    category_growth_90d: Ranking
    largest_country_change_90d: RankingEntry | None
    largest_category_change_90d: RankingEntry | None
    process: ProcessMetrics
    snapshot_text: str
    country_ranking_text: str


@dataclass(frozen=True)
class ExternalMetrics:
    new_competitions_7d: int
    recent_competitions: tuple[NoticeHighlight, ...]
    largest_competition_7d: NoticeHighlight | None
    largest_award_7d: NoticeHighlight | None
    latest_text: str | None


@dataclass(frozen=True)
class OrganisationMetrics:
    competitions_30d: CountMetric
    estimated_value_30d: ValueMetric
    awards_30d: CountMetric
    award_value_30d: ValueMetric
    changes_30d: CountMetric
    modifications_365d: CountMetric
    process: ProcessMetrics
    recent: tuple[NoticeHighlight, ...]


@dataclass(frozen=True)
class PeerMetrics:
    population: str
    population_size: int
    selected_country: str | None
    rank_population: str
    rank_population_size: int
    value_rank_90d: int | None
    activity_rank_90d: int | None
    value_percentile_90d: float | None
    process: ProcessMetrics
    single_bid_delta_pp: float | None
    median_tenders_delta: float | None
    time_to_result_delta_days: float | None


@dataclass(frozen=True)
class SupplierEntry:
    key: str
    name: str
    country: str | None
    rank: int
    award_value_eur: Decimal
    awards: int


@dataclass(frozen=True)
class SupplierMetrics:
    top_suppliers: tuple[SupplierEntry, ...]
    top5_share_pct: float | None
    total_award_value_eur: Decimal | None
    groups: int
    coverage: Coverage


@dataclass(frozen=True)
class CategoryMetrics:
    category_id: str
    label: str
    competitions_30d: CountMetric
    estimated_value_90d: ValueMetric
    award_value_90d: ValueMetric


@dataclass(frozen=True)
class RawList:
    """One kind of notice for the raw-data device: window count + latest N."""

    count_30d: int
    latest: tuple[ProcurementNotice, ...]


@dataclass(frozen=True)
class BuyerCount:
    name: str | None
    identifiers: tuple[str, ...]
    notices: int


@dataclass(frozen=True)
class CountryRawMetrics:
    """What TED published for one buyer country, without aggregation."""

    country: str
    notices_7d: int
    latest: tuple[ProcurementNotice, ...]
    competitions: RawList
    results: RawList
    changes: RawList
    planning: RawList
    direct_awards: RawList
    modifications: RawList
    stored_versions: int
    stored_notices: int
    by_stage: Mapping[str, int]
    by_month: Mapping[str, int]
    by_category: Mapping[str, int]
    top_buyers: tuple[BuyerCount, ...]


@dataclass(frozen=True)
class DataQualityMetrics:
    stored_versions: int
    stored_notices: int
    stored_procedures: int
    relevant_notices: int
    excluded_central_purchasing: int
    records_by_stage: Mapping[str, int]
    parse_errors: int
    unlinked_results: int
    framework_results: int
    fx_coverage: Coverage
    estimated_value_coverage: Coverage
    result_value_coverage: Coverage
    bid_count_coverage: Coverage
    procedure_link_coverage: Coverage
    unclassified_share_pct: float | None
    latest_publication_date: date | None
    fx_latest_date: date | None


@dataclass(frozen=True)
class RadarSnapshot:
    computed_at: datetime
    today: date
    market: MarketMetrics
    external: ExternalMetrics
    own: OrganisationMetrics | None
    peers: PeerMetrics | None
    suppliers: SupplierMetrics
    categories: Mapping[str, CategoryMetrics]
    raw: Mapping[str, CountryRawMetrics]
    quality: DataQualityMetrics
    bootstrap_complete: bool


# --------------------------------------------------------------------------- periods

type KeyFn = Callable[[ProcedureSummary], Iterable[str]]
type LabelFn = Callable[[str], str]


def procedures_started_in(
    index: ProcedureIndex, window: Window
) -> list[ProcedureSummary]:
    """Procedures whose first original competition was published in the window."""
    return [
        p
        for p in index.procedures.values()
        if p.first_competition is not None and window.contains(p.first_competition)
    ]


def results_in(index: ProcedureIndex, window: Window) -> list[ProcurementNotice]:
    return [n for n in index.results() if window.contains(n.publication_date)]


def new_competitions(index: ProcedureIndex, today: date, days: int) -> CountMetric:
    return CountMetric(
        len(procedures_started_in(index, current_window(today, days))),
        len(procedures_started_in(index, previous_window(today, days))),
        days,
    )


def awards_count(index: ProcedureIndex, today: date, days: int) -> CountMetric:
    return CountMetric(
        len(results_in(index, current_window(today, days))),
        len(results_in(index, previous_window(today, days))),
        days,
    )


def _sum_eur(
    items: Iterable[tuple[Money | None, date]], fx: FxRateTable
) -> tuple[Decimal | None, int, int]:
    total = Decimal(0)
    sample = covered = 0
    for money, on in items:
        sample += 1
        eur = value_in_eur(money, on, fx)
        if eur is not None:
            covered += 1
            total += eur
    return (total if covered else None), sample, covered


def _estimated_items(
    procedures: Iterable[ProcedureSummary], today: date
) -> list[tuple[Money | None, date]]:
    return [(p.estimated_value, p.estimated_value_date or today) for p in procedures]


def estimated_value(
    index: ProcedureIndex, today: date, days: int, fx: FxRateTable
) -> ValueMetric:
    current = procedures_started_in(index, current_window(today, days))
    previous = procedures_started_in(index, previous_window(today, days))
    total, sample, covered = _sum_eur(_estimated_items(current, today), fx)
    previous_total, _, _ = _sum_eur(_estimated_items(previous, today), fx)
    return ValueMetric(total, previous_total, sample, covered, days)


def award_value(
    index: ProcedureIndex, today: date, days: int, fx: FxRateTable
) -> ValueMetric:
    current = results_in(index, current_window(today, days))
    previous = results_in(index, previous_window(today, days))
    total, sample, covered = _sum_eur(
        ((r.result_value, r.award_date) for r in current), fx
    )
    previous_total, _, _ = _sum_eur(
        ((r.result_value, r.award_date) for r in previous), fx
    )
    return ValueMetric(total, previous_total, sample, covered, days)


# --------------------------------------------------------------------------- rankings


def rank_by(
    index: ProcedureIndex,
    today: date,
    fx: FxRateTable,
    key_fn: KeyFn,
    label_fn: LabelFn,
    *,
    days: int = 90,
) -> list[RankingEntry]:
    """Competition-rank keys by normalized estimated value of new competitions."""

    def accumulate(window: Window) -> dict[str, tuple[Decimal, int, int]]:
        acc: dict[str, tuple[Decimal, int, int]] = {}
        for procedure in procedures_started_in(index, window):
            eur = value_in_eur(
                procedure.estimated_value, procedure.estimated_value_date or today, fx
            )
            for key in key_fn(procedure):
                total, count, covered = acc.get(key, (Decimal(0), 0, 0))
                if eur is not None:
                    total += eur
                    covered += 1
                acc[key] = (total, count + 1, covered)
        return acc

    current = accumulate(current_window(today, days))
    previous = accumulate(previous_window(today, days))
    rows: list[tuple[str, Decimal | None, int, Decimal | None, int]] = []
    for key in set(current) | set(previous):
        total, count, covered = current.get(key, (Decimal(0), 0, 0))
        prev_total, prev_count, prev_covered = previous.get(key, (Decimal(0), 0, 0))
        rows.append(
            (
                key,
                total if covered else None,
                count,
                prev_total if prev_covered else None,
                prev_count,
            )
        )
    rows.sort(key=lambda r: (r[1] is None, -(r[1] or Decimal(0)), -r[2], r[0]))
    entries: list[RankingEntry] = []
    rank = 0
    last: tuple[Decimal | None, int] | None = None
    for position, (key, value, count, prev_value, prev_count) in enumerate(rows, 1):
        if (value, count) != last:
            rank = position
            last = (value, count)
        entries.append(
            RankingEntry(
                key,
                label_fn(key),
                rank,
                value,
                count,
                prev_value,
                prev_count,
                pct_change(value, prev_value),
            )
        )
    return entries


def top_ranking(
    entries: Sequence[RankingEntry], population: str, limit: int = RANKING_LIMIT
) -> Ranking:
    return Ranking(tuple(entries[:limit]), population, len(entries))


def is_growth_eligible(entry: RankingEntry) -> bool:
    """Minimum activity in the current period (plan §16.3)."""
    return entry.procedures >= GROWTH_MIN_PROCEDURES or (
        entry.value_eur is not None and entry.value_eur >= GROWTH_MIN_VALUE_EUR
    )


def _was_active(entry: RankingEntry) -> bool:
    return entry.previous_procedures >= GROWTH_MIN_PROCEDURES or (
        entry.previous_value_eur is not None
        and entry.previous_value_eur >= GROWTH_MIN_VALUE_EUR
    )


def growth_ranking(entries: Sequence[RankingEntry], population: str) -> Ranking:
    eligible = [
        e for e in entries if is_growth_eligible(e) and e.change_pct is not None
    ]
    eligible.sort(key=lambda e: (-(e.change_pct or 0), e.key))
    ranked = tuple(replace(e, rank=i) for i, e in enumerate(eligible, 1))
    return Ranking(ranked[:RANKING_LIMIT], population, len(eligible))


def largest_change(entries: Sequence[RankingEntry]) -> RankingEntry | None:
    """Largest absolute EUR change among keys active in either period."""
    candidates = [
        e
        for e in entries
        if (is_growth_eligible(e) or _was_active(e)) and e.change_eur is not None
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda e: (-abs(e.change_eur or Decimal(0)), e.key))


# --------------------------------------------------------------------------- process


def process_metrics(index: ProcedureIndex, today: date) -> ProcessMetrics:
    """Competition/process metrics over the last 365 days (plan §17, D7)."""
    window = current_window(today, 365)
    results = results_in(index, window)
    observations = [
        count
        for r in results
        if r.tender_statistics
        for count in r.tender_statistics.tender_counts
    ]
    with_counts = sum(
        1 for r in results if r.tender_statistics and r.tender_statistics.tender_counts
    )
    count_coverage = Coverage(with_counts, len(results))
    single = sum(1 for count in observations if count == 1)

    decided = [
        p
        for p in index.procedures.values()
        if p.first_result is not None and window.contains(p.first_result)
    ]
    durations = [
        p.time_to_result_days for p in decided if p.time_to_result_days is not None
    ]

    statuses = [
        s
        for r in results
        if r.tender_statistics
        for s in r.tender_statistics.selection_statuses
    ]
    with_status = sum(
        1
        for r in results
        if r.tender_statistics and r.tender_statistics.selection_statuses
    )
    closed_no_winner = statuses.count("clos-nw")
    decided_lots = closed_no_winner + statuses.count("selec-w")

    return ProcessMetrics(
        median_tenders_365d=MedianMetric(
            median(observations), len(observations), count_coverage
        ),
        single_bid_share_365d=ShareMetric(
            pct(single, len(observations)), single, len(observations), count_coverage
        ),
        median_time_to_result_365d=MedianMetric(
            median(durations), len(durations), Coverage(len(durations), len(decided))
        ),
        non_award_share_365d=ShareMetric(
            pct(closed_no_winner, decided_lots),
            closed_no_winner,
            decided_lots,
            Coverage(with_status, len(results)),
        ),
    )


# --------------------------------------------------------------------------- market


def market_snapshot_text(competitions_90d: CountMetric, value_90d: ValueMetric) -> str:
    text = f"{competitions_90d.value} competitions / 90d"
    text += f" · {format_eur(value_90d.value_eur)}"
    if value_90d.change_pct is not None:
        text += f" · {value_90d.change_pct:+.1f}% vs previous 90d"
    return text


def country_ranking_text(ranking: Ranking) -> str:
    parts = [f"{e.key} {format_eur(e.value_eur)}" for e in ranking.entries[:5]]
    return " · ".join(parts) if parts else "no data"


_COUNTRY_POPULATION = (
    "market countries with new competitions in the last 90 or previous 90 days"
)
_CATEGORY_POPULATION = (
    "strategic categories with new competitions in the last 90 or previous 90 days"
)


def market_metrics(
    index: ProcedureIndex, today: date, fx: FxRateTable, taxonomy: Taxonomy
) -> MarketMetrics:
    countries = rank_by(index, today, fx, lambda p: [p.country or "??"], str)
    categories = rank_by(
        index, today, fx, lambda p: sorted(p.categories), taxonomy.label
    )
    country_ranking = top_ranking(countries, _COUNTRY_POPULATION)
    competitions_90d = new_competitions(index, today, 90)
    value_90d = estimated_value(index, today, 90, fx)
    return MarketMetrics(
        new_competitions_30d=new_competitions(index, today, 30),
        new_competitions_90d=competitions_90d,
        estimated_value_30d=estimated_value(index, today, 30, fx),
        estimated_value_90d=value_90d,
        award_value_30d=award_value(index, today, 30, fx),
        award_value_90d=award_value(index, today, 90, fx),
        country_ranking_90d=country_ranking,
        country_growth_90d=growth_ranking(countries, f"eligible {_COUNTRY_POPULATION}"),
        category_ranking_90d=top_ranking(categories, _CATEGORY_POPULATION),
        category_growth_90d=growth_ranking(
            categories, f"eligible {_CATEGORY_POPULATION}"
        ),
        largest_country_change_90d=largest_change(countries),
        largest_category_change_90d=largest_change(categories),
        process=process_metrics(index, today),
        snapshot_text=market_snapshot_text(competitions_90d, value_90d),
        country_ranking_text=country_ranking_text(country_ranking),
    )


# --------------------------------------------------------------------------- external


def highlight(notice: ProcurementNotice, fx: FxRateTable) -> NoticeHighlight:
    if notice.stage is NoticeStage.RESULT:
        money, on = notice.result_value, notice.award_date
    else:
        money, on = notice.estimated_value, notice.publication_date
    return NoticeHighlight(
        notice_id=notice.notice_id,
        publication_number=notice.publication_number,
        procedure_id=notice.procedure_id,
        title=notice.title,
        buyer=notice.buyer.name,
        country=notice.buyer.country,
        publication_date=notice.publication_date,
        stage=notice.stage,
        original_amount=money.amount if money else None,
        original_currency=money.currency if money else None,
        value_eur=value_in_eur(money, on, fx),
        categories=notice.categories,
        source_url=notice.source_url,
    )


def _by_significance(h: NoticeHighlight) -> tuple[bool, Decimal, int, str]:
    """Value descending (unknown last), then most recent, then stable id."""
    return (
        h.value_eur is None,
        -(h.value_eur or Decimal(0)),
        -h.publication_date.toordinal(),
        h.notice_id,
    )


def _largest(highlights: Iterable[NoticeHighlight]) -> NoticeHighlight | None:
    valued = [h for h in highlights if h.value_eur is not None]
    if not valued:
        return None
    return min(valued, key=_by_significance)


def latest_notices_in(index: ProcedureIndex, window: Window) -> list[ProcurementNotice]:
    return [n for n in index.notices if window.contains(n.publication_date)]


def external_latest_text(h: NoticeHighlight, taxonomy: Taxonomy) -> str:
    category = taxonomy.label(h.categories[0]) if h.categories else "Unclassified"
    return (
        f"{h.country or '??'} · {category} · {format_eur(h.value_eur)}"
        f" · published {h.publication_date.isoformat()}"
    )


def external_metrics(
    index: ProcedureIndex, today: date, fx: FxRateTable, taxonomy: Taxonomy
) -> ExternalMetrics:
    window = current_window(today, 7)
    competitions = [
        p.latest_competition
        for p in procedures_started_in(index, window)
        if p.latest_competition is not None
    ]
    highlights = [highlight(n, fx) for n in competitions]
    recent = sorted(highlights, key=_by_significance)
    awards = [highlight(r, fx) for r in results_in(index, window)]
    latest = max(
        highlights,
        key=lambda h: (h.publication_date, h.value_eur or Decimal(0)),
        default=None,
    )
    return ExternalMetrics(
        new_competitions_7d=len(competitions),
        recent_competitions=tuple(recent[:RECENT_ITEMS_LIMIT]),
        largest_competition_7d=_largest(highlights),
        largest_award_7d=_largest(awards),
        latest_text=external_latest_text(latest, taxonomy) if latest else None,
    )


# --------------------------------------------------------------------------- own


def organisation_metrics(
    index: ProcedureIndex, today: date, fx: FxRateTable
) -> OrganisationMetrics:
    now_30, before_30 = current_window(today, 30), previous_window(today, 30)
    now_365, before_365 = current_window(today, 365), previous_window(today, 365)
    changes_now = [c for c in index.changes if now_30.contains(c.publication_date)]
    changes_before = [
        c for c in index.changes if before_30.contains(c.publication_date)
    ]
    modifications = [n for n in index.notices if n.stage is NoticeStage.MODIFICATION]
    mods_now = [m for m in modifications if now_365.contains(m.publication_date)]
    mods_before = [m for m in modifications if before_365.contains(m.publication_date)]
    recent = sorted(
        index.notices,
        key=lambda n: (n.publication_date, n.notice_version),
        reverse=True,
    )
    return OrganisationMetrics(
        competitions_30d=new_competitions(index, today, 30),
        estimated_value_30d=estimated_value(index, today, 30, fx),
        awards_30d=awards_count(index, today, 30),
        award_value_30d=award_value(index, today, 30, fx),
        changes_30d=CountMetric(len(changes_now), len(changes_before), 30),
        modifications_365d=CountMetric(len(mods_now), len(mods_before), 365),
        process=process_metrics(index, today),
        recent=tuple(highlight(n, fx) for n in recent[:RECENT_ITEMS_LIMIT]),
    )


# --------------------------------------------------------------------------- peers


def activity_rank(entries: Sequence[RankingEntry], key: str) -> int | None:
    """Competition rank by number of new procedures."""
    ordered = sorted(entries, key=lambda e: (-e.procedures, e.key))
    rank = 0
    last: int | None = None
    for position, entry in enumerate(ordered, 1):
        if entry.procedures != last:
            rank = position
            last = entry.procedures
        if entry.key == key:
            return rank
    return None


def value_percentile(entries: Sequence[RankingEntry], key: str) -> float | None:
    """Share of the population whose value is <= the key's value (inclusive rank)."""
    selected = next((e for e in entries if e.key == key), None)
    if selected is None or not entries:
        return None
    own_value = selected.value_eur or Decimal(0)
    below = sum(1 for e in entries if (e.value_eur or Decimal(0)) <= own_value)
    return pct(below, len(entries))


def _delta(own: float | None, peer: float | None) -> float | None:
    if own is None or peer is None:
        return None
    return round(own - peer, 1)


_RANK_POPULATION = _COUNTRY_POPULATION


def peer_metrics(
    config: MetricsConfig,
    relevant: Sequence[ProcurementNotice],
    market_countries_ranking: Sequence[RankingEntry],
    own: OrganisationMetrics | None,
    today: date,
    fx: FxRateTable,
) -> PeerMetrics | None:
    if config.peer_organisation_identifiers:
        population = "configured peer organisations"
        size = len(config.peer_organisation_identifiers)
        wanted = config.peer_organisation_identifiers
        notices = [n for n in relevant if set(n.buyer.identifiers) & wanted]
    elif config.peer_countries:
        population = "configured peer countries"
        size = len(config.peer_countries)
        notices = [n for n in relevant if n.buyer.country in config.peer_countries]
    elif config.selected_country:
        population = "none"
        size = 0
        notices = []
    else:
        return None
    process = process_metrics(ProcedureIndex.build(notices), today)
    selected = config.selected_country
    entry = next((e for e in market_countries_ranking if e.key == selected), None)
    own_process = own.process if own else None
    return PeerMetrics(
        population=population,
        population_size=size,
        selected_country=selected,
        rank_population=_RANK_POPULATION,
        rank_population_size=len(market_countries_ranking),
        value_rank_90d=entry.rank if entry else None,
        activity_rank_90d=(
            activity_rank(market_countries_ranking, selected) if selected else None
        ),
        value_percentile_90d=(
            value_percentile(market_countries_ranking, selected) if selected else None
        ),
        process=process,
        single_bid_delta_pp=(
            _delta(
                own_process.single_bid_share_365d.pct,
                process.single_bid_share_365d.pct,
            )
            if own_process
            else None
        ),
        median_tenders_delta=(
            _delta(
                own_process.median_tenders_365d.value,
                process.median_tenders_365d.value,
            )
            if own_process
            else None
        ),
        time_to_result_delta_days=(
            _delta(
                own_process.median_time_to_result_365d.value,
                process.median_time_to_result_365d.value,
            )
            if own_process
            else None
        ),
    )


# --------------------------------------------------------------------------- suppliers


def supplier_metrics(
    index: ProcedureIndex, today: date, fx: FxRateTable
) -> SupplierMetrics:
    """Top supplier groups by normalized award value; a consortium is one group."""
    results = [r for r in results_in(index, current_window(today, 365)) if r.winners]
    groups: dict[str, tuple[str, str | None, Decimal, int]] = {}
    covered = 0
    for notice in results:
        eur = value_in_eur(notice.result_value, notice.award_date, fx)
        if eur is None:
            continue
        covered += 1
        winners = sorted(notice.winners, key=lambda w: w.identity_key)
        key = "+".join(w.identity_key for w in winners)
        name = " + ".join(w.name or w.identity_key for w in winners)
        countries = {w.country for w in winners}
        country = countries.pop() if len(countries) == 1 else None
        _, _, total, awards = groups.get(key, (name, country, Decimal(0), 0))
        groups[key] = (name, country, total + eur, awards + 1)
    ordered = sorted(groups.items(), key=lambda item: (-item[1][2], item[0]))
    grand_total: Decimal | None = (
        sum((g[2] for g in groups.values()), Decimal(0)) if groups else None
    )
    top5 = sum((g[2] for _, g in ordered[:5]), Decimal(0))
    return SupplierMetrics(
        top_suppliers=tuple(
            SupplierEntry(key, name, country, rank, value, awards)
            for rank, (key, (name, country, value, awards)) in enumerate(
                ordered[:RANKING_LIMIT], 1
            )
        ),
        top5_share_pct=(
            round(float(top5 / grand_total * 100), 1) if grand_total else None
        ),
        total_award_value_eur=grand_total,
        groups=len(groups),
        coverage=Coverage(covered, len(results)),
    )


# --------------------------------------------------------------------------- categories


def notices_for_procedures(
    notices: Iterable[ProcurementNotice], keys: set[str]
) -> list[ProcurementNotice]:
    return [n for n in notices if (n.procedure_id or f"notice:{n.notice_id}") in keys]


def category_metrics(
    index_all: ProcedureIndex,
    notices: Sequence[ProcurementNotice],
    category_id: str,
    label: str,
    today: date,
    fx: FxRateTable,
) -> CategoryMetrics:
    keys = {p.key for p in index_all.procedures.values() if category_id in p.categories}
    index = ProcedureIndex.build(notices_for_procedures(notices, keys))
    return CategoryMetrics(
        category_id=category_id,
        label=label,
        competitions_30d=new_competitions(index, today, 30),
        estimated_value_90d=estimated_value(index, today, 90, fx),
        award_value_90d=award_value(index, today, 90, fx),
    )


# --------------------------------------------------------------------------- raw


def _newest_first(notices: Iterable[ProcurementNotice]) -> list[ProcurementNotice]:
    return sorted(
        notices,
        key=lambda n: (n.publication_date, n.notice_version, n.notice_id),
        reverse=True,
    )


def _raw_list(notices: Sequence[ProcurementNotice], window: Window) -> RawList:
    ordered = _newest_first(notices)
    return RawList(
        sum(1 for n in ordered if window.contains(n.publication_date)),
        tuple(ordered[:RAW_LIST_LIMIT]),
    )


def _buyer_counts(notices: Iterable[ProcurementNotice]) -> tuple[BuyerCount, ...]:
    groups: dict[str, tuple[str | None, tuple[str, ...], int]] = {}
    for notice in notices:
        buyer = notice.buyer
        key = (
            buyer.identifiers[0]
            if buyer.identifiers
            else normalize_name(buyer.name or "")
        )
        if not key:
            continue
        name, identifiers, count = groups.get(key, (buyer.name, buyer.identifiers, 0))
        groups[key] = (name or buyer.name, identifiers or buyer.identifiers, count + 1)
    ordered = sorted(groups.values(), key=lambda g: (-g[2], g[0] or ""))
    return tuple(BuyerCount(n, i, c) for n, i, c in ordered[:RAW_BUYERS_LIMIT])


def country_raw_metrics(
    country: str,
    notices: Iterable[ProcurementNotice],
    fx: FxRateTable,
    today: date,
    mode: RelevanceMode,
    taxonomy: Taxonomy,
) -> CountryRawMetrics:
    """Everything stored for one buyer country in the configured universe.

    Central purchasing notices are kept (the raw view hides nothing); the
    attribute converter flags them.
    """
    versions = [
        n
        for n in notices
        if n.buyer.country == country and taxonomy.is_relevant(n.match_reasons, mode)
    ]
    index = ProcedureIndex.build(versions)
    latest = index.notices
    originals = [n for n in latest if not n.is_change]
    month = current_window(today, 30)

    def stage(kind: NoticeStage) -> RawList:
        return _raw_list([n for n in originals if n.stage is kind], month)

    return CountryRawMetrics(
        country=country,
        notices_7d=sum(
            1 for n in versions if current_window(today, 7).contains(n.publication_date)
        ),
        latest=tuple(_newest_first(versions)[:RAW_LIST_LIMIT]),
        competitions=stage(NoticeStage.COMPETITION),
        results=stage(NoticeStage.RESULT),
        changes=_raw_list(index.changes, month),
        planning=stage(NoticeStage.PLANNING),
        direct_awards=stage(NoticeStage.DIRECT_AWARD),
        modifications=stage(NoticeStage.MODIFICATION),
        stored_versions=len(versions),
        stored_notices=len(latest),
        by_stage=dict(sorted(Counter(n.stage.value for n in latest).items())),
        by_month=dict(
            sorted(
                Counter(n.publication_date.strftime("%Y-%m") for n in latest).items()
            )
        ),
        by_category=dict(
            sorted(
                Counter(
                    c for n in latest for c in (n.categories or ("unclassified",))
                ).items()
            )
        ),
        top_buyers=_buyer_counts(latest),
    )


# --------------------------------------------------------------------------- quality


def data_quality(
    all_notices: Sequence[ProcurementNotice],
    relevant: Sequence[ProcurementNotice],
    excluded: int,
    parse_errors: int,
    fx: FxRateTable,
    index_all: ProcedureIndex,
) -> DataQualityMetrics:
    latest = index_all.notices
    competitions = index_all.competitions()
    results = index_all.results()
    monetary = [n for n in latest if n.estimated_value or n.result_value]
    convertible = sum(
        1
        for n in monetary
        if (
            n.estimated_value
            and value_in_eur(n.estimated_value, n.publication_date, fx) is not None
        )
        or (
            n.result_value
            and value_in_eur(n.result_value, n.award_date, fx) is not None
        )
    )
    with_counts = sum(
        1 for r in results if r.tender_statistics and r.tender_statistics.tender_counts
    )
    return DataQualityMetrics(
        stored_versions=len(all_notices),
        stored_notices=len(latest),
        stored_procedures=len(index_all),
        relevant_notices=len(relevant),
        excluded_central_purchasing=excluded,
        records_by_stage=dict(sorted(Counter(n.stage.value for n in latest).items())),
        parse_errors=parse_errors,
        unlinked_results=sum(1 for r in results if r.procedure_id is None),
        framework_results=sum(1 for r in results if r.is_framework),
        fx_coverage=Coverage(convertible, len(monetary)),
        estimated_value_coverage=Coverage(
            sum(1 for c in competitions if c.estimated_value), len(competitions)
        ),
        result_value_coverage=Coverage(
            sum(1 for r in results if r.result_value), len(results)
        ),
        bid_count_coverage=Coverage(with_counts, len(results)),
        procedure_link_coverage=Coverage(
            sum(1 for r in results if r.procedure_id), len(results)
        ),
        unclassified_share_pct=pct(
            sum(1 for n in relevant if not n.categories), len(relevant)
        ),
        latest_publication_date=max(
            (n.publication_date for n in all_notices), default=None
        ),
        fx_latest_date=fx.latest_date(),
    )


# --------------------------------------------------------------------------- snapshot


def compute_snapshot(
    notices: Iterable[ProcurementNotice],
    fx: FxRateTable,
    config: MetricsConfig,
    today: date,
    *,
    taxonomy: Taxonomy,
    parse_errors: int = 0,
    bootstrap_complete: bool = True,
    computed_at: datetime | None = None,
) -> RadarSnapshot:
    """Compute every metric from stored notice versions (plan §33, §37)."""
    all_notices = list(notices)
    relevant, excluded = relevant_notices(all_notices, config, taxonomy)
    own_org = config.own_organisation
    market = [
        n
        for n in relevant
        if not config.market_countries or n.buyer.country in config.market_countries
    ]
    own_notices = [n for n in relevant if own_org is not None and own_org.matches(n)]
    external = [n for n in market if own_org is None or not own_org.matches(n)]

    index_all = ProcedureIndex.build(all_notices)
    index_market = ProcedureIndex.build(market)
    own_result = (
        organisation_metrics(ProcedureIndex.build(own_notices), today, fx)
        if own_org
        else None
    )
    country_entries = rank_by(
        index_market, today, fx, lambda p: [p.country or "??"], str
    )
    return RadarSnapshot(
        computed_at=computed_at or datetime.now(UTC),
        today=today,
        market=market_metrics(index_market, today, fx, taxonomy),
        external=external_metrics(ProcedureIndex.build(external), today, fx, taxonomy),
        own=own_result,
        peers=peer_metrics(config, relevant, country_entries, own_result, today, fx),
        suppliers=supplier_metrics(index_market, today, fx),
        categories={
            category_id: category_metrics(
                index_market,
                market,
                category_id,
                taxonomy.label(category_id),
                today,
                fx,
            )
            for category_id in config.pinned_categories
        },
        raw={
            country: country_raw_metrics(
                country, all_notices, fx, today, config.relevance_mode, taxonomy
            )
            for country in config.raw_countries
        },
        quality=data_quality(
            all_notices, relevant, excluded, parse_errors, fx, index_all
        ),
        bootstrap_complete=bootstrap_complete,
    )


# --------------------------------------------------------------------------- events


def event_type_for(notice: ProcurementNotice) -> str | None:
    if notice.is_change:
        return "change"
    if notice.stage is NoticeStage.COMPETITION:
        return "new_competition"
    if notice.stage is NoticeStage.RESULT:
        return "result"
    if notice.stage is NoticeStage.MODIFICATION:
        return "contract_modification"
    return None


def _float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def notice_event_attributes(
    notice: ProcurementNotice, fx: FxRateTable
) -> dict[str, Any]:
    """Hard facts only (plan §23)."""
    estimated, result = notice.estimated_value, notice.result_value
    return {
        "notice_id": notice.notice_id,
        "notice_version": notice.notice_version,
        "publication_number": notice.publication_number,
        "procedure_id": notice.procedure_id,
        "stage": notice.stage.value,
        "is_change": notice.is_change,
        "title": notice.title,
        "buyer": notice.buyer.name,
        "buyer_country": notice.buyer.country,
        "publication_date": notice.publication_date.isoformat(),
        "estimated_value": _float(estimated.amount) if estimated else None,
        "estimated_currency": estimated.currency if estimated else None,
        "estimated_value_eur": _float(
            value_in_eur(estimated, notice.publication_date, fx)
        ),
        "result_value": _float(result.amount) if result else None,
        "result_currency": result.currency if result else None,
        "result_value_eur": _float(value_in_eur(result, notice.award_date, fx)),
        "categories": list(notice.categories),
        "match_reasons": sorted(notice.match_reasons),
        "source_url": notice.source_url,
    }


def notice_raw_attributes(notice: ProcurementNotice, fx: FxRateTable) -> dict[str, Any]:
    """Every stored fact about one notice version, for the raw-data device."""
    attrs = notice_event_attributes(notice, fx)
    stats = notice.tender_statistics
    framework = notice.framework_value
    change = notice.change
    attrs.update(
        {
            "notice_type": notice.notice_type,
            "notice_subtype": notice.notice_subtype,
            "buyer_identifiers": list(notice.buyer.identifiers),
            "buyer_count": notice.buyer.count,
            "buyer_legal_type": notice.buyer.legal_type,
            "procedure_type": notice.procedure_type,
            "contract_nature": list(notice.contract_nature),
            "legal_basis": list(notice.legal_basis),
            "cpv_codes": list(notice.cpv_codes),
            "is_framework": notice.is_framework,
            "framework_value": _float(framework.amount) if framework else None,
            "framework_currency": framework.currency if framework else None,
            "winners": [
                {
                    "name": w.name,
                    "identifier": w.identifier,
                    "country": w.country,
                    "size": w.size,
                }
                for w in notice.winners
            ],
            "tenders": list(stats.tender_counts) if stats else [],
            "selection_statuses": list(stats.selection_statuses) if stats else [],
            "decision_dates": (
                [d.isoformat() for d in stats.decision_dates] if stats else []
            ),
            "change_reason": change.reason_code if change else None,
            "changed_notice_id": change.changed_notice_id if change else None,
            "central_purchasing": is_central_purchasing_only(notice),
            "ted_url": attrs.pop("source_url"),
        }
    )
    return attrs


LIST_ATTRIBUTE_KEYS = (
    "publication_number",
    "publication_date",
    "stage",
    "is_change",
    "title",
    "buyer",
    "estimated_value",
    "estimated_currency",
    "estimated_value_eur",
    "result_value",
    "result_currency",
    "result_value_eur",
    "is_framework",
    "categories",
    "tenders",
    "ted_url",
)


def notice_list_attributes(
    notice: ProcurementNotice, fx: FxRateTable
) -> dict[str, Any]:
    """Compact facts for entity attribute lists (recorder caps attributes at 16 kB)."""
    raw = notice_raw_attributes(notice, fx)
    compact = {key: raw[key] for key in LIST_ATTRIBUTE_KEYS}
    compact["buyer_identifier"] = (
        notice.buyer.identifiers[0] if notice.buyer.identifiers else None
    )
    compact["winners"] = [w.name for w in notice.winners]
    return compact


def watchlist_matches(
    notice: ProcurementNotice, watchlist: WatchlistConfig, fx: FxRateTable
) -> bool:
    if watchlist.is_empty:
        return False
    if watchlist.countries and notice.buyer.country not in watchlist.countries:
        return False
    if watchlist.buyer_identifiers and not (
        set(notice.buyer.identifiers) & watchlist.buyer_identifiers
    ):
        return False
    if watchlist.categories and not (set(notice.categories) & watchlist.categories):
        return False
    if watchlist.min_estimated_value_eur is not None:
        estimated = value_in_eur(notice.estimated_value, notice.publication_date, fx)
        if estimated is None or estimated < watchlist.min_estimated_value_eur:
            return False
    if watchlist.min_award_value_eur is not None:
        awarded = value_in_eur(notice.result_value, notice.award_date, fx)
        if awarded is None or awarded < watchlist.min_award_value_eur:
            return False
    return True

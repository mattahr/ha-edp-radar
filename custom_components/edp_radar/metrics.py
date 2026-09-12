"""Pure metrics engine: notices + FX + config + date → RadarSnapshot (plan §16–20, §37).

Nothing in this module imports Home Assistant. Every function is deterministic
given its inputs so the statistics can be unit-tested with hand-calculated data.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from .const import (
    CENTRAL_PURCHASING_BUYER_THRESHOLD,
    MATCH_DEFENCE_BUYER,
    RelevanceMode,
)
from .fx_rates import FxRateTable
from .models import Money, NoticeStage, ProcurementNotice, normalize_name
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
    watchlist: WatchlistConfig = field(default_factory=WatchlistConfig)


# --------------------------------------------------------------------------- windows


@dataclass(frozen=True)
class Window:
    """Half-open rolling period: start < d <= end (plan §15)."""

    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    def contains(self, d: date) -> bool:
        return self.start < d <= self.end


def current_window(today: date, days: int) -> Window:
    return Window(today - timedelta(days=days), today)


def previous_window(today: date, days: int) -> Window:
    return Window(today - timedelta(days=2 * days), today - timedelta(days=days))


# --------------------------------------------------------------------------- helpers


def pct_change(
    current: Decimal | int | None, previous: Decimal | int | None
) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    change = (Decimal(current) - Decimal(previous)) / Decimal(previous) * 100
    return round(float(change), 1)


def pct(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 1)


def median(values: Sequence[float | int]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def value_in_eur(money: Money | None, on: date, fx: FxRateTable) -> Decimal | None:
    if money is None:
        return None
    conversion = fx.convert_to_eur(money, on)
    return conversion.eur_amount if conversion else None


def format_eur(amount: Decimal | None) -> str:
    if amount is None:
        return "EUR n/a"
    value = float(amount)
    if value >= 1e9:
        return f"EUR {value / 1e9:.1f}bn"
    if value >= 1e7:
        return f"EUR {value / 1e6:.0f}m"
    if value >= 1e6:
        return f"EUR {value / 1e6:.1f}m"
    if value >= 1e3:
        return f"EUR {value / 1e3:.0f}k"
    return f"EUR {value:.0f}"


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
class DataQualityMetrics:
    stored_versions: int
    stored_notices: int
    stored_procedures: int
    relevant_notices: int
    excluded_central_purchasing: int
    records_by_stage: Mapping[str, int]
    parse_errors: int
    unlinked_results: int
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
    quality: DataQualityMetrics
    bootstrap_complete: bool

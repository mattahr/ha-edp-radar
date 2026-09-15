"""Sensors reading the RadarSnapshot (plan §16–20, §22, §25, §45; D16, D18).

Every sensor is a thin reader of ``coordinator.data``: the description's
``value_fn``/``attributes_fn`` pick one metric out of the snapshot. Attribute
payloads stay small (rankings and recent lists are capped in the metrics
layer), Decimals become floats and dates become ISO strings.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .config import RadarConfig
from .const import RAW_LIST_LIMIT, country_name
from .coordinator import EdpRadarConfigEntry, EdpRadarCoordinator
from .entity import DeviceKind, EdpRadarEntity
from .fx_rates import FxRateTable
from .metrics import (
    CategoryMetrics,
    CountMetric,
    CountryRawMetrics,
    NoticeHighlight,
    OrganisationMetrics,
    PeerMetrics,
    ProcessMetrics,
    RadarSnapshot,
    Ranking,
    RankingEntry,
    RawList,
    SupplierMetrics,
    ValueMetric,
    notice_list_attributes,
)
from .purchasing import (
    CountryPurchaseSummary,
    CountryRank,
    PurchasingModel,
    categories_text,
    my_country_text,
    top_buyers_text,
)
from .purchasing_attrs import (
    award_attrs as _award_attrs,
)
from .purchasing_attrs import (
    categories_attrs as _categories_attrs,
)
from .purchasing_attrs import (
    country_ranking_attrs as _country_ranking_attrs,
)
from .purchasing_attrs import (
    europe_attrs as _europe_attrs,
)
from .purchasing_attrs import (
    growth_attrs as _growth_attrs,
)
from .purchasing_attrs import (
    largest_attrs as _largest_attrs,
)
from .purchasing_attrs import (
    monthly_attrs,
)
from .purchasing_attrs import (
    period_attrs as _period_attrs,
)
from .purchasing_attrs import (
    rank_row as _rank_row,
)
from .purchasing_attrs import (
    summary_attrs as _summary_attrs,
)
from .spending.sensors import async_setup_spending_sensors

type SensorValue = StateType | datetime
type ValueFn = Callable[[RadarSnapshot], SensorValue]
type AttributesFn = Callable[[RadarSnapshot], dict[str, Any]]
type ExistsFn = Callable[[RadarConfig], bool]

MARKET_POPULATION = "results published by market buyers in the last 365 days"
OWN_POPULATION = "results published by the selected organisation in the last 365 days"


# ------------------------------------------------------------- converters


def _eur(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _iso(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _count_attrs(metric: CountMetric | None) -> dict[str, Any]:
    if metric is None:
        return {}
    return {
        "previous_period": metric.previous,
        "change": metric.change,
        "change_pct": metric.change_pct,
        "period_days": metric.period_days,
    }


def _value_attrs(metric: ValueMetric | None) -> dict[str, Any]:
    if metric is None:
        return {}
    return {
        "previous_period_eur": _eur(metric.previous_eur),
        "change_pct": metric.change_pct,
        "sample_size": metric.sample_size,
        "covered_records": metric.covered,
        "coverage_pct": metric.coverage_pct,
        "period_days": metric.period_days,
    }


def _entry_attrs(entry: RankingEntry) -> dict[str, Any]:
    return {
        "rank": entry.rank,
        "key": entry.key,
        "label": entry.label,
        "value_eur": _eur(entry.value_eur),
        "procedures": entry.procedures,
        "previous_value_eur": _eur(entry.previous_value_eur),
        "previous_procedures": entry.previous_procedures,
        "change_pct": entry.change_pct,
    }


def _ranking_attrs(ranking: Ranking) -> dict[str, Any]:
    return {
        "population": ranking.population,
        "population_size": ranking.population_size,
        "ranking": [_entry_attrs(entry) for entry in ranking.entries],
    }


def _change_attrs(entry: RankingEntry | None) -> dict[str, Any]:
    if entry is None:
        return {}
    return {
        "key": entry.key,
        "label": entry.label,
        "current_value_eur": _eur(entry.value_eur),
        "previous_value_eur": _eur(entry.previous_value_eur),
        "change_eur": _eur(entry.change_eur),
        "change_pct": entry.change_pct,
        "current_procedures": entry.procedures,
        "previous_procedures": entry.previous_procedures,
    }


def _highlight_attrs(highlight: NoticeHighlight | None) -> dict[str, Any]:
    if highlight is None:
        return {}
    return {
        "title": highlight.title,
        "buyer": highlight.buyer,
        "country": highlight.country,
        "publication_date": highlight.publication_date.isoformat(),
        "stage": highlight.stage.value,
        "original_value": _eur(highlight.original_amount),
        "original_currency": highlight.original_currency,
        "value_eur": _eur(highlight.value_eur),
        "categories": list(highlight.categories),
        "ted_url": highlight.source_url,
        "publication_number": highlight.publication_number,
        "notice_id": highlight.notice_id,
        "procedure_id": highlight.procedure_id,
    }


def _tenders_attrs(process: ProcessMetrics | None, population: str) -> dict[str, Any]:
    if process is None:
        return {}
    metric = process.median_tenders_365d
    return {
        "sample_size": metric.sample_size,
        "results_with_bid_count": metric.coverage.covered,
        "results": metric.coverage.population,
        "coverage_pct": metric.coverage.pct,
        "population": population,
    }


def _single_bid_attrs(
    process: ProcessMetrics | None, population: str
) -> dict[str, Any]:
    if process is None:
        return {}
    metric = process.single_bid_share_365d
    return {
        "single_bid_lot_results": metric.numerator,
        "lot_results_with_bid_count": metric.denominator,
        "coverage_pct": metric.coverage.pct,
        "population": population,
    }


def _time_to_result_attrs(
    process: ProcessMetrics | None, population: str
) -> dict[str, Any]:
    if process is None:
        return {}
    metric = process.median_time_to_result_365d
    return {
        "sample_size": metric.sample_size,
        "decided_procedures": metric.coverage.population,
        "procedure_link_coverage_pct": metric.coverage.pct,
        "population": population,
    }


def _non_award_attrs(process: ProcessMetrics | None, population: str) -> dict[str, Any]:
    if process is None:
        return {}
    metric = process.non_award_share_365d
    return {
        "non_awarded_lot_results": metric.numerator,
        "decided_lot_results": metric.denominator,
        "coverage_pct": metric.coverage.pct,
        "population": population,
    }


def _peer_population(
    peers: PeerMetrics | None, attrs: dict[str, Any]
) -> dict[str, Any]:
    if peers is None:
        return attrs
    attrs["population"] = peers.population
    attrs["population_size"] = peers.population_size
    return attrs


def _rank_attrs(peers: PeerMetrics | None) -> dict[str, Any]:
    if peers is None:
        return {}
    return {
        "country": peers.selected_country,
        "population": peers.rank_population,
        "population_size": peers.rank_population_size,
    }


def _supplier_attrs(suppliers: SupplierMetrics) -> dict[str, Any]:
    return {
        "ranking": [
            {
                "rank": s.rank,
                "name": s.name,
                "country": s.country,
                "award_value_eur": _eur(s.award_value_eur),
                "awards": s.awards,
                "key": s.key,
            }
            for s in suppliers.top_suppliers
        ],
        "coverage_pct": suppliers.coverage.pct,
        "covered_results": suppliers.coverage.covered,
        "results_with_winners": suppliers.coverage.population,
        "total_award_value_eur": _eur(suppliers.total_award_value_eur),
        "groups": suppliers.groups,
    }


# ------------------------------------------------------------- descriptions


@dataclass(frozen=True, kw_only=True)
class EdpRadarSensorEntityDescription(SensorEntityDescription):
    """A sensor bound to one device and one snapshot reader."""

    device: DeviceKind
    value_fn: ValueFn
    attributes_fn: AttributesFn | None = None
    exists_fn: ExistsFn = lambda config: True


@dataclass(frozen=True, kw_only=True)
class EdpRadarCategorySensorEntityDescription(SensorEntityDescription):
    """A sensor created once per pinned category."""

    value_fn: Callable[[CategoryMetrics], SensorValue]
    attributes_fn: Callable[[CategoryMetrics], dict[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class EdpRadarRawSensorEntityDescription(SensorEntityDescription):
    """A sensor created once per raw-data country."""

    value_fn: Callable[[CountryRawMetrics, FxRateTable], SensorValue]
    attributes_fn: Callable[[CountryRawMetrics, FxRateTable], dict[str, Any]]


def _own(snapshot: RadarSnapshot) -> OrganisationMetrics | None:
    return snapshot.own


def _peers(snapshot: RadarSnapshot) -> PeerMetrics | None:
    return snapshot.peers


def _has_own(config: RadarConfig) -> bool:
    return config.metrics.own_organisation is not None


def _has_peer_group(config: RadarConfig) -> bool:
    return bool(
        config.metrics.peer_countries or config.metrics.peer_organisation_identifiers
    )


def _has_selected_country(config: RadarConfig) -> bool:
    return config.metrics.selected_country is not None


def _has_own_and_peers(config: RadarConfig) -> bool:
    return _has_own(config) and _has_peer_group(config)


def _count(
    key: str,
    device: DeviceKind,
    metric: Callable[[RadarSnapshot], CountMetric | None],
    **kwargs: Any,
) -> EdpRadarSensorEntityDescription:
    return EdpRadarSensorEntityDescription(
        key=key,
        translation_key=key,
        device=device,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: m.value if (m := metric(s)) is not None else None,
        attributes_fn=lambda s: _count_attrs(metric(s)),
        **kwargs,
    )


def _money(
    key: str,
    device: DeviceKind,
    metric: Callable[[RadarSnapshot], ValueMetric | None],
    **kwargs: Any,
) -> EdpRadarSensorEntityDescription:
    return EdpRadarSensorEntityDescription(
        key=key,
        translation_key=key,
        device=device,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        suggested_display_precision=0,
        value_fn=lambda s: _eur(m.value_eur) if (m := metric(s)) is not None else None,
        attributes_fn=lambda s: _value_attrs(metric(s)),
        **kwargs,
    )


def _process_sensors(
    prefix: str,
    device: DeviceKind,
    process: Callable[[RadarSnapshot], ProcessMetrics | None],
    population: str,
    *,
    exists_fn: ExistsFn = lambda config: True,
    extra_attrs: Callable[[RadarSnapshot, dict[str, Any]], dict[str, Any]] = (
        lambda s, attrs: attrs
    ),
    non_award: bool = True,
) -> tuple[EdpRadarSensorEntityDescription, ...]:
    """The four competition metrics (plan §17) for one population."""
    sensors = [
        EdpRadarSensorEntityDescription(
            key=f"{prefix}_median_tenders_365d",
            translation_key=f"{prefix}_median_tenders_365d",
            device=device,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            value_fn=lambda s: (
                p.median_tenders_365d.value if (p := process(s)) else None
            ),
            attributes_fn=lambda s: extra_attrs(
                s, _tenders_attrs(process(s), population)
            ),
            exists_fn=exists_fn,
        ),
        EdpRadarSensorEntityDescription(
            key=f"{prefix}_single_bid_share_365d",
            translation_key=f"{prefix}_single_bid_share_365d",
            device=device,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            value_fn=lambda s: (
                p.single_bid_share_365d.pct if (p := process(s)) else None
            ),
            attributes_fn=lambda s: extra_attrs(
                s, _single_bid_attrs(process(s), population)
            ),
            exists_fn=exists_fn,
        ),
        EdpRadarSensorEntityDescription(
            key=f"{prefix}_median_public_time_to_result_365d",
            translation_key=f"{prefix}_median_public_time_to_result_365d",
            device=device,
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.DAYS,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            value_fn=lambda s: (
                p.median_time_to_result_365d.value if (p := process(s)) else None
            ),
            attributes_fn=lambda s: extra_attrs(
                s, _time_to_result_attrs(process(s), population)
            ),
            exists_fn=exists_fn,
        ),
    ]
    if non_award:
        sensors.append(
            EdpRadarSensorEntityDescription(
                key=f"{prefix}_non_award_share_365d",
                translation_key=f"{prefix}_non_award_share_365d",
                device=device,
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                suggested_display_precision=1,
                entity_registry_enabled_default=False,
                value_fn=lambda s: (
                    p.non_award_share_365d.pct if (p := process(s)) else None
                ),
                attributes_fn=lambda s: extra_attrs(
                    s, _non_award_attrs(process(s), population)
                ),
                exists_fn=exists_fn,
            )
        )
    return tuple(sensors)


def _text(
    key: str, device: DeviceKind, value_fn: ValueFn, **kwargs: Any
) -> EdpRadarSensorEntityDescription:
    return EdpRadarSensorEntityDescription(
        key=key, translation_key=key, device=device, value_fn=value_fn, **kwargs
    )


def _leader_key(ranking: Ranking) -> str | None:
    return ranking.leader.key if ranking.leader else None


def _leader_label(ranking: Ranking) -> str | None:
    return ranking.leader.label if ranking.leader else None


def _delta(
    key: str,
    value_fn: Callable[[PeerMetrics], float | None],
    own_peer: Callable[
        [PeerMetrics, OrganisationMetrics], tuple[float | None, float | None]
    ],
    **kwargs: Any,
) -> EdpRadarSensorEntityDescription:
    def attributes(s: RadarSnapshot) -> dict[str, Any]:
        if s.peers is None or s.own is None:
            return {}
        own_value, peer_value = own_peer(s.peers, s.own)
        return {"own_value": own_value, "peer_value": peer_value}

    return EdpRadarSensorEntityDescription(
        key=key,
        translation_key=key,
        device=DeviceKind.PEERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: value_fn(s.peers) if s.peers else None,
        attributes_fn=attributes,
        exists_fn=_has_own_and_peers,
        **kwargs,
    )


MARKET = DeviceKind.MARKET
EXTERNAL = DeviceKind.EXTERNAL
ORGANISATION = DeviceKind.ORGANISATION
PEERS = DeviceKind.PEERS
SUPPLIERS = DeviceKind.SUPPLIERS

SENSORS: tuple[EdpRadarSensorEntityDescription, ...] = (
    # --- European Defence Market
    _count(
        "market_new_competitions_30d", MARKET, lambda s: s.market.new_competitions_30d
    ),
    _count(
        "market_new_competitions_90d", MARKET, lambda s: s.market.new_competitions_90d
    ),
    _money(
        "market_estimated_value_30d", MARKET, lambda s: s.market.estimated_value_30d
    ),
    _money(
        "market_estimated_value_90d", MARKET, lambda s: s.market.estimated_value_90d
    ),
    _money("market_award_value_30d", MARKET, lambda s: s.market.award_value_30d),
    _money("market_award_value_90d", MARKET, lambda s: s.market.award_value_90d),
    _text(
        "top_country_by_value_90d",
        MARKET,
        lambda s: _leader_key(s.market.country_ranking_90d),
        attributes_fn=lambda s: _ranking_attrs(s.market.country_ranking_90d),
    ),
    _text(
        "fastest_growing_country_90d",
        MARKET,
        lambda s: _leader_key(s.market.country_growth_90d),
        attributes_fn=lambda s: _ranking_attrs(s.market.country_growth_90d),
    ),
    _text(
        "top_category_by_value_90d",
        MARKET,
        lambda s: _leader_label(s.market.category_ranking_90d),
        attributes_fn=lambda s: _ranking_attrs(s.market.category_ranking_90d),
    ),
    _text(
        "fastest_growing_category_90d",
        MARKET,
        lambda s: _leader_label(s.market.category_growth_90d),
        attributes_fn=lambda s: _ranking_attrs(s.market.category_growth_90d),
    ),
    _text(
        "largest_country_change_90d",
        MARKET,
        lambda s: (
            e.key if (e := s.market.largest_country_change_90d) is not None else None
        ),
        attributes_fn=lambda s: _change_attrs(s.market.largest_country_change_90d),
    ),
    _text(
        "largest_category_change_90d",
        MARKET,
        lambda s: (
            e.label if (e := s.market.largest_category_change_90d) is not None else None
        ),
        attributes_fn=lambda s: _change_attrs(s.market.largest_category_change_90d),
    ),
    _text("market_snapshot_text", MARKET, lambda s: s.market.snapshot_text),
    _text("country_ranking_text", MARKET, lambda s: s.market.country_ranking_text),
    *_process_sensors("market", MARKET, lambda s: s.market.process, MARKET_POPULATION),
    # --- External Radar
    EdpRadarSensorEntityDescription(
        key="external_new_competitions_7d",
        translation_key="external_new_competitions_7d",
        device=EXTERNAL,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.external.new_competitions_7d,
        attributes_fn=lambda s: {
            "recent": [_highlight_attrs(h) for h in s.external.recent_competitions]
        },
    ),
    EdpRadarSensorEntityDescription(
        key="largest_external_competition_7d",
        translation_key="largest_external_competition_7d",
        device=EXTERNAL,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        suggested_display_precision=0,
        value_fn=lambda s: (
            _eur(h.value_eur) if (h := s.external.largest_competition_7d) else None
        ),
        attributes_fn=lambda s: _highlight_attrs(s.external.largest_competition_7d),
    ),
    EdpRadarSensorEntityDescription(
        key="largest_external_award_7d",
        translation_key="largest_external_award_7d",
        device=EXTERNAL,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        suggested_display_precision=0,
        value_fn=lambda s: (
            _eur(h.value_eur) if (h := s.external.largest_award_7d) else None
        ),
        attributes_fn=lambda s: _highlight_attrs(s.external.largest_award_7d),
    ),
    _text("external_latest_text", EXTERNAL, lambda s: s.external.latest_text),
    # --- Selected Organisation
    _count(
        "own_public_competitions_30d",
        ORGANISATION,
        lambda s: o.competitions_30d if (o := _own(s)) else None,
        exists_fn=_has_own,
    ),
    _count(
        "own_public_awards_30d",
        ORGANISATION,
        lambda s: o.awards_30d if (o := _own(s)) else None,
        exists_fn=_has_own,
    ),
    _count(
        "own_public_changes_30d",
        ORGANISATION,
        lambda s: o.changes_30d if (o := _own(s)) else None,
        exists_fn=_has_own,
    ),
    _count(
        "own_public_modifications_365d",
        ORGANISATION,
        lambda s: o.modifications_365d if (o := _own(s)) else None,
        exists_fn=_has_own,
    ),
    _money(
        "own_public_estimated_value_30d",
        ORGANISATION,
        lambda s: o.estimated_value_30d if (o := _own(s)) else None,
        exists_fn=_has_own,
    ),
    _money(
        "own_public_award_value_30d",
        ORGANISATION,
        lambda s: o.award_value_30d if (o := _own(s)) else None,
        exists_fn=_has_own,
    ),
    *_process_sensors(
        "own",
        ORGANISATION,
        lambda s: o.process if (o := _own(s)) else None,
        OWN_POPULATION,
        exists_fn=_has_own,
    ),
    # --- Peer Comparison
    *_process_sensors(
        "peer",
        PEERS,
        lambda s: p.process if (p := _peers(s)) else None,
        "configured peer group",
        exists_fn=_has_peer_group,
        extra_attrs=lambda s, attrs: _peer_population(s.peers, attrs),
        non_award=False,
    ),
    EdpRadarSensorEntityDescription(
        key="selected_country_value_rank_90d",
        translation_key="selected_country_value_rank_90d",
        device=PEERS,
        value_fn=lambda s: p.value_rank_90d if (p := _peers(s)) else None,
        attributes_fn=lambda s: _rank_attrs(s.peers),
        exists_fn=_has_selected_country,
    ),
    EdpRadarSensorEntityDescription(
        key="selected_country_activity_rank_90d",
        translation_key="selected_country_activity_rank_90d",
        device=PEERS,
        value_fn=lambda s: p.activity_rank_90d if (p := _peers(s)) else None,
        attributes_fn=lambda s: _rank_attrs(s.peers),
        exists_fn=_has_selected_country,
    ),
    EdpRadarSensorEntityDescription(
        key="selected_country_value_percentile_90d",
        translation_key="selected_country_value_percentile_90d",
        device=PEERS,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda s: p.value_percentile_90d if (p := _peers(s)) else None,
        attributes_fn=lambda s: _rank_attrs(s.peers),
        exists_fn=_has_selected_country,
    ),
    _delta(
        "own_vs_peer_single_bid_delta_pp",
        lambda p: p.single_bid_delta_pp,
        lambda p, o: (
            o.process.single_bid_share_365d.pct,
            p.process.single_bid_share_365d.pct,
        ),
        native_unit_of_measurement=PERCENTAGE,
    ),
    _delta(
        "own_vs_peer_median_tenders_delta",
        lambda p: p.median_tenders_delta,
        lambda p, o: (
            o.process.median_tenders_365d.value,
            p.process.median_tenders_365d.value,
        ),
    ),
    _delta(
        "own_vs_peer_public_time_to_result_delta_days",
        lambda p: p.time_to_result_delta_days,
        lambda p, o: (
            o.process.median_time_to_result_365d.value,
            p.process.median_time_to_result_365d.value,
        ),
        native_unit_of_measurement=UnitOfTime.DAYS,
    ),
    # --- Supplier Landscape (D18: created but disabled by default)
    EdpRadarSensorEntityDescription(
        key="top_supplier_by_award_value_365d",
        translation_key="top_supplier_by_award_value_365d",
        device=SUPPLIERS,
        entity_registry_enabled_default=False,
        value_fn=lambda s: (
            s.suppliers.top_suppliers[0].name if s.suppliers.top_suppliers else None
        ),
        attributes_fn=lambda s: _supplier_attrs(s.suppliers),
    ),
    EdpRadarSensorEntityDescription(
        key="supplier_top5_share_365d",
        translation_key="supplier_top5_share_365d",
        device=SUPPLIERS,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.suppliers.top5_share_pct,
        attributes_fn=lambda s: _supplier_attrs(s.suppliers),
    ),
)

CATEGORY_SENSORS: tuple[EdpRadarCategorySensorEntityDescription, ...] = (
    EdpRadarCategorySensorEntityDescription(
        key="competitions_30d",
        translation_key="category_competitions_30d",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.competitions_30d.value,
        attributes_fn=lambda c: _count_attrs(c.competitions_30d),
    ),
    EdpRadarCategorySensorEntityDescription(
        key="competitions_change_pct",
        translation_key="category_competitions_change_pct",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda c: c.competitions_30d.change_pct,
        attributes_fn=lambda c: _count_attrs(c.competitions_30d),
    ),
    EdpRadarCategorySensorEntityDescription(
        key="estimated_value_90d",
        translation_key="category_estimated_value_90d",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        suggested_display_precision=0,
        value_fn=lambda c: _eur(c.estimated_value_90d.value_eur),
        attributes_fn=lambda c: _value_attrs(c.estimated_value_90d),
    ),
    EdpRadarCategorySensorEntityDescription(
        key="estimated_value_change_pct",
        translation_key="category_estimated_value_change_pct",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda c: c.estimated_value_90d.change_pct,
        attributes_fn=lambda c: _value_attrs(c.estimated_value_90d),
    ),
    EdpRadarCategorySensorEntityDescription(
        key="award_value_90d",
        translation_key="category_award_value_90d",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        suggested_display_precision=0,
        value_fn=lambda c: _eur(c.award_value_90d.value_eur),
        attributes_fn=lambda c: _value_attrs(c.award_value_90d),
    ),
)


def _raw_list_sensor(
    key: str, pick: Callable[[CountryRawMetrics], RawList]
) -> EdpRadarRawSensorEntityDescription:
    return EdpRadarRawSensorEntityDescription(
        key=key,
        translation_key=f"raw_{key}",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda r, fx: pick(r).count_30d,
        attributes_fn=lambda r, fx: {
            "notices": [notice_list_attributes(n, fx) for n in pick(r).latest]
        },
    )


RAW_SENSORS: tuple[EdpRadarRawSensorEntityDescription, ...] = (
    EdpRadarRawSensorEntityDescription(
        key="notices_7d",
        translation_key="raw_notices_7d",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda r, fx: r.notices_7d,
        attributes_fn=lambda r, fx: {
            "notices": [notice_list_attributes(n, fx) for n in r.latest]
        },
    ),
    _raw_list_sensor("competitions_30d", lambda r: r.competitions),
    _raw_list_sensor("results_30d", lambda r: r.results),
    _raw_list_sensor("changes_30d", lambda r: r.changes),
    _raw_list_sensor("planning_30d", lambda r: r.planning),
    _raw_list_sensor("direct_awards_30d", lambda r: r.direct_awards),
    _raw_list_sensor("modifications_30d", lambda r: r.modifications),
    EdpRadarRawSensorEntityDescription(
        key="stored_notices",
        translation_key="raw_stored_notices",
        value_fn=lambda r, fx: r.stored_notices,
        attributes_fn=lambda r, fx: {
            "stored_versions": r.stored_versions,
            "by_stage": dict(r.by_stage),
            "by_month": dict(r.by_month),
            "by_category": dict(r.by_category),
            "top_buyers": [
                {
                    "name": b.name,
                    "identifiers": list(b.identifiers),
                    "notices": b.notices,
                }
                for b in r.top_buyers
            ],
        },
    ),
)

# ------------------------------------------------------------- purchasing (Phase 2)

type PurchasingValueFn = Callable[[PurchasingModel, str | None], SensorValue]
type PurchasingAttributesFn = Callable[[PurchasingModel, str | None], dict[str, Any]]


@dataclass(frozen=True, kw_only=True)
class EdpRadarPurchasingSensorEntityDescription(SensorEntityDescription):
    """A sensor reading the country purchasing model; ``country`` is My country."""

    device: DeviceKind
    value_fn: PurchasingValueFn
    attributes_fn: PurchasingAttributesFn | None = None
    exists_fn: ExistsFn = lambda config: True


def _mine(
    model: PurchasingModel, country: str | None, days: int | None = None
) -> CountryPurchaseSummary | None:
    period = model.primary if days is None else model.secondary[days]
    return period.countries.get(country) if country else None


def _my_rank(model: PurchasingModel, country: str | None) -> CountryRank | None:
    return model.primary.rank_of(country) if country else None


def _my_country_value_attrs(
    model: PurchasingModel, country: str | None
) -> dict[str, Any]:
    summary = _mine(model, country)
    if summary is None:
        return {"country": country}
    return {
        **_summary_attrs(summary),
        "monthly": monthly_attrs(model.monthly_series(summary.country)),
    }


def _my_country_rank_attrs(
    model: PurchasingModel, country: str | None
) -> dict[str, Any]:
    period = model.primary
    summary = _mine(model, country)
    entry = _my_rank(model, country)
    return {
        "country": country,
        **_period_attrs(period.europe),
        "share_pct": entry.share_pct if entry else None,
        "population_size": len(period.ranking),
        "countries_active": period.europe.countries_active,
        "awards": summary.award_count if summary else None,
        "valued_awards": summary.valued_awards if summary else None,
        "value_status": (
            "no awards in the period"
            if summary is None or not summary.award_count
            else "value unknown: no award with a usable value"
            if entry is None
            else "ranked"
        ),
    }


def _my(
    key: str,
    value_fn: PurchasingValueFn,
    attributes_fn: PurchasingAttributesFn | None = None,
    **kwargs: Any,
) -> EdpRadarPurchasingSensorEntityDescription:
    return EdpRadarPurchasingSensorEntityDescription(
        key=key,
        translation_key=key,
        device=DeviceKind.MY_COUNTRY,
        value_fn=value_fn,
        attributes_fn=attributes_fn,
        exists_fn=_has_selected_country,
        **kwargs,
    )


def _purchasing_money(
    key: str,
    device: DeviceKind,
    value_fn: PurchasingValueFn,
    attributes_fn: PurchasingAttributesFn | None = None,
    **kwargs: Any,
) -> EdpRadarPurchasingSensorEntityDescription:
    return EdpRadarPurchasingSensorEntityDescription(
        key=key,
        translation_key=key,
        device=device,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        suggested_display_precision=0,
        value_fn=value_fn,
        attributes_fn=attributes_fn,
        exists_fn=(
            _has_selected_country
            if device is DeviceKind.MY_COUNTRY
            else (lambda config: True)
        ),
        **kwargs,
    )


def _my_value(model: PurchasingModel, country: str | None) -> float | None:
    summary = _mine(model, country)
    return _eur(summary.award_value_eur) if summary else None


PURCHASING_SENSORS: tuple[EdpRadarPurchasingSensorEntityDescription, ...] = (
    # --- My Country (Phase 2 §19, §24)
    _purchasing_money(
        "my_country_awarded_value_12m",
        DeviceKind.MY_COUNTRY,
        _my_value,
        _my_country_value_attrs,
    ),
    _purchasing_money(
        "my_country_awarded_value_previous_12m",
        DeviceKind.MY_COUNTRY,
        lambda m, c: _eur(s.previous_value_eur) if (s := _mine(m, c)) else None,
        lambda m, c: (
            {
                "country": c,
                "period_days": s.window.days,
                "period_end": s.window.start.isoformat(),
                "awards": s.previous_award_count,
            }
            if (s := _mine(m, c))
            else {"country": c}
        ),
    ),
    _my(
        "my_country_awarded_value_change_pct",
        lambda m, c: s.change_pct if (s := _mine(m, c)) else None,
        lambda m, c: (
            {
                "country": c,
                "current_eur": _eur(s.award_value_eur),
                "previous_eur": _eur(s.previous_value_eur),
                "change_eur": _eur(s.change_eur),
            }
            if (s := _mine(m, c))
            else {"country": c}
        ),
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
    ),
    _my(
        "my_country_rank_12m",
        lambda m, c: e.rank if (e := _my_rank(m, c)) else None,
        _my_country_rank_attrs,
    ),
    _my(
        "my_country_share_12m",
        lambda m, c: e.share_pct if (e := _my_rank(m, c)) else None,
        _my_country_rank_attrs,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
    ),
    _my(
        "my_country_awards_12m",
        lambda m, c: s.award_count if (s := _mine(m, c)) else None,
        lambda m, c: _summary_attrs(s) if (s := _mine(m, c)) else {"country": c},
        state_class=SensorStateClass.MEASUREMENT,
    ),
    _my(
        "my_country_value_coverage_12m",
        lambda m, c: s.value_coverage_pct if (s := _mine(m, c)) else None,
        lambda m, c: _summary_attrs(s) if (s := _mine(m, c)) else {"country": c},
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
    ),
    _my(
        "my_country_top_category_12m",
        lambda m, c: (
            s.top_categories[0].label
            if (s := _mine(m, c)) and s.top_categories
            else None
        ),
        lambda m, c: (
            {
                "country": c,
                **_period_attrs(s),
                **_categories_attrs(s),
                "unclassified_share_pct": s.unclassified_share_pct,
            }
            if (s := _mine(m, c))
            else {"country": c}
        ),
    ),
    _purchasing_money(
        "my_country_largest_award_12m",
        DeviceKind.MY_COUNTRY,
        lambda m, c: (
            _eur(s.largest_awards[0].value_eur)
            if (s := _mine(m, c)) and s.largest_awards
            else None
        ),
        lambda m, c: _largest_attrs(s.largest_awards, s) if (s := _mine(m, c)) else {},
    ),
    _purchasing_money(
        "my_country_awarded_value_90d",
        DeviceKind.MY_COUNTRY,
        lambda m, c: _eur(s.award_value_eur) if (s := _mine(m, c, 90)) else None,
        lambda m, c: (
            {
                **_summary_attrs(s),
                "value_30d_eur": (
                    _eur(t.award_value_eur) if (t := _mine(m, c, 30)) else None
                ),
            }
            if (s := _mine(m, c, 90))
            else {"country": c}
        ),
    ),
    _my(
        "my_country_summary_text",
        lambda m, c: my_country_text(m.primary, c) if c else None,
    ),
    _my(
        "my_country_categories_text",
        lambda m, c: categories_text(s) if (s := _mine(m, c)) else None,
    ),
    # --- European Purchasing (Phase 2 §16, §19)
    _purchasing_money(
        "europe_awarded_value_12m",
        DeviceKind.PURCHASING,
        lambda m, c: _eur(m.primary.europe.total_value_eur),
        lambda m, c: {
            **_europe_attrs(m.primary.europe),
            **_categories_attrs(m.primary.europe),
        },
    ),
    _purchasing_money(
        "europe_awarded_value_90d",
        DeviceKind.PURCHASING,
        lambda m, c: _eur(m.secondary[90].europe.total_value_eur),
        lambda m, c: {
            **_europe_attrs(m.secondary[90].europe),
            "value_30d_eur": _eur(m.secondary[30].europe.total_value_eur),
        },
    ),
    EdpRadarPurchasingSensorEntityDescription(
        key="europe_largest_buyer_12m",
        translation_key="europe_largest_buyer_12m",
        device=DeviceKind.PURCHASING,
        value_fn=lambda m, c: (
            e.country if (e := m.primary.europe.largest_buyer) else None
        ),
        attributes_fn=lambda m, c: (
            _rank_row(e, c) if (e := m.primary.europe.largest_buyer) else {}
        ),
    ),
    _purchasing_money(
        "europe_largest_buyer_value_12m",
        DeviceKind.PURCHASING,
        lambda m, c: (
            _eur(e.summary.award_value_eur)
            if (e := m.primary.europe.largest_buyer)
            else None
        ),
        lambda m, c: _rank_row(e, c) if (e := m.primary.europe.largest_buyer) else {},
    ),
    EdpRadarPurchasingSensorEntityDescription(
        key="europe_countries_with_value_12m",
        translation_key="europe_countries_with_value_12m",
        device=DeviceKind.PURCHASING,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda m, c: m.primary.europe.countries_with_value,
        attributes_fn=lambda m, c: {
            **_period_attrs(m.primary.europe),
            "countries_active": m.primary.europe.countries_active,
            "unranked": list(m.primary.unranked),
        },
    ),
    _purchasing_money(
        "europe_joint_value_12m",
        DeviceKind.PURCHASING,
        lambda m, c: _eur(m.primary.europe.joint_value_eur),
        lambda m, c: {
            **_period_attrs(m.primary.europe),
            "unknown_country_eur": _eur(m.primary.europe.unknown_country_value_eur),
            "joint_awards": (
                s.award_count if (s := m.primary.countries.get("MULTI")) else 0
            ),
        },
    ),
    _purchasing_money(
        "europe_largest_award_12m",
        DeviceKind.PURCHASING,
        lambda m, c: (
            _eur(a[0].value_eur) if (a := m.primary.europe.largest_awards) else None
        ),
        lambda m, c: _largest_attrs(m.primary.europe.largest_awards, m.primary.europe),
    ),
    EdpRadarPurchasingSensorEntityDescription(
        key="europe_quarantined_awards",
        translation_key="europe_quarantined_awards",
        device=DeviceKind.PURCHASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda m, c: len(m.quarantined),
        attributes_fn=lambda m, c: {
            # Largest first; the recorder caps attributes at 16 kB.
            "quarantined": [_award_attrs(a) for a in m.quarantined[:RAW_LIST_LIMIT]],
            "rules": [
                "above_absolute_cap: EUR 10bn",
                "exceeds_estimate: 100× a real estimate (≥ 10 000)",
                "exceeds_tender_values: 100× the notice's own tender values",
                "duplicate_value_in_procedure: same value repeated in a procedure",
            ],
        },
    ),
    EdpRadarPurchasingSensorEntityDescription(
        key="top_buyers_text",
        translation_key="top_buyers_text",
        device=DeviceKind.PURCHASING,
        value_fn=lambda m, c: top_buyers_text(m.primary),
    ),
    # --- Country Ranking (Phase 2 §18, §23)
    EdpRadarPurchasingSensorEntityDescription(
        key="country_ranking_12m",
        translation_key="country_ranking_12m",
        device=DeviceKind.RANKING,
        value_fn=lambda m, c: (
            m.primary.ranking[0].country if m.primary.ranking else None
        ),
        attributes_fn=lambda m, c: _country_ranking_attrs(m.primary, c),
    ),
    EdpRadarPurchasingSensorEntityDescription(
        key="country_ranking_90d",
        translation_key="country_ranking_90d",
        device=DeviceKind.RANKING,
        value_fn=lambda m, c: (
            m.secondary[90].ranking[0].country if m.secondary[90].ranking else None
        ),
        attributes_fn=lambda m, c: _country_ranking_attrs(m.secondary[90], c),
    ),
    EdpRadarPurchasingSensorEntityDescription(
        key="country_growth_ranking_12m",
        translation_key="country_growth_ranking_12m",
        device=DeviceKind.RANKING,
        value_fn=lambda m, c: m.primary.growth[0].country if m.primary.growth else None,
        attributes_fn=lambda m, c: _growth_attrs(m.primary, c),
    ),
)


FRESHNESS = SensorEntityDescription(
    key="ted_data_last_updated",
    translation_key="ted_data_last_updated",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)


# ------------------------------------------------------------- platform


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EdpRadarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors that the configuration calls for."""
    coordinator = entry.runtime_data.radar
    config = coordinator.config
    entities: list[SensorEntity] = [
        EdpRadarSensor(coordinator, description)
        for description in SENSORS
        if description.exists_fn(config)
    ]
    entities.append(EdpRadarFreshnessSensor(coordinator))
    entities.extend(
        EdpRadarPurchasingSensor(coordinator, description)
        for description in PURCHASING_SENSORS
        if description.exists_fn(config)
    )
    for category_id in config.metrics.pinned_categories:
        label = coordinator.taxonomy.label(category_id)
        entities.extend(
            EdpRadarCategorySensor(coordinator, description, category_id, label)
            for description in CATEGORY_SENSORS
        )
    for country in config.metrics.raw_countries:
        entities.extend(
            EdpRadarRawSensor(coordinator, description, country)
            for description in RAW_SENSORS
        )
    async_add_entities(entities)
    async_setup_spending_sensors(entry, async_add_entities)


class EdpRadarSensor(EdpRadarEntity, SensorEntity):
    """A sensor reading one metric from the snapshot."""

    entity_description: EdpRadarSensorEntityDescription

    def __init__(
        self,
        coordinator: EdpRadarCoordinator,
        description: EdpRadarSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description, description.device)

    @property
    def native_value(self) -> SensorValue:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        return self.entity_description.value_fn(snapshot)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        snapshot = self.snapshot
        if snapshot is None or self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(snapshot)


class EdpRadarPurchasingSensor(EdpRadarEntity, SensorEntity):
    """A sensor reading the country purchasing model for My country."""

    entity_description: EdpRadarPurchasingSensorEntityDescription

    def __init__(
        self,
        coordinator: EdpRadarCoordinator,
        description: EdpRadarPurchasingSensorEntityDescription,
    ) -> None:
        country = coordinator.config.metrics.selected_country
        if description.device is DeviceKind.MY_COUNTRY and country:
            super().__init__(
                coordinator,
                description,
                description.device,
                suffix=country,
                label=country_name(country),
            )
        else:
            super().__init__(coordinator, description, description.device)
        self._country = country

    @property
    def native_value(self) -> SensorValue:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        return self.entity_description.value_fn(snapshot.purchasing, self._country)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        snapshot = self.snapshot
        if snapshot is None or self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(snapshot.purchasing, self._country)


class EdpRadarCategorySensor(EdpRadarEntity, SensorEntity):
    """A sensor for one pinned strategic category."""

    entity_description: EdpRadarCategorySensorEntityDescription

    def __init__(
        self,
        coordinator: EdpRadarCoordinator,
        description: EdpRadarCategorySensorEntityDescription,
        category_id: str,
        category_label: str,
    ) -> None:
        super().__init__(
            coordinator,
            description,
            DeviceKind.CATEGORY,
            suffix=category_id,
            label=category_label,
        )
        self._category_id = category_id

    def _metrics(self) -> CategoryMetrics | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        return snapshot.categories.get(self._category_id)

    @property
    def native_value(self) -> SensorValue:
        metrics = self._metrics()
        return None if metrics is None else self.entity_description.value_fn(metrics)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        metrics = self._metrics()
        if metrics is None or self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(metrics)


class EdpRadarRawSensor(EdpRadarEntity, SensorEntity):
    """A raw-data sensor for one buyer country."""

    entity_description: EdpRadarRawSensorEntityDescription

    def __init__(
        self,
        coordinator: EdpRadarCoordinator,
        description: EdpRadarRawSensorEntityDescription,
        country: str,
    ) -> None:
        super().__init__(
            coordinator,
            description,
            DeviceKind.RAW,
            suffix=country,
            label=country_name(country),
        )
        self._country = country

    def _metrics(self) -> CountryRawMetrics | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        return snapshot.raw.get(self._country)

    @property
    def native_value(self) -> SensorValue:
        metrics = self._metrics()
        if metrics is None:
            return None
        return self.entity_description.value_fn(metrics, self.coordinator.store.fx)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        metrics = self._metrics()
        if metrics is None:
            return None
        return self.entity_description.attributes_fn(metrics, self.coordinator.store.fx)


class EdpRadarFreshnessSensor(EdpRadarEntity, SensorEntity):
    """Last successful TED refresh plus ingestion state (plan §45, D8)."""

    def __init__(self, coordinator: EdpRadarCoordinator) -> None:
        super().__init__(coordinator, FRESHNESS, DeviceKind.MARKET)

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.store.index.last_successful_update

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        coordinator = self.coordinator
        index = coordinator.store.index
        data = coordinator.data
        progress = coordinator.bootstrap_progress
        return {
            "latest_publication_date": _iso(index.last_publication_date),
            "stored_versions": len(coordinator.store.notices),
            "stored_notices": data.quality.stored_notices if data else None,
            "stored_procedures": data.quality.stored_procedures if data else None,
            "bootstrap_complete": data.bootstrap_complete if data else False,
            "bootstrap_progress": (
                {"fetched": progress[0], "total": progress[1]} if progress else None
            ),
            "last_ted_error": coordinator.last_ted_error,
            "last_fx_error": coordinator.last_fx_error,
            "fx_latest_date": _iso(coordinator.store.fx.latest_date()),
            "taxonomy_version": index.taxonomy_version,
        }

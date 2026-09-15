"""Spending sensors (Phase 3 Plan 2; spec S30–S37, S43).

One ``SpendingSensor`` per description; each reads one source's
``SourceSeries`` from the ``SpendingCoordinator`` snapshot and never fetches
anything itself. Money is exposed in whole currency units (S32); Sweden is
the fixed focus (S2); rankings never cross sources (S8).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from ..entity import spending_device_info
from .attrs import (
    MILLION,
    Companion,
    monthly_series_attrs,
    price_base_year,
    provenance_attrs,
    ranking_attrs,
    scaled,
)
from .calculations import (
    MonthChange,
    Ranking,
    YtdChange,
    annual_series,
    coverage,
    latest_month,
    latest_year,
    month_change,
    monthly_series,
    nominal_change_pct,
    rank,
    value_at,
    ytd_change,
)
from .coordinator import SpendingCoordinator
from .models import DatapointStatus, ReferencePeriod, SourceSeries, SpendingDataPoint
from .registry import (
    EDA,
    EUROSTAT,
    FOCUS_COUNTRY,
    NATO,
    STATSKONTORET,
    metric_spec,
    source_spec,
)
from .text import nato_position_text, statskontoret_snapshot_text

if TYPE_CHECKING:
    from ..coordinator import EdpRadarConfigEntry

type ValueFn = Callable[[SourceSeries, date], StateType]
type AttributesFn = Callable[[SourceSeries, date, datetime], dict[str, Any]]


@dataclass(frozen=True, kw_only=True)
class SpendingSensorEntityDescription(SensorEntityDescription):
    """A sensor bound to one source device and one reader of its series."""

    source_id: str
    value_fn: ValueFn
    attributes_fn: AttributesFn | None = None


# ----------------------------------------------------------------- builders


def _money(
    key: str,
    source_id: str,
    currency: str,
    value_fn: ValueFn,
    attributes_fn: AttributesFn | None = None,
) -> SpendingSensorEntityDescription:
    return SpendingSensorEntityDescription(
        key=key,
        translation_key=key,
        source_id=source_id,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=currency,
        suggested_display_precision=0,
        value_fn=value_fn,
        attributes_fn=attributes_fn,
    )


def _pct(
    key: str,
    source_id: str,
    value_fn: ValueFn,
    attributes_fn: AttributesFn | None = None,
) -> SpendingSensorEntityDescription:
    return SpendingSensorEntityDescription(
        key=key,
        translation_key=key,
        source_id=source_id,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=value_fn,
        attributes_fn=attributes_fn,
    )


def _rank(
    key: str,
    source_id: str,
    value_fn: ValueFn,
    attributes_fn: AttributesFn,
) -> SpendingSensorEntityDescription:
    return SpendingSensorEntityDescription(
        key=key,
        translation_key=key,
        source_id=source_id,
        value_fn=value_fn,
        attributes_fn=attributes_fn,
    )


def _text(
    key: str,
    source_id: str,
    value_fn: ValueFn,
    attributes_fn: AttributesFn | None = None,
) -> SpendingSensorEntityDescription:
    return SpendingSensorEntityDescription(
        key=key,
        translation_key=key,
        source_id=source_id,
        value_fn=value_fn,
        attributes_fn=attributes_fn,
    )


def _age(
    key: str, source_id: str, value_fn: ValueFn, attributes_fn: AttributesFn
) -> SpendingSensorEntityDescription:
    return SpendingSensorEntityDescription(
        key=key,
        translation_key=key,
        source_id=source_id,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=value_fn,
        attributes_fn=attributes_fn,
    )


def _provenance(
    point: SpendingDataPoint,
    series: SourceSeries,
    today: date,
    *,
    reference: ReferencePeriod | None = None,
    status: DatapointStatus | None = None,
) -> dict[str, Any]:
    return provenance_attrs(
        point,
        spec=source_spec(point.source_id),
        metric=metric_spec(point.source_id, point.metric_id),
        retrieved_at=series.retrieved_at,
        today=today,
        reference=reference,
        status=status,
    )


def _pct_value(value: Decimal | None) -> float | None:
    return scaled(value, 1)


# ------------------------------------------------------------ Statskontoret

MATERIEL = "materiel_outturn"
DEFENCE = "uo6_defence_outturn"
UO6_TOTAL = "uo6_total_outturn"


def _sk_ytd(
    series: SourceSeries, metric_id: str
) -> tuple[SpendingDataPoint, YtdChange] | None:
    latest = latest_month(series.datapoints, metric_id, FOCUS_COUNTRY)
    if latest is None:
        return None
    change = ytd_change(
        series.datapoints,
        metric_id,
        FOCUS_COUNTRY,
        latest.reference.start.year,
        latest.reference.start.month,
    )
    return None if change is None else (latest, change)


def _ytd_reference(latest: SpendingDataPoint) -> ReferencePeriod:
    end = latest.reference.end
    return ReferencePeriod(date(end.year, 1, 1), end, f"Jan–{latest.reference.label}")


def _sk_ytd_value(metric_id: str) -> ValueFn:
    return lambda series, today: (
        scaled(pair[1].current, MILLION)
        if (pair := _sk_ytd(series, metric_id))
        else None
    )


def _sk_ytd_attrs(metric_id: str) -> AttributesFn:
    def attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
        pair = _sk_ytd(series, metric_id)
        if pair is None:
            return {}
        latest, change = pair
        year = latest.reference.start.year
        months = monthly_series(series.datapoints, metric_id, FOCUS_COUNTRY)
        out = _provenance(latest, series, today, reference=_ytd_reference(latest))
        out.update(
            {
                "months_included": change.months,
                "previous_year_ytd_sek": scaled(change.previous, MILLION),
                "change_pct": _pct_value(change.pct),
                "monthly_current_year": monthly_series_attrs(
                    months, year, "sek", MILLION
                ),
                "monthly_previous_year": monthly_series_attrs(
                    months, year - 1, "sek", MILLION
                ),
            }
        )
        if metric_id == DEFENCE:
            total = _sk_ytd(series, UO6_TOTAL)
            out["uo6_total_ytd_sek"] = (
                scaled(total[1].current, MILLION) if total else None
            )
        return out

    return attrs


def _sk_month(series: SourceSeries, metric_id: str) -> MonthChange | None:
    latest = latest_month(series.datapoints, metric_id, FOCUS_COUNTRY)
    if latest is None:
        return None
    return month_change(
        series.datapoints,
        metric_id,
        FOCUS_COUNTRY,
        latest.reference.start.year,
        latest.reference.start.month,
    )


def _sk_month_value(metric_id: str) -> ValueFn:
    return lambda series, today: (
        scaled(m.current.value, MILLION)
        if (m := _sk_month(series, metric_id))
        else None
    )


def _sk_month_attrs(metric_id: str) -> AttributesFn:
    def attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
        change = _sk_month(series, metric_id)
        if change is None:
            return {}
        out = _provenance(change.current, series, today)
        out.update(
            {
                "month_label": change.current.reference.label,
                "same_month_previous_year_sek": scaled(
                    change.previous.value if change.previous else None, MILLION
                ),
                "change_pct": _pct_value(change.pct),
            }
        )
        return out

    return attrs


def _sk_change_value(metric_id: str) -> ValueFn:
    return lambda series, today: (
        _pct_value(pair[1].pct) if (pair := _sk_ytd(series, metric_id)) else None
    )


def _sk_change_attrs(metric_id: str) -> AttributesFn:
    def attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
        pair = _sk_ytd(series, metric_id)
        if pair is None:
            return {}
        latest, change = pair
        out = _provenance(latest, series, today, reference=_ytd_reference(latest))
        out.update(
            {
                "current_sek": scaled(change.current, MILLION),
                "previous_sek": scaled(change.previous, MILLION),
                "change_sek": scaled(change.change, MILLION),
            }
        )
        return out

    return attrs


def _sk_snapshot(series: SourceSeries, today: date) -> StateType:
    pair = _sk_ytd(series, MATERIEL)
    if pair is None:
        return None
    return statskontoret_snapshot_text(pair[1], pair[0].reference.label)


def _sk_snapshot_attrs(
    series: SourceSeries, today: date, now: datetime
) -> dict[str, Any]:
    pair = _sk_ytd(series, MATERIEL)
    if pair is None:
        return {}
    latest, _change = pair
    return _provenance(latest, series, today, reference=_ytd_reference(latest))


STATSKONTORET_SENSORS: tuple[SpendingSensorEntityDescription, ...] = (
    _money(
        "statskontoret_materiel_ytd",
        STATSKONTORET,
        "SEK",
        _sk_ytd_value(MATERIEL),
        _sk_ytd_attrs(MATERIEL),
    ),
    _money(
        "statskontoret_materiel_latest_month",
        STATSKONTORET,
        "SEK",
        _sk_month_value(MATERIEL),
        _sk_month_attrs(MATERIEL),
    ),
    _pct(
        "statskontoret_materiel_ytd_change_pct",
        STATSKONTORET,
        _sk_change_value(MATERIEL),
        _sk_change_attrs(MATERIEL),
    ),
    _money(
        "statskontoret_defence_ytd",
        STATSKONTORET,
        "SEK",
        _sk_ytd_value(DEFENCE),
        _sk_ytd_attrs(DEFENCE),
    ),
    _money(
        "statskontoret_defence_latest_month",
        STATSKONTORET,
        "SEK",
        _sk_month_value(DEFENCE),
        _sk_month_attrs(DEFENCE),
    ),
    _pct(
        "statskontoret_defence_ytd_change_pct",
        STATSKONTORET,
        _sk_change_value(DEFENCE),
        _sk_change_attrs(DEFENCE),
    ),
    _text(
        "statskontoret_snapshot_text",
        STATSKONTORET,
        _sk_snapshot,
        _sk_snapshot_attrs,
    ),
)


# ------------------------------------------------------- annual sources


def _latest(
    series: SourceSeries, metric_id: str, unit: str | None = None
) -> SpendingDataPoint | None:
    return latest_year(series.datapoints, metric_id, FOCUS_COUNTRY, unit=unit)


def _ranking(series: SourceSeries, point: SpendingDataPoint) -> Ranking | None:
    """Rank Sweden's datapoint within its own metric, reference and unit."""
    return rank(
        series.datapoints,
        metric_id=point.metric_id,
        unit=point.unit,
        reference=point.reference,
    )


def _companion(
    series: SourceSeries, metric_id: str, reference: ReferencePeriod, scale: int
) -> Companion:
    return (
        lambda country: value_at(series.datapoints, metric_id, country, reference),
        scale,
    )


def _focus_value(
    series: SourceSeries, metric_id: str, reference: ReferencePeriod
) -> Decimal | None:
    return value_at(series.datapoints, metric_id, FOCUS_COUNTRY, reference)


def _focus_rank(
    series: SourceSeries, metric_id: str, unit: str, reference: ReferencePeriod
) -> int | None:
    ranking = rank(
        series.datapoints, metric_id=metric_id, unit=unit, reference=reference
    )
    return None if ranking is None else ranking.focus_rank


def _year_over_year(
    series: SourceSeries, point: SpendingDataPoint
) -> tuple[Decimal | None, Decimal | None]:
    """``(previous year's value, change %)`` for the focus country."""
    annual = annual_series(
        series.datapoints, point.metric_id, FOCUS_COUNTRY, unit=point.unit
    )
    previous = annual.get(point.reference.start.year - 1)
    if previous is None:
        return None, None
    return previous.value, nominal_change_pct(point.value, previous.value)


def _annual_value(metric_id: str, scale: int = MILLION) -> ValueFn:
    return lambda series, today: (
        scaled(p.value, scale) if (p := _latest(series, metric_id)) else None
    )


def _rank_value(metric_id: str) -> ValueFn:
    def value(series: SourceSeries, today: date) -> StateType:
        point = _latest(series, metric_id)
        ranking = _ranking(series, point) if point else None
        return None if ranking is None else ranking.focus_rank

    return value


def _rank_attrs(
    metric_id: str,
    value_key: str,
    scale: int,
    companions: dict[str, tuple[str, int]] | None = None,
) -> AttributesFn:
    """Ranking attributes; ``companions`` maps attribute name → (metric id, scale)."""

    def attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
        point = _latest(series, metric_id)
        ranking = _ranking(series, point) if point else None
        if point is None or ranking is None:
            return {}
        cov = coverage(series.datapoints, metric_id, point.reference, unit=point.unit)
        out = _provenance(point, series, today)
        out.update(
            ranking_attrs(
                ranking,
                cov,
                value_key=value_key,
                scale=scale,
                companions={
                    name: _companion(series, other, point.reference, other_scale)
                    for name, (other, other_scale) in (companions or {}).items()
                },
            )
        )
        return out

    return attrs


# ---------------------------------------------------------------- Eurostat

EU_EXPENDITURE = "defence_expenditure"
EU_INVESTMENT = "defence_investment"


def _eurostat_value_attrs(metric_id: str) -> AttributesFn:
    def attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
        point = _latest(series, metric_id)
        if point is None:
            return {}
        reference = point.reference
        previous, change = _year_over_year(series, point)
        ranking = _ranking(series, point)
        out = _provenance(point, series, today)
        out.update(
            {
                "reference_year": reference.start.year,
                "pct_gdp": _pct_value(
                    _focus_value(series, f"{metric_id}_pct_gdp", reference)
                ),
                "nac_million": scaled(
                    _focus_value(series, f"{metric_id}_nac", reference)
                ),
                "previous_year_eur": scaled(previous, MILLION),
                "change_pct": _pct_value(change),
                "rank": None if ranking is None else ranking.focus_rank,
                "pct_gdp_rank": _focus_rank(
                    series, f"{metric_id}_pct_gdp", "PCT_GDP", reference
                ),
                "population": None if ranking is None else ranking.population,
            }
        )
        return out

    return attrs


EUROSTAT_SENSORS: tuple[SpendingSensorEntityDescription, ...] = (
    _money(
        "eurostat_defence_expenditure",
        EUROSTAT,
        "EUR",
        _annual_value(EU_EXPENDITURE),
        _eurostat_value_attrs(EU_EXPENDITURE),
    ),
    _rank(
        "eurostat_defence_expenditure_rank",
        EUROSTAT,
        _rank_value(EU_EXPENDITURE),
        _rank_attrs(
            EU_EXPENDITURE,
            "eur",
            MILLION,
            {"pct_gdp": (f"{EU_EXPENDITURE}_pct_gdp", 1)},
        ),
    ),
    _money(
        "eurostat_defence_investment",
        EUROSTAT,
        "EUR",
        _annual_value(EU_INVESTMENT),
        _eurostat_value_attrs(EU_INVESTMENT),
    ),
    _rank(
        "eurostat_defence_investment_rank",
        EUROSTAT,
        _rank_value(EU_INVESTMENT),
        _rank_attrs(EU_INVESTMENT, "eur", MILLION),
    ),
)


# -------------------------------------------------------------------- NATO

NATO_USD = "defence_expenditure_usd_current"
NATO_NAC = "defence_expenditure_nac"
NATO_USD_CONSTANT = "defence_expenditure_usd_constant"
NATO_PCT_GDP = "defence_expenditure_pct_gdp"
NATO_EQUIPMENT_SHARE = "equipment_share_pct"
NATO_EQUIPMENT_USD = "equipment_expenditure_usd_current"


def _latest_actual(series: SourceSeries, metric_id: str) -> SpendingDataPoint | None:
    annual = annual_series(series.datapoints, metric_id, FOCUS_COUNTRY)
    actual = [p for p in annual.values() if p.status is DatapointStatus.ACTUAL]
    return max(actual, key=lambda p: p.reference.start) if actual else None


def _nato_value_attrs(
    series: SourceSeries, today: date, now: datetime
) -> dict[str, Any]:
    point = _latest(series, NATO_USD)
    if point is None:
        return {}
    reference = point.reference
    previous, change = _year_over_year(series, point)
    ranking = _ranking(series, point)
    constant = latest_year(series.datapoints, NATO_USD_CONSTANT, FOCUS_COUNTRY)
    constant_value = (
        constant.value
        if constant is not None and constant.reference == reference
        else None
    )
    actual = _latest_actual(series, NATO_USD)
    out = _provenance(point, series, today)
    out.update(
        {
            "reference_year": reference.start.year,
            "nac_million": scaled(_focus_value(series, NATO_NAC, reference)),
            "usd_constant": scaled(constant_value, MILLION),
            "price_base_year": price_base_year(constant.unit) if constant else None,
            "pct_gdp": _pct_value(_focus_value(series, NATO_PCT_GDP, reference)),
            "latest_actual": None
            if actual is None
            else {
                "year": actual.reference.start.year,
                "usd": scaled(actual.value, MILLION),
            },
            "previous_year_usd": scaled(previous, MILLION),
            "change_pct": _pct_value(change),
            "rank": None if ranking is None else ranking.focus_rank,
            "population": None if ranking is None else ranking.population,
        }
    )
    return out


def _nato_pct_attrs(series: SourceSeries, today: date, now: datetime) -> dict[str, Any]:
    point = _latest(series, NATO_PCT_GDP)
    ranking = _ranking(series, point) if point else None
    if point is None or ranking is None:
        return {}
    out = _provenance(point, series, today)
    out.update(
        {
            "reference_year": point.reference.start.year,
            "rank": ranking.focus_rank,
            "population": ranking.population,
            "alliance_median_pct_gdp": _pct_value(ranking.median),
        }
    )
    return out


def _nato_equipment_attrs(
    series: SourceSeries, today: date, now: datetime
) -> dict[str, Any]:
    point = _latest(series, NATO_EQUIPMENT_SHARE)
    ranking = _ranking(series, point) if point else None
    if point is None or ranking is None:
        return {}
    out = _provenance(point, series, today)
    out.update(
        {
            "reference_year": point.reference.start.year,
            "equipment_usd": scaled(
                _focus_value(series, NATO_EQUIPMENT_USD, point.reference), MILLION
            ),
            "rank": ranking.focus_rank,
            "population": ranking.population,
        }
    )
    return out


def _nato_position(series: SourceSeries, today: date) -> StateType:
    pct = _latest(series, NATO_PCT_GDP)
    ranking = _ranking(series, pct) if pct else None
    if pct is None or ranking is None:
        return None
    usd = _focus_value(series, NATO_USD, pct.reference)
    return nato_position_text(
        ranking,
        None if usd is None else usd * MILLION,
        pct.value,
        pct.reference.start.year,
        pct.status,
    )


def _nato_position_attrs(
    series: SourceSeries, today: date, now: datetime
) -> dict[str, Any]:
    point = _latest(series, NATO_PCT_GDP)
    return {} if point is None else _provenance(point, series, today)


NATO_SENSORS: tuple[SpendingSensorEntityDescription, ...] = (
    _money(
        "nato_defence_expenditure",
        NATO,
        "USD",
        _annual_value(NATO_USD),
        _nato_value_attrs,
    ),
    _pct(
        "nato_defence_expenditure_pct_gdp",
        NATO,
        _annual_value(NATO_PCT_GDP, 1),
        _nato_pct_attrs,
    ),
    _rank(
        "nato_defence_expenditure_pct_gdp_rank",
        NATO,
        _rank_value(NATO_PCT_GDP),
        _rank_attrs(NATO_PCT_GDP, "pct_gdp", 1, {"usd": (NATO_USD, MILLION)}),
    ),
    _pct(
        "nato_equipment_share_pct",
        NATO,
        _annual_value(NATO_EQUIPMENT_SHARE, 1),
        _nato_equipment_attrs,
    ),
    _text("nato_position_text", NATO, _nato_position, _nato_position_attrs),
)


# --------------------------------------------------------------------- EDA

EDA_EXPENDITURE = "defence_expenditure"
EDA_INVESTMENT = "defence_investment"
EDA_PCT_GDP = "defence_expenditure_pct_gdp"
EDA_PCT_GOVERNMENT = "defence_expenditure_pct_government"
EDA_PER_CAPITA = "defence_expenditure_per_capita"


def _eda_value_attrs(
    series: SourceSeries, today: date, now: datetime
) -> dict[str, Any]:
    point = _latest(series, EDA_EXPENDITURE)
    if point is None:
        return {}
    reference = point.reference
    previous, change = _year_over_year(series, point)
    ranking = _ranking(series, point)
    out = _provenance(point, series, today)
    out.update(
        {
            "reference_year": reference.start.year,
            "pct_gdp": _pct_value(_focus_value(series, EDA_PCT_GDP, reference)),
            "pct_government": _pct_value(
                _focus_value(series, EDA_PCT_GOVERNMENT, reference)
            ),
            "per_capita_eur": scaled(_focus_value(series, EDA_PER_CAPITA, reference)),
            "investment_eur": scaled(
                _focus_value(series, EDA_INVESTMENT, reference), MILLION
            ),
            "previous_year_eur": scaled(previous, MILLION),
            "change_pct": _pct_value(change),
            "rank": None if ranking is None else ranking.focus_rank,
            "population": None if ranking is None else ranking.population,
        }
    )
    return out


EDA_SENSORS: tuple[SpendingSensorEntityDescription, ...] = (
    _money(
        "eda_defence_expenditure",
        EDA,
        "EUR",
        _annual_value(EDA_EXPENDITURE),
        _eda_value_attrs,
    ),
    _rank(
        "eda_defence_expenditure_rank",
        EDA,
        _rank_value(EDA_EXPENDITURE),
        _rank_attrs(
            EDA_EXPENDITURE,
            "eur",
            MILLION,
            {"pct_gdp": (EDA_PCT_GDP, 1), "per_capita_eur": (EDA_PER_CAPITA, 1)},
        ),
    ),
    _rank(
        "eda_defence_investment_rank",
        EDA,
        _rank_value(EDA_INVESTMENT),
        _rank_attrs(EDA_INVESTMENT, "eur", MILLION),
    ),
)


# ------------------------------------------------------------------ catalogue

SPENDING_SENSORS: tuple[SpendingSensorEntityDescription, ...] = (
    *STATSKONTORET_SENSORS,
    *EUROSTAT_SENSORS,
    *NATO_SENSORS,
    *EDA_SENSORS,
)


# ------------------------------------------------------------------- entity


class SpendingSensor(CoordinatorEntity[SpendingCoordinator], SensorEntity):
    """A sensor reading one source's series from the spending snapshot."""

    _attr_has_entity_name = True
    entity_description: SpendingSensorEntityDescription

    def __init__(
        self,
        coordinator: SpendingCoordinator,
        description: SpendingSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry_id = coordinator.entry.entry_id
        self._attr_unique_id = f"{entry_id}_spending_{description.key}"
        self._attr_device_info = spending_device_info(entry_id, description.source_id)

    @property
    def _series(self) -> SourceSeries | None:
        data = self.coordinator.data
        return None if data is None else data.get(self.entity_description.source_id)

    @property
    def native_value(self) -> StateType:
        series = self._series
        if series is None:
            return None
        return self.entity_description.value_fn(series, dt_util.now().date())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        series = self._series
        builder = self.entity_description.attributes_fn
        if series is None or builder is None:
            return None
        return builder(series, dt_util.now().date(), dt_util.utcnow())


def async_setup_spending_sensors(
    entry: EdpRadarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Every spending sensor exists whenever the integration is set up."""
    coordinator = entry.runtime_data.spending
    async_add_entities(
        SpendingSensor(coordinator, description) for description in SPENDING_SENSORS
    )

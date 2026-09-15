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
from .attrs import MILLION, monthly_series_attrs, provenance_attrs, scaled
from .calculations import (
    MonthChange,
    YtdChange,
    latest_month,
    month_change,
    monthly_series,
    ytd_change,
)
from .coordinator import SpendingCoordinator
from .models import DatapointStatus, ReferencePeriod, SourceSeries, SpendingDataPoint
from .registry import FOCUS_COUNTRY, STATSKONTORET, metric_spec, source_spec
from .text import statskontoret_snapshot_text

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
    key: str, source_id: str, value_fn: ValueFn
) -> SpendingSensorEntityDescription:
    return SpendingSensorEntityDescription(
        key=key, translation_key=key, source_id=source_id, value_fn=value_fn
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
    _text("statskontoret_snapshot_text", STATSKONTORET, _sk_snapshot),
)


# ------------------------------------------------------------------ catalogue

SPENDING_SENSORS: tuple[SpendingSensorEntityDescription, ...] = (
    *STATSKONTORET_SENSORS,
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

"""Source and metric registry invariants (S8, plan §9, §47)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from custom_components.edp_radar.spending.models import Cadence
from custom_components.edp_radar.spending.registry import (
    FOCUS_COUNTRY,
    METRICS,
    SOURCE_ORDER,
    SOURCES,
    metric_spec,
    source_spec,
)


def test_focus_country_is_sweden() -> None:
    assert FOCUS_COUNTRY == "SE"


def test_five_sources_in_plan_order() -> None:
    assert SOURCE_ORDER == ("statskontoret", "eurostat", "nato", "eda", "sipri")
    assert set(SOURCES) == set(SOURCE_ORDER)
    assert source_spec("statskontoret").cadence is Cadence.MONTHLY
    assert source_spec("statskontoret").check_interval == timedelta(days=1)
    assert source_spec("eurostat").cadence is Cadence.TWICE_YEARLY
    assert source_spec("nato").check_interval == timedelta(days=7)
    assert all(spec.official for spec in SOURCES.values() if spec.source_id != "sipri")
    assert source_spec("sipri").official is False


def test_every_metric_belongs_to_its_source_and_group() -> None:
    for (source_id, metric_id), spec in METRICS.items():
        assert spec.source_id == source_id
        assert spec.metric_id == metric_id
        assert spec.comparison_group == source_id
        assert spec.unit
        assert spec.definition
    assert metric_spec("statskontoret", "materiel_outturn").unit == "SEK_MILLION"
    assert metric_spec("eurostat", "defence_investment_pct_gdp").unit == "PCT_GDP"
    assert metric_spec(
        "nato", "equipment_expenditure_usd_current"
    ).definition.startswith("Derived")
    with pytest.raises(KeyError):
        metric_spec("nato", "nope")

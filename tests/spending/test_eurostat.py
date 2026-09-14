"""Eurostat gov_ev JSON-stat decoding (S10; plan §20–§26, §82)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.spending.models import DatapointStatus, SourceRelease
from custom_components.edp_radar.spending.providers.base import SchemaChangedError
from custom_components.edp_radar.spending.providers.eurostat import (
    API_URL,
    EurostatProvider,
    parse_jsonstat,
    release_from_payload,
)
from custom_components.edp_radar.spending.registry import EUROSTAT

FIXTURE = (
    Path(__file__).parent.parent
    / "fixtures"
    / "spending"
    / "eurostat"
    / "gov_ev-defence.json"
)


def _payload() -> bytes:
    return FIXTURE.read_bytes()


def test_release_from_updated_timestamp() -> None:
    release = release_from_payload(_payload())
    assert release.release_id == "2026-04-27T23:00:00+0200"
    assert release.published_at == date(2026, 4, 27)
    assert release.download_url == API_URL
    assert release.format == "json-stat"


def test_parse_all_countries_and_units() -> None:
    result = parse_jsonstat(_payload(), release_from_payload(_payload()))
    points = {
        (p.metric_id, p.country, p.reference.start.year): p for p in result.datapoints
    }
    assert points[("defence_expenditure", "SE", 2025)].value == Decimal("17196.9")
    assert points[("defence_expenditure_pct_gdp", "SE", 2025)].value == Decimal("2.9")
    assert points[("defence_expenditure_nac", "SE", 2025)].value == Decimal("190306.0")
    assert points[("defence_investment", "SE", 2025)].value == Decimal("4864.3")
    assert points[("defence_investment_pct_gdp", "SE", 2025)].value == Decimal("0.8")
    assert points[("defence_investment", "DE", 2025)].value == Decimal("13527.0")
    assert points[("defence_expenditure", "GR", 2025)].value == Decimal("5998.0")
    assert ("defence_expenditure", "IT", 2025) not in points
    assert not any(p.country.startswith("EU") for p in result.datapoints)
    assert len({p.country for p in result.datapoints}) == 27
    assert len(result.datapoints) == 771
    assert {p.status for p in result.datapoints} == {DatapointStatus.ACTUAL}
    assert points[("defence_expenditure", "SE", 2025)].unit == "EUR_MILLION"
    assert points[("defence_expenditure", "SE", 2025)].reference.label == "2025"
    assert result.layout_fingerprint == "freq,expend,na_item,unit,geo,time"


def test_dimension_order_independence_and_status_flags() -> None:
    data = json.loads(_payload())
    # Reorder dimensions: time first, geo last; rebuild the value map accordingly.
    ids = data["id"]
    new_ids = ["time", "freq", "expend", "na_item", "unit", "geo"]
    sizes = dict(zip(ids, data["size"], strict=True))
    index = {k: data["dimension"][k]["category"]["index"] for k in ids}

    def old_strides() -> dict[str, int]:
        strides, step = {}, 1
        for k in reversed(ids):
            strides[k], step = step, step * sizes[k]
        return strides

    def new_strides() -> dict[str, int]:
        strides, step = {}, 1
        for k in reversed(new_ids):
            strides[k], step = step, step * sizes[k]
        return strides

    old_s, new_s = old_strides(), new_strides()
    new_value: dict[str, float] = {}
    for old_flat, value in data["value"].items():
        remaining = int(old_flat)
        positions = {}
        for k in ids:
            positions[k], remaining = divmod(remaining, old_s[k])
        new_value[str(sum(positions[k] * new_s[k] for k in new_ids))] = value
    data["id"], data["size"] = new_ids, [sizes[k] for k in new_ids]
    data["value"] = new_value
    se_2025 = sum(
        index[k][code] * new_s[k]
        for k, code in (
            ("time", "2025"),
            ("freq", "A"),
            ("expend", "DEF"),
            ("na_item", "TE"),
            ("unit", "MIO_EUR"),
            ("geo", "SE"),
        )
    )
    data["status"] = {str(se_2025): "p"}
    payload = json.dumps(data).encode()
    result = parse_jsonstat(payload, release_from_payload(payload))
    point = next(
        p
        for p in result.datapoints
        if p.metric_id == "defence_expenditure"
        and p.country == "SE"
        and p.reference.start.year == 2025
    )
    assert point.value == Decimal("17196.9")
    assert point.status is DatapointStatus.PROVISIONAL
    assert point.flags == ("p",)
    assert len(result.datapoints) == 771


def test_missing_codes_fail() -> None:
    data = json.loads(_payload())
    del data["dimension"]["na_item"]["category"]["index"]["P51G"]
    data["size"][2] = 1
    with pytest.raises(SchemaChangedError, match="P51G"):
        parse_jsonstat(json.dumps(data).encode(), release_from_payload(_payload()))
    with pytest.raises(SchemaChangedError, match="updated"):
        release_from_payload(b'{"class": "dataset"}')


def test_status_list_form_sets_estimate_flag() -> None:
    data = json.loads(_payload())
    ids = data["id"]
    sizes = data["size"]
    index = {k: data["dimension"][k]["category"]["index"] for k in ids}
    strides: dict[str, int] = {}
    step = 1
    for k, size in zip(reversed(ids), reversed(sizes), strict=True):
        strides[k] = step
        step *= size
    total = step
    se_2025 = sum(
        index[k][code] * strides[k]
        for k, code in (
            ("freq", "A"),
            ("expend", "DEF"),
            ("na_item", "TE"),
            ("unit", "MIO_EUR"),
            ("geo", "SE"),
            ("time", "2025"),
        )
    )
    status = [""] * total
    status[se_2025] = "e"
    data["status"] = status
    payload = json.dumps(data).encode()
    result = parse_jsonstat(payload, release_from_payload(payload))
    point = next(
        p
        for p in result.datapoints
        if p.metric_id == "defence_expenditure"
        and p.country == "SE"
        and p.reference.start.year == 2025
    )
    assert point.status is DatapointStatus.ESTIMATE
    assert point.flags == ("e",)


def test_time_code_that_is_not_a_year_emits_warning() -> None:
    baseline = parse_jsonstat(_payload(), release_from_payload(_payload()))
    year_2025_count = sum(
        1 for p in baseline.datapoints if p.reference.start.year == 2025
    )

    data = json.loads(_payload())
    time_index = data["dimension"]["time"]["category"]["index"]
    time_index["2025Q4"] = time_index.pop("2025")
    payload = json.dumps(data).encode()
    result = parse_jsonstat(payload, release_from_payload(payload))
    assert len(result.datapoints) == 771 - year_2025_count
    assert any("2025Q4" in warning for warning in result.warnings)


async def test_provider_round_trip(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(API_URL, content=_payload())
    provider = EurostatProvider()
    session = async_get_clientsession(hass)
    release = await provider.async_discover_latest(session)
    fetched, payload = await provider.async_fetch_release(session, release)
    assert len(aioclient_mock.mock_calls) == 1  # discovery payload is reused
    assert fetched.checksum
    assert len(provider.parse_release(payload, fetched).datapoints) == 771


async def test_fetch_release_on_cache_miss_derives_release_from_fresh_payload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A provider with no cached discovery must not stamp a stale release."""
    aioclient_mock.get(API_URL, content=_payload())
    provider = EurostatProvider()
    session = async_get_clientsession(hass)
    stale = SourceRelease(
        source_id=EUROSTAT,
        release_id="stale",
        published_at=date(2020, 1, 1),
        download_url=API_URL,
        canonical_url=API_URL,
        format="json-stat",
    )
    fetched, _payload_bytes = await provider.async_fetch_release(session, stale)
    assert fetched.release_id == "2026-04-27T23:00:00+0200"
    assert fetched.published_at == date(2026, 4, 27)


def test_unknown_geo_code_is_skipped_with_warning() -> None:
    """An aggregate Eurostat doesn't recognise must never be guessed as a country."""
    data = json.loads(_payload())
    geo_index = data["dimension"]["geo"]["category"]["index"]
    geo_index["EA21"] = geo_index.pop("EU27_2020")
    payload = json.dumps(data).encode()
    result = parse_jsonstat(payload, release_from_payload(payload))
    assert not any(p.country == "EA21" for p in result.datapoints)
    assert len({p.country for p in result.datapoints}) == 27
    assert sum(1 for w in result.warnings if "EA21" in w) == 1


def test_non_annual_frequency_is_a_schema_change() -> None:
    data = json.loads(_payload())
    data["dimension"]["freq"]["category"]["index"] = {"Q": 0}
    data["dimension"]["freq"]["category"]["label"] = {"Q": "Quarterly"}
    quarterly = json.dumps(data).encode()
    with pytest.raises(SchemaChangedError, match="freq"):
        parse_jsonstat(quarterly, release_from_payload(_payload()))

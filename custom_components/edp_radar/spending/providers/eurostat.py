"""Eurostat ``gov_ev`` defence expenditure and investment (S10; plan §20–§26).

One fixed Statistics-API request; JSON-stat 2.0 is decoded through ``id``,
``size`` and the dimension category indexes, never through array positions.
"""

from __future__ import annotations

import itertools
import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from aiohttp import ClientSession

from ..countries import EUROSTAT_AGGREGATES, EUROSTAT_GEO_FIXES
from ..models import (
    DatapointStatus,
    ReferencePeriod,
    SourceRelease,
    SpendingDataPoint,
)
from ..registry import EUROSTAT, source_spec
from .base import (
    FetchResult,
    ParseResult,
    Payload,
    SchemaChangedError,
    async_fetch_bytes,
    with_fetch_metadata,
)

API_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_ev"
    "?lang=en&expend=DEF&na_item=TE&na_item=P51G&unit=MIO_EUR&unit=PC_GDP&unit=MIO_NAC"
)
CANONICAL_URL = "https://ec.europa.eu/eurostat/cache/metadata/en/gov_ev_esms.htm"
EXPEND = "DEF"
METRICS: dict[tuple[str, str], tuple[str, str]] = {
    ("TE", "MIO_EUR"): ("defence_expenditure", "EUR_MILLION"),
    ("TE", "MIO_NAC"): ("defence_expenditure_nac", "NAC_MILLION"),
    ("TE", "PC_GDP"): ("defence_expenditure_pct_gdp", "PCT_GDP"),
    ("P51G", "MIO_EUR"): ("defence_investment", "EUR_MILLION"),
    ("P51G", "MIO_NAC"): ("defence_investment_nac", "NAC_MILLION"),
    ("P51G", "PC_GDP"): ("defence_investment_pct_gdp", "PCT_GDP"),
}
FLAG_STATUS: dict[str, DatapointStatus] = {
    "p": DatapointStatus.PROVISIONAL,
    "e": DatapointStatus.ESTIMATE,
    "f": DatapointStatus.PROJECTION,
}


def _load(payload: bytes) -> dict[str, Any]:
    try:
        data = json.loads(payload)
    except ValueError as err:
        raise SchemaChangedError(f"Eurostat response is not JSON: {err}") from err
    if not isinstance(data, dict) or data.get("class") != "dataset":
        raise SchemaChangedError("Eurostat response is not a JSON-stat dataset")
    return data


def release_from_payload(payload: bytes) -> SourceRelease:
    data = _load(payload)
    updated = data.get("updated")
    if not isinstance(updated, str):
        raise SchemaChangedError("Eurostat dataset has no 'updated' timestamp")
    return SourceRelease(
        source_id=EUROSTAT,
        release_id=updated,
        published_at=datetime.fromisoformat(updated).date(),
        download_url=API_URL,
        canonical_url=CANONICAL_URL,
        format="json-stat",
    )


def _index(data: dict[str, Any], dimension: str) -> dict[str, int]:
    try:
        index = data["dimension"][dimension]["category"]["index"]
    except (KeyError, TypeError) as err:
        raise SchemaChangedError(f"Eurostat dimension {dimension!r} missing") from err
    if isinstance(index, list):
        return {str(code): position for position, code in enumerate(index)}
    return {str(code): int(position) for code, position in index.items()}


def _status_flags(data: dict[str, Any]) -> dict[int, str]:
    status = data.get("status")
    if isinstance(status, dict):
        return {int(k): str(v) for k, v in status.items()}
    if isinstance(status, list):
        return {i: str(v) for i, v in enumerate(status) if v}
    return {}


def parse_jsonstat(payload: bytes, release: SourceRelease) -> ParseResult:
    data = _load(payload)
    ids: list[str] = [str(i) for i in data.get("id", [])]
    sizes: list[int] = [int(s) for s in data.get("size", [])]
    for required in ("expend", "na_item", "unit", "geo", "time"):
        if required not in ids:
            raise SchemaChangedError(f"Eurostat dimension {required!r} missing")
    indexes = {dim: _index(data, dim) for dim in ids}
    if EXPEND not in indexes["expend"]:
        raise SchemaChangedError("Eurostat expend code DEF missing")
    for na_item, unit in METRICS:
        if na_item not in indexes["na_item"]:
            raise SchemaChangedError(f"Eurostat na_item code {na_item} missing")
        if unit not in indexes["unit"]:
            raise SchemaChangedError(f"Eurostat unit code {unit} missing")
    strides: dict[str, int] = {}
    step = 1
    for dim, size in zip(reversed(ids), reversed(sizes), strict=True):
        strides[dim] = step
        step *= size
    values = data.get("value")
    if not isinstance(values, dict):
        raise SchemaChangedError("Eurostat value map missing")
    flags = _status_flags(data)
    fixed = {
        dim: indexes[dim]
        for dim in ids
        if dim not in {"na_item", "unit", "geo", "time"}
    }
    fixed_offset = 0
    for dim, index in fixed.items():
        code = EXPEND if dim == "expend" else next(iter(index))
        fixed_offset += index[code] * strides[dim]
    warnings: list[str] = []
    datapoints: list[SpendingDataPoint] = []
    for (na_item, unit), (metric_id, unit_id) in METRICS.items():
        base = (
            fixed_offset
            + indexes["na_item"][na_item] * strides["na_item"]
            + indexes["unit"][unit] * strides["unit"]
        )
        for (geo, geo_pos), (time, time_pos) in itertools.product(
            indexes["geo"].items(), indexes["time"].items()
        ):
            if geo in EUROSTAT_AGGREGATES:
                continue
            flat = base + geo_pos * strides["geo"] + time_pos * strides["time"]
            raw = values.get(str(flat))
            if raw is None:
                continue
            try:
                year = int(time)
            except ValueError:
                warnings.append(f"time code {time!r} is not a year")
                continue
            flag = flags.get(flat, "")
            status = next(
                (FLAG_STATUS[c] for c in flag if c in FLAG_STATUS),
                DatapointStatus.ACTUAL,
            )
            datapoints.append(
                SpendingDataPoint(
                    source_id=EUROSTAT,
                    metric_id=metric_id,
                    country=EUROSTAT_GEO_FIXES.get(geo, geo),
                    reference=ReferencePeriod.year(year),
                    value=Decimal(str(raw)),
                    unit=unit_id,
                    status=status,
                    release_id=release.release_id,
                    published_at=release.published_at,
                    source_url=CANONICAL_URL,
                    flags=(flag,) if flag else (),
                )
            )
    return ParseResult(tuple(datapoints), tuple(warnings), ",".join(ids))


class EurostatProvider:
    """Discovery *is* the request: the response carries ``updated``."""

    def __init__(self) -> None:
        self.spec = source_spec(EUROSTAT)
        self._cached: tuple[str, FetchResult] | None = None

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease:
        fetched = await async_fetch_bytes(session, API_URL)
        release = release_from_payload(fetched.payload)
        self._cached = (release.release_id, fetched)
        return with_fetch_metadata(release, fetched)

    async def async_fetch_release(
        self, session: ClientSession, release: SourceRelease
    ) -> tuple[SourceRelease, Payload]:
        if self._cached is not None and self._cached[0] == release.release_id:
            fetched = self._cached[1]
            return with_fetch_metadata(release, fetched), fetched.payload
        # Cache miss (e.g. after a restart): the requested release is stale by
        # definition, so the release returned must describe *this* payload, not
        # whatever was asked for.
        fetched = await async_fetch_bytes(session, API_URL)
        fresh_release = release_from_payload(fetched.payload)
        return with_fetch_metadata(fresh_release, fetched), fetched.payload

    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult:
        if not isinstance(payload, bytes):
            raise SchemaChangedError("Eurostat expects a single JSON payload")
        return parse_jsonstat(payload, release)

"""NATO defence expenditure workbook (S11; plan §27–§33).

Discovery reads the stable topic page's "Archive of tables" links
(``def-exp-YYYY-en.pdf``), takes the newest year and derives the XLSX on the
same path. Tables are located by sheet name, title prefix and block subtitle;
years come from the header row (``2025e`` marks estimates); countries from
label tables. The equipment value is derived (plan §30) and flagged.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientSession

from ..countries import SKIP_LABELS, normalise_label, resolve_country
from ..models import (
    DatapointStatus,
    ReferencePeriod,
    SourceRelease,
    SpendingDataPoint,
)
from ..registry import NATO, source_spec
from ..xlsx import (
    find_row,
    number,
    open_workbook,
    require_sheet,
    rows_of,
    text,
    year_header,
)
from .base import (
    ParseResult,
    Payload,
    SchemaChangedError,
    async_fetch_bytes,
    async_head_metadata,
    http_date_to_date,
    with_fetch_metadata,
)

TOPIC_URL = "https://www.nato.int/en/what-we-do/introduction-to-nato/defence-expenditures-and-natos-5-commitment"
_ARCHIVE_LINK = re.compile(
    r'href=\\?"([^"\\]*def-exp-(\d{4})-en\.pdf)\\?"', re.IGNORECASE
)
_CURRENCY = re.compile(r"\(([^)]*)\)\s*$")


@dataclass(frozen=True, slots=True)
class TableSpec:
    sheet: str
    block: int
    subtitle: str
    metric_id: str
    unit: str
    keep_currency: bool = False


TABLES: tuple[TableSpec, ...] = (
    TableSpec(
        "Table 1", 0, "current prices", "defence_expenditure_nac", "NAC_MILLION", True
    ),
    TableSpec(
        "Table 2", 0, "current prices", "defence_expenditure_usd_current", "USD_MILLION"
    ),
    TableSpec(
        "Table 2",
        1,
        "constant 2021",
        "defence_expenditure_usd_constant",
        "USD_MILLION_CONSTANT_2021",
    ),
    TableSpec(
        "Table 3", 0, "share of real gdp", "defence_expenditure_pct_gdp", "PCT_GDP"
    ),
    TableSpec("Table 8a", 0, "equipment", "equipment_share_pct", "PCT"),
)


def _starts_with(prefix: str) -> Callable[[str], bool]:
    return lambda t: t.startswith(prefix)


def discover_workbook(html_text: str, base_url: str) -> tuple[int, str]:
    """Newest archive year and its XLSX URL."""
    best: tuple[int, str] | None = None
    for path, year in _ARCHIVE_LINK.findall(html_text):
        candidate = (int(year), urljoin(base_url, path[:-4] + ".xlsx"))
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        raise SchemaChangedError("NATO topic page has no def-exp-YYYY-en links")
    return best


def _blocks(
    rows: list[tuple[Any, ...]],
) -> list[tuple[int, dict[int, tuple[int, bool]]]]:
    """Header rows (empty first cell + year cells) with their year map."""
    found = []
    for index, row in enumerate(rows):
        if row and text(row[0]) == "":
            years = year_header(row)
            if years:
                found.append((index, years))
    return found


def _subtitle_before(rows: list[tuple[Any, ...]], header_index: int) -> str:
    for index in range(header_index - 1, max(-1, header_index - 4), -1):
        label = text(rows[index][0]) if rows[index] else ""
        if label:
            return label
    return ""


def _parse_table(
    rows: list[tuple[Any, ...]], spec: TableSpec, release: SourceRelease
) -> tuple[list[SpendingDataPoint], list[str]]:
    blocks = _blocks(rows)
    if len(blocks) <= spec.block:
        raise SchemaChangedError(f"{spec.sheet}: block {spec.block} missing")
    header_index, years = blocks[spec.block]
    subtitle = _subtitle_before(rows, header_index).casefold()
    if spec.subtitle not in subtitle:
        raise SchemaChangedError(
            f"{spec.sheet}: expected subtitle containing {spec.subtitle!r}, "
            f"got {subtitle!r}"
        )
    points: list[SpendingDataPoint] = []
    warnings: list[str] = []
    for row in rows[header_index + 1 :]:
        label = text(row[0]) if row else ""
        if not label or label.casefold().startswith("notes"):
            break
        plain = normalise_label(label)
        if plain in SKIP_LABELS:
            continue
        country = resolve_country(label)
        if country is None:
            warnings.append(f"{spec.sheet}: unknown country label {label!r}")
            continue
        flags: list[str] = []
        currency = _CURRENCY.search(label)
        if spec.keep_currency and currency:
            flags.append(f"currency:{currency.group(1).strip()}")
        if "*" in label:
            flags.append("footnote_star")
        for column, (year, is_estimate) in years.items():
            value = number(row[column].value if column < len(row) else None)
            if value is None:
                continue
            points.append(
                SpendingDataPoint(
                    source_id=NATO,
                    metric_id=spec.metric_id,
                    country=country,
                    reference=ReferencePeriod.year(year),
                    value=value,
                    unit=spec.unit,
                    status=DatapointStatus.ESTIMATE
                    if is_estimate
                    else DatapointStatus.ACTUAL,
                    release_id=release.release_id,
                    published_at=release.published_at,
                    source_url=release.canonical_url,
                    flags=tuple(flags),
                )
            )
    return points, warnings


def _derive_equipment(
    points: list[SpendingDataPoint], release: SourceRelease
) -> list[SpendingDataPoint]:
    usd = {
        (p.country, p.reference.start.year): p
        for p in points
        if p.metric_id == "defence_expenditure_usd_current"
    }
    share = {
        (p.country, p.reference.start.year): p
        for p in points
        if p.metric_id == "equipment_share_pct"
    }
    derived = []
    for key, total in usd.items():
        pct = share.get(key)
        if pct is None:
            continue
        estimate = DatapointStatus.ESTIMATE in (total.status, pct.status)
        derived.append(
            SpendingDataPoint(
                source_id=NATO,
                metric_id="equipment_expenditure_usd_current",
                country=total.country,
                reference=total.reference,
                value=total.value * pct.value / Decimal(100),
                unit="USD_MILLION",
                status=DatapointStatus.ESTIMATE if estimate else DatapointStatus.ACTUAL,
                release_id=release.release_id,
                published_at=release.published_at,
                source_url=release.canonical_url,
                flags=("derived",),
            )
        )
    return derived


def parse_nato_workbook(payload: bytes, release: SourceRelease) -> ParseResult:
    book = open_workbook(payload)
    points: list[SpendingDataPoint] = []
    warnings: list[str] = []
    titles: list[str] = []
    for spec in TABLES:
        rows = rows_of(require_sheet(book, spec.sheet))
        title_index = find_row(
            rows, _starts_with(f"{spec.sheet}:"), what=f"{spec.sheet} title"
        )
        if spec.block == 0:
            titles.append(text(rows[title_index][0]))
        table_points, table_warnings = _parse_table(rows, spec, release)
        if not table_points:
            raise SchemaChangedError(f"{spec.sheet}: no country rows parsed")
        points.extend(table_points)
        warnings.extend(table_warnings)
    points.extend(_derive_equipment(points, release))
    return ParseResult(tuple(points), tuple(warnings), " | ".join(titles))


class NatoProvider:
    def __init__(self) -> None:
        self.spec = source_spec(NATO)

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease:
        page = await async_fetch_bytes(session, TOPIC_URL)
        year, xlsx_url = discover_workbook(
            page.payload.decode("utf-8", "replace"), TOPIC_URL
        )
        etag, last_modified = await async_head_metadata(session, xlsx_url)
        return SourceRelease(
            source_id=NATO,
            release_id=f"{year}:{etag or last_modified or 'unknown'}",
            published_at=http_date_to_date(last_modified),
            download_url=xlsx_url,
            canonical_url=TOPIC_URL,
            format="xlsx",
            etag=etag,
            last_modified=last_modified,
        )

    async def async_fetch_release(
        self, session: ClientSession, release: SourceRelease
    ) -> tuple[SourceRelease, Payload]:
        fetched = await async_fetch_bytes(session, release.download_url)
        return with_fetch_metadata(release, fetched), fetched.payload

    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult:
        if not isinstance(payload, bytes):
            raise SchemaChangedError("NATO expects a single workbook payload")
        return parse_nato_workbook(payload, release)

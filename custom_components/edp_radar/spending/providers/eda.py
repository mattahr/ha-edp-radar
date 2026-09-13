"""EDA defence data workbooks (S11; plan §34–§39; docs/providers/eda.md).

Country-level data lives in one ``Member States`` sheet per annual workbook
(one year each) plus the frozen ``Billions`` history (2005–2021) in every
workbook. Discovery lists every ``Defence Data YYYY`` link on the portal;
the provider fetches all workbooks from 2022 onwards and parses ``Billions``
from the newest one only.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientSession

from ..countries import resolve_country
from ..models import (
    DatapointStatus,
    ReferencePeriod,
    SourceRelease,
    SpendingDataPoint,
)
from ..registry import EDA, source_spec
from ..xlsx import number, open_workbook, require_sheet, rows_of, text
from .base import (
    ParseResult,
    Payload,
    SchemaChangedError,
    async_fetch_bytes,
    async_head_metadata,
    http_date_to_date,
    sha256_hex,
)

PORTAL_URL = "https://www.eda.europa.eu/publications-and-data/defence-data"
MIN_YEAR = 2022
_LINK = re.compile(
    r"""href=(["'])([^"']*\.xlsx)\1[^>]*>\s*(?:<span>)?\s*Defence Data (\d{4})""",
    re.IGNORECASE | re.DOTALL,
)
_STARS = re.compile(r"\*+")
PERCENT = Decimal(100)

# (normalised header, metric_id, unit, multiply by 100)
MEMBER_STATE_COLUMNS: tuple[tuple[str, str, str, bool], ...] = (
    ("total defence expenditure", "defence_expenditure", "EUR_MILLION", False),
    ("defence investment", "defence_investment", "EUR_MILLION", False),
    (
        "total defence expenditure as % of gdp",
        "defence_expenditure_pct_gdp",
        "PCT_GDP",
        True,
    ),
    (
        "total defence expenditure as % of government expenditure",
        "defence_expenditure_pct_government",
        "PCT",
        True,
    ),
    (
        "total defence expenditure per capita",
        "defence_expenditure_per_capita",
        "EUR",
        False,
    ),
)
BILLIONS_COLUMNS: tuple[tuple[str, str, str, bool], ...] = (
    ("total defence expenditure", "defence_expenditure", "EUR_MILLION", False),
    (
        "defence equipment procurement expenditure",
        "equipment_procurement",
        "EUR_MILLION",
        False,
    ),
    ("defence r&d expenditure", "defence_rnd", "EUR_MILLION", False),
    ("defence investment", "defence_investment", "EUR_MILLION", False),
    (
        "total defence expenditure as % of gdp",
        "defence_expenditure_pct_gdp",
        "PCT_GDP",
        True,
    ),
)


def discover_workbooks(html_text: str, base_url: str) -> dict[int, str]:
    links = {
        int(year): urljoin(base_url, url) for _, url, year in _LINK.findall(html_text)
    }
    if not links:
        raise SchemaChangedError("EDA portal has no 'Defence Data YYYY' workbook links")
    return links


def _normalise(header: str) -> str:
    return " ".join(header.split()).casefold()


def _columns(
    header_row: tuple[Any, ...],
    wanted: tuple[tuple[str, str, str, bool], ...],
    sheet: str,
) -> dict[str, int]:
    names = [_normalise(text(cell)) for cell in header_row]
    columns: dict[str, int] = {}
    for label in ("year",):
        if label not in names:
            raise SchemaChangedError(f"{sheet}: column {label!r} missing")
        columns[label] = names.index(label)
    for header, metric_id, _unit, _pct in wanted:
        if header not in names:
            pretty = header.title().replace("Gdp", "GDP").replace("R&D", "R&D")
            raise SchemaChangedError(f"{sheet}: column {pretty!r} missing")
        columns[metric_id] = names.index(header)
    return columns


def _member_states_sheet(book: Any) -> str:
    for name in book.sheetnames:
        if str(name).strip().casefold().startswith("member states"):
            return str(name)
    raise SchemaChangedError(f"no 'Member States' sheet; found {book.sheetnames}")


def _emit(
    rows: list[tuple[Any, ...]],
    columns: dict[str, int],
    wanted: tuple[tuple[str, str, str, bool], ...],
    release: SourceRelease,
    *,
    sheet: str,
    estimates_marked: bool,
    extra_flags: tuple[str, ...],
    warnings: list[str],
) -> list[SpendingDataPoint]:
    points: list[SpendingDataPoint] = []
    for row in rows[1:]:
        label = text(row[0]) if row else ""
        if not label or label.startswith("*"):
            continue
        country = resolve_country(label)
        if country is None:
            warnings.append(f"{sheet}: unknown country label {label!r}")
            continue
        year_value = number(row[columns["year"]].value)
        if year_value is None:
            warnings.append(f"{sheet}: row {label!r} has no year")
            continue
        stars = _STARS.search(label)
        star_count = len(stars.group(0)) if stars else 0
        flags = list(extra_flags)
        status = DatapointStatus.ACTUAL
        if star_count == 1 and estimates_marked:
            status = DatapointStatus.ESTIMATE
        elif star_count > 1:
            flags.append(f"note_{star_count}")
        for _header, metric_id, unit, pct in wanted:
            value = number(row[columns[metric_id]].value)
            if value is None:
                continue
            points.append(
                SpendingDataPoint(
                    source_id=EDA,
                    metric_id=metric_id,
                    country=country,
                    reference=ReferencePeriod.year(int(year_value)),
                    value=value * PERCENT if pct else value,
                    unit=unit,
                    status=status,
                    release_id=release.release_id,
                    published_at=release.published_at,
                    source_url=release.canonical_url,
                    flags=tuple(flags),
                )
            )
    return points


def parse_eda_workbooks(
    payload: Mapping[str, bytes], release: SourceRelease
) -> ParseResult:
    if not payload:
        raise SchemaChangedError("EDA payload has no workbooks")
    years = sorted(payload, key=int, reverse=True)
    newest = years[0]
    if release.release_id.split(":")[0] != newest:
        raise SchemaChangedError(
            f"EDA newest workbook {newest} does not match release {release.release_id}"
        )
    points: list[SpendingDataPoint] = []
    warnings: list[str] = []
    fingerprints: list[str] = []
    for year in years:
        book = open_workbook(payload[year])
        sheet = _member_states_sheet(book)
        rows = rows_of(require_sheet(book, sheet))
        if not rows:
            raise SchemaChangedError(f"{sheet}: empty")
        columns = _columns(rows[0], MEMBER_STATE_COLUMNS, sheet)
        estimates_marked = any(
            text(r[0]).casefold().startswith("*estimated") for r in rows[1:] if r
        )
        sheet_points = _emit(
            rows,
            columns,
            MEMBER_STATE_COLUMNS,
            release,
            sheet=sheet,
            estimates_marked=estimates_marked,
            extra_flags=(),
            warnings=warnings,
        )
        if not sheet_points:
            raise SchemaChangedError(f"{sheet}: no country rows parsed")
        points.extend(sheet_points)
        fingerprints.append(f"{year}:{sheet.strip()}")
        if year == newest:
            billions = rows_of(require_sheet(book, "Billions"))
            if not billions:
                raise SchemaChangedError("Billions: empty")
            b_columns = _columns(billions[0], BILLIONS_COLUMNS, "Billions")
            b_points = _emit(
                billions,
                b_columns,
                BILLIONS_COLUMNS,
                release,
                sheet="Billions",
                estimates_marked=False,
                extra_flags=("sheet:billions",),
                warnings=warnings,
            )
            if not b_points:
                raise SchemaChangedError("Billions: no country rows parsed")
            points.extend(b_points)
            fingerprints.append("Billions")
    return ParseResult(tuple(points), tuple(warnings), " | ".join(fingerprints))


class EdaProvider:
    def __init__(self) -> None:
        self.spec = source_spec(EDA)
        self._links: dict[int, str] = {}
        self._validators: dict[int, tuple[str | None, str | None]] = {}

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease:
        page = await async_fetch_bytes(session, PORTAL_URL)
        links = discover_workbooks(page.payload.decode("utf-8", "replace"), PORTAL_URL)
        self._links = {year: url for year, url in links.items() if year >= MIN_YEAR}
        if not self._links:
            raise SchemaChangedError(
                f"EDA portal lists no workbook from {MIN_YEAR} onwards"
            )
        newest = max(self._links)
        self._validators = {}
        for year, url in sorted(self._links.items()):
            self._validators[year] = await async_head_metadata(session, url)
        digest = hashlib.sha256(
            "|".join(
                f"{y}:{self._links[y]}:{e}:{m}"
                for y, (e, m) in sorted(self._validators.items())
            ).encode()
        ).hexdigest()[:16]
        etag, last_modified = self._validators[newest]
        return SourceRelease(
            source_id=EDA,
            release_id=f"{newest}:{digest}",
            published_at=http_date_to_date(last_modified),
            download_url=self._links[newest],
            canonical_url=PORTAL_URL,
            format="xlsx",
            etag=etag,
            last_modified=last_modified,
        )

    async def async_fetch_release(
        self, session: ClientSession, release: SourceRelease
    ) -> tuple[SourceRelease, Payload]:
        if not self._links:
            await self.async_discover_latest(session)
        workbooks: dict[str, bytes] = {}
        for year, url in sorted(self._links.items()):
            workbooks[str(year)] = (await async_fetch_bytes(session, url)).payload
        combined = sha256_hex(b"".join(workbooks[y] for y in sorted(workbooks)))
        return dataclasses.replace(release, checksum=combined), workbooks

    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult:
        if isinstance(payload, bytes):
            raise SchemaChangedError("EDA expects one payload per workbook year")
        return parse_eda_workbooks(payload, release)

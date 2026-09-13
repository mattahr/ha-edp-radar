"""SIPRI Military Expenditure Database (S11; plan §40–§44).

The landing page links the current workbook and states when it was revised;
a new release id triggers a full re-import (plan §43). Three sheets are read.
SIPRI marks estimates with blue font and highly uncertain data with red font;
``§`` in the Notes column means adopted budget rather than outturn, so the
status vocabulary maps it to ``budget``. Non-marked figures are stored as
``actual`` meaning "SIPRI reported figure", not "official outturn" (plan §44).
Years before ``MIN_YEAR`` are not stored (storage size; the workbook keeps
1949 onwards).
"""

from __future__ import annotations

import dataclasses
import re
from datetime import date, datetime
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
from ..registry import SIPRI, source_spec
from ..xlsx import (
    find_row,
    font_colour_index,
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
)

LANDING_URL = "https://www.sipri.org/databases/milex"
MIN_YEAR = 1990
BLUE = 12
RED = 10
PERCENT = Decimal(100)
_XLSX = re.compile(r'href="((?:https?:)?//www\.sipri\.org/[^"]*\.xlsx)"')
_REVISED = re.compile(r"revised on (\d{1,2} [A-Za-z]+ \d{4})")
_FOOTNOTE = re.compile(r"\d+")
NOTE_FLAGS: dict[str, str] = {
    "†": "excludes_pensions",
    "‡": "current_spending_only",
    "¶": "excludes_paramilitary",
    "‖": "currency_redenominated",
}
BUDGET_MARK = "§"
# (sheet, metric_id, unit, multiply by 100)
SHEETS: tuple[tuple[str, str, str, bool], ...] = (
    (
        "Constant (2024) US$",
        "military_expenditure_usd_constant",
        "USD_MILLION_CONSTANT_2024",
        False,
    ),
    ("Current US$", "military_expenditure_usd_current", "USD_MILLION", False),
    ("Share of GDP", "military_expenditure_pct_gdp", "PCT_GDP", True),
)


def discover_release(html_text: str, base_url: str) -> tuple[str, date | None]:
    """Workbook URL and the revision date from the landing page."""
    link = _XLSX.search(html_text)
    if link is None:
        raise SchemaChangedError("SIPRI landing page has no xlsx link")
    url = link.group(1)
    if url.startswith("//"):
        url = "https:" + url
    revised = _REVISED.search(html_text)
    revised_on = None
    if revised:
        try:
            revised_on = datetime.strptime(revised.group(1), "%d %B %Y").date()
        except ValueError:
            revised_on = None
    return urljoin(base_url, url), revised_on


def _note_flags(notes: str) -> tuple[list[str], bool]:
    flags = [flag for mark, flag in NOTE_FLAGS.items() if mark in notes]
    flags.extend(f"footnote_{n}" for n in _FOOTNOTE.findall(notes))
    return flags, BUDGET_MARK in notes


def _parse_sheet(
    rows: list[tuple[Any, ...]],
    sheet: str,
    metric_id: str,
    unit: str,
    pct: bool,
    release: SourceRelease,
    warnings: list[str],
) -> tuple[list[SpendingDataPoint], str]:
    legend_index = find_row(
        rows, lambda t: "blue" in t.casefold(), what=f"{sheet} colour legend"
    )
    header_index = find_row(rows, lambda t: t == "Country", what=f"{sheet} header")
    header = rows[header_index]
    years = {column: year for column, (year, _) in year_header(header).items()}
    if not years:
        raise SchemaChangedError(f"{sheet}: header has no year columns")
    notes_column = next(
        (i for i, cell in enumerate(header) if text(cell) == "Notes"), None
    )
    if notes_column is None:
        raise SchemaChangedError(f"{sheet}: 'Notes' column missing")
    points: list[SpendingDataPoint] = []
    for row in rows[header_index + 1 :]:
        label = text(row[0]) if row else ""
        if not label or normalise_label(label) in SKIP_LABELS:
            continue
        cells = {column: row[column] for column in years if column < len(row)}
        if not any(number(cell.value) is not None for cell in cells.values()):
            continue  # region heading or a country without data
        country = resolve_country(label)
        if country is None:
            warnings.append(f"{sheet}: unknown country label {label!r}")
            continue
        flags, is_budget = _note_flags(text(row[notes_column]))
        base_status = DatapointStatus.BUDGET if is_budget else DatapointStatus.ACTUAL
        for column, cell in cells.items():
            year = years[column]
            if year < MIN_YEAR:
                continue
            value = number(cell.value)
            if value is None:
                continue
            colour = font_colour_index(cell)
            status = DatapointStatus.ESTIMATE if colour == BLUE else base_status
            point_flags = [*flags, "highly_uncertain"] if colour == RED else list(flags)
            points.append(
                SpendingDataPoint(
                    source_id=SIPRI,
                    metric_id=metric_id,
                    country=country,
                    reference=ReferencePeriod.year(year),
                    value=value * PERCENT if pct else value,
                    unit=unit,
                    status=status,
                    release_id=release.release_id,
                    published_at=release.published_at,
                    source_url=release.canonical_url,
                    flags=tuple(point_flags),
                )
            )
    if not points:
        raise SchemaChangedError(f"{sheet}: no country rows parsed")
    return points, f"{sheet}: {text(rows[legend_index][0])}"


def parse_sipri_workbook(payload: bytes, release: SourceRelease) -> ParseResult:
    book = open_workbook(payload)
    points: list[SpendingDataPoint] = []
    warnings: list[str] = []
    fingerprints: list[str] = []
    for sheet, metric_id, unit, pct in SHEETS:
        rows = rows_of(require_sheet(book, sheet))
        sheet_points, fingerprint = _parse_sheet(
            rows, sheet, metric_id, unit, pct, release, warnings
        )
        points.extend(sheet_points)
        fingerprints.append(fingerprint)
    return ParseResult(tuple(points), tuple(warnings), " | ".join(fingerprints))


class SipriProvider:
    def __init__(self) -> None:
        self.spec = source_spec(SIPRI)

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease:
        page = await async_fetch_bytes(session, LANDING_URL)
        url, revised_on = discover_release(
            page.payload.decode("utf-8", "replace"), LANDING_URL
        )
        etag, last_modified = await async_head_metadata(session, url)
        filename = url.rsplit("/", 1)[-1]
        stamp = (
            revised_on.isoformat()
            if revised_on
            else (last_modified or etag or "unknown")
        )
        return SourceRelease(
            source_id=SIPRI,
            release_id=f"{filename}:{stamp}",
            published_at=revised_on or http_date_to_date(last_modified),
            download_url=url,
            canonical_url=LANDING_URL,
            format="xlsx",
            etag=etag,
            last_modified=last_modified,
        )

    async def async_fetch_release(
        self, session: ClientSession, release: SourceRelease
    ) -> tuple[SourceRelease, Payload]:
        """Fetch the workbook, keeping validators discovered at HEAD time.

        The workbook GET does not reliably repeat the ``ETag``/``Last-Modified``
        headers already captured by ``async_discover_latest``'s HEAD request,
        so they are kept unless the GET response supplies fresher ones.
        """
        fetched = await async_fetch_bytes(session, release.download_url)
        return (
            dataclasses.replace(
                release,
                etag=fetched.etag or release.etag,
                last_modified=fetched.last_modified or release.last_modified,
                checksum=fetched.checksum,
            ),
            fetched.payload,
        )

    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult:
        if not isinstance(payload, bytes):
            raise SchemaChangedError("SIPRI expects a single workbook payload")
        return parse_sipri_workbook(payload, release)

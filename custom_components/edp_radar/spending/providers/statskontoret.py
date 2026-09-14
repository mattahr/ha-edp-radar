"""Statskontoret monthly budget outturn (S9; plan §12–§19).

Discovery reads the official open-data page for the current year, picks the
newest ``Utgifter <month> <year>`` release (definitive beats preliminary for
the same month), its ``Senast uppdaterad`` date and the Zip (CSV) link. The CSV
covers January 2006 up to the release month; rows are identified by the
stable ``Anslag`` code, never by display names.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

from aiohttp import ClientSession

from ..models import (
    DatapointStatus,
    ReferencePeriod,
    SourceRelease,
    SpendingDataPoint,
)
from ..registry import FOCUS_COUNTRY, STATSKONTORET, source_spec
from . import base
from .base import (
    ParseResult,
    Payload,
    SchemaChangedError,
    SourceUnavailableError,
    async_fetch_bytes,
    with_fetch_metadata,
)

BASE_URL = "https://www.statskontoret.se"
DISCOVERY_URL = f"{BASE_URL}/analys-och-statistik/oppna-data/manadsutfall/"
UNIT = "SEK_MILLION"
EXPENDITURE_AREA = "06"
DEFENCE_PREFIX = "0601"
MATERIEL_APPROPRIATION = "0601003"
MONTH_COLUMNS: tuple[str, ...] = (
    "Utfall januari",
    "Utfall februari",
    "Utfall mars",
    "Utfall april",
    "Utfall maj",
    "Utfall juni",
    "Utfall juli",
    "Utfall augusti",
    "Utfall september",
    "Utfall oktober",
    "Utfall november",
    "Utfall december",
)
REQUIRED_COLUMNS: tuple[str, ...] = ("Utgiftsområde", "Anslag", "År", *MONTH_COLUMNS)
METRICS: tuple[tuple[str, Callable[[str, str], bool]], ...] = (
    ("uo6_total_outturn", lambda area, _anslag: area == EXPENDITURE_AREA),
    ("uo6_defence_outturn", lambda _area, anslag: anslag.startswith(DEFENCE_PREFIX)),
    ("materiel_outturn", lambda _area, anslag: anslag == MATERIEL_APPROPRIATION),
)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True, slots=True)
class DiscoveredRelease:
    year: int
    month: int
    status_raw: str
    updated: date | None
    csv_url: str
    heading: str

    @property
    def is_definitive(self) -> bool:
        return self.status_raw.casefold().startswith("definitiv")


class _DiscoveryParser(HTMLParser):
    """Collect heading, ``Senast uppdaterad`` and links per ``<li class="data">``."""

    def __init__(self) -> None:
        super().__init__()
        self.entries: list[tuple[str, str | None, list[str]]] = []
        self._in_entry = False
        self._heading: list[str] = []
        self._updated: str | None = None
        self._links: list[str] = []
        self._capture: str | None = None
        self._await_dd = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "li" and "data" in (attributes.get("class") or "").split():
            self._in_entry, self._heading, self._updated, self._links = (
                True,
                [],
                None,
                [],
            )
        elif self._in_entry and tag == "h2":
            self._capture = "h2"
        elif self._in_entry and tag == "dt":
            self._capture = "dt"
        elif self._in_entry and tag == "dd" and self._await_dd:
            self._capture = "dd"
        elif self._in_entry and tag == "a" and attributes.get("href"):
            self._links.append(attributes["href"] or "")

    def handle_data(self, data: str) -> None:
        if self._capture == "h2":
            self._heading.append(data)
        elif self._capture == "dt":
            self._await_dd = "senast uppdaterad" in data.casefold()
        elif self._capture == "dd":
            match = _DATE.search(data)
            if match:
                self._updated = match.group(0)
            self._await_dd = False

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h2", "dt", "dd"}:
            self._capture = None
        elif tag == "li" and self._in_entry:
            self.entries.append(
                ("".join(self._heading).strip(), self._updated, self._links)
            )
            self._in_entry = False


def parse_discovery_page(html_text: str, page_url: str) -> list[DiscoveredRelease]:
    """Expenditure (Utgifter) releases on the page, oldest first."""
    parser = _DiscoveryParser()
    parser.feed(html_text)
    releases: list[DiscoveredRelease] = []
    for heading, updated, links in parser.entries:
        for href in links:
            query = parse_qs(urlsplit(href).query)
            if query.get("documentType") != ["Utgift"] or query.get("fileType") != [
                "Zip"
            ]:
                continue
            try:
                year = int(query["Year"][0])
                month = int(query["month"][0])
                status_raw = query["status"][0]
            except (KeyError, IndexError, ValueError) as err:
                raise SchemaChangedError(
                    f"unexpected Statskontoret link {href!r}"
                ) from err
            releases.append(
                DiscoveredRelease(
                    year=year,
                    month=month,
                    status_raw=status_raw,
                    updated=date.fromisoformat(updated) if updated else None,
                    csv_url=urljoin(page_url, href),
                    heading=heading,
                )
            )
    releases.sort(key=lambda r: (r.year, r.month, r.is_definitive))
    return releases


def select_latest(releases: list[DiscoveredRelease]) -> DiscoveredRelease:
    if not releases:
        raise SchemaChangedError("no Utgifter releases found on the Statskontoret page")
    return releases[-1]


def status_of(status_raw: str) -> DatapointStatus:
    folded = status_raw.casefold()
    if folded.startswith("definitiv"):
        return DatapointStatus.ACTUAL
    if folded.startswith("prelimin"):
        return DatapointStatus.PRELIMINARY
    raise SchemaChangedError(f"unknown Statskontoret status {status_raw!r}")


def release_from(discovered: DiscoveredRelease, page_url: str) -> SourceRelease:
    slug = "definitiv" if discovered.is_definitive else "preliminar"
    updated = discovered.updated.isoformat() if discovered.updated else "unknown"
    return SourceRelease(
        source_id=STATSKONTORET,
        release_id=f"{discovered.year}-{discovered.month:02d}-{slug}-{updated}",
        published_at=discovered.updated,
        download_url=discovered.csv_url,
        canonical_url=page_url,
        format="csv",
    )


def _release_period(release: SourceRelease) -> tuple[int, int, DatapointStatus]:
    query = parse_qs(urlsplit(release.download_url).query)
    try:
        return (
            int(query["Year"][0]),
            int(query["month"][0]),
            status_of(query["status"][0]),
        )
    except (KeyError, IndexError, ValueError) as err:
        raise SchemaChangedError(
            f"release URL lacks Year/month/status: {release.download_url}"
        ) from err


def _csv_text(payload: bytes) -> str:
    if payload[:2] == b"PK":
        archive = zipfile.ZipFile(io.BytesIO(payload))
        names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise SchemaChangedError("Statskontoret zip contains no CSV")
        info = archive.getinfo(names[0])
        if info.file_size > base.MAX_PAYLOAD_BYTES:
            raise SourceUnavailableError(
                f"{names[0]} is larger than {base.MAX_PAYLOAD_BYTES} bytes "
                f"({info.file_size})"
            )
        payload = archive.read(names[0])
    return payload.decode("utf-8-sig")


def _decimal(text: str) -> Decimal | None:
    if not text.strip():
        return None
    try:
        return Decimal(text.strip().replace(",", "."))
    except InvalidOperation as err:
        raise SchemaChangedError(f"non-numeric outturn value {text!r}") from err


def parse_outturn_csv(payload: bytes, release: SourceRelease) -> ParseResult:
    """Sum the three metrics per (year, month) from the appropriation rows."""
    release_year, release_month, release_status = _release_period(release)
    reader = csv.reader(io.StringIO(_csv_text(payload)), delimiter=";")
    header = next(reader, None)
    if header is None:
        raise SchemaChangedError("Statskontoret CSV is empty")
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise SchemaChangedError(f"Statskontoret CSV lacks columns {missing}")
    index = {name: header.index(name) for name in REQUIRED_COLUMNS}
    sums: dict[tuple[str, int, int], Decimal] = {}
    matched_rows = 0
    for row in reader:
        if len(row) < len(header):
            continue
        area, anslag = row[index["Utgiftsområde"]], row[index["Anslag"]]
        if area != EXPENDITURE_AREA:
            continue
        matched_rows += 1
        year = int(row[index["År"]])
        for month, column in enumerate(MONTH_COLUMNS, start=1):
            if (year, month) > (release_year, release_month):
                # A row can carry a stray value for a month later than the
                # release (plan §60); a partially reported future month must
                # never become a datapoint.
                continue
            value = _decimal(row[index[column]])
            if value is None:
                continue
            for metric_id, predicate in METRICS:
                if predicate(area, anslag):
                    key = (metric_id, year, month)
                    sums[key] = sums.get(key, Decimal(0)) + value
    if matched_rows == 0:
        raise SchemaChangedError("Statskontoret CSV has no rows for utgiftsområde 06")
    datapoints = tuple(
        SpendingDataPoint(
            source_id=STATSKONTORET,
            metric_id=metric_id,
            country=FOCUS_COUNTRY,
            reference=ReferencePeriod.month(year, month),
            value=value,
            unit=UNIT,
            status=release_status
            if (year, month) == (release_year, release_month)
            else DatapointStatus.ACTUAL,
            release_id=release.release_id,
            published_at=release.published_at,
            source_url=release.canonical_url,
        )
        for (metric_id, year, month), value in sorted(sums.items())
    )
    return ParseResult(datapoints, (), ";".join(header))


class StatskontoretProvider:
    """Discovery page → newest Utgifter Zip → CSV."""

    def __init__(self, *, today: Callable[[], date] = date.today) -> None:
        self.spec = source_spec(STATSKONTORET)
        self._today = today

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease:
        year = self._today().year
        for candidate in (year, year - 1):
            page_url = f"{DISCOVERY_URL}?year={candidate}"
            page = await async_fetch_bytes(session, page_url)
            releases = parse_discovery_page(
                page.payload.decode("utf-8", "replace"), page_url
            )
            if releases:
                return release_from(select_latest(releases), page_url)
        raise SchemaChangedError(
            "Statskontoret lists no Utgifter releases for this or last year"
        )

    async def async_fetch_release(
        self, session: ClientSession, release: SourceRelease
    ) -> tuple[SourceRelease, Payload]:
        fetched = await async_fetch_bytes(session, release.download_url)
        return with_fetch_metadata(release, fetched), fetched.payload

    def parse_release(self, payload: Payload, release: SourceRelease) -> ParseResult:
        if not isinstance(payload, bytes):
            raise SchemaChangedError("Statskontoret expects a single CSV/Zip payload")
        return parse_outturn_csv(payload, release)

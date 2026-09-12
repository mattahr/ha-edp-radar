"""Download and trim the real spending fixtures (S18).

Usage:
    PYTHONPATH=. uv run python scripts/fetch_spending_fixtures.py statskontoret
    PYTHONPATH=. uv run python scripts/fetch_spending_fixtures.py all

Downloads are cached under --cache (default .cache/spending/fixtures). Trimming
keeps the rows/sheets the parsers and tests need; numbers are never edited.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import re
import sys
import zipfile
import zlib
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

FIXTURES = Path("tests/fixtures/spending")
USER_AGENT = "ha-edp-radar fixture fetcher"


def download(url: str, cache: Path, name: str) -> bytes:
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / name
    if target.exists():
        return target.read_bytes()
    # Python 3.14's http.client defaults to "Accept-Encoding: identity"; the
    # Statskontoret server 404s on that header, so request gzip/deflate explicitly
    # and decompress the response ourselves (http.client does not do it for us).
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    with urlopen(Request(url, headers=headers)) as response:
        data: bytes = response.read()
        encoding = response.headers.get("Content-Encoding", "")
    if encoding == "gzip":
        data = gzip.decompress(data)
    elif encoding == "deflate":
        data = zlib.decompress(data)
    target.write_bytes(data)
    print(f"downloaded {url} -> {target} ({len(data)} bytes)")
    return data


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"wrote {path} ({len(data)} bytes)")


# ----------------------------------------------------------------- Statskontoret

SK_BASE = "https://www.statskontoret.se"
SK_PAGE = SK_BASE + "/analys-och-statistik/oppna-data/manadsutfall/?year={year}"
SK_FILE = (
    SK_BASE
    + "/OpenDataManadsUtfallPage/GetFile?documentType=Utgift&fileType=Zip"
    + "&fileName=x.zip&Year={year}&month={month}&status={status}"
)
_LI_DATA = re.compile(r'<li class="data[^"]*">.*?</li>', re.S)


def trim_statskontoret_page(html: str) -> str:
    """Keep only the ``<li class="data">`` blocks for Utgifter releases."""
    blocks = [b for b in _LI_DATA.findall(html) if "documentType=Utgift" in b]
    body = "\n".join(blocks)
    return (
        f'<!DOCTYPE html>\n<html lang="sv"><body><ul class="fixture">\n'
        f"{body}\n</ul></body></html>\n"
    )


def trim_statskontoret_csv(zip_bytes: bytes, years: set[str]) -> bytes:
    """Header + every utgiftsområde 06 row of ``years`` + three non-06 rows."""
    archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    text = archive.read(archive.namelist()[0]).decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    kept = [rows[0]]
    others = 0
    for row in rows[1:]:
        if row[0] == "06" and row[10] in years:
            kept.append(row)
        elif others < 3 and row[10] in years:
            kept.append(row)
            others += 1
    out = io.StringIO()
    csv.writer(out, delimiter=";", lineterminator="\n").writerows(kept)
    return ("﻿" + out.getvalue()).encode("utf-8")


def fetch_statskontoret(cache: Path) -> None:
    folder = FIXTURES / "statskontoret"
    for year in (2026, 2025):
        page = download(SK_PAGE.format(year=year), cache, f"statskontoret-{year}.html")
        write(
            folder / f"discovery-{year}.html",
            trim_statskontoret_page(page.decode("utf-8")).encode("utf-8"),
        )
    july = download(
        SK_FILE.format(year=2026, month=7, status="Definitiv"),
        cache,
        "statskontoret-2026-07.zip",
    )
    write(
        folder / "utgifter-2026-07.csv", trim_statskontoret_csv(july, {"2025", "2026"})
    )
    prelim = download(
        SK_FILE.format(year=2025, month=12, status=quote("Preliminär 1")),
        cache,
        "statskontoret-2025-12-preliminar.zip",
    )
    write(
        folder / "utgifter-2025-12-preliminar.csv",
        trim_statskontoret_csv(prelim, {"2025"}),
    )
    definitive = download(
        SK_FILE.format(year=2025, month=12, status="Definitiv"),
        cache,
        "statskontoret-2025-12-definitiv.zip",
    )
    write(
        folder / "utgifter-2025-12-definitiv.csv",
        trim_statskontoret_csv(definitive, {"2025"}),
    )


FETCHERS = {"statskontoret": fetch_statskontoret}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("source", choices=[*FETCHERS, "all"])
    parser.add_argument("--cache", default=".cache/spending/fixtures")
    args = parser.parse_args(argv)
    cache = Path(args.cache)
    for name, fetcher in FETCHERS.items():
        if args.source in (name, "all"):
            fetcher(cache)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

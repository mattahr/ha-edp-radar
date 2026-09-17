"""Phase 3A/3B harness: profile every spending source and validate the facts.

Usage:
    PYTHONPATH=. uv run python scripts/spending_profile.py \
        --out docs/phase3-source-profile.md
    PYTHONPATH=. uv run python scripts/spending_profile.py --no-fetch

Every provider's latest release is discovered, downloaded and cached under
--cache (default .cache/spending/profile); --no-fetch re-parses the newest
cached release. The report holds aggregates, provenance and the Sweden
answers of plan §71 — never raw workbooks.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import aiohttp

from custom_components.edp_radar.spending.calculations import (
    latest_month,
    latest_reference,
    nominal_change_pct,
    nordic_subset,
    rank,
    ytd,
)
from custom_components.edp_radar.spending.freshness import (
    freshness_state,
    publication_age_days,
    reference_age_days,
)
from custom_components.edp_radar.spending.models import (
    DatapointStatus,
    SourceRelease,
    SpendingDataPoint,
)
from custom_components.edp_radar.spending.providers import all_providers
from custom_components.edp_radar.spending.providers.base import (
    ParseResult,
    Payload,
    SourceUnavailableError,
    SpendingProvider,
    SpendingProviderError,
)
from custom_components.edp_radar.spending.registry import (
    FOCUS_COUNTRY,
    SOURCE_ORDER,
    metrics_for,
    source_spec,
)

BUDGET_PAGE = (
    "https://www.statskontoret.se/analys-och-statistik/utfall/"
    "utfall-for-statens-budget/?year={year}&month={month}"
)
UO6_NAME = "Försvar och samhällets krisberedskap"

REVISION_BEHAVIOUR = {
    "statskontoret": (
        "Every monthly file carries the full history; December is published as "
        "preliminär then definitiv. The store diff records changed values as "
        "revisions."
    ),
    "eurostat": (
        "Twice-yearly dissemination may revise earlier years; `updated` changes "
        "the release id and the store diff records revisions."
    ),
    "nato": (
        "Each annual workbook restates 2014 onwards and re-marks the last two "
        "years as estimates; revisions detected by the store diff."
    ),
    "eda": (
        "Occasional in-year revisions (EDA statement); every workbook ≥ 2022 is "
        "re-fetched and compared."
    ),
    "sipri": (
        "Annual release plus in-year revisions replacing the file; full "
        "re-import and store diff."
    ),
}
PARSER_RISK = {
    "statskontoret": (
        "HTML discovery markup (`li.data`, `Senast uppdaterad`, GetFile query) "
        "and CSV column names."
    ),
    "eurostat": (
        "Dimension/unit codes; a renamed code fails discovery of the metric "
        "(SchemaChangedError)."
    ),
    "nato": (
        "Sheet names, `Table N:` titles, block subtitles, `YYYYe` headers, label "
        "spellings; XLSX must share the PDF path."
    ),
    "eda": (
        "Portal anchor text `Defence Data YYYY`, `Member States` sheet header "
        "wording, footnote conventions."
    ),
    "sipri": (
        "Landing-page anchor and revision sentence; header row `Country`; colour "
        "semantics (blue/red)."
    ),
}


def _table(rows: list[tuple[Any, ...]], header: tuple[str, ...]) -> str:
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    lines += [
        "| " + " | ".join(str(c) if str(c) else "—" for c in row) + " |" for row in rows
    ]
    return "\n".join(lines)


def _fmt(value: Decimal | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:,.{digits}f}"


def _reference_age_text(latest_end: date | None, today: date) -> str:
    if latest_end is None:
        return "reference age n/a"
    age = reference_age_days(latest_end, today)
    if age < 0:
        return (
            f"reference age {age} d (reference period ends {latest_end}, "
            "not yet complete)"
        )
    return f"reference age {age} d"


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text)[:120]


async def fetch_release(
    provider: SpendingProvider, session: aiohttp.ClientSession, cache: Path
) -> tuple[SourceRelease, Payload]:
    release = await provider.async_discover_latest(session)
    fetched, payload = await provider.async_fetch_release(session, release)
    folder = cache / provider.spec.source_id / _slug(fetched.release_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "release.json").write_text(json.dumps(fetched.to_dict(), indent=2))
    if isinstance(payload, bytes):
        (folder / "payload.bin").write_bytes(payload)
    else:
        for key, blob in payload.items():
            (folder / f"payload.{key}.bin").write_bytes(blob)
    return fetched, payload


def cached_release(
    provider: SpendingProvider, cache: Path
) -> tuple[SourceRelease, Payload]:
    folders = sorted(
        (cache / provider.spec.source_id).glob("*/release.json"),
        key=lambda p: p.stat().st_mtime,
    )
    if not folders:
        raise SystemExit(
            f"no cached release for {provider.spec.source_id}; run without --no-fetch"
        )
    folder = folders[-1].parent
    release = SourceRelease.from_dict(json.loads((folder / "release.json").read_text()))
    single = folder / "payload.bin"
    if single.exists():
        return release, single.read_bytes()
    parts = {p.name.split(".")[1]: p.read_bytes() for p in folder.glob("payload.*.bin")}
    return release, parts


async def check_budget_page(
    session: aiohttp.ClientSession | None, cache: Path, today: date
) -> dict[str, Any]:
    """Plan §53: does the human-readable outturn page expose a UO6 budget?

    The page's budget column is labelled ``SB + ÄB`` (statens budget plus
    ändringsbudget).
    """
    month = today.month - 2 if today.month > 2 else 12
    year = today.year if today.month > 2 else today.year - 1
    url = BUDGET_PAGE.format(year=year, month=month)
    target = cache / "statskontoret" / "budget-page.html"
    failed = {"url": url, "sb_ab_column": False, "uo6_row": False}
    if session is not None:
        # A side check must never discard the provider results: degrade to
        # an error entry on any network, timeout or HTTP failure.
        try:
            async with (
                asyncio.timeout(60),
                session.get(
                    url, headers={"User-Agent": "ha-edp-radar profile"}
                ) as response,
            ):
                if response.status != 200:
                    raise SourceUnavailableError(f"HTTP {response.status} for {url}")
                html = await response.text()
        except (
            aiohttp.ClientError,
            TimeoutError,
            OSError,
            SpendingProviderError,
        ) as err:
            return {**failed, "error": f"{type(err).__name__}: {err}"}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html)
    elif target.exists():
        html = target.read_text()
    else:
        return {
            **failed,
            "error": f"no cached page at {target}; run without --no-fetch",
        }
    return {
        "url": url,
        "sb_ab_column": "SB + ÄB" in html or "SB&nbsp;+&nbsp;ÄB" in html,
        "uo6_row": UO6_NAME in html,
        "error": None,
    }


def profile_section(
    provider: SpendingProvider, release: SourceRelease, result: ParseResult, today: date
) -> str:
    spec = provider.spec
    points = result.datapoints
    metrics = Counter(p.metric_id for p in points)
    statuses = Counter(p.status.value for p in points)
    countries = sorted({p.country for p in points})
    latest_by_metric = {
        m: latest_reference(points, m, min_countries=1) for m in metrics
    }
    latest_end = max((r.end for r in latest_by_metric.values() if r), default=None)
    missing_latest: list[str] = []
    for metric_id, ref in latest_by_metric.items():
        if ref is None:
            continue
        have = {
            p.country for p in points if p.metric_id == metric_id and p.reference == ref
        }
        missing_latest.append(
            f"{metric_id} {ref.label}: {len(have)}/{len(countries)} countries"
        )
    rows = [
        ("technical access confirmed", "yes"),
        ("discovery method", f"{spec.canonical_url} → {release.download_url}"),
        ("format", release.format),
        (
            "latest release found",
            f"`{release.release_id}` published {release.published_at} "
            f"(etag {release.etag!r}, checksum {(release.checksum or '')[:12]}…)",
        ),
        ("latest reference period", latest_end.isoformat() if latest_end else "n/a"),
        ("available countries", f"{len(countries)}: {', '.join(countries)}"),
        (
            "available metrics",
            ", ".join(f"{m} ({n})" for m, n in sorted(metrics.items())),
        ),
        (
            "actual/estimate/projection distinctions",
            ", ".join(f"{s}: {n}" for s, n in sorted(statuses.items())),
        ),
        ("source publication date available", "yes" if release.published_at else "no"),
        ("revision behaviour", REVISION_BEHAVIOUR[spec.source_id]),
        (
            "missing data",
            "; ".join(missing_latest)
            + (f"; warnings: {'; '.join(result.warnings)}" if result.warnings else ""),
        ),
        ("parser risk", PARSER_RISK[spec.source_id]),
        (
            "freshness today",
            freshness_state(spec, latest_end, release.published_at, today).value
            + f" (publication age {publication_age_days(release.published_at, today)}"
            f" d, {_reference_age_text(latest_end, today)})",
        ),
        ("layout fingerprint", f"`{result.layout_fingerprint[:160]}`"),
    ]
    return f"## {spec.display_name}\n\n" + _table(rows, ("Item", "Value")) + "\n"


def _rank_line(points: tuple[SpendingDataPoint, ...], metric_id: str, unit: str) -> str:
    ref = latest_reference(points, metric_id)
    if ref is None:
        return f"- {metric_id}: no reference period with ≥ 2 countries"
    ranking = rank(points, metric_id=metric_id, unit=unit, reference=ref)
    if ranking is None:
        return f"- {metric_id} {ref.label}: Sweden missing or zero"
    nordic = ", ".join(
        f"{e.country} #{e.rank} {_fmt(e.value)}" for e in nordic_subset(ranking)
    )
    return (
        f"- {metric_id} {ref.label} ({unit}, statuses {'/'.join(ranking.statuses)}): "
        f"Sweden #{ranking.focus_rank} of {ranking.population}, "
        f"{_fmt(ranking.focus_value)}; "
        f"top {ranking.top.country} {_fmt(ranking.top.value)}; "
        f"median {_fmt(ranking.median)}; Nordic: {nordic}"
    )


def _budget_line(budget: dict[str, Any]) -> str:
    if budget.get("error"):
        return (
            f"- Budget utilisation (plan §53): the human-readable page {budget['url']} "
            f"could not be fetched ({budget['error']}); budget utilisation stays "
            "omitted (S16)."
        )
    return (
        f"- Budget utilisation (plan §53): human-readable page {budget['url']} — "
        f"SB + ÄB column present: {budget['sb_ab_column']}, "
        f"UO6 row present: {budget['uo6_row']}. "
        + (
            "A per-expenditure-area budget is exposed; a budget metric can be "
            "designed in Plan 2."
            if budget["uo6_row"] and budget["sb_ab_column"]
            else "No per-expenditure-area budget with provenance found; budget "
            "utilisation is omitted (S16)."
        )
    )


def validation_section(
    results: dict[str, tuple[SourceRelease, ParseResult]], budget: dict[str, Any]
) -> str:
    out = ["# Factual validation (plan §71)\n"]
    if "statskontoret" in results:
        release, result = results["statskontoret"]
        points = result.datapoints
        latest = latest_month(points, "materiel_outturn", FOCUS_COUNTRY)
        lines = ["## Statskontoret\n"]
        if latest:
            y, m = latest.reference.start.year, latest.reference.start.month
            current = ytd(points, "materiel_outturn", FOCUS_COUNTRY, y, m)
            previous = ytd(points, "materiel_outturn", FOCUS_COUNTRY, y - 1, m)
            defence_ytd = ytd(points, "uo6_defence_outturn", FOCUS_COUNTRY, y, m)
            total_ytd = ytd(points, "uo6_total_outturn", FOCUS_COUNTRY, y, m)
            lines += [
                f"- Latest Swedish reference month: **{latest.reference.label}** "
                f"(status {latest.status.value})",
                f"- Materiel acquisition latest month: SEK {_fmt(latest.value)} m",
                f"- Materiel acquisition YTD Jan–{latest.reference.label}: "
                f"SEK {_fmt(current)} m; same period {y - 1}: SEK {_fmt(previous)} m; "
                f"nominal change {_fmt(nominal_change_pct(current, previous))} %",
                f"- Defence appropriations (1:1–1:14) YTD: SEK {_fmt(defence_ytd)} m; "
                f"UO6 total YTD: SEK {_fmt(total_ytd)} m",
                f"- Publication date: {release.published_at}; "
                f"release `{release.release_id}`",
            ]
        lines.append(_budget_line(budget))
        out.append("\n".join(lines) + "\n")
    if "eurostat" in results:
        points = results["eurostat"][1].datapoints
        out.append(
            "## Eurostat\n\n"
            + "\n".join(
                [
                    _rank_line(points, "defence_expenditure", "EUR_MILLION"),
                    _rank_line(points, "defence_expenditure_pct_gdp", "PCT_GDP"),
                    _rank_line(points, "defence_investment", "EUR_MILLION"),
                    _rank_line(points, "defence_investment_pct_gdp", "PCT_GDP"),
                ]
            )
            + "\n"
        )
    if "nato" in results:
        points = results["nato"][1].datapoints
        actual_years = sorted(
            {
                p.reference.start.year
                for p in points
                if p.status is DatapointStatus.ACTUAL
            }
        )
        estimate_years = sorted(
            {
                p.reference.start.year
                for p in points
                if p.status is DatapointStatus.ESTIMATE
            }
        )
        out.append(
            "## NATO\n\n"
            + "\n".join(
                [
                    f"- Actual years {actual_years[0]}–{actual_years[-1]}; "
                    f"estimate years {estimate_years}",
                    _rank_line(
                        points, "defence_expenditure_usd_current", "USD_MILLION"
                    ),
                    _rank_line(points, "defence_expenditure_pct_gdp", "PCT_GDP"),
                    _rank_line(points, "equipment_share_pct", "PCT"),
                    _rank_line(
                        points, "equipment_expenditure_usd_current", "USD_MILLION"
                    ),
                ]
            )
            + "\n"
        )
    if "eda" in results:
        points = results["eda"][1].datapoints
        lines = ["## EDA\n"]
        for spec in metrics_for("eda"):
            ref = latest_reference(points, spec.metric_id, min_countries=1)
            have_se = any(
                p.metric_id == spec.metric_id and p.country == FOCUS_COUNTRY
                for p in points
            )
            lines.append(
                f"- {spec.metric_id}: latest {ref.label if ref else 'n/a'}, "
                f"Sweden {'available' if have_se else 'missing'}"
            )
        lines += [
            _rank_line(points, "defence_expenditure", "EUR_MILLION"),
            _rank_line(points, "defence_investment", "EUR_MILLION"),
            _rank_line(points, "equipment_procurement", "EUR_MILLION"),
        ]
        out.append("\n".join(lines) + "\n")
    if "sipri" in results:
        points = results["sipri"][1].datapoints
        se_years = sorted(
            p.reference.start.year
            for p in points
            if p.country == FOCUS_COUNTRY
            and p.metric_id == "military_expenditure_usd_constant"
        )
        constant_unit = next(
            p.unit
            for p in points
            if p.metric_id == "military_expenditure_usd_constant"
            and p.country == FOCUS_COUNTRY
        )
        out.append(
            "## SIPRI\n\n"
            + "\n".join(
                [
                    f"- Sweden available {se_years[0]}–{se_years[-1]} "
                    "(stored from MIN_YEAR; the workbook starts 1949)",
                    _rank_line(
                        points, "military_expenditure_usd_constant", constant_unit
                    ),
                    _rank_line(points, "military_expenditure_pct_gdp", "PCT_GDP"),
                ]
            )
            + "\n"
        )
    return "\n".join(out)


async def run(args: argparse.Namespace) -> str:
    cache = Path(args.cache)
    today = date.fromisoformat(args.today) if args.today else datetime.now(UTC).date()
    providers = {p.spec.source_id: p for p in all_providers()}
    results: dict[str, tuple[SourceRelease, ParseResult]] = {}
    errors: dict[str, str] = {}
    session: aiohttp.ClientSession | None = (
        None if args.no_fetch else aiohttp.ClientSession()
    )
    try:
        for provider in providers.values():
            source_id = provider.spec.source_id
            try:
                release, payload = (
                    cached_release(provider, cache)
                    if session is None
                    else await fetch_release(provider, session, cache)
                )
                results[source_id] = (release, provider.parse_release(payload, release))
                print(
                    f"{source_id}: {len(results[source_id][1].datapoints)} datapoints",
                    file=sys.stderr,
                )
            except Exception as err:
                # Mirrors the coordinator's per-provider isolation: a
                # KeyError/IndexError bug in one parser must not abort the
                # whole report, only that source's "no" row.
                errors[source_id] = f"{type(err).__name__}: {err}"
                print(f"{source_id}: FAILED {errors[source_id]}", file=sys.stderr)
        budget = await check_budget_page(session, cache, today)
    finally:
        if session is not None:
            await session.close()
    generated = datetime.now(UTC).isoformat(timespec="seconds")
    sections = [
        "# Phase 3 source profile\n",
        f"Generated {generated} by `scripts/spending_profile.py` "
        f"(report date {today}). "
        "Plan §70 profile per provider, then the plan §71 factual validation. "
        "Values are aggregates and Sweden facts with provenance; no raw payloads.\n",
    ]
    for source_id in SOURCE_ORDER:
        if source_id in results:
            sections.append(
                profile_section(providers[source_id], *results[source_id], today)
            )
        else:
            sections.append(
                f"## {source_spec(source_id).display_name}\n\n"
                "| Item | Value |\n| --- | --- |\n"
                "| technical access confirmed | **no** — "
                f"{errors.get(source_id, 'not attempted')} |\n"
            )
    sections.append(validation_section(results, budget))
    return "\n".join(sections)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", default="docs/phase3-source-profile.md")
    parser.add_argument("--cache", default=".cache/spending/profile")
    parser.add_argument(
        "--no-fetch", action="store_true", help="re-parse the newest cached release"
    )
    parser.add_argument(
        "--today", default=None, help="report date YYYY-MM-DD (default: today)"
    )
    args = parser.parse_args(argv)
    report = asyncio.run(run(args))
    Path(args.out).write_text(report, encoding="utf-8")
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

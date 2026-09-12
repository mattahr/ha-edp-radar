"""Phase 0 research harness (plan §50 Phase 0, §54): profile real TED data.

Usage:
    PYTHONPATH=. uv run python scripts/data_profile.py --days 90 --mode strict \
        --out docs/data-profile.md

Raw pages are cached under --cache (default .cache/profile) so the report can be
regenerated without hitting the API (--no-fetch). The report contains only
aggregates; no notice text is written.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import aiohttp

from custom_components.edp_radar.api import TedApiClient
from custom_components.edp_radar.const import RelevanceMode
from custom_components.edp_radar.fx import EcbFxClient
from custom_components.edp_radar.fx_rates import FxRateTable
from custom_components.edp_radar.lifecycle import ProcedureIndex
from custom_components.edp_radar.metrics import (
    MetricsConfig,
    compute_snapshot,
    format_eur,
    is_central_purchasing_only,
    value_in_eur,
)
from custom_components.edp_radar.models import NoticeStage
from custom_components.edp_radar.normalizer import (
    REQUESTED_FIELDS,
    as_strings,
    normalize_many,
)
from custom_components.edp_radar.query import TedQueryBuilder as Q
from custom_components.edp_radar.taxonomy import Taxonomy

type Raw = list[dict[str, Any]]


def _pct(part: int, whole: int) -> str:
    return "n/a" if whole == 0 else f"{part / whole * 100:.1f}%"


def _table(rows: list[tuple[Any, ...]], header: tuple[str, ...]) -> str:
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def _paths(args: argparse.Namespace) -> tuple[Path, Path]:
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    countries = args.countries or "all"
    return (
        cache / f"{args.mode}-{args.days}d-{countries}.json",
        cache / f"fx-{args.days}d.json",
    )


async def fetch(
    args: argparse.Namespace, taxonomy: Taxonomy
) -> tuple[Raw, FxRateTable]:
    start = date.today() - timedelta(days=args.days)
    mode = RelevanceMode(args.mode)
    query = Q.combine_and(
        Q.publication_range(start),
        Q.defence_universe(mode, taxonomy.defence_cpv_prefixes),
        Q.countries(args.countries.split(",")) if args.countries else "",
    )
    print(f"query: {query}", file=sys.stderr)
    raw: Raw = []
    async with aiohttp.ClientSession() as session:
        client = TedApiClient(session)
        await client.async_validate_query(query)

        def progress(done: int, total: int | None) -> None:
            print(f"  fetched {done}/{total}", file=sys.stderr)

        async for notice in client.async_search_notices(
            query, REQUESTED_FIELDS, progress=progress
        ):
            raw.append(notice)
        ecb = EcbFxClient(session)
        if args.days > 80:
            rates = await ecb.async_fetch_history()
        else:
            rates = await ecb.async_fetch_recent()
    table = FxRateTable()
    table.update({d: r for d, r in rates.items() if d >= start - timedelta(days=30)})
    return raw, table


def profile(
    raw: Raw, fx: FxRateTable, taxonomy: Taxonomy, args: argparse.Namespace
) -> str:
    notices, errors = normalize_many(raw, taxonomy)
    index = ProcedureIndex.build(notices)
    latest = index.notices
    competitions = index.competitions()
    results = index.results()
    today = date.today()
    lines: list[str] = []
    add = lines.append

    add(f"# TED data profile — {args.mode} mode, last {args.days} days")
    add("")
    add(
        f"Generated {datetime.now(UTC).isoformat(timespec='seconds')} by "
        f"`scripts/data_profile.py` (taxonomy {taxonomy.version}). "
        f"Countries: {args.countries or 'all'}."
    )
    add("")
    add("## Volume")
    add("")
    cpb = sum(1 for n in latest if is_central_purchasing_only(n))
    add(
        _table(
            [
                ("raw notices returned", len(raw)),
                ("parse errors", errors),
                ("notice versions", len(notices)),
                ("unique notice ids", len(latest)),
                ("unique procedures (incl. unlinked pseudo-procedures)", len(index)),
                (
                    "central-purchasing-only notices (>10 buyers, buyer signal only)",
                    cpb,
                ),
            ],
            ("measure", "value"),
        )
    )
    add("")
    add("## Versions and changes")
    add("")
    versions = Counter(n.notice_version for n in notices)
    add(_table(sorted(versions.items()), ("notice-version", "count")))
    add("")
    changes = [n for n in notices if n.is_change]
    add(
        f"- notice versions carrying change info: {len(changes)} "
        f"(v1: {sum(1 for n in changes if n.notice_version == 1)}, "
        f"v>1: {sum(1 for n in changes if n.notice_version > 1)})"
    )
    mods = sum(1 for n in latest if n.stage is NoticeStage.MODIFICATION)
    add(f"- modification notices: {mods}")
    add("")
    add("## Stage distribution (latest versions)")
    add("")
    stages = Counter(n.stage.value for n in latest)
    add(_table(sorted(stages.items()), ("stage", "count")))
    add("")
    add("## Match reasons (latest versions)")
    add("")
    reasons = Counter("+".join(sorted(n.match_reasons)) or "(none)" for n in latest)
    add(_table(sorted(reasons.items()), ("reasons", "count")))
    add("")
    add("## Primary buyer country (latest versions, top 30)")
    add("")
    countries = Counter(n.buyer.country or "??" for n in latest)
    add(_table(countries.most_common(30), ("country", "count")))
    add("")
    add("## Coverage")
    add("")
    est = sum(1 for c in competitions if c.estimated_value)
    est_eur = sum(
        1
        for c in competitions
        if value_in_eur(c.estimated_value, c.publication_date, fx) is not None
    )
    res = sum(1 for r in results if r.result_value)
    frameworks = [r for r in results if r.is_framework]
    ceilings = sum(1 for r in frameworks if r.framework_value)

    res_eur = sum(
        1 for r in results if value_in_eur(r.result_value, r.award_date, fx) is not None
    )
    with_winners = [r for r in results if r.winners]
    with_ids = sum(1 for r in with_winners if all(w.identifier for w in r.winners))
    with_counts = sum(
        1 for r in results if r.tender_statistics and r.tender_statistics.tender_counts
    )
    with_status = sum(
        1
        for r in results
        if r.tender_statistics and r.tender_statistics.selection_statuses
    )
    decided = [p for p in index.procedures.values() if p.first_result]
    linked = sum(1 for p in decided if p.first_competition)
    add(
        _table(
            [
                (
                    "procedure-id coverage (latest versions)",
                    _pct(sum(1 for n in latest if n.procedure_id), len(latest)),
                ),
                (
                    "buyer-identifier coverage",
                    _pct(sum(1 for n in latest if n.buyer.identifiers), len(latest)),
                ),
                (
                    "competitions with estimated value",
                    f"{est}/{len(competitions)} ({_pct(est, len(competitions))})",
                ),
                (
                    "… convertible to EUR",
                    f"{est_eur}/{len(competitions)} "
                    f"({_pct(est_eur, len(competitions))})",
                ),
                (
                    "results with result value",
                    f"{res}/{len(results)} ({_pct(res, len(results))})",
                ),
                (
                    "… convertible to EUR",
                    f"{res_eur}/{len(results)} ({_pct(res_eur, len(results))})",
                ),
                ("results with winners", f"{len(with_winners)}/{len(results)}"),
                (
                    "framework-agreement results (ceiling kept, award value unknown)",
                    f"{sum(1 for r in results if r.is_framework)}/{len(results)}",
                ),
                (
                    "… with a winner identifier for every winner",
                    _pct(with_ids, len(with_winners)),
                ),
                (
                    "… of which with a declared framework ceiling",
                    f"{ceilings}/{len(frameworks)}",
                ),
                (
                    "results with comparable tender counts",
                    _pct(with_counts, len(results)),
                ),
                ("results with selection statuses", _pct(with_status, len(results))),
                (
                    "results linked to a competition in the window",
                    _pct(linked, len(decided)),
                ),
                (
                    "notices without strategic category",
                    _pct(sum(1 for n in latest if not n.categories), len(latest)),
                ),
            ],
            ("measure", "value"),
        )
    )
    add("")
    add("## Currencies")
    add("")
    currencies = Counter(
        m.currency
        for n in latest
        for m in (n.estimated_value, n.result_value)
        if m is not None
    )
    add(_table(currencies.most_common(), ("currency", "monetary fields")))
    add("")
    add("## Received-submission type codes (all result notices, per lot entry)")
    add("")
    codes = Counter(
        s.type_code
        for r in results
        if r.tender_statistics
        for s in r.tender_statistics.statistics
    )
    add(_table(codes.most_common(), ("type code", "entries")))
    add("")
    add("## Selection status and non-award justifications")
    add("")
    statuses = Counter(
        s
        for r in results
        if r.tender_statistics
        for s in r.tender_statistics.selection_statuses
    )
    add(_table(statuses.most_common(), ("winner-selection-status", "lot entries")))
    add("")
    justifications = Counter(
        j
        for r in results
        if r.tender_statistics
        for j in r.tender_statistics.non_award_justifications
    )
    add(_table(justifications.most_common(), ("non-award-justification", "entries")))
    add("")
    add("## Top CPV divisions (latest versions)")
    add("")
    divisions = Counter(code[:2] for n in latest for code in set(n.cpv_codes))
    add(_table(divisions.most_common(15), ("CPV division", "notices")))
    add("")
    add("## Strategic categories (latest versions, multi-label)")
    add("")
    cats = Counter(c for n in latest for c in n.categories)
    add(
        _table(
            [(taxonomy.label(c), v) for c, v in cats.most_common()],
            ("category", "notices"),
        )
    )
    add("")
    add("## Raw-array alignment anomalies")
    add("")

    def mismatch(a: str, b: str) -> int:
        return sum(
            1
            for r in raw
            if r.get(a) and len(as_strings(r.get(a))) != len(as_strings(r.get(b)))
        )

    add(
        _table(
            [
                (
                    "estimated-value-lot vs estimated-value-cur-lot length mismatch",
                    mismatch("estimated-value-lot", "estimated-value-cur-lot"),
                ),
                (
                    "result-value-lot vs result-value-cur-lot length mismatch",
                    mismatch("result-value-lot", "result-value-cur-lot"),
                ),
                (
                    "received-submissions code vs val length mismatch",
                    mismatch(
                        "received-submissions-type-code",
                        "received-submissions-type-val",
                    ),
                ),
                (
                    "unique winner names vs winner-identifier count mismatch",
                    sum(
                        1
                        for n in latest
                        if n.winners and any(w.identifier is None for w in n.winners)
                    ),
                ),
                (
                    "buyer-identifier count != buyer-country count",
                    mismatch("buyer-identifier", "buyer-country"),
                ),
                (
                    "notices with > 10 buyers",
                    sum(1 for n in latest if n.buyer.count > 10),
                ),
            ],
            ("check", "notices"),
        )
    )
    add("")
    add(f"## Snapshot preview (market metrics, {args.mode} universe)")
    add("")
    config = MetricsConfig(relevance_mode=RelevanceMode(args.mode))
    snapshot = compute_snapshot(notices, fx, config, today, taxonomy=taxonomy)
    m = snapshot.market
    p = m.process
    add(
        _table(
            [
                (
                    "new competitions 30d / previous",
                    f"{m.new_competitions_30d.value} / "
                    f"{m.new_competitions_30d.previous}",
                ),
                (
                    "estimated value 30d",
                    f"{format_eur(m.estimated_value_30d.value_eur)} "
                    f"(coverage {m.estimated_value_30d.coverage_pct}%)",
                ),
                (
                    "award value 30d",
                    f"{format_eur(m.award_value_30d.value_eur)} "
                    f"(coverage {m.award_value_30d.coverage_pct}%)",
                ),
                (
                    "top country 90d",
                    m.country_ranking_90d.leader.key
                    if m.country_ranking_90d.leader
                    else "n/a",
                ),
                (
                    "top category 90d",
                    m.category_ranking_90d.leader.label
                    if m.category_ranking_90d.leader
                    else "n/a",
                ),
                (
                    "median tenders 365d",
                    f"{p.median_tenders_365d.value} "
                    f"(n={p.median_tenders_365d.sample_size})",
                ),
                ("single-bid share 365d", f"{p.single_bid_share_365d.pct}%"),
                (
                    "median public time to result 365d",
                    f"{p.median_time_to_result_365d.value} days "
                    f"(n={p.median_time_to_result_365d.sample_size})",
                ),
                ("non-award share 365d", f"{p.non_award_share_365d.pct}%"),
                ("snapshot text", m.snapshot_text),
                ("country ranking text", m.country_ranking_text),
                ("external latest text", snapshot.external.latest_text),
                (
                    "top supplier 365d",
                    snapshot.suppliers.top_suppliers[0].name
                    if snapshot.suppliers.top_suppliers
                    else "n/a",
                ),
                ("supplier top-5 share", f"{snapshot.suppliers.top5_share_pct}%"),
            ],
            ("metric", "value"),
        )
    )
    add("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--mode", choices=["strict", "broad"], default="strict")
    parser.add_argument("--countries", default="", help="comma-separated alpha-2")
    parser.add_argument("--out", default="docs/data-profile.md")
    parser.add_argument("--cache", default=".cache/profile")
    parser.add_argument("--no-fetch", action="store_true", help="use cached pages")
    args = parser.parse_args()
    taxonomy = Taxonomy.load()
    raw_path, fx_path = _paths(args)
    if args.no_fetch and raw_path.exists() and fx_path.exists():
        raw = json.loads(raw_path.read_text())
        fx = FxRateTable.from_dict(json.loads(fx_path.read_text()))
    else:
        raw, fx = asyncio.run(fetch(args, taxonomy))
        raw_path.write_text(json.dumps(raw))
        fx_path.write_text(json.dumps(fx.to_dict()))
    report = profile(raw, fx, taxonomy, args)
    Path(args.out).write_text(report, encoding="utf-8")
    print(f"wrote {args.out} ({len(raw)} raw notices)", file=sys.stderr)


if __name__ == "__main__":
    main()

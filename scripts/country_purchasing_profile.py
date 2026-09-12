"""Phase 2 data profile: can TED result notices answer "which countries buy most?"

Usage:
    PYTHONPATH=. uv run python scripts/country_purchasing_profile.py \
        --days 760 --mode strict --out docs/country-purchasing-data-profile.md

Reuses the raw page cache of ``scripts/data_profile.py`` (``--no-fetch`` reads
it without touching the API). The report answers the questions in the Phase 2
plan §12: award-value coverage, buyer-country coverage, currencies, framework
behaviour, versions/duplicates, lots, joint procurement, award dates and the
largest values with their plausibility flags. Only aggregates and public
notice identifiers are written.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from custom_components.edp_radar.const import to_alpha2
from custom_components.edp_radar.fx_rates import FxRateTable
from custom_components.edp_radar.lifecycle import ProcedureIndex
from custom_components.edp_radar.metrics import (
    MetricsConfig,
    format_eur,
    relevant_notices,
    value_in_eur,
)
from custom_components.edp_radar.models import (
    AWARD_DATE_BASIS_DECISION,
    Money,
    NoticeStage,
    ProcurementNotice,
)
from custom_components.edp_radar.normalizer import as_strings, normalize_many
from custom_components.edp_radar.purchasing import (
    ResultKind,
    attribute_country,
    build_purchasing_model,
    classify_result,
    extract_awarded_value,
)
from custom_components.edp_radar.taxonomy import Taxonomy
from scripts.data_profile import _paths, _pct, _table, fetch

type Raw = list[dict[str, Any]]

FINDINGS = """\
## Findings and decisions (reviewed 2026-09-12)

The tables below are regenerated from the cache; this section is the human
reading of them (Phase 2 plan §12, §31, §35 step 1) and the decisions it led
to. Decision numbers (P1 …) are referenced from code comments and the README.

**What the data can answer.** 47 934 notices over 760 days contain 21 289
result notices, 19 239 of them awarded. 5 924 awarded results (31 %) are
framework agreements; of the remaining 13 315, 12 167 (91 %) carry a positive
Notice Value and 99.2 % of those convert to EUR. Buyer country is present on
every result. So "which country reported the highest awarded value" can be
answered — for the reported part of the market, which differs a lot by country.

**Coverage is the headline caveat.** Poland, Estonia, Spain and Czechia report
a value on ~99 % of non-framework awards. Germany reports one on 34 % and buys
mostly through frameworks (1 074 of 2 519 awarded results), so only 19 % of
its awards carry a usable value; France (30 %) and Romania (22 %) are
framework-heavy too. Germany's rank therefore understates it materially, and
the ranking must always be read with the coverage column, which every sensor
carries (P10 semantics: awards without a usable value are *unknown*, never 0).

**Framework Notice Values are not awards (P2).** Where both exist, the Notice
Value of a framework result is below the framework maximum in 82 % of cases
and equal to it in 12 %; the largest ones are the framework's estimate
(FR PL6T trucks EUR 2.4bn), a ceiling with tiny tender values (HR electricity
EUR 1.5bn) or the same framework re-reported in every call-off notice (RO
transport platforms, four notices of RON 2.3–3.4bn). No consistent "actually
awarded" amount exists at notice level, so framework results count as awarded
results without a usable value, and the `framework_results` count is exposed
per country.

**Lots and tenders (P1).** `result-value-lot` is positive on six non-framework
results in two years, so there is nothing to fall back on. The sum of winning
tender values equals the Notice Value within 1 % on 84 % of valued results,
but exceeds it on 7.6 % (tender × lot repetition) — not a safe fallback, only
a plausibility reference (P6).

**Joint procurement is rare (P3).** Seven results in two years list buyers
from several countries (Nordic joint buys of ammunition, tools, wagons), EUR
9.7m of attributable value; they are kept once under `MULTI` and the European
total is attributable + `MULTI` (+ unknown-country), an identity the model
tests.

**Award dates (P4).** 47 % of awarded results carry a winner decision date;
74 % of those lie 0–60 days before publication, 4.7 % more than a year before
(framework call-offs quoting the original decision). The award date is the
decision date when it lies 0–365 days before publication, else the
publication date; the basis is stored per award and the mix differs by
country (Spain 97 % decision dates, Sweden 86 %, Germany 6 %).

**Duplicates (P7).** 92 procedures repeat one Notice Value in several original
result notices (EUR 386m beyond the first notice): DNS call-offs quoting the
system total, republished notices, identical lots. Only the earliest notice
counts; the rest are quarantined and listed.

**Unit errors are the dominant data-quality problem (P5, P6, P8, P9).** The
largest "award" in the sample is a diesel supply of PLN 1 086 150 000 000
(EUR 258bn); Portuguese leasing and trainer-aircraft awards are exactly 1 000×
their estimates; Polish cleaning, uniform and diagnostics awards are 1 000×
their own tender values. Deterministic rules quarantine a value that
contradicts its own procedure — above EUR 10bn (P5); more than 100× a real
estimate of the same procedure, or more than 100× the notice's own tender
values unless a real estimate corroborates it (P6); placeholders such as 1,
98 or 100 are never compared (P8). Rules cannot catch everything: the 2024
Polish food supply notices (EUR 2.9bn of sauces and tea, EUR 1.6bn of meat,
EUR 1.1bn of potatoes) have no estimate and equally inflated tender values, so
they stay counted — inside the *previous* 12 months — and every award of
EUR 250m or more that no real estimate corroborates is marked
`unverified_large` and summed per country (P9) so that a total can be read
together with how much of it rests on unverified records.

**Categories (P11).** One category per award from the main procedure CPV keeps
the split summing to 100 %; the unclassified share is exposed and dominates
most countries with the current CPV-only taxonomy (owner decision pending on
an "Infrastructure & facilities" category).

**Open for the owner.** (a) A documented domain cap for consumables (food,
cleaning, waste) would remove the remaining Polish 2024 unit errors but is a
judgement rule, not an internal contradiction — not implemented. (b) German
coverage cannot be improved from TED alone. (c) The taxonomy's unclassified
share.
"""


def _dec(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except Exception:  # profiling tolerates any junk value
        return None
    return parsed if parsed.is_finite() else None


def _decimals(value: Any) -> list[Decimal]:
    return [d for d in (_dec(v) for v in as_strings(value)) if d is not None]


def _title(raw: Mapping[str, Any]) -> str:
    title = raw.get("title-proc")
    if isinstance(title, Mapping):
        title = next(iter(title.values()), "")
    if isinstance(title, list):
        title = title[0] if title else ""
    return str(title or "").replace("|", "/")[:70]


def _bucket(value: Decimal, edges: Sequence[tuple[Decimal, str]], last: str) -> str:
    for edge, label in edges:
        if value <= edge:
            return label
    return last


def _counter_table(counter: Counter[str], header: tuple[str, str]) -> str:
    return _table(counter.most_common(), header)


class Profile:
    """All derived views over one raw sample, built once."""

    def __init__(
        self, raw: Raw, fx: FxRateTable, taxonomy: Taxonomy, today: date
    ) -> None:
        self.raw = raw
        self.fx = fx
        self.taxonomy = taxonomy
        self.today = today
        notices, self.parse_errors = normalize_many(raw, taxonomy)
        self.notices = notices
        self.relevant, self.excluded_cpb = relevant_notices(
            notices, MetricsConfig(), taxonomy
        )
        self.index = ProcedureIndex.build(self.relevant)
        self.results = self.index.results()
        self.raw_by_number = {r["publication-number"]: r for r in raw}
        self.kinds = {r.publication_number: classify_result(r) for r in self.results}
        self.awarded = [
            r
            for r in self.results
            if self.kinds[r.publication_number] is ResultKind.AWARDED
        ]
        self.frameworks = [r for r in self.awarded if r.is_framework]
        self.plain = [r for r in self.awarded if not r.is_framework]
        self.valued = [r for r in self.plain if r.result_value is not None]

    def raw_of(self, notice: ProcurementNotice) -> Mapping[str, Any]:
        return self.raw_by_number[notice.publication_number]

    def eur(self, notice: ProcurementNotice) -> Decimal | None:
        return value_in_eur(notice.result_value, notice.award_date, self.fx)

    def estimate(self, notice: ProcurementNotice) -> Money | None:
        """Estimated value from the notice itself, else its procedure."""
        if notice.estimated_value is not None:
            return notice.estimated_value
        key = notice.procedure_id or f"notice:{notice.notice_id}"
        summary = self.index.procedures.get(key)
        return summary.estimated_value if summary else None


# ------------------------------------------------------------------ sections


def section_volume(p: Profile) -> list[str]:
    months = sorted({n.publication_date.strftime("%Y-%m") for n in p.notices})
    kinds = Counter(k.value for k in p.kinds.values())
    return [
        "## Volume",
        "",
        _table(
            [
                ("raw notices returned", len(p.raw)),
                ("parse errors", p.parse_errors),
                ("months covered", f"{months[0]} … {months[-1]} ({len(months)})"),
                ("relevant notice versions (strict, CPB excluded)", len(p.relevant)),
                ("central-purchasing-only notices excluded", p.excluded_cpb),
                ("result notices (latest original version)", len(p.results)),
                *((f"… of kind `{k}`", v) for k, v in sorted(kinds.items())),
                ("awarded results that are framework agreements", len(p.frameworks)),
                ("awarded non-framework results", len(p.plain)),
                ("… with usable Notice Value", len(p.valued)),
            ],
            ("measure", "value"),
        ),
        "",
    ]


def section_by_country(p: Profile) -> list[str]:
    rows: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    for notice in p.results:
        country = attribute_country(notice) or "??"
        row = rows[country]
        kind = p.kinds[notice.publication_number]
        row[0] += 1
        if kind is not ResultKind.AWARDED:
            row[1] += 1
            continue
        if notice.is_framework:
            row[2] += 1
            continue
        row[3] += 1
        if notice.result_value is not None:
            row[4] += 1
            if p.eur(notice) is not None:
                row[5] += 1
    table = [
        (
            country,
            total,
            non_awarded,
            frameworks,
            plain,
            f"{valued} ({_pct(valued, plain)})",
            f"{_pct(valued, plain + frameworks)}",
            f"{_pct(eur, plain)}",
        )
        for country, (
            total,
            non_awarded,
            frameworks,
            plain,
            valued,
            eur,
        ) in sorted(rows.items(), key=lambda kv: -kv[1][0])
    ]
    return [
        "## Award notices and Notice Value coverage by country",
        "",
        "`valued` = awarded non-framework results with a positive Notice Value "
        "(BT-161). `coverage incl. FW` counts framework results as awarded "
        "without a usable value; `EUR` = share of non-framework awarded results "
        "convertible to EUR at the award date.",
        "",
        _table(
            table,
            (
                "country",
                "results",
                "non-awarded",
                "framework",
                "non-FW awarded",
                "valued (coverage)",
                "coverage incl. FW",
                "EUR",
            ),
        ),
        "",
    ]


def section_currencies(p: Profile) -> list[str]:
    currencies: Counter[str] = Counter()
    convertible: Counter[str] = Counter()
    value_by_currency: dict[str, Decimal] = defaultdict(Decimal)
    eur_total = Decimal(0)
    eur_converted = Decimal(0)
    for notice in p.valued:
        money = notice.result_value
        assert money is not None
        currencies[money.currency] += 1
        value_by_currency[money.currency] += money.amount
        eur = p.eur(notice)
        if eur is not None:
            convertible[money.currency] += 1
            eur_converted += eur
            eur_total += eur
    rows = [
        (
            currency,
            count,
            f"{convertible[currency]} ({_pct(convertible[currency], count)})",
            f"{value_by_currency[currency]:,.0f}",
        )
        for currency, count in currencies.most_common()
    ]
    return [
        "## Currencies (awarded non-framework results with Notice Value)",
        "",
        _table(rows, ("currency", "results", "convertible to EUR", "sum (original)")),
        "",
        f"- EUR-convertible share of valued results: "
        f"{_pct(sum(convertible.values()), len(p.valued))}; converted total "
        f"{format_eur(eur_converted)} before the plausibility quarantine.",
        "",
    ]


def section_buyer_country(p: Profile) -> list[str]:
    counts: Counter[str] = Counter()
    multi_value = Decimal(0)
    multi_examples: list[tuple[Any, ...]] = []
    for notice in p.results:
        countries = notice.buyer.countries
        if not countries:
            counts["missing"] += 1
        elif len(countries) == 1:
            counts["exactly one"] += 1
        else:
            counts["several (MULTI)"] += 1
            eur = p.eur(notice) if not notice.is_framework else None
            if eur is not None:
                multi_value += eur
            multi_examples.append(
                (
                    notice.publication_number,
                    "/".join(countries),
                    notice.buyer.count,
                    format_eur(eur),
                    _title(p.raw_of(notice)),
                )
            )
    return [
        "## Buyer-country coverage and joint procurement",
        "",
        _table(
            sorted(counts.items()), ("distinct buyer countries per result", "results")
        ),
        "",
        f"- joint/multinational results: {counts['several (MULTI)']}, attributable "
        f"awarded value (non-framework, EUR-convertible) {format_eur(multi_value)}.",
        "- `buyer-country` arrays are flattened across buyers and not aligned with "
        "lots, so no lot-level split by country is possible; the value is kept "
        "once under `MULTI`.",
        "",
        _table(
            multi_examples,
            ("notice", "countries", "buyers", "awarded value", "title"),
        )
        if multi_examples
        else "(no multi-country results in the sample)",
        "",
    ]


def section_frameworks(p: Profile) -> list[str]:
    raw_fw = [p.raw_of(n) for n in p.frameworks]
    with_nv = [r for r in raw_fw if (_dec(r.get("result-value-notice")) or 0) > 0]
    with_max = [
        r
        for r in raw_fw
        if (_dec(r.get("result-framework-maximum-value-notice")) or 0) > 0
    ]
    both = [r for r in with_nv if r in with_max]
    ratio: Counter[str] = Counter()
    for r in both:
        nv = _dec(r["result-value-notice"])
        fm = _dec(r["result-framework-maximum-value-notice"])
        assert nv is not None and fm is not None
        ratio[
            _bucket(
                nv / fm,
                [
                    (Decimal("0.5"), "< 0.5"),
                    (Decimal("0.99"), "0.5 – 0.99"),
                    (Decimal("1.01"), "= 1"),
                    (Decimal("2"), "1 – 2"),
                    (Decimal("10"), "2 – 10"),
                ],
                "> 10",
            )
        ] += 1
    tender_positive = sum(
        1 for r in raw_fw if any(v > 0 for v in _decimals(r.get("tender-value")))
    )
    tender_zero = sum(
        1
        for r in raw_fw
        if r.get("tender-value")
        and all(v <= 0 for v in _decimals(r.get("tender-value")))
    )
    top = sorted(
        (
            (Decimal(r["result-value-notice"]), r)
            for r in with_nv
            if r.get("result-value-cur-notice")
        ),
        key=lambda item: -item[0],
    )[:8]
    examples = [
        (
            r["publication-number"],
            to_alpha2(as_strings(r.get("buyer-country"))[0]),
            f"{value:,.0f} {r.get('result-value-cur-notice')}",
            (
                f"{_dec(r.get('result-framework-maximum-value-notice')):,.0f}"
                if r.get("result-framework-maximum-value-notice")
                else "—"
            ),
            len(_decimals(r.get("tender-value"))),
            _title(r),
        )
        for value, r in top
    ]
    return [
        "## Framework agreements",
        "",
        _table(
            [
                ("awarded framework results", len(p.frameworks)),
                ("… with a positive Notice Value (BT-161)", len(with_nv)),
                ("… with a Framework Maximum Value (BT-118)", len(with_max)),
                ("… with both", len(both)),
                ("… with at least one positive tender value", tender_positive),
                ("… with tender values all zero", tender_zero),
                (
                    "framework-agreement-lot values",
                    ", ".join(
                        f"{k}: {v}"
                        for k, v in Counter(
                            v
                            for r in raw_fw
                            for v in set(as_strings(r.get("framework-agreement-lot")))
                        ).most_common()
                    ),
                ),
            ],
            ("measure", "value"),
        ),
        "",
        "Notice Value ÷ Framework Maximum Value where both exist:",
        "",
        _table(sorted(ratio.items()), ("ratio", "results")),
        "",
        "Largest framework Notice Values (never counted as purchases):",
        "",
        _table(
            examples,
            (
                "notice",
                "country",
                "Notice Value",
                "framework max",
                "tender values",
                "title",
            ),
        ),
        "",
    ]


def section_versions(p: Profile) -> list[str]:
    all_results = [n for n in p.relevant if n.stage is NoticeStage.RESULT]
    versions = Counter(n.notice_version for n in all_results)
    ids = Counter(n.notice_id for n in all_results)
    republished = sum(1 for count in ids.values() if count > 1)
    changes = sum(1 for n in all_results if n.is_change)
    # Same procedure, same value, different original result notices.
    seen: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for notice in p.valued:
        money = notice.result_value
        assert money is not None
        key = (
            notice.procedure_id or f"notice:{notice.notice_id}",
            str(money.amount),
            money.currency,
        )
        seen[key].append(notice.publication_number)
    duplicates = {k: v for k, v in seen.items() if len(v) > 1}
    dup_value = Decimal(0)
    for numbers in duplicates.values():
        for number in numbers[1:]:
            notice = next(n for n in p.valued if n.publication_number == number)
            dup_value += p.eur(notice) or Decimal(0)
    return [
        "## Notice versions, republication and duplicate values",
        "",
        _table(
            [
                ("result notice versions stored", len(all_results)),
                *((f"version {v}", c) for v, c in sorted(versions.items())),
                ("result notice ids with more than one stored version", republished),
                ("result versions carrying change info (not originals)", changes),
                (
                    "procedures with one Notice Value in several original results",
                    len(duplicates),
                ),
                ("… repeated value beyond the first notice", format_eur(dup_value)),
            ],
            ("measure", "value"),
        ),
        "",
        "The store keeps every `(notice-identifier, notice-version)`; the lifecycle "
        "index uses the latest version per identifier and excludes change notices, "
        "so a republished result is counted once.",
        "",
    ]


def section_lots(p: Profile) -> list[str]:
    agreement: Counter[str] = Counter()
    for notice in p.valued:
        raw = p.raw_of(notice)
        tenders = _decimals(raw.get("tender-value"))
        money = notice.result_value
        assert money is not None
        if not tenders:
            agreement["no tender values"] += 1
            continue
        total = sum(tenders)
        if total == 0:
            agreement["tender values all zero"] += 1
        elif abs(total - money.amount) / money.amount < Decimal("0.01"):
            agreement["sum(tender-value) = Notice Value (±1 %)"] += 1
        elif total < money.amount:
            agreement["sum(tender-value) < Notice Value"] += 1
        else:
            agreement["sum(tender-value) > Notice Value"] += 1
    missing = [n for n in p.plain if n.result_value is None]
    missing_tender = sum(
        1
        for n in missing
        if (t := _decimals(p.raw_of(n).get("tender-value"))) and all(v > 0 for v in t)
    )
    lot_positive = sum(
        1
        for n in p.plain
        if any(v > 0 for v in _decimals(p.raw_of(n).get("result-value-lot")))
    )
    return [
        "## Lot behaviour",
        "",
        _table(
            [
                ("awarded non-framework results without Notice Value", len(missing)),
                ("… where every tender value is positive", missing_tender),
                (
                    "non-framework results with a positive `result-value-lot`",
                    lot_positive,
                ),
            ],
            ("measure", "value"),
        ),
        "",
        "Notice Value versus the sum of `tender-value` (BT-720) on the same notice:",
        "",
        _counter_table(agreement, ("relation", "results")),
        "",
        "Notice Value already represents the notice total; tender values disagree "
        "upwards often enough that summing them is not a safe fallback.",
        "",
    ]


def section_award_dates(p: Profile) -> list[str]:
    basis = Counter(n.award_date_basis for n in p.awarded)
    lag: Counter[str] = Counter()
    by_country: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for notice in p.awarded:
        country = attribute_country(notice) or "??"
        by_country[country][0] += 1
        if notice.award_date_basis == AWARD_DATE_BASIS_DECISION:
            by_country[country][1] += 1
        stats = notice.tender_statistics
        if stats and stats.decision_dates:
            days = (notice.publication_date - min(stats.decision_dates)).days
            lag[
                _bucket(
                    Decimal(days),
                    [
                        (Decimal(-1), "< 0"),
                        (Decimal(30), "0 – 30"),
                        (Decimal(60), "31 – 60"),
                        (Decimal(90), "61 – 90"),
                        (Decimal(180), "91 – 180"),
                        (Decimal(365), "181 – 365"),
                    ],
                    "> 365",
                )
            ] += 1
    rows = [
        (country, total, f"{decided} ({_pct(decided, total)})")
        for country, (total, decided) in sorted(
            by_country.items(), key=lambda kv: -kv[1][0]
        )
    ]
    return [
        "## Award-date coverage",
        "",
        _table(sorted(basis.items()), ("date basis used", "awarded results")),
        "",
        "Publication date minus earliest `winner-decision-date`, where present:",
        "",
        _table(sorted(lag.items()), ("lag (days)", "results")),
        "",
        "Decision-date basis by country:",
        "",
        _table(rows, ("country", "awarded results", "on decision-date basis")),
        "",
    ]


def section_procedure_types(p: Profile) -> list[str]:
    types = Counter(n.procedure_type or "(none)" for n in p.awarded)
    return [
        "## Procedure types among awarded results",
        "",
        "All of these count as purchases (plan §32); `neg-wo-call` is a direct award.",
        "",
        _counter_table(types, ("procedure-type", "awarded results")),
        "",
    ]


def section_largest(p: Profile, limit: int = 50) -> list[str]:
    rows: list[tuple[Any, ...]] = []
    flagged: Counter[str] = Counter()
    valued = sorted(
        ((p.eur(n), n) for n in p.valued),
        key=lambda item: -(item[0] or Decimal(0)),
    )
    for eur, notice in valued:
        if eur is None:
            continue
        estimate = p.estimate(notice)
        value = extract_awarded_value(notice, p.fx, estimate=estimate)
        money = notice.result_value
        assert money is not None
        for flag in value.flags:
            flagged[flag] += 1
        if len(rows) < limit:
            rows.append(
                (
                    len(rows) + 1,
                    f"[{notice.publication_number}]({notice.source_url})",
                    attribute_country(notice) or "??",
                    format_eur(eur),
                    f"{money.amount:,.0f} {money.currency}",
                    f"{estimate.amount:,.0f} {estimate.currency}" if estimate else "—",
                    (
                        f"{notice.tender_value_total.amount:,.0f}"
                        if notice.tender_value_total
                        else "—"
                    ),
                    ", ".join(value.flags),
                    _title(p.raw_of(notice)),
                )
            )
    return [
        f"## Largest {limit} awarded values (non-framework, EUR at award date)",
        "",
        "Quarantine flags (`above_absolute_cap`, `exceeds_estimate`, "
        "`exceeds_tender_values`, `duplicate_value_in_procedure`) exclude a value "
        "from every total; `unverified_large` keeps it but marks that no real "
        "estimate corroborates an award of EUR 250m or more.",
        "",
        _table(
            rows,
            (
                "#",
                "notice",
                "country",
                "EUR",
                "original",
                "estimate",
                "Σ tenders",
                "flags",
                "title",
            ),
        ),
        "",
        "Flags over all valued non-framework awards (duplicates are detected in "
        "the model, see below):",
        "",
        _table(
            [*sorted(flagged.items()), ("total valued results", len(p.valued))],
            ("flag", "results"),
        ),
        "",
    ]


def section_model(p: Profile) -> list[str]:
    model = build_purchasing_model(
        p.relevant, p.fx, p.today, taxonomy=p.taxonomy, index=p.index
    )
    period = model.primary
    rows = [
        (
            entry.rank,
            entry.country,
            format_eur(entry.summary.award_value_eur),
            f"{entry.share_pct}%" if entry.share_pct is not None else "—",
            (
                f"{entry.summary.change_pct:+.1f}%"
                if entry.summary.change_pct is not None
                else "—"
            ),
            entry.summary.award_count,
            (
                f"{entry.summary.value_coverage_pct}%"
                if entry.summary.value_coverage_pct is not None
                else "—"
            ),
            entry.summary.framework_results,
            entry.summary.suspicious_results,
            (
                f"{entry.summary.unverified_large_results} / "
                f"{format_eur(entry.summary.unverified_large_value_eur)}"
                if entry.summary.unverified_large_results
                else "—"
            ),
            (
                entry.summary.top_categories[0].label
                if entry.summary.top_categories
                else "—"
            ),
        )
        for entry in period.ranking
    ]
    unranked = [
        (
            country,
            period.countries[country].award_count,
            period.countries[country].framework_results,
        )
        for country in period.unranked
    ]
    europe = period.europe
    attributable = sum(
        (e.summary.award_value_eur or Decimal(0)) for e in period.ranking
    )
    identity = attributable + (europe.joint_value_eur or Decimal(0))
    identity += europe.unknown_country_value_eur or Decimal(0)
    growth = [
        (
            e.rank,
            e.country,
            f"{e.summary.change_pct:+.1f}%",
            format_eur(e.summary.award_value_eur),
        )
        for e in period.growth[:10]
    ]
    quarantined = [
        (
            f"[{a.publication_number}]({a.source_url})",
            a.country or "??",
            format_eur(a.value_eur),
            f"{a.amount:,.0f} {a.currency}" if a.amount is not None else "—",
            ", ".join(a.flags),
            (a.title or "").replace("|", "/")[:60],
        )
        for a in model.quarantined
    ]
    return [
        "## Model preview: rolling 12 months (purchasing model, strict universe)",
        "",
        f"Period: {period.window.start.isoformat()} < award date ≤ "
        f"{period.window.end.isoformat()}; previous period of equal length.",
        "",
        _table(
            rows,
            (
                "rank",
                "country",
                "awarded 12m",
                "share",
                "vs previous 12m",
                "awards",
                "value coverage",
                "framework results",
                "quarantined",
                "unverified large",
                "top category",
            ),
        ),
        "",
        (
            _table(
                unranked,
                ("country without usable value", "awarded", "framework results"),
            )
            if unranked
            else "(every active country has at least one usable value)"
        ),
        "",
        _table(
            [
                ("European total 12m", format_eur(europe.total_value_eur)),
                ("country-attributable", format_eur(europe.attributable_value_eur)),
                ("joint/multinational (MULTI)", format_eur(europe.joint_value_eur)),
                (
                    "unknown buyer country",
                    format_eur(europe.unknown_country_value_eur),
                ),
                ("previous 12m total", format_eur(europe.previous_total_value_eur)),
                (
                    "awarded results / with usable value",
                    f"{europe.award_count} / {europe.valued_awards}",
                ),
                ("countries with attributable value", europe.countries_with_value),
                ("countries active", europe.countries_active),
                ("quarantined results (excluded, listed)", europe.suspicious_results),
                (
                    "identity: Σ ranked countries + MULTI + unknown = total",
                    "OK" if identity == (europe.total_value_eur or 0) else "MISMATCH",
                ),
            ],
            ("measure", "value"),
        ),
        "",
        "Fastest-growing eligible countries (≥ 5 valued awards or ≥ EUR 50m now):",
        "",
        (
            _table(growth, ("rank", "country", "change", "awarded 12m"))
            if growth
            else "(none)"
        ),
        "",
        "Quarantined awards (all stored periods):",
        "",
        _table(quarantined, ("notice", "country", "EUR", "original", "flags", "title"))
        if quarantined
        else "(none)",
        "",
    ]


def build_report(p: Profile, args: argparse.Namespace) -> str:
    lines = [
        f"# Country purchasing data profile — {args.mode} mode, last {args.days} days",
        "",
        f"Generated {datetime.now(UTC).isoformat(timespec='seconds')} by "
        f"`scripts/country_purchasing_profile.py` (taxonomy {p.taxonomy.version}). "
        f"Countries: {args.countries or 'all'}. Reference date {p.today.isoformat()}.",
        "",
        "**Definition of a purchase (plan §4):** the Notice Value (BT-161) of an "
        "awarded, non-framework result notice, counted once per notice and "
        "converted to EUR at the award date. Framework ceilings, estimates, "
        "non-awarded procedures and quarantined implausible values are not "
        "purchases.",
        "",
        FINDINGS,
    ]
    for section in (
        section_volume,
        section_by_country,
        section_currencies,
        section_buyer_country,
        section_frameworks,
        section_versions,
        section_lots,
        section_award_dates,
        section_procedure_types,
        section_largest,
        section_model,
    ):
        lines.extend(section(p))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--days", type=int, default=760)
    parser.add_argument("--mode", choices=["strict", "broad"], default="strict")
    parser.add_argument("--countries", default="", help="comma-separated alpha-2")
    parser.add_argument("--out", default="docs/country-purchasing-data-profile.md")
    parser.add_argument("--cache", default=".cache/profile")
    parser.add_argument("--no-fetch", action="store_true", help="use cached pages")
    args = parser.parse_args()
    taxonomy = Taxonomy.load()
    raw_path, fx_path = _paths(args)
    if args.no_fetch and raw_path.exists() and fx_path.exists():
        raw: Raw = json.loads(raw_path.read_text())
        fx = FxRateTable.from_dict(json.loads(fx_path.read_text()))
    else:
        raw, fx = asyncio.run(fetch(args, taxonomy))
        raw_path.write_text(json.dumps(raw))
        fx_path.write_text(json.dumps(fx.to_dict()))
    profile = Profile(raw, fx, taxonomy, date.today())
    Path(args.out).write_text(build_report(profile, args), encoding="utf-8")
    print(f"wrote {args.out} ({len(raw)} raw notices)", file=sys.stderr)


if __name__ == "__main__":
    main()

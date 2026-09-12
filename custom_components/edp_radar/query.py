"""Expert-search query builder for the TED Search API (plan §36, addendum §1)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from datetime import date

from .const import (
    DEFENCE_ACTIVITY_CODE,
    DEFENCE_LEGAL_BASIS_CODE,
    RelevanceMode,
    to_alpha3,
)

_TOKEN = re.compile(r"\w+", re.UNICODE)


class TedQueryBuilder:
    """Compose TED expert-search fragments. All methods are pure and return strings."""

    @staticmethod
    def quote(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    @staticmethod
    def ted_date(d: date) -> str:
        return d.strftime("%Y%m%d")

    @staticmethod
    def _group(part: str) -> str:
        if " " in part and not (part.startswith("(") and part.endswith(")")):
            return f"({part})"
        return part

    @classmethod
    def combine_and(cls, *parts: str) -> str:
        kept = [cls._group(p) for p in parts if p]
        return " AND ".join(kept)

    @classmethod
    def combine_or(cls, *parts: str) -> str:
        kept = [p for p in parts if p]
        if not kept:
            return ""
        if len(kept) == 1:
            return kept[0]
        return "(" + " OR ".join(kept) + ")"

    @classmethod
    def defence_universe(cls, mode: RelevanceMode, cpv_prefixes: Sequence[str]) -> str:
        signals = [
            f"authority-main-activity={DEFENCE_ACTIVITY_CODE}",
            f"legal-basis={DEFENCE_LEGAL_BASIS_CODE}",
        ]
        if mode is RelevanceMode.BROAD and cpv_prefixes:
            wildcards = " ".join(f"{p}*" for p in cpv_prefixes)
            signals.append(f"classification-cpv IN ({wildcards})")
        return "(" + " OR ".join(signals) + ")"

    @classmethod
    def publication_range(cls, start: date, end: date | None = None) -> str:
        lower = f"PD>={cls.ted_date(start)}"
        if end is None:
            return lower
        return f"({lower} AND PD<={cls.ted_date(end)})"

    @staticmethod
    def countries(alpha2: Iterable[str]) -> str:
        codes = sorted({to_alpha3(c) for c in alpha2})
        if not codes:
            return ""
        return f"buyer-country IN ({' '.join(codes)})"

    @classmethod
    def buyer_identifiers(cls, identifiers: Iterable[str]) -> str:
        quoted = [cls.quote(i) for i in identifiers if i]
        if not quoted:
            return ""
        return f"buyer-identifier IN ({' '.join(quoted)})"

    @staticmethod
    def buyer_name_search(term: str) -> str:
        """Full-text prefix search: one wildcard token per word.

        Verified 2026-09-12: a quoted phrase combined with ``*`` never matches,
        while unquoted ``försvarets* materiel*`` does.
        """
        tokens = [f"{t}*" for t in _TOKEN.findall(term)]
        if not tokens:
            return ""
        return f"buyer-name ~ ({' '.join(tokens)})"

    @classmethod
    def publication_number(cls, number: str) -> str:
        return f"ND={cls.quote(number)}"

    @staticmethod
    def sort_by_publication_date(query: str, *, descending: bool = True) -> str:
        direction = "DESC" if descending else "ASC"
        return f"{query} SORT BY publication-date {direction}"

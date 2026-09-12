"""Defence relevance signals and strategic-category classification (plan §5–6, §14)."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from .const import (
    DEFENCE_ACTIVITY_CODE,
    DEFENCE_LEGAL_BASIS_CODE,
    MATCH_DEFENCE_BUYER,
    MATCH_DEFENCE_CPV,
    MATCH_DEFENCE_LEGAL_BASIS,
    RelevanceMode,
)

_DATA_DIR = Path(__file__).parent / "data"
_CPV = re.compile(r"^(\d{8})(?:-\d)?$")
STRICT_REASONS = frozenset({MATCH_DEFENCE_BUYER, MATCH_DEFENCE_LEGAL_BASIS})


def normalize_cpv(code: str) -> str | None:
    """Return the 8-digit CPV code without check digit, or None."""
    match = _CPV.match(code.strip())
    return match.group(1) if match else None


@dataclass(frozen=True)
class CategoryRule:
    category_id: str
    label: str
    cpv_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class Taxonomy:
    version: str
    defence_cpv_prefixes: tuple[str, ...]
    rules: tuple[CategoryRule, ...]

    @classmethod
    def load(cls) -> Taxonomy:
        """Load the versioned JSON rules shipped with the integration (cached)."""
        return _load()

    @property
    def category_ids(self) -> tuple[str, ...]:
        return tuple(r.category_id for r in self.rules)

    def label(self, category_id: str) -> str:
        for rule in self.rules:
            if rule.category_id == category_id:
                return rule.label
        return category_id

    def is_defence_cpv(self, code: str) -> bool:
        normalized = normalize_cpv(code)
        return normalized is not None and normalized.startswith(
            self.defence_cpv_prefixes
        )

    def match_reasons(
        self,
        *,
        activities: Iterable[str],
        legal_basis: Iterable[str],
        cpv_codes: Iterable[str],
    ) -> frozenset[str]:
        """Every defence signal that matches, independent of the configured mode."""
        reasons: set[str] = set()
        if DEFENCE_ACTIVITY_CODE in set(activities):
            reasons.add(MATCH_DEFENCE_BUYER)
        if DEFENCE_LEGAL_BASIS_CODE in set(legal_basis):
            reasons.add(MATCH_DEFENCE_LEGAL_BASIS)
        if any(self.is_defence_cpv(code) for code in cpv_codes):
            reasons.add(MATCH_DEFENCE_CPV)
        return frozenset(reasons)

    @staticmethod
    def is_relevant(reasons: frozenset[str], mode: RelevanceMode) -> bool:
        if mode is RelevanceMode.STRICT:
            return bool(reasons & STRICT_REASONS)
        return bool(reasons)

    def classify(self, cpv_codes: Iterable[str]) -> tuple[str, ...]:
        """Assign each code to the category with the longest matching prefix."""
        categories: set[str] = set()
        for raw in cpv_codes:
            code = normalize_cpv(raw)
            if code is None:
                continue
            best: tuple[int, str] | None = None
            for rule in self.rules:
                for prefix in rule.cpv_prefixes:
                    if code.startswith(prefix) and (
                        best is None or len(prefix) > best[0]
                    ):
                        best = (len(prefix), rule.category_id)
            if best is not None:
                categories.add(best[1])
        return tuple(sorted(categories))


@cache
def _load() -> Taxonomy:
    defence = json.loads((_DATA_DIR / "defence_cpv.json").read_text(encoding="utf-8"))
    categories = json.loads(
        (_DATA_DIR / "strategic_categories.json").read_text(encoding="utf-8")
    )
    rules = tuple(
        CategoryRule(c["id"], c["label"], tuple(c["cpv_prefixes"]))
        for c in categories["categories"]
    )
    version = f"{defence['version']}/{categories['version']}"
    return Taxonomy(version, tuple(p["prefix"] for p in defence["prefixes"]), rules)

"""Plain-dict views of the country purchasing model for entity attributes and
action responses (Phase 2 §18–§22, §29). No Home Assistant imports."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .const import PURCHASING_RANKING_LIMIT, country_name
from .periods import pct
from .purchasing import (
    Award,
    CountryPurchaseSummary,
    CountryRank,
    EuropeSummary,
    MonthlyValue,
    PurchasingPeriod,
)


def eur(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def monthly_attrs(series: tuple[MonthlyValue, ...]) -> list[dict[str, Any]]:
    return [
        {
            "month": m.month,
            "value_eur": eur(m.value_eur),
            "awards": m.awards,
            "valued_awards": m.valued_awards,
        }
        for m in series
    ]


def largest_attrs(
    awards: tuple[Award, ...], summary: CountryPurchaseSummary | EuropeSummary | None
) -> dict[str, Any]:
    attrs: dict[str, Any] = award_attrs(awards[0]) if awards else {}
    attrs["largest_awards"] = [award_attrs(a) for a in awards]
    if summary is not None:
        attrs.update(period_attrs(summary))
    return attrs


def award_attrs(award: Award) -> dict[str, Any]:
    return {
        "publication_number": award.publication_number,
        "title": award.title,
        "buyer": award.buyer,
        "country": award.country,
        "award_date": award.date.isoformat(),
        "award_date_basis": award.date_basis,
        "value": eur(award.amount),
        "currency": award.currency,
        "value_eur": eur(award.value_eur),
        "category": award.primary_category,
        "categories": list(award.categories),
        "flags": list(award.flags),
        "ted_url": award.source_url,
    }


def period_attrs(summary: CountryPurchaseSummary | EuropeSummary) -> dict[str, Any]:
    return {
        "period_days": summary.window.days,
        "period_start": summary.window.start.isoformat(),
        "period_end": summary.window.end.isoformat(),
    }


def summary_attrs(summary: CountryPurchaseSummary) -> dict[str, Any]:
    """Every count behind a country's awarded value (Phase 2 §15, §29)."""
    return {
        "country": summary.country,
        **period_attrs(summary),
        "awarded_value_eur": eur(summary.award_value_eur),
        "previous_period_eur": eur(summary.previous_value_eur),
        "change_eur": eur(summary.change_eur),
        "change_pct": summary.change_pct,
        "awards": summary.award_count,
        "valued_awards": summary.valued_awards,
        "value_coverage_pct": summary.value_coverage_pct,
        "framework_results": summary.framework_results,
        "non_awarded_results": summary.non_awarded_results,
        "quarantined_results": summary.suspicious_results,
        "unconvertible_results": summary.unconvertible_results,
        "unverified_large_results": summary.unverified_large_results,
        "unverified_large_value_eur": eur(summary.unverified_large_value_eur),
        "decision_date_basis_pct": pct(
            summary.decision_date_awards, summary.award_count
        ),
    }


def categories_attrs(
    summary: CountryPurchaseSummary | EuropeSummary,
) -> dict[str, Any]:
    return {
        "categories": [
            {
                "category": share.category_id,
                "label": share.label,
                "value_eur": eur(share.value_eur),
                "share_pct": share.share_pct,
                "awards": share.awards,
            }
            for share in summary.top_categories
        ],
    }


def europe_attrs(europe: EuropeSummary) -> dict[str, Any]:
    return {
        **period_attrs(europe),
        "total_value_eur": eur(europe.total_value_eur),
        "country_attributable_eur": eur(europe.attributable_value_eur),
        "joint_multinational_eur": eur(europe.joint_value_eur),
        "unknown_country_eur": eur(europe.unknown_country_value_eur),
        "previous_period_eur": eur(europe.previous_total_value_eur),
        "change_pct": europe.change_pct,
        "awards": europe.award_count,
        "valued_awards": europe.valued_awards,
        "value_coverage_pct": europe.value_coverage_pct,
        "framework_results": europe.framework_results,
        "non_awarded_results": europe.non_awarded_results,
        "quarantined_results": europe.suspicious_results,
        "unverified_large_results": europe.unverified_large_results,
        "countries_with_value": europe.countries_with_value,
        "countries_active": europe.countries_active,
    }


def rank_row(entry: CountryRank, my_country: str | None) -> dict[str, Any]:
    summary = entry.summary
    return {
        "rank": entry.rank,
        "country": entry.country,
        "name": country_name(entry.country),
        "value_eur": eur(summary.award_value_eur),
        "share_pct": entry.share_pct,
        "previous_value_eur": eur(summary.previous_value_eur),
        "change_pct": summary.change_pct,
        "awards": summary.award_count,
        "valued_awards": summary.valued_awards,
        "value_coverage_pct": summary.value_coverage_pct,
        "framework_results": summary.framework_results,
        "quarantined_results": summary.suspicious_results,
        "unverified_large_results": summary.unverified_large_results,
        "top_category": (
            summary.top_categories[0].label if summary.top_categories else None
        ),
        "is_my_country": entry.country == my_country,
    }


def ranking_rows(
    period: PurchasingPeriod, my_country: str | None
) -> list[dict[str, Any]]:
    """Top N plus My country even when it ranks lower (Phase 2 §18)."""
    rows = list(period.ranking[:PURCHASING_RANKING_LIMIT])
    mine = period.rank_of(my_country) if my_country else None
    if mine is not None and mine not in rows:
        rows.append(mine)
    return [rank_row(entry, my_country) for entry in rows]


def country_ranking_attrs(
    period: PurchasingPeriod, my_country: str | None
) -> dict[str, Any]:
    mine = period.rank_of(my_country) if my_country else None
    return {
        **period_attrs(period.europe),
        "ranking": ranking_rows(period, my_country),
        "all_countries": [
            {
                "rank": e.rank,
                "country": e.country,
                "value_eur": eur(e.summary.award_value_eur),
                "share_pct": e.share_pct,
                "value_coverage_pct": e.summary.value_coverage_pct,
            }
            for e in period.ranking
        ],
        "unranked": [
            {
                "country": country,
                "awards": period.countries[country].award_count,
                "framework_results": period.countries[country].framework_results,
            }
            for country in period.unranked
        ],
        "my_country": rank_row(mine, my_country) if mine else None,
        "population_size": len(period.ranking),
        "countries_active": period.europe.countries_active,
        "total_value_eur": eur(period.europe.total_value_eur),
    }


def growth_attrs(period: PurchasingPeriod, my_country: str | None) -> dict[str, Any]:
    return {
        **period_attrs(period.europe),
        "ranking": [
            rank_row(entry, my_country)
            for entry in period.growth[:PURCHASING_RANKING_LIMIT]
        ],
        "population_size": len(period.growth),
        "eligibility": "at least 5 valued awards or EUR 50m awarded in the period",
    }

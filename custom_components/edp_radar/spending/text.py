"""Compact factual text for the two spending text sensors (plan §76).

Facts, source and period only — no interpretation. ``format_amount`` takes
whole currency units (what the entities expose), not source millions.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .calculations import Ranking, YtdChange
from .models import DatapointStatus


def _round(value: Decimal, decimals: int) -> str:
    """``value`` rounded half-up to ``decimals`` places, as a plain string."""
    quantum = Decimal(1).scaleb(-decimals)
    return str(value.quantize(quantum, rounding=ROUND_HALF_UP))


def _pct_text(value: Decimal, *, signed: bool) -> str:
    """One decimal, half-up; ``signed`` renders an explicit sign (``+0.0%`` at zero)."""
    if not signed:
        return f"{_round(value, 1)}%"
    sign = "-" if value < 0 else "+"
    return f"{sign}{_round(abs(value), 1)}%"


def format_amount(currency: str, amount: Decimal | None) -> str:
    """``"SEK 48.2bn"`` — the magnitude thresholds of ``periods.format_eur``,
    rounded half-up in ``Decimal`` for any currency."""
    if amount is None:
        return f"{currency} n/a"
    if amount >= Decimal("1e9"):
        return f"{currency} {_round(amount / Decimal(10**9), 1)}bn"
    if amount >= Decimal("1e7"):
        return f"{currency} {_round(amount / Decimal(10**6), 0)}m"
    if amount >= Decimal("1e6"):
        return f"{currency} {_round(amount / Decimal(10**6), 1)}m"
    if amount >= Decimal("1e3"):
        return f"{currency} {_round(amount / Decimal(10**3), 0)}k"
    return f"{currency} {_round(amount, 0)}"


def _yoy(pct: Decimal | None) -> str:
    return "YoY n/a" if pct is None else f"{_pct_text(pct, signed=True)} YoY"


def statskontoret_snapshot_text(
    ytd: YtdChange | None, through_label: str | None
) -> str | None:
    """``Materiel YTD SEK 48.2bn · +31% YoY · Statskontoret · through Aug 2026``."""
    if ytd is None or through_label is None:
        return None
    amount = format_amount("SEK", ytd.current * 1_000_000)
    return (
        f"Materiel YTD {amount} · {_yoy(ytd.pct)} · "
        f"Statskontoret · through {through_label}"
    )


def nato_position_text(
    ranking: Ranking | None,
    usd: Decimal | None,
    pct_gdp: Decimal | None,
    reference_year: int | None,
    status: DatapointStatus | None,
) -> str | None:
    """``SE #7 of 31 · USD 24.2bn · 3.2% GDP · NATO 2026 estimate``."""
    if ranking is None or reference_year is None or status is None:
        return None
    share = "n/a" if pct_gdp is None else _pct_text(pct_gdp, signed=False)
    return (
        f"SE #{ranking.focus_rank} of {ranking.population} · "
        f"{format_amount('USD', usd)} · {share} GDP · "
        f"NATO {reference_year} {status.value}"
    )

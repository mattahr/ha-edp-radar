"""Rolling periods and small numeric helpers shared by the metric engines.

Imports nothing from Home Assistant and nothing from ``metrics``/``purchasing``
so both can use it without cycles.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from .fx_rates import FxRateTable
from .models import Money


@dataclass(frozen=True)
class Window:
    """Half-open rolling period: start < d <= end (plan §15)."""

    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    def contains(self, d: date) -> bool:
        return self.start < d <= self.end


def current_window(today: date, days: int) -> Window:
    return Window(today - timedelta(days=days), today)


def previous_window(today: date, days: int) -> Window:
    return Window(today - timedelta(days=2 * days), today - timedelta(days=days))


def pct_change(
    current: Decimal | int | None, previous: Decimal | int | None
) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    change = (Decimal(current) - Decimal(previous)) / Decimal(previous) * 100
    return round(float(change), 1)


def pct(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 1)


def median(values: Sequence[float | int]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def value_in_eur(money: Money | None, on: date, fx: FxRateTable) -> Decimal | None:
    if money is None:
        return None
    conversion = fx.convert_to_eur(money, on)
    return conversion.eur_amount if conversion else None


def format_eur(amount: Decimal | None) -> str:
    if amount is None:
        return "EUR n/a"
    value = float(amount)
    if value >= 1e9:
        return f"EUR {value / 1e9:.1f}bn"
    if value >= 1e7:
        return f"EUR {value / 1e6:.0f}m"
    if value >= 1e6:
        return f"EUR {value / 1e6:.1f}m"
    if value >= 1e3:
        return f"EUR {value / 1e3:.0f}k"
    return f"EUR {value:.0f}"

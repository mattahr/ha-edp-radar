"""Spending providers in plan order (plan §69)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from .base import SpendingProvider
from .eda import EdaProvider
from .eurostat import EurostatProvider
from .nato import NatoProvider
from .sipri import SipriProvider
from .statskontoret import StatskontoretProvider


def all_providers(
    *, today: Callable[[], date] | None = None
) -> tuple[SpendingProvider, ...]:
    """Statskontoret, Eurostat, NATO, EDA, SIPRI (registry.SOURCE_ORDER).

    ``today`` lets Home Assistant supply its own clock (``dt_util``); scripts
    fall back to ``date.today``.
    """
    return (
        StatskontoretProvider(today=today or date.today),
        EurostatProvider(),
        NatoProvider(),
        EdaProvider(),
        SipriProvider(),
    )

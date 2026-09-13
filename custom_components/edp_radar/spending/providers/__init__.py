"""Spending providers in plan order (plan §69)."""

from __future__ import annotations

from .base import SpendingProvider
from .eda import EdaProvider
from .eurostat import EurostatProvider
from .nato import NatoProvider
from .sipri import SipriProvider
from .statskontoret import StatskontoretProvider


def all_providers() -> tuple[SpendingProvider, ...]:
    """Statskontoret, Eurostat, NATO, EDA, SIPRI (registry.SOURCE_ORDER)."""
    return (
        StatskontoretProvider(),
        EurostatProvider(),
        NatoProvider(),
        EdaProvider(),
        SipriProvider(),
    )

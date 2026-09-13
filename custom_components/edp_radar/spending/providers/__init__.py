"""Spending providers; ``all_providers`` is filled in as providers land."""

from __future__ import annotations

from .base import SpendingProvider
from .eda import EdaProvider
from .eurostat import EurostatProvider
from .nato import NatoProvider
from .statskontoret import StatskontoretProvider


def all_providers() -> tuple[SpendingProvider, ...]:
    """Providers in plan order (Statskontoret, Eurostat, NATO, EDA, SIPRI)."""
    return (StatskontoretProvider(), EurostatProvider(), NatoProvider(), EdaProvider())

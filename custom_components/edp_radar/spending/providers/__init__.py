"""Spending providers; ``all_providers`` is filled in as providers land."""

from __future__ import annotations

from .base import SpendingProvider


def all_providers() -> tuple[SpendingProvider, ...]:
    """Providers in plan order (Statskontoret, Eurostat, NATO, EDA, SIPRI)."""
    return ()

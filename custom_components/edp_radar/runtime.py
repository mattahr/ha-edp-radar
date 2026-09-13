"""Per-entry runtime objects (S1)."""

from __future__ import annotations

from dataclasses import dataclass

from .coordinator import EdpRadarCoordinator
from .spending.coordinator import SpendingCoordinator


@dataclass(slots=True)
class RuntimeData:
    radar: EdpRadarCoordinator
    spending: SpendingCoordinator

"""Shared pytest fixtures."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from custom_components.edp_radar.const import TED_API_BASE_URL

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def real_notices() -> list[dict[str, Any]]:
    """Real TED notices captured 2026-09-12 (see scripts/fetch_fixture_notices.py)."""
    return json.loads((FIXTURES / "ted" / "real_notices.json").read_text())


@pytest.fixture
def real_notice(
    real_notices: list[dict[str, Any]],
) -> Callable[[str], dict[str, Any]]:
    """Return a lookup by publication number (deep-copied per call)."""
    by_number = {n["publication-number"]: n for n in real_notices}

    def _get(publication_number: str) -> dict[str, Any]:
        return json.loads(json.dumps(by_number[publication_number]))

    return _get


TED_SEARCH_URL = f"{TED_API_BASE_URL}/notices/search"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of custom_components in every test."""

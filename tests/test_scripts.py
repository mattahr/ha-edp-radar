"""Smoke tests for the developer scripts (importable, pure helpers)."""

from __future__ import annotations

from datetime import date

from scripts.spending_profile import _reference_age_text, _table


def test_table_renders_empty_cell_as_em_dash() -> None:
    assert "| a | — |" in _table([("a", "")], ("x", "y"))


def test_reference_age_text_none() -> None:
    assert _reference_age_text(None, date(2026, 9, 13)) == "reference age n/a"


def test_reference_age_text_not_yet_complete() -> None:
    text = _reference_age_text(date(2026, 12, 31), date(2026, 9, 13))
    assert "not yet complete" in text
    assert "-109" in text


def test_reference_age_text_complete() -> None:
    assert (
        _reference_age_text(date(2026, 7, 31), date(2026, 9, 13))
        == "reference age 44 d"
    )

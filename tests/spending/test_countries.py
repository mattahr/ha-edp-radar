"""Label → alpha-2 resolution shared by the XLSX providers (S7)."""

from __future__ import annotations

from custom_components.edp_radar.spending.countries import (
    EUROSTAT_AGGREGATES,
    EUROSTAT_GEO_FIXES,
    NORDIC,
    SKIP_LABELS,
    normalise_label,
    resolve_country,
)


def test_plain_labels_resolve() -> None:
    assert resolve_country("Sweden") == "SE"
    assert resolve_country("Türkiye") == "TR"
    assert resolve_country("Slovak Republic") == "SK"
    assert resolve_country("Czech Republic") == "CZ"
    assert resolve_country("United States of America") == "US"
    assert resolve_country("Korea, South") == "KR"


def test_decorated_labels_are_normalised_first() -> None:
    assert normalise_label("Sweden* (Kronor)") == "Sweden"
    assert normalise_label("Slovenia*** ") == "Slovenia"
    assert normalise_label("Croatia ") == "Croatia"
    assert resolve_country("Sweden* (Kronor)") == "SE"
    assert resolve_country("Luxembourg**") == "LU"


def test_unknown_and_skipped_labels() -> None:
    assert resolve_country("Atlantis") is None
    assert "NATO Total" in SKIP_LABELS
    assert "USSR" in SKIP_LABELS
    assert resolve_country("USSR") is None


def test_eurostat_helpers() -> None:
    assert EUROSTAT_GEO_FIXES == {"EL": "GR", "UK": "GB"}
    assert "EU27_2020" in EUROSTAT_AGGREGATES
    assert NORDIC == ("SE", "FI", "DK", "NO", "IS")


def test_skipped_labels_are_distinguishable_from_unknown_ones() -> None:
    from custom_components.edp_radar.spending.countries import (
        is_skipped_label,
        resolve_country,
    )

    assert is_skipped_label("European Union")
    assert is_skipped_label("NATO Total*")
    assert not is_skipped_label("Atlantis")
    assert resolve_country("European Union") is None
    assert resolve_country("Atlantis") is None

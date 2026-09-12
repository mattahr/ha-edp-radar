import json
from pathlib import Path

from custom_components.edp_radar.const import (
    MATCH_DEFENCE_BUYER,
    MATCH_DEFENCE_CPV,
    MATCH_DEFENCE_LEGAL_BASIS,
    RelevanceMode,
)
from custom_components.edp_radar.taxonomy import Taxonomy, normalize_cpv

DATA = Path("custom_components/edp_radar/data")


def test_normalize_cpv() -> None:
    assert normalize_cpv("35300000-7") == "35300000"
    assert normalize_cpv("35300000") == "35300000"
    assert normalize_cpv(" 353 ") is None
    assert normalize_cpv("abc") is None


def test_load_reads_versions_and_rules() -> None:
    tax = Taxonomy.load()
    assert tax.version == "2026.09.1/2026.09.1"
    assert "353" in tax.defence_cpv_prefixes
    assert tax.label("uas_cuas") == "UAS / C-UAS"
    assert "other_defence" in tax.category_ids


def test_defence_cpv_excludes_police_and_fire() -> None:
    tax = Taxonomy.load()
    assert tax.is_defence_cpv("35330000") is True
    assert tax.is_defence_cpv("35811300-5") is True
    assert tax.is_defence_cpv("35110000") is False
    assert tax.is_defence_cpv("35200000") is False
    assert tax.is_defence_cpv("35815100") is False


def test_match_reasons_are_independent_signals() -> None:
    tax = Taxonomy.load()
    reasons = tax.match_reasons(
        activities=["gen-pub", "defence"],
        legal_basis=["32014L0024"],
        cpv_codes=["30125100"],
    )
    assert reasons == frozenset({MATCH_DEFENCE_BUYER})
    reasons = tax.match_reasons(
        activities=[], legal_basis=["32009L0081"], cpv_codes=["35330000", "15811000"]
    )
    assert reasons == frozenset({MATCH_DEFENCE_LEGAL_BASIS, MATCH_DEFENCE_CPV})
    assert (
        tax.match_reasons(activities=["health"], legal_basis=[], cpv_codes=[])
        == frozenset()
    )


def test_is_relevant_depends_on_mode() -> None:
    tax = Taxonomy.load()
    cpv_only = frozenset({MATCH_DEFENCE_CPV})
    assert tax.is_relevant(cpv_only, RelevanceMode.STRICT) is False
    assert tax.is_relevant(cpv_only, RelevanceMode.BROAD) is True
    buyer_only = frozenset({MATCH_DEFENCE_BUYER})
    assert tax.is_relevant(buyer_only, RelevanceMode.STRICT) is True
    assert tax.is_relevant(frozenset(), RelevanceMode.BROAD) is False


def test_classify_longest_prefix_and_multi_label() -> None:
    tax = Taxonomy.load()
    assert tax.classify(["35612000"]) == ("uas_cuas",)
    assert tax.classify(["35611100"]) == ("air_systems",)
    assert tax.classify(["35300000"]) == ("other_defence",)
    assert tax.classify(["35310000"]) == ("land_systems",)
    assert tax.classify(["72000000", "35620000", "72000000"]) == (
        "air_missile_defence",
        "cyber_it",
    )
    assert tax.classify(["45200000"]) == ()
    assert tax.classify(["not-a-cpv"]) == ()


def test_no_prefix_is_owned_by_two_categories() -> None:
    data = json.loads((DATA / "strategic_categories.json").read_text())
    seen: dict[str, str] = {}
    for cat in data["categories"]:
        for prefix in cat["cpv_prefixes"]:
            assert prefix not in seen, f"{prefix} in {seen[prefix]} and {cat['id']}"
            seen[prefix] = cat["id"]

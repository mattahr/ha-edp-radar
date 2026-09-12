from datetime import date

from custom_components.edp_radar.const import RelevanceMode
from custom_components.edp_radar.query import TedQueryBuilder as Q


def test_strict_universe() -> None:
    assert (
        Q.defence_universe(RelevanceMode.STRICT, ["353", "354"])
        == "(authority-main-activity=defence OR legal-basis=32009L0081)"
    )


def test_broad_universe_adds_cpv_prefixes_as_wildcards() -> None:
    assert Q.defence_universe(RelevanceMode.BROAD, ["353", "35811300"]) == (
        "(authority-main-activity=defence OR legal-basis=32009L0081"
        " OR classification-cpv IN (353* 35811300*))"
    )


def test_publication_range() -> None:
    assert Q.publication_range(date(2025, 8, 9)) == "PD>=20250809"
    assert (
        Q.publication_range(date(2025, 8, 9), date(2026, 9, 12))
        == "(PD>=20250809 AND PD<=20260912)"
    )


def test_countries_use_alpha3_sorted() -> None:
    assert Q.countries(["FI", "SE"]) == "buyer-country IN (FIN SWE)"
    assert Q.countries([]) == ""


def test_buyer_filters_are_quoted_and_escaped() -> None:
    assert Q.buyer_identifiers(["202100-0340"]) == 'buyer-identifier IN ("202100-0340")'
    assert Q.buyer_identifiers(['Leitweg-ID: 991"x']) == (
        'buyer-identifier IN ("Leitweg-ID: 991\\"x")'
    )
    assert Q.buyer_name_search("försvar") == "buyer-name ~ (försvar*)"
    assert Q.buyer_name_search(' Försvarets "materiel-verk" (FMV) ') == (
        "buyer-name ~ (Försvarets* materiel* verk* FMV*)"
    )
    assert Q.buyer_name_search('"()') == ""
    assert Q.publication_number("626136-2026") == 'ND="626136-2026"'


def test_combinators_skip_empty_and_keep_precedence() -> None:
    assert Q.combine_and("PD>=20250809", "", "buyer-country IN (SWE)") == (
        "PD>=20250809 AND (buyer-country IN (SWE))"
    )
    assert Q.combine_or("a=1", "b=2") == "(a=1 OR b=2)"
    assert Q.combine_and("a=1") == "a=1"
    assert Q.combine_and() == ""


def test_full_bootstrap_query_shape() -> None:
    query = Q.sort_by_publication_date(
        Q.combine_and(
            Q.publication_range(date(2025, 8, 9)),
            Q.defence_universe(RelevanceMode.STRICT, []),
            Q.countries(["SE", "FI"]),
        )
    )
    assert query == (
        "PD>=20250809 AND (authority-main-activity=defence OR legal-basis=32009L0081)"
        " AND (buyer-country IN (FIN SWE)) SORT BY publication-date DESC"
    )

from custom_components.edp_radar.const import (
    EU_COUNTRIES,
    NORDIC_COUNTRIES,
    TED_COUNTRIES,
    to_alpha2,
    to_alpha3,
)


def test_alpha_round_trip() -> None:
    assert to_alpha3("SE") == "SWE"
    assert to_alpha2("SWE") == "SE"
    assert to_alpha3("se") == "SWE"


def test_unknown_codes_pass_through() -> None:
    assert to_alpha2("XXX") == "XXX"
    assert to_alpha3("ZZ") == "ZZ"


def test_country_sets() -> None:
    assert len(EU_COUNTRIES) == 27
    assert frozenset({"SE", "FI", "DK", "NO", "IS"}) == NORDIC_COUNTRIES
    assert EU_COUNTRIES < TED_COUNTRIES
    for code in TED_COUNTRIES:
        assert to_alpha2(to_alpha3(code)) == code

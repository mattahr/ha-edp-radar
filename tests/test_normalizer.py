from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from custom_components.edp_radar.const import (
    MATCH_DEFENCE_BUYER,
    MATCH_DEFENCE_CPV,
    MATCH_DEFENCE_LEGAL_BASIS,
)
from custom_components.edp_radar.models import Money, NoticeStage
from custom_components.edp_radar.normalizer import (
    REQUESTED_FIELDS,
    NormalizationError,
    as_strings,
    first_text,
    normalize_many,
    normalize_notice,
    parse_ted_date,
)
from custom_components.edp_radar.taxonomy import Taxonomy

type Lookup = Callable[[str], dict[str, Any]]


@pytest.fixture
def taxonomy() -> Taxonomy:
    return Taxonomy.load()


def test_requested_fields_are_unique_and_exclude_descriptions() -> None:
    assert len(REQUESTED_FIELDS) == len(set(REQUESTED_FIELDS))
    assert "description-proc" not in REQUESTED_FIELDS
    assert "notice-identifier" in REQUESTED_FIELDS
    assert "change-notice-version-identifier" in REQUESTED_FIELDS


def test_helpers() -> None:
    assert first_text({"deu": "Titel"}) == "Titel"
    assert first_text({"swe": ["FMV"], "eng": ["FMV Ltd"]}) == "FMV Ltd"
    assert first_text(["a", "b"]) == "a"
    assert first_text(None) is None
    assert first_text("  ") is None
    assert as_strings(None) == ()
    assert as_strings("x") == ("x",)
    assert as_strings(["a", None, 1]) == ("a", "1")
    assert parse_ted_date("2026-09-11+02:00") == date(2026, 9, 11)
    assert parse_ted_date("2026-07-21Z") == date(2026, 7, 21)
    assert parse_ted_date("nonsense") is None


def test_competition_single_lot(real_notice: Lookup, taxonomy: Taxonomy) -> None:
    notice = normalize_notice(real_notice("626977-2026"), taxonomy)
    assert notice.notice_id == "05bda7d3-9510-41db-81d2-0fa4e0eef464"
    assert notice.notice_version == 1
    assert notice.publication_number == "626977-2026"
    assert notice.publication_date == date(2026, 9, 11)
    assert notice.procedure_id == "df98839a-96e5-40e5-bfc8-165dc0c6e571"
    assert notice.stage is NoticeStage.COMPETITION
    assert notice.is_change is False
    assert notice.title is not None
    assert notice.title.startswith("Suministro de dos grupos")
    assert notice.buyer.name == "Intendente de San Fernando"
    assert notice.buyer.identifiers == ("10000140000584", "S1115005I")
    assert notice.buyer.country == "ES"
    assert notice.buyer.count == 1
    assert notice.buyer.main_activities == ("defence",)
    assert notice.legal_basis == ("32014L0024",)
    assert notice.cpv_codes == ("31000000",)
    assert notice.match_reasons == frozenset({MATCH_DEFENCE_BUYER})
    assert notice.estimated_value == Money(Decimal("185000"), "EUR")
    assert notice.result_value is None
    assert notice.winners == ()
    assert notice.tender_statistics is None
    assert notice.source_url == "https://ted.europa.eu/en/notice/-/detail/626977-2026"
    assert notice.classification_rule_version == taxonomy.version


def test_lot_values_with_collapsed_currency_are_summed(
    real_notice: Lookup, taxonomy: Taxonomy
) -> None:
    notice = normalize_notice(real_notice("626146-2026"), taxonomy)
    assert notice.estimated_value == Money(Decimal("647008.8"), "EUR")
    assert notice.categories == ("logistics_support",)


def test_procedure_value_wins_over_lot_values(
    real_notice: Lookup, taxonomy: Taxonomy
) -> None:
    notice = normalize_notice(real_notice("626585-2026"), taxonomy)
    assert notice.estimated_value == Money(Decimal("339075"), "EUR")


def test_lot_values_with_ambiguous_currencies_are_unknown(
    real_notice: Lookup, taxonomy: Taxonomy
) -> None:
    raw = real_notice("626146-2026")
    raw["estimated-value-cur-lot"] = ["EUR", "SEK"]
    assert normalize_notice(raw, taxonomy).estimated_value is None


def test_change_notice_as_new_id_and_as_new_version(
    real_notice: Lookup, taxonomy: Taxonomy
) -> None:
    new_id = normalize_notice(real_notice("626359-2026"), taxonomy)
    assert new_id.stage is NoticeStage.COMPETITION
    assert new_id.is_change is True
    assert new_id.change is not None
    assert new_id.change.reason_code == "cor-buy"
    assert new_id.match_reasons == frozenset({MATCH_DEFENCE_LEGAL_BASIS})
    assert new_id.buyer.main_activities == ()

    v2 = normalize_notice(real_notice("626569-2026"), taxonomy)
    assert v2.notice_version == 2
    assert v2.is_change is True
    assert v2.change is not None
    assert v2.change.reason_code == "update-add"
    assert v2.change.description == (
        "Modification de la date limite de réception des offres"
    )
    assert v2.version_key.endswith(":2")

    plain_v2 = normalize_notice(real_notice("628113-2026"), taxonomy)
    assert plain_v2.notice_version == 2
    assert plain_v2.is_change is False


def test_result_single_winner(real_notice: Lookup, taxonomy: Taxonomy) -> None:
    notice = normalize_notice(real_notice("626136-2026"), taxonomy)
    assert notice.stage is NoticeStage.RESULT
    assert notice.result_value == Money(Decimal("55600000"), "DKK")
    assert notice.estimated_value == Money(Decimal("85000000"), "DKK")
    assert len(notice.winners) == 1
    winner = notice.winners[0]
    assert winner.identifier == "29847096"
    assert winner.country == "DK"
    assert winner.size == "sme"
    assert winner.name == "Element Logic Denmark A/S"
    assert notice.tender_statistics is not None
    assert notice.tender_statistics.tender_counts == (3,)
    assert notice.tender_statistics.selection_statuses == ("selec-w",)
    assert notice.tender_statistics.decision_dates == (date(2026, 7, 21),)
    assert notice.award_date == date(2026, 7, 21)


def test_result_multi_lot_statistics_and_non_awards(
    real_notice: Lookup, taxonomy: Taxonomy
) -> None:
    notice = normalize_notice(real_notice("627236-2026"), taxonomy)
    assert notice.result_value == Money(Decimal("10306545.8"), "PLN")
    stats = notice.tender_statistics
    assert stats is not None
    # 14 lots, but the 5 non-awarded (no-rece) lots carry no submission statistics
    assert len(stats.tender_counts) == 9
    assert stats.selection_statuses.count("clos-nw") == 5
    assert stats.selection_statuses.count("selec-w") == 9
    assert stats.non_award_justifications == ("no-rece",) * 5
    # winner-name lists 9 winning tenders for 4 unique organisations
    assert [w.name for w in notice.winners] == [
        'Fabryka Broni "ŁUCZNIK" - Radom Sp. z o.o.',
        'Zakłady Mechaniczne "TARNÓW" S.A.',
        "Pagacz i Synowie Sp. z o.o.",
        "Przedsiębiorstwo Sprzętu Ochronnego MASKPOL S.A.",
    ]
    assert [w.identifier for w in notice.winners] == [
        "5741002058",
        "8792618405",
        "8730006835",
        "9482182612",
    ]
    assert {w.country for w in notice.winners} == {"PL"}
    # 35322100 → air & missile defence, 3534*/35322200 → land, 35813000 → logistics
    assert notice.categories == (
        "air_missile_defence",
        "land_systems",
        "logistics_support",
    )
    assert notice.match_reasons == frozenset(
        {MATCH_DEFENCE_BUYER, MATCH_DEFENCE_LEGAL_BASIS, MATCH_DEFENCE_CPV}
    )


def test_result_value_sentinel_minus_one_is_unknown(
    real_notice: Lookup, taxonomy: Taxonomy
) -> None:
    notice = normalize_notice(real_notice("628418-2026"), taxonomy)
    assert notice.result_value is None
    assert notice.estimated_value == Money(Decimal("1149499.20"), "EUR")
    assert notice.tender_statistics is not None
    assert notice.tender_statistics.tender_counts == (1, 1)
    assert notice.match_reasons == frozenset(
        {MATCH_DEFENCE_BUYER, MATCH_DEFENCE_LEGAL_BASIS, MATCH_DEFENCE_CPV}
    )


def test_framework_result_keeps_ceiling_but_no_award_value(
    real_notice: Lookup, taxonomy: Taxonomy
) -> None:
    raw = real_notice("626136-2026")
    raw["framework-agreement-lot"] = ["fa-mix"]
    raw["result-value-notice"] = "17424000000"
    raw["result-framework-maximum-value-notice"] = "316800000"
    raw["result-framework-maximum-value-cur-notice"] = "EUR"
    notice = normalize_notice(raw, taxonomy)
    assert notice.is_framework is True
    assert notice.result_value is None
    assert notice.framework_value == Money(Decimal("316800000"), "EUR")
    assert type(notice).from_dict(notice.to_dict()) == notice

    plain = normalize_notice(real_notice("626136-2026"), taxonomy)
    assert plain.is_framework is False and plain.framework_value is None

    without_max = real_notice("626136-2026")
    without_max["framework-agreement-lot"] = ["fa-wo-rc"]
    fallback = normalize_notice(without_max, taxonomy)
    assert fallback.framework_value == Money(Decimal("55600000"), "DKK")
    assert fallback.result_value is None

    competition = real_notice("626359-2026")
    competition["framework-agreement-lot"] = ["fa-mix"]
    framework_competition = normalize_notice(competition, taxonomy)
    assert framework_competition.is_framework is True
    assert framework_competition.framework_value is None


def test_winner_with_two_identifiers_gets_no_identifier(
    real_notice: Lookup, taxonomy: Taxonomy
) -> None:
    notice = normalize_notice(real_notice("626208-2026"), taxonomy)
    assert len(notice.winners) == 1
    assert notice.winners[0].identifier is None
    assert notice.winners[0].country == "SK"
    assert notice.winners[0].identity_key.startswith("SK:")


def test_repeated_winner_names_collapse_to_one_winner(
    real_notice: Lookup, taxonomy: Taxonomy
) -> None:
    notice = normalize_notice(real_notice("628418-2026"), taxonomy)
    assert len(notice.winners) == 1
    assert notice.winners[0].name == "Rheinmetall Electronics GmbH"
    assert notice.winners[0].identifier == "DE 811127845"
    assert notice.winners[0].country == "DE"
    two_ids = normalize_notice(real_notice("627092-2026"), taxonomy)
    assert len(two_ids.winners) == 1
    assert two_ids.winners[0].identifier is None  # two identifiers for one name
    assert two_ids.winners[0].country == "SI"


def test_other_stages(real_notice: Lookup, taxonomy: Taxonomy) -> None:
    planning = normalize_notice(real_notice("626028-2026"), taxonomy)
    assert planning.stage is NoticeStage.PLANNING
    assert planning.procedure_id is None
    direct = normalize_notice(real_notice("626308-2026"), taxonomy)
    assert direct.stage is NoticeStage.DIRECT_AWARD
    modification = normalize_notice(real_notice("619411-2026"), taxonomy)
    assert modification.stage is NoticeStage.MODIFICATION
    assert modification.modification is not None
    assert modification.modification.justifications == ("add-wss",)
    assert modification.modification.previous_notice_ids == ("291876-2024",)


def test_unknown_form_type_is_other(real_notice: Lookup, taxonomy: Taxonomy) -> None:
    raw = real_notice("626977-2026")
    raw["form-type"] = "bri"
    assert normalize_notice(raw, taxonomy).stage is NoticeStage.OTHER


def test_multi_buyer_central_purchasing(
    real_notice: Lookup, taxonomy: Taxonomy
) -> None:
    notice = normalize_notice(real_notice("613361-2026"), taxonomy)
    assert notice.buyer.count == 12
    assert notice.buyer.country == "HR"
    assert "defence" in notice.buyer.main_activities
    assert notice.match_reasons == frozenset({MATCH_DEFENCE_BUYER})


def test_swedish_sek_notice(real_notice: Lookup, taxonomy: Taxonomy) -> None:
    notice = normalize_notice(real_notice("626862-2026"), taxonomy)
    assert notice.buyer.country == "SE"
    assert notice.buyer.identifiers == ("2021005182",)
    assert notice.estimated_value == Money(Decimal("6000000"), "SEK")
    assert notice.tender_statistics is not None
    assert notice.tender_statistics.tender_counts == (0, 1, 1)
    assert notice.tender_statistics.selection_statuses == ("clos-nw",) * 3


def test_title_is_truncated(real_notice: Lookup, taxonomy: Taxonomy) -> None:
    raw = real_notice("626977-2026")
    raw["title-proc"] = {"spa": "x" * 500}
    title = normalize_notice(raw, taxonomy).title
    assert title is not None and len(title) == 200


def test_missing_identity_raises_and_normalize_many_counts(
    real_notice: Lookup, taxonomy: Taxonomy
) -> None:
    raw = real_notice("626977-2026")
    del raw["notice-identifier"]
    with pytest.raises(NormalizationError):
        normalize_notice(raw, taxonomy)
    notices, errors = normalize_many([raw, real_notice("626136-2026")], taxonomy)
    assert errors == 1
    assert [n.publication_number for n in notices] == ["626136-2026"]


def test_all_fixtures_normalize(
    real_notices: list[dict[str, Any]], taxonomy: Taxonomy
) -> None:
    notices, errors = normalize_many(real_notices, taxonomy)
    assert errors == 0
    assert len(notices) == 18
    for notice in notices:
        assert type(notice).from_dict(notice.to_dict()) == notice

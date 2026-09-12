"""Hand-calculated tests for the country purchasing model (Phase 2 plan §4–§30)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from custom_components.edp_radar.fx_rates import FxRateTable
from custom_components.edp_radar.models import (
    AWARD_DATE_BASIS_DECISION,
    AWARD_DATE_BASIS_PUBLICATION,
    Buyer,
    Money,
    NoticeStage,
    ProcurementNotice,
    Winner,
)
from custom_components.edp_radar.purchasing import (
    FLAG_ABOVE_CAP,
    FLAG_DUPLICATE_VALUE,
    FLAG_EXCEEDS_ESTIMATE,
    FLAG_EXCEEDS_TENDERS,
    FLAG_FRAMEWORK,
    FLAG_UNCONVERTIBLE,
    FLAG_UNVERIFIED_LARGE,
    MULTI_COUNTRY,
    UNCLASSIFIED,
    PurchasingModel,
    ResultKind,
    attribute_country,
    build_purchasing_model,
    categories_text,
    classify_result,
    extract_awarded_value,
    my_country_text,
    top_buyers_text,
)
from custom_components.edp_radar.taxonomy import Taxonomy

from .factories import buyer, competition, days_ago, flat_fx, make_notice, result

TODAY = date(2026, 9, 12)
FX = flat_fx({"SEK": "10", "PLN": "4"}, date(2024, 1, 1), TODAY)
WINNER = (Winner("Saab AB", "556036-0793", "SE", "large"),)


@pytest.fixture(scope="module")
def taxonomy() -> Taxonomy:
    return Taxonomy.load()


def eur(amount: str) -> Money:
    return Money(Decimal(amount), "EUR")


def awarded(
    notice_id: str,
    country: str,
    published: date,
    value: Money | None,
    *,
    procedure_id: str | None = None,
    decided: date | None = None,
    cpv: str = "35400000",
    categories: tuple[str, ...] = ("land_systems",),
    **overrides: object,
) -> ProcurementNotice:
    fields: dict[str, object] = {
        "buyer": buyer(f"Buyer {country}", country, f"id-{country}"),
        "cpv_codes": (cpv,),
        "categories": categories,
        **overrides,
    }
    return result(
        notice_id,
        procedure_id or f"p-{notice_id}",
        published,
        value=value,
        statuses=("selec-w",),
        winners=WINNER,
        decision_dates=(decided,) if decided else (),
        **fields,
    )


# ------------------------------------------------------------------ classification


def test_classify_result_by_selection_status_winners_and_value() -> None:
    won = result("a", "p", TODAY, statuses=("clos-nw", "selec-w"))
    assert classify_result(won) is ResultKind.AWARDED
    lost = result("b", "p", TODAY, statuses=("clos-nw", "open-nw"))
    assert classify_result(lost) is ResultKind.NOT_AWARDED
    winners_only = result("c", "p", TODAY, winners=WINNER)
    assert classify_result(winners_only) is ResultKind.AWARDED
    value_only = result("d", "p", TODAY, value=eur("5"))
    assert classify_result(value_only) is ResultKind.AWARDED
    empty = result("e", "p", TODAY)
    assert classify_result(empty) is ResultKind.UNKNOWN
    assert classify_result(competition("f", "p", TODAY)) is ResultKind.UNKNOWN


def test_attribute_country_single_multi_and_missing() -> None:
    assert attribute_country(make_notice(buyer=buyer("FMV", "SE"))) == "SE"
    same = Buyer("A", (), "SE", None, (), 3, countries=("SE",))
    assert attribute_country(make_notice(buyer=same)) == "SE"
    joint = Buyer("A", (), "FI", None, (), 2, countries=("FI", "SE"))
    assert attribute_country(make_notice(buyer=joint)) == MULTI_COUNTRY
    unknown = Buyer("A", (), None, None, (), 1)
    assert attribute_country(make_notice(buyer=unknown)) is None


# ------------------------------------------------------------------ extraction


def test_extract_awarded_value_converts_at_award_date_and_records_basis() -> None:
    notice = awarded(
        "n", "SE", TODAY, Money(Decimal("1000"), "SEK"), decided=date(2026, 8, 1)
    )
    value = extract_awarded_value(notice, FX)
    assert value.money == Money(Decimal("1000"), "SEK")
    assert value.value_eur == Decimal("100.00")
    assert value.source == "result-value-notice"
    assert value.date == date(2026, 8, 1)
    assert value.date_basis == AWARD_DATE_BASIS_DECISION
    assert value.flags == ()
    assert value.usable is True

    plain = extract_awarded_value(awarded("m", "SE", TODAY, eur("7")), FX)
    assert plain.date == TODAY
    assert plain.date_basis == AWARD_DATE_BASIS_PUBLICATION
    assert plain.value_eur == Decimal("7")


def test_extract_awarded_value_missing_framework_and_unconvertible() -> None:
    missing = extract_awarded_value(awarded("a", "SE", TODAY, None), FX)
    assert missing.money is None and missing.value_eur is None
    assert missing.source is None and missing.usable is False

    framework = extract_awarded_value(
        awarded("b", "SE", TODAY, None, is_framework=True, framework_value=eur("9")),
        FX,
    )
    assert framework.flags == (FLAG_FRAMEWORK,)
    assert framework.value_eur is None and framework.usable is False

    exotic = extract_awarded_value(
        awarded("c", "SE", TODAY, Money(Decimal("5"), "XXX")), FX
    )
    assert exotic.money is not None and exotic.value_eur is None
    assert exotic.flags == (FLAG_UNCONVERTIBLE,)
    assert exotic.usable is False and exotic.suspicious is False


def test_extract_awarded_value_flags_implausible_values() -> None:
    huge = extract_awarded_value(awarded("a", "PL", TODAY, eur("10000000001")), FX)
    assert huge.flags == (FLAG_ABOVE_CAP,)
    assert huge.suspicious is True and huge.usable is False
    assert huge.value_eur == Decimal("10000000001")

    inflated = extract_awarded_value(
        awarded("b", "PT", TODAY, eur("7274615930")), FX, estimate=eur("7317073.17")
    )
    assert inflated.flags == (FLAG_EXCEEDS_ESTIMATE,)
    assert inflated.usable is False

    exactly_ratio = extract_awarded_value(
        awarded("c", "PT", TODAY, eur("1000000")), FX, estimate=eur("10000")
    )
    assert exactly_ratio.flags == ()

    # Buyers enter placeholder estimates (1, 98, 100 SEK …): not a comparison.
    placeholder = extract_awarded_value(
        awarded("e", "SE", TODAY, Money(Decimal("415000000"), "SEK")),
        FX,
        estimate=Money(Decimal("98"), "SEK"),
    )
    assert placeholder.flags == ()

    # EUR 250m and up without a real estimate: kept, but marked for a human eye.
    unverified = extract_awarded_value(
        awarded("i", "SE", TODAY, eur("250000000")), FX, estimate=eur("100")
    )
    assert unverified.flags == (FLAG_UNVERIFIED_LARGE,)
    assert unverified.suspicious is False and unverified.usable is True

    # Notice Value 1000× the notice's own winning tenders is a unit error too.
    tenders = extract_awarded_value(
        awarded(
            "f",
            "PL",
            TODAY,
            Money(Decimal("7247040000"), "PLN"),
            tender_value_total=Money(Decimal("7247040"), "PLN"),
        ),
        FX,
    )
    assert tenders.flags == (FLAG_EXCEEDS_TENDERS,)
    assert tenders.usable is False
    consistent = extract_awarded_value(
        awarded(
            "g",
            "PL",
            TODAY,
            Money(Decimal("7247040"), "PLN"),
            tender_value_total=Money(Decimal("7000000"), "PLN"),
        ),
        FX,
    )
    assert consistent.flags == ()
    # Placeholder tender values ("1" per tender) are not a comparison either …
    placeholder_tenders = extract_awarded_value(
        awarded("j", "NL", TODAY, eur("100000000"), tender_value_total=eur("1")),
        FX,
    )
    assert placeholder_tenders.flags == ()
    # … and a real estimate that corroborates the Notice Value wins over
    # tender values that contradict it.
    arbitrated = extract_awarded_value(
        awarded(
            "k",
            "SE",
            TODAY,
            Money(Decimal("1100000000"), "SEK"),
            tender_value_total=Money(Decimal("1100000"), "SEK"),
        ),
        FX,
        estimate=Money(Decimal("1000000000"), "SEK"),
    )
    assert arbitrated.flags == ()

    # A large award corroborated by a real estimate is verified.
    verified = extract_awarded_value(
        awarded("h", "DK", TODAY, eur("2115606235")), FX, estimate=eur("2000000000")
    )
    assert verified.flags == ()

    other_currency = extract_awarded_value(
        awarded("d", "PT", TODAY, eur("1000")), FX, estimate=Money(Decimal("1"), "SEK")
    )
    assert other_currency.flags == ()


# ------------------------------------------------------------------ model


def _notices() -> list[ProcurementNotice]:
    current = days_ago(TODAY, 100)
    previous = days_ago(TODAY, 400)
    return [
        # SE: two usable awards now (one on decision-date basis), one before.
        awarded(
            "se1",
            "SE",
            days_ago(TODAY, 20),
            eur("100000000"),
            decided=days_ago(TODAY, 40),
            cpv="35330000",
            categories=("ammunition_explosives",),
            title="Ammunition",
        ),
        awarded("se2", "SE", current, eur("50000000"), title="Vehicles"),
        awarded("se0", "SE", previous, eur("100000000")),
        # SE: framework (excluded), non-award (EUR 0), unconvertible, unclassified
        awarded(
            "se3",
            "SE",
            current,
            None,
            is_framework=True,
            framework_value=eur("2000000000"),
        ),
        result(
            "se4",
            "p-se4",
            current,
            statuses=("clos-nw",),
            buyer=buyer("Buyer SE", "SE"),
        ),
        awarded("se5", "SE", current, Money(Decimal("1"), "XXX")),
        awarded(
            "se6",
            "SE",
            days_ago(TODAY, 10),
            eur("10000000"),
            cpv="45000000",
            categories=(),
        ),
        # DE: one large unverified award now, nothing before (growth undefined).
        awarded("de1", "DE", current, eur("300000000")),
        # FI+SE joint procurement: counted once as MULTI.
        awarded(
            "joint",
            "FI",
            current,
            eur("20000000"),
            buyer=Buyer("PVK", (), "FI", None, ("defence",), 2, countries=("FI", "SE")),
        ),
        # PL: awards without any usable value → unknown, not zero.
        awarded("pl1", "PL", current, None),
        awarded("pl2", "PL", current, None),
        # FR: an implausible value is quarantined, a plausible one counts.
        awarded("fr1", "FR", current, eur("12000000000")),
        awarded("fr2", "FR", current, eur("10000000")),
        # PT: award 1000× its competition's estimate → quarantined.
        competition(
            "pt-cn", "p-pt", days_ago(TODAY, 300), estimated_value=eur("70000")
        ),
        awarded("pt1", "PT", current, eur("70000000"), procedure_id="p-pt"),
        # DK: the same value published twice for one procedure counts once.
        awarded("dk1", "DK", days_ago(TODAY, 90), eur("5000000"), procedure_id="p-dk"),
        awarded("dk2", "DK", days_ago(TODAY, 80), eur("5000000"), procedure_id="p-dk"),
        # Older than 24 months: ignored by every period.
        awarded("old", "SE", days_ago(TODAY, 800), eur("999000000")),
    ]


@pytest.fixture(scope="module")
def model(taxonomy: Taxonomy) -> PurchasingModel:
    return build_purchasing_model(_notices(), FX, TODAY, taxonomy=taxonomy)


def test_ranking_orders_countries_by_usable_value(model: PurchasingModel) -> None:
    period = model.primary
    assert period.window.days == 365
    assert [(e.rank, e.country) for e in period.ranking] == [
        (1, "DE"),
        (2, "SE"),
        (3, "FR"),
        (4, "DK"),
    ]
    values = {e.country: e.summary.award_value_eur for e in period.ranking}
    assert values == {
        "DE": Decimal("300000000"),
        "SE": Decimal("160000000"),
        "FR": Decimal("10000000"),
        "DK": Decimal("5000000"),
    }
    # PT (quarantined only) and PL (no values) are active but unranked.
    assert period.unranked == ("PL", "PT")
    assert period.countries["PL"].award_value_eur is None
    assert period.countries["PL"].award_count == 2
    assert MULTI_COUNTRY not in [e.country for e in period.ranking]
    assert period.rank_of("SE") is period.ranking[1]
    assert period.rank_of("PL") is None


def test_country_summary_counts_coverage_and_change(model: PurchasingModel) -> None:
    se = model.primary.countries["SE"]
    assert se.award_count == 5  # se1 se2 se3(framework) se5 se6; not se4/se0
    assert se.valued_awards == 3
    assert se.value_coverage_pct == 60.0
    assert se.framework_results == 1
    assert se.non_awarded_results == 1
    assert se.unconvertible_results == 1
    assert se.suspicious_results == 0
    assert se.decision_date_awards == 1
    assert se.previous_value_eur == Decimal("100000000")
    assert se.previous_award_count == 1
    assert se.change_eur == Decimal("60000000")
    assert se.change_pct == 60.0

    de = model.primary.countries["DE"]
    assert de.previous_value_eur == Decimal(0)  # nothing awarded before: zero
    assert de.change_pct is None  # … so no growth percentage

    fr = model.primary.countries["FR"]
    assert fr.suspicious_results == 1
    assert fr.award_value_eur == Decimal("10000000")
    assert fr.unverified_large_results == 0

    assert de.unverified_large_results == 1
    assert de.unverified_large_value_eur == Decimal("300000000")
    assert se.unverified_large_results == 0
    assert se.unverified_large_value_eur is None

    dk = model.primary.countries["DK"]
    assert dk.valued_awards == 1 and dk.suspicious_results == 1


def test_share_and_european_total_identity(model: PurchasingModel) -> None:
    period = model.primary
    europe = period.europe
    assert europe.attributable_value_eur == Decimal("475000000")
    assert europe.joint_value_eur == Decimal("20000000")
    assert europe.unknown_country_value_eur is None
    assert europe.total_value_eur == Decimal("495000000")
    assert europe.previous_total_value_eur == Decimal("100000000")
    assert europe.countries_with_value == 4
    assert europe.countries_active == 6
    assert europe.suspicious_results == 3  # fr1, pt1, dk2
    assert europe.unverified_large_results == 1  # de1
    assert europe.largest_buyer is period.ranking[0]
    total = sum((e.summary.award_value_eur or 0) for e in period.ranking)
    assert total + europe.joint_value_eur == europe.total_value_eur
    assert period.rank_of("SE").share_pct == pytest.approx(32.3, abs=0.05)
    assert period.rank_of("DE").share_pct == pytest.approx(60.6, abs=0.05)


def test_growth_ranking_requires_minimum_activity(model: PurchasingModel) -> None:
    growth = model.primary.growth
    # DE has no previous period, DK/FR are below EUR 50m with < 5 awards.
    assert [(e.rank, e.country, e.summary.change_pct) for e in growth] == [
        (1, "SE", 60.0)
    ]


def test_categories_split_by_main_cpv_and_expose_unclassified(
    model: PurchasingModel,
) -> None:
    se = model.primary.countries["SE"]
    assert [(c.category_id, c.value_eur, c.share_pct) for c in se.top_categories] == [
        ("ammunition_explosives", Decimal("100000000"), 62.5),
        ("land_systems", Decimal("50000000"), 31.3),
        (UNCLASSIFIED, Decimal("10000000"), 6.3),
    ]
    assert se.top_categories[0].label == "Ammunition & explosives"
    assert se.top_categories[2].label == "Unclassified"
    assert se.unclassified_share_pct == 6.3
    europe = model.primary.europe
    assert europe.top_categories[0].category_id == "land_systems"
    assert europe.top_categories[0].value_eur == Decimal("385000000")


def test_largest_awards_are_traceable(model: PurchasingModel) -> None:
    se = model.primary.countries["SE"]
    largest = se.largest_awards
    assert [a.publication_number for a in largest] == ["se1-1", "se2-1", "se6-1"]
    top = largest[0]
    assert top.value_eur == Decimal("100000000")
    assert top.title == "Ammunition"
    assert top.buyer == "Buyer SE"
    assert top.country == "SE"
    assert top.date == days_ago(TODAY, 40)
    assert top.date_basis == AWARD_DATE_BASIS_DECISION
    assert top.primary_category == "ammunition_explosives"
    assert top.source_url is None  # factories set none; sensors pass it through
    largest_europe = model.primary.europe.largest_awards[0]
    assert largest_europe.publication_number == "de1-1"
    assert largest_europe.flags == (FLAG_UNVERIFIED_LARGE,)


def test_quarantined_awards_are_listed_with_reasons(model: PurchasingModel) -> None:
    quarantined = {a.publication_number: a.flags for a in model.quarantined}
    assert quarantined == {
        "fr1-1": (FLAG_ABOVE_CAP,),
        "pt1-1": (FLAG_EXCEEDS_ESTIMATE,),
        "dk2-1": (FLAG_DUPLICATE_VALUE,),
    }


def test_secondary_periods_use_the_award_date(model: PurchasingModel) -> None:
    ninety, thirty = model.secondary[90], model.secondary[30]
    assert ninety.window.days == 90 and thirty.window.days == 30
    se_90 = ninety.countries["SE"]
    # se1 (decided 40 days ago), se6 (10 days ago) and dk1 (90 days ago: outside,
    # the window is half-open) …
    assert se_90.award_value_eur == Decimal("110000000")
    # … while dk2 (80 days ago) is inside but quarantined: active, value unknown.
    assert ninety.countries["DK"].award_value_eur is None
    assert ninety.countries["DK"].suspicious_results == 1
    # DE awarded in the previous 90 days only: EUR 0 now, not unknown (§30).
    de = ninety.countries["DE"]
    assert de.award_count == 0 and de.award_value_eur == Decimal(0)
    assert de.previous_value_eur == Decimal("300000000")
    assert de.change_pct == -100.0
    assert ninety.ranking[-1].country == "PT"  # zero-valued countries rank last
    assert ninety.unranked == ("DK",)
    se_30 = thirty.countries["SE"]
    assert se_30.award_value_eur == Decimal("10000000")
    assert ninety.europe.total_value_eur == Decimal("110000000")


def test_monthly_series_covers_the_trend_window(model: PurchasingModel) -> None:
    series = model.monthly_series("SE")
    assert len(series) == 24
    assert series[-1].month == "2026-09"
    assert series[-1].value_eur == Decimal("10000000")
    assert series[-1].awards == 1
    by_month = {m.month: m for m in series}
    assert by_month["2026-08"].value_eur == Decimal("100000000")
    assert by_month["2026-06"].value_eur == Decimal("50000000")
    assert by_month["2026-06"].awards == 3  # se2, se3 (framework) and se5
    assert by_month["2026-01"].value_eur == Decimal(0)
    assert by_month["2026-01"].awards == 0
    assert by_month["2025-08"].value_eur == Decimal("100000000")
    assert model.monthly_series("XX") == ()


def test_texts(model: PurchasingModel) -> None:
    period = model.primary
    assert my_country_text(period, "SE") == "SE · EUR 160m / 12m · #2 · 32.3% · +60.0%"
    assert my_country_text(period, "DE") == "DE · EUR 300m / 12m · #1 · 60.6%"
    assert my_country_text(period, "PL") == "PL · value unknown / 12m · 2 awards"
    assert my_country_text(period, "XX") == "XX · no awards / 12m"
    assert top_buyers_text(period) == (
        "DE EUR 300m · SE EUR 160m · FR EUR 10m · DK EUR 5.0m"
    )
    assert categories_text(period.countries["SE"]) == (
        "Ammunition & explosives EUR 100m · Land systems EUR 50m · Unclassified EUR 10m"
    )


def test_empty_model(taxonomy: Taxonomy) -> None:
    empty = build_purchasing_model([], FxRateTable(), TODAY, taxonomy=taxonomy)
    assert empty.primary.ranking == ()
    assert empty.primary.europe.total_value_eur is None
    assert empty.primary.europe.largest_buyer is None
    assert empty.quarantined == ()
    assert top_buyers_text(empty.primary) == "no data"


def test_change_notices_and_non_results_are_ignored(taxonomy: Taxonomy) -> None:
    original = awarded("x", "SE", days_ago(TODAY, 10), eur("100"))
    republished = awarded(
        "x",
        "SE",
        days_ago(TODAY, 5),
        eur("100"),
        notice_version=2,
        publication_number="x-2",
    )
    model = build_purchasing_model(
        [original, republished, competition("c", "p", TODAY)],
        FX,
        TODAY,
        taxonomy=taxonomy,
    )
    se = model.primary.countries["SE"]
    assert se.award_count == 1 and se.award_value_eur == Decimal("100")
    assert model.quarantined == ()
    assert make_notice().stage is NoticeStage.COMPETITION

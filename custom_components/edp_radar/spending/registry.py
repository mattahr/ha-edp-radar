"""Source registry and metric definitions (S8; plan §9, §24, §30, §37, §42, §47).

``comparison_group`` equals the source id: rankings and medians only ever
combine datapoints of one source, one metric, one reference period and one
unit (plan §48).
"""

from __future__ import annotations

from datetime import timedelta

from .models import Cadence, MetricSpec, SourceSpec

FOCUS_COUNTRY = "SE"

STATSKONTORET = "statskontoret"
EUROSTAT = "eurostat"
NATO = "nato"
EDA = "eda"
SIPRI = "sipri"

SOURCE_ORDER: tuple[str, ...] = (STATSKONTORET, EUROSTAT, NATO, EDA, SIPRI)

SOURCES: dict[str, SourceSpec] = {
    STATSKONTORET: SourceSpec(
        source_id=STATSKONTORET,
        display_name="Statskontoret monthly budget outturn",
        publisher="Statskontoret",
        official=True,
        canonical_url="https://www.statskontoret.se/analys-och-statistik/oppna-data/manadsutfall/",
        cadence=Cadence.MONTHLY,
        expected_lag_days=31,
        check_interval=timedelta(days=1),
        formats=("csv",),
    ),
    EUROSTAT: SourceSpec(
        source_id=EUROSTAT,
        display_name="Eurostat gov_ev defence expenditure and investment",
        publisher="Eurostat",
        official=True,
        canonical_url="https://ec.europa.eu/eurostat/cache/metadata/en/gov_ev_esms.htm",
        cadence=Cadence.TWICE_YEARLY,
        expected_lag_days=120,
        check_interval=timedelta(days=1),
        formats=("json-stat",),
    ),
    NATO: SourceSpec(
        source_id=NATO,
        display_name="NATO defence expenditure of NATO countries",
        publisher="NATO",
        official=True,
        canonical_url="https://www.nato.int/en/what-we-do/introduction-to-nato/defence-expenditures-and-natos-5-commitment",
        cadence=Cadence.ANNUAL,
        expected_lag_days=200,
        check_interval=timedelta(days=7),
        formats=("xlsx",),
    ),
    EDA: SourceSpec(
        source_id=EDA,
        display_name="EDA defence data",
        publisher="European Defence Agency",
        official=True,
        canonical_url="https://www.eda.europa.eu/publications-and-data/defence-data",
        cadence=Cadence.ANNUAL,
        expected_lag_days=250,
        check_interval=timedelta(days=7),
        formats=("xlsx",),
    ),
    SIPRI: SourceSpec(
        source_id=SIPRI,
        display_name="SIPRI military expenditure database",
        publisher="SIPRI",
        official=False,
        canonical_url="https://www.sipri.org/databases/milex",
        cadence=Cadence.ANNUAL,
        expected_lag_days=120,
        check_interval=timedelta(days=7),
        formats=("xlsx",),
    ),
}


def _metric(
    source_id: str, metric_id: str, name: str, definition: str, unit: str
) -> MetricSpec:
    return MetricSpec(metric_id, source_id, name, definition, unit, source_id)


_METRIC_LIST: tuple[MetricSpec, ...] = (
    # Statskontoret (S9)
    _metric(
        STATSKONTORET,
        "uo6_total_outturn",
        "Expenditure area 6 outturn",
        "Monthly outturn of all appropriations in utgiftsområde 6 (Försvar och "
        "samhällets krisberedskap).",
        "SEK_MILLION",
    ),
    _metric(
        STATSKONTORET,
        "uo6_defence_outturn",
        "Defence appropriations outturn",
        "Monthly outturn of appropriations 6:1:1–6:1:14 (Anslag 0601001–0601014).",
        "SEK_MILLION",
    ),
    _metric(
        STATSKONTORET,
        "materiel_outturn",
        "Materiel acquisition outturn",
        "Monthly outturn of appropriation 6:1:3 Anskaffning av materiel och "
        "anläggningar (Anslag 0601003).",
        "SEK_MILLION",
    ),
    # Eurostat gov_ev (S10)
    _metric(
        EUROSTAT,
        "defence_expenditure",
        "Government defence expenditure",
        "gov_ev: total general government expenditure on defence (expend=DEF, "
        "na_item=TE), ESA 2010.",
        "EUR_MILLION",
    ),
    _metric(
        EUROSTAT,
        "defence_expenditure_nac",
        "Government defence expenditure (national currency)",
        "gov_ev DEF/TE in million units of national currency.",
        "NAC_MILLION",
    ),
    _metric(
        EUROSTAT,
        "defence_expenditure_pct_gdp",
        "Government defence expenditure, % of GDP",
        "gov_ev DEF/TE as a percentage of GDP.",
        "PCT_GDP",
    ),
    _metric(
        EUROSTAT,
        "defence_investment",
        "Government defence investment",
        "gov_ev: gross fixed capital formation on defence (expend=DEF, na_item=P51G).",
        "EUR_MILLION",
    ),
    _metric(
        EUROSTAT,
        "defence_investment_nac",
        "Government defence investment (national currency)",
        "gov_ev DEF/P51G in million units of national currency.",
        "NAC_MILLION",
    ),
    _metric(
        EUROSTAT,
        "defence_investment_pct_gdp",
        "Government defence investment, % of GDP",
        "gov_ev DEF/P51G as a percentage of GDP.",
        "PCT_GDP",
    ),
    # NATO (S11)
    _metric(
        NATO,
        "defence_expenditure_nac",
        "Defence expenditure (national currency)",
        "Table 1, current prices, million national currency units (NATO definition).",
        "NAC_MILLION",
    ),
    _metric(
        NATO,
        "defence_expenditure_usd_current",
        "Defence expenditure (USD, current)",
        "Table 2, current prices and exchange rates, million US dollars.",
        "USD_MILLION",
    ),
    _metric(
        NATO,
        "defence_expenditure_usd_constant",
        "Defence expenditure (USD, constant prices)",
        "Table 2, constant prices and exchange rates, million US dollars; the "
        "base year is read from the workbook and appended to the datapoint "
        "unit (S39).",
        "USD_MILLION_CONSTANT",
    ),
    _metric(
        NATO,
        "defence_expenditure_pct_gdp",
        "Defence expenditure, % of real GDP",
        "Table 3, share of real GDP based on 2021 prices.",
        "PCT_GDP",
    ),
    _metric(
        NATO,
        "equipment_share_pct",
        "Equipment share of defence expenditure",
        "Table 8a, equipment (a) as a percentage of total defence expenditure.",
        "PCT",
    ),
    _metric(
        NATO,
        "equipment_expenditure_usd_current",
        "Equipment expenditure (USD, current)",
        "Derived: Table 2 current-price USD expenditure × Table 8a equipment "
        "share / 100 (plan §30).",
        "USD_MILLION",
    ),
    # EDA (S11)
    _metric(
        EDA,
        "defence_expenditure",
        "Total defence expenditure",
        "Member States sheet: Total Defence Expenditure, million EUR, current prices.",
        "EUR_MILLION",
    ),
    _metric(
        EDA,
        "defence_investment",
        "Defence investment",
        "Member States sheet: Defence Investment (equipment procurement + "
        "R&D), million EUR.",
        "EUR_MILLION",
    ),
    _metric(
        EDA,
        "defence_expenditure_pct_gdp",
        "Total defence expenditure, % of GDP",
        "Member States sheet share of GDP × 100.",
        "PCT_GDP",
    ),
    _metric(
        EDA,
        "defence_expenditure_pct_government",
        "Total defence expenditure, % of government expenditure",
        "Member States sheet share of general government expenditure × 100.",
        "PCT",
    ),
    _metric(
        EDA,
        "defence_expenditure_per_capita",
        "Total defence expenditure per capita",
        "Member States sheet, EUR per capita.",
        "EUR",
    ),
    _metric(
        EDA,
        "equipment_procurement",
        "Defence equipment procurement",
        "Billions sheet: Defence Equipment Procurement Expenditure, million "
        "EUR (2005–2021 only).",
        "EUR_MILLION",
    ),
    _metric(
        EDA,
        "defence_rnd",
        "Defence R&D expenditure",
        "Billions sheet: Defence R&D Expenditure, million EUR (2005–2021 only).",
        "EUR_MILLION",
    ),
    # SIPRI (S11)
    _metric(
        SIPRI,
        "military_expenditure_usd_constant",
        "Military expenditure (USD, constant prices)",
        "Sheet 'Constant (YYYY) US$', million US dollars at constant prices "
        "and exchange rates; the base year is read from the workbook and "
        "appended to the datapoint unit (S39).",
        "USD_MILLION_CONSTANT",
    ),
    _metric(
        SIPRI,
        "military_expenditure_usd_current",
        "Military expenditure (USD, current)",
        "Sheet 'Current US$', million US dollars at current prices and exchange rates.",
        "USD_MILLION",
    ),
    _metric(
        SIPRI,
        "military_expenditure_pct_gdp",
        "Military expenditure, % of GDP",
        "Sheet 'Share of GDP' ratio × 100.",
        "PCT_GDP",
    ),
)

METRICS: dict[tuple[str, str], MetricSpec] = {
    (spec.source_id, spec.metric_id): spec for spec in _METRIC_LIST
}


def source_spec(source_id: str) -> SourceSpec:
    return SOURCES[source_id]


def metric_spec(source_id: str, metric_id: str) -> MetricSpec:
    return METRICS[(source_id, metric_id)]


def metrics_for(source_id: str) -> tuple[MetricSpec, ...]:
    return tuple(spec for spec in _METRIC_LIST if spec.source_id == source_id)

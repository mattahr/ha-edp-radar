"""Country label resolution for XLSX sources and Eurostat code fixes (S7, D2).

Every label observed in the NATO 2025/2026 workbooks, the EDA 2022–2025
workbooks and the SIPRI 1949–2025 v1.2 workbook is listed. Anything else
resolves to ``None`` and the caller records a parse warning; historical
entities and aggregates are listed in ``SKIP_LABELS`` so they produce no
warning.
"""

from __future__ import annotations

import re

_DECORATION = re.compile(r"\*+|\s*\([^)]*\)\s*$")

NORDIC: tuple[str, ...] = ("SE", "FI", "DK", "NO", "IS")

EUROSTAT_GEO_FIXES: dict[str, str] = {"EL": "GR", "UK": "GB"}
EUROSTAT_AGGREGATES: frozenset[str] = frozenset(
    {"EU27_2020", "EU28", "EA", "EA20", "EA19"}
)

SKIP_LABELS: frozenset[str] = frozenset(
    {
        "Czechoslovakia",
        "German Democratic Republic",
        "Yugoslavia",
        "USSR",
        "Yemen, North",
        "European Union",
        "NATO Total",
        "NATO Europe and Canada",
        "EU27",
        "EU 27",
        "EDA 26",
    }
)

COUNTRY_LABELS: dict[str, str] = {
    # Europe (NATO, EDA and SIPRI spellings)
    "Albania": "AL",
    "Austria": "AT",
    "Belgium": "BE",
    "Bosnia and Herzegovina": "BA",
    "Bulgaria": "BG",
    "Croatia": "HR",
    "Cyprus": "CY",
    "Czechia": "CZ",
    "Czech Republic": "CZ",
    "Denmark": "DK",
    "Estonia": "EE",
    "Finland": "FI",
    "France": "FR",
    "Germany": "DE",
    "Greece": "GR",
    "Hungary": "HU",
    "Iceland": "IS",
    "Ireland": "IE",
    "Italy": "IT",
    "Kosovo": "XK",
    "Latvia": "LV",
    "Lithuania": "LT",
    "Luxembourg": "LU",
    "Malta": "MT",
    "Moldova": "MD",
    "Montenegro": "ME",
    "Netherlands": "NL",
    "North Macedonia": "MK",
    "Norway": "NO",
    "Poland": "PL",
    "Portugal": "PT",
    "Romania": "RO",
    "Serbia": "RS",
    "Slovakia": "SK",
    "Slovak Republic": "SK",
    "Slovenia": "SI",
    "Spain": "ES",
    "Sweden": "SE",
    "Switzerland": "CH",
    "Türkiye": "TR",
    "Turkey": "TR",
    "Ukraine": "UA",
    "United Kingdom": "GB",
    "Belarus": "BY",
    "Russia": "RU",
    "Armenia": "AM",
    "Azerbaijan": "AZ",
    "Georgia": "GE",
    # Americas
    "Canada": "CA",
    "United States": "US",
    "United States of America": "US",
    "Mexico": "MX",
    "Belize": "BZ",
    "Costa Rica": "CR",
    "Cuba": "CU",
    "Dominican Republic": "DO",
    "El Salvador": "SV",
    "Guatemala": "GT",
    "Haiti": "HT",
    "Honduras": "HN",
    "Jamaica": "JM",
    "Nicaragua": "NI",
    "Panama": "PA",
    "Trinidad and Tobago": "TT",
    "Argentina": "AR",
    "Bolivia": "BO",
    "Brazil": "BR",
    "Chile": "CL",
    "Colombia": "CO",
    "Ecuador": "EC",
    "Guyana": "GY",
    "Paraguay": "PY",
    "Peru": "PE",
    "Uruguay": "UY",
    "Venezuela": "VE",
    # Africa
    "Algeria": "DZ",
    "Libya": "LY",
    "Morocco": "MA",
    "Tunisia": "TN",
    "Angola": "AO",
    "Benin": "BJ",
    "Botswana": "BW",
    "Burkina Faso": "BF",
    "Burundi": "BI",
    "Cameroon": "CM",
    "Cape Verde": "CV",
    "Central African Republic": "CF",
    "Chad": "TD",
    "Congo, DR": "CD",
    "Congo, Republic": "CG",
    "Cote d'Ivoire": "CI",
    "Djibouti": "DJ",
    "Equatorial Guinea": "GQ",
    "Eritrea": "ER",
    "Ethiopia": "ET",
    "Gabon": "GA",
    "Gambia, The": "GM",
    "Ghana": "GH",
    "Guinea": "GN",
    "Guinea-Bissau": "GW",
    "Kenya": "KE",
    "Lesotho": "LS",
    "Liberia": "LR",
    "Madagascar": "MG",
    "Malawi": "MW",
    "Mali": "ML",
    "Mauritania": "MR",
    "Mauritius": "MU",
    "Mozambique": "MZ",
    "Namibia": "NA",
    "Niger": "NE",
    "Nigeria": "NG",
    "Rwanda": "RW",
    "Senegal": "SN",
    "Seychelles": "SC",
    "Sierra Leone": "SL",
    "Somalia": "SO",
    "South Africa": "ZA",
    "South Sudan": "SS",
    "Sudan": "SD",
    "Eswatini": "SZ",
    "Tanzania": "TZ",
    "Togo": "TG",
    "Uganda": "UG",
    "Zambia": "ZM",
    "Zimbabwe": "ZW",
    # Asia and Oceania
    "Australia": "AU",
    "Fiji": "FJ",
    "New Zealand": "NZ",
    "Papua New Guinea": "PG",
    "Afghanistan": "AF",
    "Bangladesh": "BD",
    "India": "IN",
    "Nepal": "NP",
    "Pakistan": "PK",
    "Sri Lanka": "LK",
    "China": "CN",
    "Japan": "JP",
    "Korea, North": "KP",
    "Korea, South": "KR",
    "Mongolia": "MN",
    "Taiwan": "TW",
    "Brunei": "BN",
    "Cambodia": "KH",
    "Indonesia": "ID",
    "Laos": "LA",
    "Malaysia": "MY",
    "Myanmar": "MM",
    "Philippines": "PH",
    "Singapore": "SG",
    "Thailand": "TH",
    "Timor Leste": "TL",
    "Viet Nam": "VN",
    "Kazakhstan": "KZ",
    "Kyrgyz Republic": "KG",
    "Tajikistan": "TJ",
    "Turkmenistan": "TM",
    "Uzbekistan": "UZ",
    # Middle East
    "Bahrain": "BH",
    "Egypt": "EG",
    "Iran": "IR",
    "Iraq": "IQ",
    "Israel": "IL",
    "Jordan": "JO",
    "Kuwait": "KW",
    "Lebanon": "LB",
    "Oman": "OM",
    "Qatar": "QA",
    "Saudi Arabia": "SA",
    "Syria": "SY",
    "United Arab Emirates": "AE",
    "Yemen": "YE",
}


def normalise_label(label: str) -> str:
    """Strip footnote asterisks, a trailing ``(currency)`` and whitespace."""
    return _DECORATION.sub("", label).strip()


def is_skipped_label(label: str) -> bool:
    """Aggregates and dissolved states that are deliberately not countries."""
    return normalise_label(label) in SKIP_LABELS


def resolve_country(label: str) -> str | None:
    """Alpha-2 code for a source label; ``None`` when unknown or skipped (see
    ``is_skipped_label`` to tell the two apart)."""
    plain = normalise_label(label)
    if plain in SKIP_LABELS:
        return None
    return COUNTRY_LABELS.get(plain)

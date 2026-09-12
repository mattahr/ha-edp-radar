# Provider: NATO defence expenditure

| Item | Value |
| --- | --- |
| Canonical discovery URL | `https://www.nato.int/en/what-we-do/introduction-to-nato/defence-expenditures-and-natos-5-commitment` ("Archive of tables": `def-exp-YYYY-en.pdf` per year) |
| Verified (2026-09-12) | newest year 2026 → `https://www.nato.int/content/dam/nato/webready/documents/finance/def-exp-2026-en.xlsx` (69 931 bytes, `ETag "0x8DEDE695735E099"`, `Last-Modified Fri, 10 Jul 2026 09:55:14 GMT`); 2025 workbook also available (108 341 bytes) |
| Format | XLSX, sheets `Table 1` … `Table 8b`; each sheet: title in A1 (`Table N: …`), unit rows, then blocks of `<blank> ; 2014 … 2024 ; 2025e ; 2026e` header + country rows; aggregate rows `NATO Europe and Canada`, `NATO Total`; `Notes:` row at the end |
| Cadence | Annual (June/July), occasionally revised in between |
| Publication date | `Last-Modified` of the XLSX (the topic page has no date) |
| Reference period | Calendar year; `e` suffix = estimate |

## Metric mapping (S11)

| Sheet / block | Subtitle check | metric_id | unit |
| --- | --- | --- | --- |
| Table 1 / 0 | "current prices" | `defence_expenditure_nac` (flag `currency:<name>` from the label) | NAC_MILLION |
| Table 2 / 0 | "current prices" | `defence_expenditure_usd_current` | USD_MILLION |
| Table 2 / 1 | "constant 2021" | `defence_expenditure_usd_constant` | USD_MILLION_CONSTANT_2021 |
| Table 3 / 0 | "share of real gdp" | `defence_expenditure_pct_gdp` | PCT_GDP |
| Table 8a / 0 | "equipment" | `equipment_share_pct` | PCT |
| derived | — | `equipment_expenditure_usd_current` = USD current × equipment share / 100 (flag `derived`; estimate if either input is) | USD_MILLION |

## Status semantics

Header `YYYYe` → `estimate`; otherwise `actual`. The 2026 workbook marks 2025 and 2026 as estimates; the 2025 workbook 2024 and 2025. Country labels with `*` carry `footnote_star` (2026: Slovenia; 2025: eleven allies with revised figures). Aggregates are skipped.

## Parser assumptions

- Sheet names `Table 1`, `Table 2`, `Table 3`, `Table 8a` exist; A1 starts with `Table N:` (2025: "Defence expenditure", 2026: "Core defence expenditure" — the prefix is what is checked, the full titles form the layout fingerprint).
- Blocks are header rows with an empty first cell and year cells; the nearest non-empty row above must contain the expected subtitle keyword.
- Country rows end at a blank row or a `Notes` row. Iceland has no row (no armed forces).

## Known weaknesses

- Equipment value is derived, not published; the derivation is explicit and tested (plan §30).
- Discovery depends on the archive anchor pattern `def-exp-YYYY-en.pdf` and on the XLSX sharing its path.

## Fixtures

`tests/fixtures/spending/nato/def-exp-2026-en.xlsx`, `def-exp-2025-en.xlsx` (whole workbooks), `topic-page.html` (archive anchors only).

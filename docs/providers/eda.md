# Provider: EDA defence data

Profiled 2026-09-12 on the workbooks linked from the portal (plan §36).

| Item | Value |
| --- | --- |
| Canonical discovery URL | `https://www.eda.europa.eu/publications-and-data/defence-data` |
| Verified links | anchors `<a href='…xlsx'><span>Defence Data YYYY</span></a>` for 2020–2025: `final-defence-data-2025-1.xlsx`, `defence-data-2024.xlsx`, `defence-data-2023.xlsx`, `eda-2022-defence-data.xlsx`, `defence-data-2021.xlsx`, `data-by-pms-for-the-eda-website.xlsx` (2020); `Last-Modified` present on the files |
| Layout 2022–2025 | sheets `EU27` (aggregates only), `Billions` (26 countries × 2005–2021, long format), `Member States[ YYYY]` (27 countries, **one year per workbook**) |
| Layout 2020–2021 | one sheet per country, years 2017–2021 — subset of `Billions`; **not used** |
| Formulas | workbooks contain formulas (cached values are read with `data_only`); fixtures are therefore kept as the original bytes |
| Cadence | Annual (Defence Data report, late summer/autumn); revisions possible |
| Publication date | `Last-Modified` of the newest workbook |
| Reference period | Calendar year |

## Sheets and columns

`Member States` header (normalised): `eu ms | year | total defence expenditure | defence investment | total defence expenditure as % of gdp | total defence expenditure as % of government expenditure | total defence expenditure per capita`. Values: EUR million (current prices), ratios as fractions, EUR per capita. Footnote rows start with `*`: `*Estimated 2025 figures` (labels with one `*`), `**Luxembourg … GNI`, `***Slovenia …`. Labels may carry trailing spaces (`Croatia `) and use `Czech Republic`.

`Billions` header: `pms | year | total defence expenditure | defence equipment procurement expenditure | defence r&d expenditure | defence investment | gdp (mrd) | total defence expenditure as % of gdp`. Despite the sheet name the expenditure columns are EUR million (Sweden 2021 = 6 000 = EUR 6.0 bn); `gdp (mrd)` is EUR billion. 26 countries (no Denmark), 2005–2021, identical in the 2022–2025 workbooks (frozen history). `-` = not available.

## Metric verdicts (plan §39)

| metric_id | Source sheet | Years | Verdict |
| --- | --- | --- | --- |
| `defence_expenditure` | Member States (2022+), Billions (2005–2021) | 2005–2025 | GREEN |
| `defence_investment` | Member States, Billions | 2005–2025 | GREEN |
| `defence_expenditure_pct_gdp` | Member States, Billions (×100) | 2005–2025 | GREEN |
| `defence_expenditure_pct_government` | Member States (×100) | 2022–2025 | GREEN |
| `defence_expenditure_per_capita` | Member States | 2022–2025 | GREEN |
| `equipment_procurement` | Billions only | 2005–2021 | GREEN for history, **not available for current years** at country level |
| `defence_rnd` | Billions only | 2005–2021 | GREEN for history only |
| collaborative procurement / R&T | `EU27` aggregates only | — | not exposed (no country level) |

## Status semantics

Member States: label with exactly one `*` and a footnote row starting with `*Estimated` → `estimate`; otherwise `actual`. `**` → flag `note_2`, `***` → flag `note_3`. Billions: `actual`, flag `sheet:billions`.

## Parser assumptions

- One sheet whose name starts with `Member States` per workbook; header matched by normalised prefixes; `Year` column gives the reference year.
- `Billions` is read from the newest workbook only.
- Workbooks before 2022 are ignored (different layout, no additional data).

## Known weaknesses

- Country-level equipment procurement stops in 2021; the `EU27` sheet has newer aggregates only.
- Denmark is absent from `Billions` (joined the data set in 2021).

## Fixtures

`tests/fixtures/spending/eda/portal.html` (anchors only), `defence-data-2025.xlsx`, `defence-data-2022.xlsx` (original bytes).

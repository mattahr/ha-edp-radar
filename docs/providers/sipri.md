# Provider: SIPRI Military Expenditure Database

| Item | Value |
| --- | --- |
| Canonical discovery URL | `https://www.sipri.org/databases/milex` |
| Verified (2026-09-12) | link `//www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2025_v1.2.xlsx` (922 552 bytes, `Last-Modified Mon, 27 Apr 2026 15:20:25 GMT`, ETag present); page text "revised on 27 April 2026 at 19:00 CET … replaces all previous versions" |
| Format | XLSX; sheets `Front page`, `Regional totals`, `Local currency financial years`, `Local currency calendar years`, `Constant (2024) US$`, `Current US$`, `Share of GDP`, `Per capita`, `Share of Govt. spending`, `Footnotes` |
| Cadence | Annual (late April), in-year revisions replace the file |
| Publication date | revision date from the landing page, else `Last-Modified` |
| Reference period | Calendar year (financial-year sheet not used) |
| Official | No — independent research dataset built from open sources |

## Sheet layout

Rows 1–4 title/legend ("Figures in blue are SIPRI estimates. Figures in red indicate highly uncertain data." and the missing-value legend); header row starts with `Country` (row 6; `Notes` column at B or C; year columns 1949–2025 as integers); region rows (`Africa`, `Europe`, `Western Europe`, …) have no values; `...`/`. .` = unavailable, `xxx` = country did not exist. Historical entities (`USSR`, `Yugoslavia`, `Czechoslovakia`, `German Democratic Republic`, `Yemen, North`, `European Union`) are skipped.

## Metric mapping (S11)

| Sheet | metric_id | unit |
| --- | --- | --- |
| `Constant (2024) US$` | `military_expenditure_usd_constant` | USD_MILLION_CONSTANT_2024 |
| `Current US$` | `military_expenditure_usd_current` | USD_MILLION |
| `Share of GDP` (ratio × 100) | `military_expenditure_pct_gdp` | PCT_GDP |

Only years ≥ 1990 are stored (`MIN_YEAR`, storage size); the workbook goes back to 1949.

## Status and flags

- Blue font (indexed colour 12) → `estimate`; red font (10) → flag `highly_uncertain`.
- Notes `§` (adopted budget, not actual expenditure) → `budget`; `†` → `excludes_pensions`; `‡` → `current_spending_only`; `¶` → `excludes_paramilitary`; `‖` → `currency_redenominated`; numbered footnotes → `footnote_<n>`.
- Everything else → `actual` = "SIPRI reported figure" (not an official outturn, plan §44).

## Parser assumptions

- The colour legend row (containing "blue") and the `Country` header row exist on every sheet (`SchemaChangedError` otherwise).
- Font colours are read from cell styles; the fixture preserves them.

## Fetch validators

The workbook GET does not reliably repeat the `ETag`/`Last-Modified` headers
already captured by the landing-page HEAD request, so `async_fetch_release`
keeps the discovery-time validators unless the GET response supplies fresher
ones (mirrors the EDA provider's approach of not overwriting validators with
absent ones).

## Known weaknesses

- Full re-import on every new release; revisions to any year are detected by the store diff.
- Sweden's 1957–1979 values are SIPRI estimates (blue); below `MIN_YEAR` anyway.

## Fixtures

`tests/fixtures/spending/sipri/landing.html` (link + revision sentence), `milex-trimmed.xlsx` (three sheets; rows from `Europe` onwards: 59 countries incl. Middle East).

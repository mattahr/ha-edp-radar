# Provider: Statskontoret monthly budget outturn

| Item | Value |
| --- | --- |
| Canonical discovery URL | `https://www.statskontoret.se/analys-och-statistik/oppna-data/manadsutfall/?year=YYYY` |
| Verified example (2026-09-12) | `Utgifter juli 2026`, `Senast uppdaterad 2026-08-24`, Zip link `GetFile?documentType=Utgift&fileType=Zip&…&Year=2026&month=7&status=Definitiv` |
| Format | Zip containing one CSV: `;`-delimited, UTF-8 with BOM, decimal comma, 31 columns, one row per appropriation item × agency × year, months as columns (`Utfall januari` … `Utfall december`), values in SEK million |
| Coverage | January 2006 → release month; every release contains the full history |
| Licence | CC0 (stated on the page) |
| Cadence | Monthly, "senast sista vardagen i månaden efter aktuell utfallsmånad" |
| Publication date | `Senast uppdaterad` on the discovery page (the Zip has no `Last-Modified`) |
| Reference period | Calendar month; YTD is computed from months |

## Metric mapping (S9)

| metric_id | Rows | Unit |
| --- | --- | --- |
| `uo6_total_outturn` | `Utgiftsområde == "06"` | SEK_MILLION |
| `uo6_defence_outturn` | `Anslag` starts with `0601` (1:1–1:14) | SEK_MILLION |
| `materiel_outturn` | `Anslag == "0601003"` (1:3 Anskaffning av materiel och anläggningar; FMV and Försvarsmakten items incl. Läglighetsköp) | SEK_MILLION |

## Status semantics

`status=Definitiv` → `actual`; `status=Preliminär 1` → `preliminary` **for the release month only** (earlier months in a preliminary file equal the earlier definitive releases). December appears twice: preliminary (late January) and definitive (late March). The definitive release replaces the preliminary datapoints (same key) and records a revision when the value differs — December 2025 materiel: 19 729.43 → 23 327.02. The definitive-December flag is read at discovery and only takes effect at the next parse, so if the definitive December file appears on the site before that next monthly release runs, the stored December datapoint keeps its preliminary value and status until that release (at most about a month).

## Parser assumptions

- Columns are looked up by name; `Utgiftsområde`, `Anslag`, `År` and the twelve month columns are required (`SchemaChangedError` otherwise).
- Rows with `Utgiftsområde != "06"` are ignored; a file without UO6 rows fails.
- Empty month cells mean "not yet reported"; a month is emitted only when at least one row has a value.
- Release year/month/status are read from the `GetFile` query parameters.

## Known weaknesses

- No budget figure (anslagsbelopp) in the CSV: budget utilisation needs another official source (see `docs/phase3-source-profile.md`).
- The discovery page is HTML; the parser depends on `<li class="data">`, `<h2>`, `<dt>Senast uppdaterad</dt><dd>` and the `GetFile` query parameters.
- December status window (S26): between the January release and the definitive December release in late March, the selected `?year=<Y>` page's December Y-1 column holds the preliminary figure but is labelled `actual`, since only the release month carries the release status.

## Fixtures

`tests/fixtures/spending/statskontoret/` — `discovery-2026.html`, `discovery-2025.html`, `utgifter-2026-07.csv`, `utgifter-2025-12-preliminar.csv`, `utgifter-2025-12-definitiv.csv` (trimmed to UO6 rows 2025–2026 by `scripts/fetch_spending_fixtures.py`).

# Phase 3 source profile

Generated 2026-09-14T23:25:24+00:00 by `scripts/spending_profile.py` (report date 2026-09-13). Plan §70 profile per provider, then the plan §71 factual validation. Values are aggregates and Sweden facts with provenance; no raw payloads.

## Statskontoret monthly budget outturn

| Item | Value |
| --- | --- |
| technical access confirmed | yes |
| discovery method | https://www.statskontoret.se/analys-och-statistik/oppna-data/manadsutfall/ → https://www.statskontoret.se/OpenDataManadsUtfallPage/GetFile?documentType=Utgift&fileType=Zip&fileName=M%C3%A5nadsutfall%20utgifter%20januari%202006%20-%20juli%202026,%20definitivt.zip&Year=2026&month=7&status=Definitiv |
| format | csv |
| latest release found | `2026-07-definitiv-2026-08-24` published 2026-08-24 (etag None, checksum e3bfd695c07d…) |
| latest reference period | 2026-07-31 |
| available countries | 1: SE |
| available metrics | materiel_outturn (211), uo6_defence_outturn (247), uo6_total_outturn (247) |
| actual/estimate/projection distinctions | actual: 705 |
| source publication date available | yes |
| revision behaviour | Every monthly file carries the full history; December is published as preliminär then definitiv. The store diff records changed values as revisions. |
| missing data | materiel_outturn Jul 2026: 1/1 countries; uo6_defence_outturn Jul 2026: 1/1 countries; uo6_total_outturn Jul 2026: 1/1 countries |
| parser risk | HTML discovery markup (`li.data`, `Senast uppdaterad`, GetFile query) and CSV column names. |
| freshness today | current (publication age 20 d, reference age 44 d) |
| layout fingerprint | `Utgiftsområde;Utgiftsområdesnamn;Anslag;Anslagsnamn;Anslagspost;Anslagspostsnamn;Anslagsdelpost;Anslagsdelpostsnamn;Myndighet;Organisationsnummer;År;Utfall janu` |

## Eurostat gov_ev defence expenditure and investment

| Item | Value |
| --- | --- |
| technical access confirmed | yes |
| discovery method | https://ec.europa.eu/eurostat/cache/metadata/en/gov_ev_esms.htm → https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_ev?lang=en&expend=DEF&na_item=TE&na_item=P51G&unit=MIO_EUR&unit=PC_GDP&unit=MIO_NAC |
| format | json-stat |
| latest release found | `2026-04-27T23:00:00+0200` published 2026-04-27 (etag None, checksum f5bbd2ae0c00…) |
| latest reference period | 2025-12-31 |
| available countries | 27: AT, BE, BG, CY, CZ, DE, DK, EE, ES, FI, FR, GR, HR, HU, IE, IT, LT, LU, LV, MT, NL, PL, PT, RO, SE, SI, SK |
| available metrics | defence_expenditure (122), defence_expenditure_nac (122), defence_expenditure_pct_gdp (122), defence_investment (135), defence_investment_nac (135), defence_investment_pct_gdp (135) |
| actual/estimate/projection distinctions | actual: 771 |
| source publication date available | yes |
| revision behaviour | Twice-yearly dissemination may revise earlier years; `updated` changes the release id and the store diff records revisions. |
| missing data | defence_expenditure 2025: 22/27 countries; defence_expenditure_nac 2025: 22/27 countries; defence_expenditure_pct_gdp 2025: 22/27 countries; defence_investment 2025: 27/27 countries; defence_investment_nac 2025: 27/27 countries; defence_investment_pct_gdp 2025: 27/27 countries |
| parser risk | Dimension/unit codes; a renamed code fails discovery of the metric (SchemaChangedError). |
| freshness today | current (publication age 139 d, reference age 256 d) |
| layout fingerprint | `freq,expend,na_item,unit,geo,time` |

## NATO defence expenditure of NATO countries

| Item | Value |
| --- | --- |
| technical access confirmed | yes |
| discovery method | https://www.nato.int/en/what-we-do/introduction-to-nato/defence-expenditures-and-natos-5-commitment → https://www.nato.int/content/dam/nato/webready/documents/finance/def-exp-2026-en.xlsx |
| format | xlsx |
| latest release found | `2026:"0x8DEDE695735E099"` published 2026-07-10 (etag '"0x8DEDE695735E099"', checksum 11e302d3f556…) |
| latest reference period | 2026-12-31 |
| available countries | 31: AL, BE, BG, CA, CZ, DE, DK, EE, ES, FI, FR, GB, GR, HR, HU, IT, LT, LU, LV, ME, MK, NL, NO, PL, PT, RO, SE, SI, SK, TR, US |
| available metrics | defence_expenditure_nac (403), defence_expenditure_pct_gdp (403), defence_expenditure_usd_constant (403), defence_expenditure_usd_current (403), equipment_expenditure_usd_current (403), equipment_share_pct (403) |
| actual/estimate/projection distinctions | actual: 2046, estimate: 372 |
| source publication date available | yes |
| revision behaviour | Each annual workbook restates 2014 onwards and re-marks the last two years as estimates; revisions detected by the store diff. |
| missing data | defence_expenditure_nac 2026: 31/31 countries; defence_expenditure_usd_current 2026: 31/31 countries; defence_expenditure_usd_constant 2026: 31/31 countries; defence_expenditure_pct_gdp 2026: 31/31 countries; equipment_share_pct 2026: 31/31 countries; equipment_expenditure_usd_current 2026: 31/31 countries |
| parser risk | Sheet names, `Table N:` titles, block subtitles, `YYYYe` headers, label spellings; XLSX must share the PDF path. |
| freshness today | current (publication age 65 d, reference age -109 d (reference period ends 2026-12-31, not yet complete)) |
| layout fingerprint | `Table 1: Core defence expenditure | Table 2: Core defence expenditure | Table 3: Core defence expenditure as a share of GDP and annual real change | Table 8a: D` |

## EDA defence data

| Item | Value |
| --- | --- |
| technical access confirmed | yes |
| discovery method | https://www.eda.europa.eu/publications-and-data/defence-data → https://www.eda.europa.eu/docs/default-source/documents/defence-data/final-defence-data-2025-1.xlsx |
| format | xlsx |
| latest release found | `2025:bed42c278fb4068d` published 2026-09-04 (etag None, checksum e952aa51eb81…) |
| latest reference period | 2025-12-31 |
| available countries | 27: AT, BE, BG, CY, CZ, DE, DK, EE, ES, FI, FR, GR, HR, HU, IE, IT, LT, LU, LV, MT, NL, PL, PT, RO, SE, SI, SK |
| available metrics | defence_expenditure (540), defence_expenditure_pct_gdp (540), defence_expenditure_pct_government (108), defence_expenditure_per_capita (108), defence_investment (539), defence_rnd (430), equipment_procurement (432) |
| actual/estimate/projection distinctions | actual: 2662, estimate: 35 |
| source publication date available | yes |
| revision behaviour | Occasional in-year revisions (EDA statement); every workbook ≥ 2022 is re-fetched and compared. |
| missing data | defence_expenditure 2025: 27/27 countries; defence_investment 2025: 27/27 countries; defence_expenditure_pct_gdp 2025: 27/27 countries; defence_expenditure_pct_government 2025: 27/27 countries; defence_expenditure_per_capita 2025: 27/27 countries; equipment_procurement 2021: 26/27 countries; defence_rnd 2021: 26/27 countries |
| parser risk | Portal anchor text `Defence Data YYYY`, `Member States` sheet header wording, footnote conventions. |
| freshness today | current (publication age 9 d, reference age 256 d) |
| layout fingerprint | `2025:Member States 2025 | Billions | 2024:Member States 2024 | 2023:Member States 2023 | 2022:Member States` |

## SIPRI military expenditure database

| Item | Value |
| --- | --- |
| technical access confirmed | yes |
| discovery method | https://www.sipri.org/databases/milex → https://www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2025_v1.2.xlsx |
| format | xlsx |
| latest release found | `SIPRI-Milex-data-1949-2025_v1.2.xlsx:2026-04-27` published 2026-04-27 (etag '"e13b8-65072a76c0127"', checksum 6cc3a30b1064…) |
| latest reference period | 2025-12-31 |
| available countries | 168: AE, AF, AL, AM, AO, AR, AT, AU, AZ, BA, BD, BE, BF, BG, BH, BI, BJ, BN, BO, BR, BW, BY, BZ, CA, CD, CF, CG, CH, CI, CL, CM, CN, CO, CR, CU, CV, CY, CZ, DE, DJ, DK, DO, DZ, EC, EE, EG, ER, ES, ET, FI, FJ, FR, GA, GB, GE, GH, GM, GN, GQ, GR, GT, GW, GY, HN, HR, HT, HU, ID, IE, IL, IN, IQ, IR, IS, IT, JM, JO, JP, KE, KG, KH, KP, KR, KW, KZ, LA, LB, LK, LR, LS, LT, LU, LV, LY, MA, MD, ME, MG, MK, ML, MM, MN, MR, MT, MU, MW, MX, MY, MZ, NA, NE, NG, NI, NL, NO, NP, NZ, OM, PA, PE, PG, PH, PK, PL, PT, PY, QA, RO, RS, RU, RW, SA, SC, SD, SE, SG, SI, SK, SL, SN, SO, SS, SV, SY, SZ, TD, TG, TH, TJ, TL, TM, TN, TR, TT, TW, TZ, UA, UG, US, UY, UZ, VE, VN, XK, YE, ZA, ZM, ZW |
| available metrics | military_expenditure_pct_gdp (5370), military_expenditure_usd_constant (5289), military_expenditure_usd_current (5377) |
| actual/estimate/projection distinctions | actual: 10745, budget: 3106, estimate: 2185 |
| source publication date available | yes |
| revision behaviour | Annual release plus in-year revisions replacing the file; full re-import and store diff. |
| missing data | military_expenditure_usd_constant 2025: 151/168 countries; military_expenditure_usd_current 2025: 151/168 countries; military_expenditure_pct_gdp 2025: 151/168 countries |
| parser risk | Landing-page anchor and revision sentence; header row `Country`; colour semantics (blue/red). |
| freshness today | current (publication age 139 d, reference age 256 d) |
| layout fingerprint | `Constant (2024) US$: Figures in blue are SIPRI estimates. Figures in red indicate highly uncertain data. | Current US$: Figures in blue are SIPRI estimates. Fig` |

# Factual validation (plan §71)

## Statskontoret

- Latest Swedish reference month: **Jul 2026** (status actual)
- Materiel acquisition latest month: SEK 3,753.5 m
- Materiel acquisition YTD Jan–Jul 2026: SEK 25,877.0 m; same period 2025: SEK 19,905.4 m; nominal change 30.0 %
- Defence appropriations (1:1–1:14) YTD: SEK 81,422.4 m; UO6 total YTD: SEK 87,336.3 m
- Publication date: 2026-08-24; release `2026-07-definitiv-2026-08-24`
- Budget utilisation (plan §53): human-readable page https://www.statskontoret.se/analys-och-statistik/utfall/utfall-for-statens-budget/?year=2026&month=7 — SB + ÄB column present: True, UO6 row present: False. No per-expenditure-area budget with provenance found; budget utilisation is omitted (S16).

## Eurostat

- defence_expenditure 2025 (EUR_MILLION, statuses actual): Sweden #4 of 22, 17,196.9; top DE 68,824.0; median 3,808.3; Nordic: SE #4 17,196.9, DK #5 8,997.7, FI #9 4,750.0
- defence_expenditure_pct_gdp 2025 (PCT_GDP, statuses actual): Sweden #4 of 22, 2.9; top EE 4.2; median 1.8; Nordic: SE #4 2.9, DK #7 2.2, FI #12 1.7
- defence_investment 2025 (EUR_MILLION, statuses actual): Sweden #5 of 27, 4,864.3; top PL 14,736.4; median 1,048.6; Nordic: SE #5 4,864.3, DK #10 1,372.4, FI #16 883.0
- defence_investment_pct_gdp 2025 (PCT_GDP, statuses actual): Sweden #5 of 27, 0.8; top EE 1.6; median 0.4; Nordic: SE #5 0.8, DK #18 0.3, FI #20 0.3

## NATO

- Actual years 2014–2024; estimate years [2025, 2026]
- defence_expenditure_usd_current 2026 (USD_MILLION, statuses estimate): Sweden #11 of 31, 24,186.0; top US 1,032,849.0; median 11,275.0; Nordic: SE #11 24,186.0, NO #12 19,247.0, DK #13 17,615.0, FI #17 9,027.0
- defence_expenditure_pct_gdp 2026 (PCT_GDP, statuses estimate): Sweden #7 of 31, 3.2; top LT 5.3; median 2.2; Nordic: DK #6 3.5, SE #7 3.2, NO #8 3.2, FI #12 2.6
- equipment_share_pct 2026 (PCT, statuses estimate): Sweden #25 of 31, 25.4; top PL 55.9; median 34.0; Nordic: FI #12 36.7, DK #13 34.6, SE #25 25.4, NO #31 18.0
- equipment_expenditure_usd_current 2026 (USD_MILLION, statuses estimate): Sweden #11 of 31, 6,145.7; top US 292,399.6; median 3,454.8; Nordic: SE #11 6,145.7, DK #12 6,103.6, NO #16 3,454.8, FI #17 3,310.2

## EDA

- defence_expenditure: latest 2025, Sweden available
- defence_investment: latest 2025, Sweden available
- defence_expenditure_pct_gdp: latest 2025, Sweden available
- defence_expenditure_pct_government: latest 2025, Sweden available
- defence_expenditure_per_capita: latest 2025, Sweden available
- equipment_procurement: latest 2021, Sweden available
- defence_rnd: latest 2021, Sweden available
- defence_expenditure 2025 (EUR_MILLION, statuses actual/estimate): Sweden #7 of 27, 14,789.0; top DE 106,899.0; median 5,393.0; Nordic: SE #7 14,789.0, DK #8 13,493.7, FI #11 8,052.1
- defence_investment 2025 (EUR_MILLION, statuses actual/estimate): Sweden #7 of 27, 4,227.9; top DE 31,610.0; median 1,715.6; Nordic: SE #7 4,227.9, DK #8 4,207.5, FI #9 3,543.7
- equipment_procurement 2021 (EUR_MILLION, statuses actual): Sweden #9 of 26, 1,500.0; top DE 7,354.9; median 607.5; Nordic: FI #8 1,983.0, SE #9 1,500.0

## SIPRI

- Sweden available 1990–2025 (stored from MIN_YEAR; the workbook starts 1949)
- military_expenditure_usd_constant 2025 (USD_MILLION_CONSTANT_2024, statuses actual/budget/estimate): Sweden #26 of 151, 14,954.1; top US 929,162.9; median 1,263.4; Nordic: NO #24 16,085.4, SE #26 14,954.1, DK #27 14,083.0, FI #36 7,614.1, IS #150 0.0
- military_expenditure_pct_gdp 2025 (PCT_GDP, statuses actual/budget/estimate): Sweden #38 of 151, 2.5; top UA 39.6; median 1.7; Nordic: NO #18 3.3, DK #19 3.3, FI #35 2.6, SE #38 2.5, IS #150 0.0

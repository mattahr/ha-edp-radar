# Provider: Eurostat `gov_ev`

| Item | Value |
| --- | --- |
| Canonical metadata URL | `https://ec.europa.eu/eurostat/cache/metadata/en/gov_ev_esms.htm` |
| Request (fixed) | `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_ev?lang=en&expend=DEF&na_item=TE&na_item=P51G&unit=MIO_EUR&unit=PC_GDP&unit=MIO_NAC` |
| Verified (2026-09-13) | `updated 2026-04-27T23:00:00+0200`; dimensions `freq=A`, `expend=DEF`, `na_item=P51G,TE`, `unit=MIO_EUR,MIO_NAC,PC_GDP`, `geo` = EU27_2020 + 27 member states (`EL` = Greece), `time` 2021–2025; 771 country values, no `status` flags |
| Format | JSON-stat 2.0 |
| Cadence | Reported twice yearly (end of March, end of September); disseminated twice yearly |
| Publication date | `updated` in the response (also the release id) |
| Reference period | Calendar year |

## Metric mapping (S10)

| na_item | unit | metric_id | unit |
| --- | --- | --- | --- |
| TE | MIO_EUR | `defence_expenditure` | EUR_MILLION |
| TE | MIO_NAC | `defence_expenditure_nac` | NAC_MILLION |
| TE | PC_GDP | `defence_expenditure_pct_gdp` | PCT_GDP |
| P51G | MIO_EUR | `defence_investment` | EUR_MILLION |
| P51G | MIO_NAC | `defence_investment_nac` | NAC_MILLION |
| P51G | PC_GDP | `defence_investment_pct_gdp` | PCT_GDP |

## Status semantics

JSON-stat `status` flags per observation: `p` → provisional, `e` → estimate, `f` → projection, anything else → `actual` with the flag kept in `flags`. The 2026-04 dissemination carries no flags at all; April/October are never inferred as preliminary/final (plan §23).

## Parser assumptions

- `class == "dataset"`, `id`/`size`/`dimension`/`value` present; flat indexes computed from `size` (row-major, last dimension fastest).
- Codes `DEF`, `TE`, `P51G`, `MIO_EUR`, `PC_GDP`, `MIO_NAC` must exist (`SchemaChangedError` otherwise).
- `EL → GR`, `UK → GB`; `EU27_2020` and other aggregates are skipped.
- Missing observations (e.g. IT/ES/NL 2025 in the 2026-04 release) produce no datapoint.

## Known weaknesses

- Coverage starts 2021; `gov_10a_exp` (COFOG) is a separate, future series (plan §25).
- Fewer countries report the latest year: rankings must state population size.

## Fixtures

`tests/fixtures/spending/eurostat/gov_ev-defence.json` (complete real response, 13 KB).

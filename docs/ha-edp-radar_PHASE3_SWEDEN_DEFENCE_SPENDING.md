# ha-edp-radar — Phase 3: Sweden Defence Spending & International Benchmarks

**Status:** Complete implementation plan  
**Assumption:** Phase 1 and Phase 2 already exist or are being implemented.  
**Primary focus:** Sweden  
**Primary question:** What is Sweden spending on defence and materiel, how current is the information, and how does Sweden compare with other countries?  
**Plan updated:** 2026-09-12

---

# 1. Purpose

Phase 3 adds a **defence spending layer** to `ha-edp-radar`.

Phase 2 answers primarily:

> Which countries have the largest publicly reported awarded defence procurement values?

Phase 3 adds:

> How much is Sweden actually spending on defence and materiel, how does that compare with other countries, and how current is each figure?

The integration remains factual.

It must not:

- interpret whether spending is sufficient,
- make political judgements,
- generate advice,
- infer intent,
- produce AI-generated narratives,
- combine incompatible definitions into a synthetic "true defence spending" number.

The user should see the facts, definitions, provenance, age and status of the information and draw conclusions independently.

---

# 2. Sweden is fixed as the primary country

From Phase 3 onward, the integration is specifically Sweden-focused.

The main country is:

```text
Sweden / SE
```

Other countries exist primarily for:

- ranking,
- comparison,
- trend comparison,
- contextualising Sweden.

The integration should still retain all country-level data exposed by each international source.

---

# 3. Questions Phase 3 should eventually answer

## Sweden now

1. How much has Sweden spent on defence so far this year?
2. How much has Sweden spent on materiel acquisition so far this year?
3. What was the latest month's spending?
4. How does YTD spending compare with the same period last year?
5. How much of the current annual budget has been used?
6. How old is the latest Swedish spending information?

## Sweden over time

7. How has Swedish defence spending changed historically?
8. How has equipment/materiel spending changed?
9. How much of Swedish defence spending goes to equipment?
10. How do current levels compare with previous years?

## Sweden compared with others

11. Which countries spend the most on defence?
12. Where does Sweden rank?
13. Which countries spend the most on major equipment / equipment procurement?
14. Where does Sweden rank on those measures?
15. What percentage of GDP does Sweden spend compared with others?
16. How quickly is Sweden's spending changing relative to others?
17. How much of the international comparison is actual data versus estimates/projections?

## Procurement versus expenditure

18. How does Sweden's TED awarded-contract activity compare with national spending/outturn?
19. Is awarded procurement activity moving in the same direction as Swedish materiel expenditure?
20. How does the recent TED picture relate to slower official annual international statistics?

These different measures should be displayed side by side.

They must not automatically be added together.

---

# 4. Phase 3 principle: technical feasibility first

No source enters Phase 3 merely because useful information exists on a website.

For every provider, we must verify:

```text
Can the data be discovered automatically?
Can it be downloaded automatically?
Is the format stable enough to parse?
Can the relevant metrics be identified without manual work?
Can source publication date be obtained?
Can reference period be obtained?
Can actual / preliminary / estimate / projection be distinguished?
Can source revisions be detected?
Can the process be tested with fixtures?
```

If any source fails this feasibility gate, it remains experimental and must not be used for production sensors.

The preferred workflow is:

```text
SOURCE DISCOVERY
      ↓
TECHNICAL FEASIBILITY
      ↓
INGEST
      ↓
NORMALISE METADATA
      ↓
VERIFY DEFINITIONS
      ↓
PROFILE COVERAGE
      ↓
COMPARE SOURCES
      ↓
DESIGN SENSORS
```

---

# 5. Provider feasibility summary

| Source | Primary role | Access method | Format | Expected cadence | Feasibility |
|---|---|---|---|---|---|
| Statskontoret | Swedish current budget outturn | Official discovery page + download links | CSV / XLSX | Monthly | GREEN |
| TED | Awarded procurement activity | Existing Search API from Phase 1/2 | JSON | Business-day / near-daily | GREEN |
| Eurostat `gov_ev` | Harmonised EU defence expenditure/investment | Official REST API | JSON-stat 2.0 | Data reported twice yearly | GREEN |
| NATO Defence Expenditure | Harmonised NATO comparison | Official publication page + XLSX | XLSX | Periodic / annual | GREEN |
| EDA Defence Data | EU defence/equipment benchmark | Official portal + XLSX | XLSX | Annual | GREEN for access, YELLOW until metric coverage profiled |
| SIPRI Military Expenditure | Long historical/global comparison | Official landing page + XLSX | XLSX | Annual | GREEN |

No core Phase 3 provider is currently considered technically blocked.

---

# 6. Every datapoint must carry provenance

This is a mandatory design rule.

A numeric value is not sufficient.

Every datapoint must be able to answer:

```text
What does this measure?
Where did it come from?
What period does it describe?
When was it published?
When did we retrieve it?
How old is the underlying reference period?
Is it actual, preliminary, provisional, estimated, projected, or budget?
What unit/currency is it expressed in?
```

Conceptual model:

```yaml
metric: sweden_materiel_outturn_ytd
value: 48.2
unit: SEK billion

country: SE

source:
  id: statskontoret_monthly_outturn
  publisher: Statskontoret
  dataset: Månadsutfall för statens budget
  url: https://www.statskontoret.se/...

reference_period:
  start: 2026-01-01
  end: 2026-08-31

published_at: 2026-09-xx
retrieved_at: 2026-09-12T23:00:00+02:00

publication_age_days: 4
reference_age_days: 12

status: actual
source_revision: null
```

The exact implementation may differ.

The metadata itself is mandatory.

---

# 7. Two different kinds of age

Do not expose only a generic:

```text
last updated
```

There are at least two important ages.

## Publication age

How long ago did the source publish or update this datapoint?

Example:

```text
Published 4 days ago
```

## Reference age

How old is the end of the period the figure describes?

Example:

```text
Data through 31 August
12 days behind today
```

These can differ substantially.

Example:

```text
NATO 2026 estimate
published 7 July 2026
reference year 2026
```

versus:

```text
EDA 2025 actual
published 16 July 2026
reference year 2025
```

The UI must make this distinction visible.

---

# 8. Datapoint status

Every figure must have a clear status.

Use a controlled vocabulary:

```text
actual
preliminary
provisional
estimate
projection
budget
```

Definitions:

## `actual`

Reported realised expenditure/outturn for a completed reference period.

## `preliminary`

Reported realised data which the publisher explicitly describes as preliminary.

## `provisional`

Official statistical data which may still be revised.

## `estimate`

A source's estimate for a period that may be current or incomplete.

## `projection`

Forward-looking projection.

## `budget`

Authorised/planned budget amount, not realised expenditure.

Never present:

```text
actual
```

and:

```text
projection
```

as equivalent observations.

---

# 9. Source registry

Maintain a source registry.

Every provider should have metadata such as:

```text
source_id
display_name
publisher
official/non_official
canonical_discovery_url
expected_update_frequency
geographic_coverage
metric_definitions
retrieval_method
format
```

Example:

```yaml
source_id: statskontoret_monthly_outturn
display_name: Statskontoret monthly budget outturn
publisher: Statskontoret
official: true
expected_update_frequency: monthly
geography:
  - SE
format:
  - csv
  - xlsx
```

This registry is used by:

- diagnostics,
- freshness calculations,
- UI source attribution,
- documentation.

---

# 10. Provider contract

Every Phase 3 provider should conceptually expose:

```python
async def discover_latest() -> SourceRelease:
    ...

async def fetch_release(release: SourceRelease) -> bytes | dict:
    ...

async def parse_release(...) -> list[SpendingDataPoint]:
    ...
```

A `SourceRelease` should contain as much as possible before parsing:

```text
source_id
release_id
published_at
reference_period
download_url
format
checksum/version when available
```

A provider is not complete until `discover_latest()` works without a hard-coded current-year download filename.

---

# 11. Generic provider acceptance criteria

A provider is GREEN only when all of the following are tested:

1. Latest release can be discovered automatically.
2. Data can be downloaded without browser interaction.
3. Relevant records can be parsed.
4. Sweden can be identified consistently.
5. Other countries can be identified consistently where applicable.
6. Reference period is captured.
7. Publication/update date is captured or derived from an official source.
8. Status (`actual`, `estimate`, etc.) can be assigned.
9. Source URL is retained.
10. A changed file URL does not break discovery if the official landing page remains valid.
11. Parser fixtures exist.
12. A schema/layout change fails visibly rather than silently returning wrong data.

---

# 12. Source A — Statskontoret monthly Swedish budget outturn

**Provider status:** GREEN  
**Publisher:** Statskontoret  
**Role:** Primary near-current Swedish actual spending source.

Statskontoret publishes monthly outturn for the Swedish central government budget.

The underlying data is based on government agencies' reporting to Hermes.

The official open-data page states:

- data is available from January 2006,
- expenditure is available at appropriation-item/sub-item and agency level,
- updates are monthly,
- files are available in Excel and CSV,
- use is CC0.

Canonical discovery page:

```text
https://www.statskontoret.se/analys-och-statistik/oppna-data/manadsutfall/
```

Year-specific pages use:

```text
?year=YYYY
```

Example:

```text
https://www.statskontoret.se/analys-och-statistik/oppna-data/manadsutfall/?year=2026
```

---

# 13. Statskontoret access method

Do not hard-code monthly file names.

Use the official discovery page.

Provider flow:

```text
GET discovery page for current year
          ↓
Parse available month sections
          ↓
Find latest "Utgifter <month> <year>"
          ↓
Read "Senast uppdaterad"
          ↓
Find CSV download link
          ↓
Download CSV
          ↓
Parse expenditure rows
```

Prefer CSV over XLSX for the runtime provider.

Use XLSX as fallback only if CSV disappears or a schema problem requires it.

The official page itself exposes:

```text
month
publication/update date
Excel link
CSV link
```

so the provider does not need to guess release URLs.

---

# 14. Statskontoret publication cadence

Statskontoret states that monthly outturn is published:

```text
senast sista vardagen i månaden efter aktuell utfallsmånad
```

The provider should therefore calculate an expected latest reference month.

Example:

```text
Current date: 12 September
Expected latest reference month:
July or August depending on official publication schedule/release existence
```

Do not mark data "late" solely from a fixed 30-day age threshold.

Freshness is source-cadence aware.

---

# 15. Statskontoret preliminary/definitive handling

December has special handling.

The official open-data archive exposes:

```text
December — preliminär
December — definitiv
```

The preliminary December value may later be replaced by a definitive year-end release.

Map this explicitly:

```text
preliminär -> preliminary
definitiv -> actual
```

When a definitive December release appears:

- replace/retire the preliminary current value for the same period,
- retain revision metadata if practical.

---

# 16. Statskontoret metrics to extract

Priority metrics:

```text
Utgiftsområde 6 — relevant total
1:3 Anskaffning av materiel och anläggningar
```

Desired facts for each:

```text
latest month outturn
YTD outturn
same YTD period previous year
annual budget where available in the source context
```

The open-data CSV is the canonical detailed source.

The existing human-readable budget-outturn page may be used only as a validation reference, not as the primary parser if the CSV contains the required values.

---

# 17. Statskontoret metric identity

Do not identify rows only by translated/display text if stable appropriation identifiers are present.

Prefer:

```text
expenditure_area_id
appropriation_id
appropriation_item_id
agency_id
```

where available.

Store display labels for UI only.

This protects the provider against small wording changes.

---

# 18. Statskontoret parser profiling

Before finalising the provider, inspect at least:

```text
2024 full year
2025 full year
2026 latest available month
```

Document:

```text
column names
encoding
delimiter
decimal format
appropriation identifiers
monthly-value semantics
YTD semantics
budget fields if present
revision behaviour
```

Create:

```text
docs/providers/statskontoret.md
```

with a minimal schema description.

---

# 19. Statskontoret feasibility test

The provider is accepted when it can automatically return:

```yaml
country: SE
metric: materiel_acquisition_outturn_ytd
value: ...
unit: SEK
reference_start: 2026-01-01
reference_end: <latest month end>
published_at: <official update date>
status: actual
source_url: <official Statskontoret release/discovery URL>
```

and equivalent previous-year comparison data.

---

# 20. Source B — Eurostat `gov_ev`

**Provider status:** GREEN  
**Publisher:** Eurostat  
**Role:** Best machine-readable current harmonised EU comparison source.

Dataset:

```text
gov_ev
```

The dataset covers expenditure variables supporting the EU economic governance framework and contains:

```text
total expenditure on defence
investment in defence
```

The metadata states:

- data is compiled using ESA 2010,
- coverage for defence expenditure/investment begins in 2021,
- reference area is EU and EU Member States,
- reference period is calendar year,
- data is provided by national authorities,
- reporting occurs twice yearly, at the end of March and end of September,
- data is disseminated twice yearly,
- units include million EUR, national currency and % of GDP.

Canonical metadata page:

```text
https://ec.europa.eu/eurostat/cache/metadata/en/gov_ev_esms.htm
```

---

# 21. Eurostat API access

Use the official Eurostat Statistics REST API.

Base request:

```text
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_ev
```

The Statistics API:

- is REST,
- requires no credentials,
- returns JSON-stat 2.0,
- supports dimension filters,
- is intended for programmatic use.

Generic URL structure:

```text
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/<DATASET_CODE>?<filters>
```

Provider flow:

```text
GET gov_ev through Eurostat Statistics API
          ↓
Read JSON-stat dimensions
          ↓
Select defence expenditure/investment indicators
          ↓
Select comparable units
          ↓
Read all EU countries
          ↓
Normalise country-year datapoints
```

---

# 22. Eurostat query strategy

Do not hard-code array positions in JSON-stat.

Parse:

```text
id
size
dimension
value
status
updated
```

Use dimension labels/codes.

At development time:

1. fetch the full small `gov_ev` dataset or metadata structure,
2. print all dimension codes,
3. identify exact indicator and unit codes,
4. create constants from verified codes.

The production provider may then filter server-side.

---

# 23. Eurostat freshness and status

Eurostat's dataset metadata states data are reported twice yearly.

The provider should retain:

```text
response updated timestamp
reference year
status flags if provided in JSON-stat
```

The April/first reporting cycle may include preliminary values.

Later values may be revised.

Do not hard-code:

```text
April = preliminary
October = final
```

unless the official dataset/status metadata supports that exact interpretation for the datapoint.

Instead prefer source-provided status flags when available.

---

# 24. Eurostat metrics to ingest

At minimum:

```text
government defence expenditure
government defence expenditure % GDP
defence investment
defence investment % GDP if exposed
```

For cross-country ranking:

```text
same dataset
same reference year
same unit
same status class where possible
```

Sweden must always be retained even if missing from a top-N list.

---

# 25. Eurostat historical complement

The older dataset:

```text
gov_10a_exp
```

may be retained as a separate provider/series for longer COFOG defence history.

It must not be silently joined with `gov_ev` as though the metric definition is identical.

Name the series explicitly:

```text
Eurostat gov_ev defence expenditure
Eurostat gov_10a_exp COFOG defence expenditure
```

---

# 26. Eurostat feasibility test

The provider is accepted when it can automatically return:

```yaml
country: SE
metric: eurostat_defence_expenditure
reference_year: 2025
value: ...
unit: EUR million
status: ...
source_updated_at: ...
source_url: ...
```

plus equivalent data for all available EU countries.

---

# 27. Source C — NATO Defence Expenditure

**Provider status:** GREEN  
**Publisher:** NATO  
**Role:** Harmonised comparison across NATO allies.

Current publication page verified for 2026:

```text
https://www.nato.int/en/news-and-events/articles/news/2026/07/07/defence-investment-update-record-spending-in-europe-and-canada
```

The page exposes:

```text
Download the tables in Excel format
```

The current verified 2026 workbook target is:

```text
https://www.nato.int/content/dam/nato/webready/documents/finance/def-exp-2026-en.xlsx
```

This exact file URL is an example only.

Runtime discovery must use the publication page or a stable NATO index, not a hard-coded year/file name.

---

# 28. NATO access method

Provider flow:

```text
GET current NATO defence-expenditure publication/index
          ↓
Identify newest applicable release
          ↓
Find link labelled "Download the tables in Excel format"
          ↓
Download XLSX
          ↓
Enumerate sheets
          ↓
Locate tables by header text
          ↓
Parse country × year × metric
```

Do not parse fixed Excel cell coordinates unless a fixture confirms there is no safer alternative.

Prefer:

```text
sheet name
header scanning
known country labels
known metric labels
```

---

# 29. NATO workbook parser strategy

On every supported release:

1. list workbook sheet names,
2. inspect first N rows for table titles,
3. detect header rows,
4. map country labels to ISO codes,
5. parse numeric cells,
6. retain footnotes/status markers.

Create fixtures for at least:

```text
current 2026 workbook
one previous-year workbook
```

This is necessary because NATO may change workbook layout over time.

---

# 30. NATO metrics to ingest

Prioritise:

```text
total defence expenditure
defence expenditure as % GDP
major equipment expenditure
major equipment share of defence expenditure
```

Only ingest a metric after confirming its table definition in the workbook.

Do not infer equipment value by multiplying percentages unless the workbook does not directly provide a value and the calculation is explicitly defined and tested.

---

# 31. NATO actual vs estimate

NATO releases often include historical values and current-year estimates.

The parser must preserve source status.

Conceptually:

```yaml
country: SE
year: 2026
metric: defence_expenditure
status: estimate
```

while:

```yaml
country: SE
year: 2025
metric: defence_expenditure
status: actual
```

may apply if the workbook/source marks it as such.

Do not infer status merely from:

```text
year < current year
```

if the workbook has explicit footnotes/status indicators.

---

# 32. NATO publication date

Use the publication page date as:

```text
published_at
```

for values originating in that release unless the workbook contains a more specific revision/publication date.

Retain the publication page URL as the canonical source URL.

---

# 33. NATO feasibility test

The provider is accepted when it can automatically:

- discover the latest official workbook,
- download it,
- return Sweden and all other listed allies,
- preserve actual/estimate distinction,
- return at least total defence expenditure and one equipment-related measure,
- retain publication/reference dates.

---

# 34. Source D — EDA Defence Data

**Provider status:** GREEN for technical access, YELLOW for exact country-level metric coverage until profiled  
**Publisher:** European Defence Agency  
**Role:** EU defence and equipment-procurement benchmark.

Canonical portal:

```text
https://www.eda.europa.eu/publications-and-data/defence-data
```

EDA states:

- defence data is collected annually,
- data has been collected since 2006, with some indicators from 2005,
- Ministries of Defence of 27 Member States provide the data,
- figures may occasionally be revised,
- the portal includes national data and annual data analysis.

The portal exposes current and historical Excel datasets.

The verified 2025 data link currently resolves to:

```text
https://www.eda.europa.eu/docs/default-source/documents/defence-data/final-defence-data-2025-1.xlsx
```

Again, this direct file URL is an example, not a runtime constant.

---

# 35. EDA access method

Provider flow:

```text
GET EDA Defence Data Portal
          ↓
Parse "Data Analysis" section
          ↓
Identify latest year
          ↓
Follow latest official Excel link
          ↓
Download XLSX
          ↓
Profile workbook schema
          ↓
Parse country-level metrics that are actually present
```

For historical backfill:

- use annual current workbooks where available,
- use EDA's historical collective/national Excel datasets where needed.

Do not rely on PDF extraction if the corresponding XLSX is available.

---

# 36. EDA workbook feasibility gate

Before implementing permanent metrics, the agent must produce:

```text
sheet names
table titles
header rows
country identifier format
metric names
units
actual/estimate/projection markers
missing-value conventions
footnotes
```

Output:

```text
docs/providers/eda.md
```

The parser should not be finalised before this profile exists.

---

# 37. EDA metrics to prioritise

If country-level data is exposed reliably, prioritise:

```text
total defence expenditure
defence investment
equipment procurement
equipment procurement share
R&D / R&T
collaborative equipment procurement
```

The most valuable metric is:

```text
equipment procurement
```

because it is closest to the buyer/procurement focus of the integration.

However:

> An EDA aggregate metric must not be assumed to exist consistently at country level.

Only expose metrics proven available in the workbook.

---

# 38. EDA revisions

EDA states that data can occasionally be revised during the year.

Use:

```text
source + metric + country + reference year
```

as the logical datapoint identity.

If a newly downloaded workbook contains a different value:

```text
update current value
record revision_detected_at
retain previous value in revision metadata if practical
```

Do not assume historical EDA values are immutable.

---

# 39. EDA feasibility test

The provider is accepted for each metric individually.

For example:

```text
EDA total defence expenditure: GREEN
EDA equipment procurement: GREEN
EDA collaborative procurement: YELLOW
```

This prevents the whole provider from being treated as all-or-nothing.

---

# 40. Source E — SIPRI Military Expenditure

**Provider status:** GREEN  
**Publisher:** SIPRI  
**Role:** Long historical and global comparison.

Canonical landing page:

```text
https://www.sipri.org/databases/milex
```

The database currently contains country time series for:

```text
1949–2025
```

and is updated annually.

The landing page exposes:

```text
Download the SIPRI Military Expenditure Database (Excel)
```

The page also publishes a revision timestamp.

For the current edition, the page states the file was revised:

```text
27 April 2026
```

and that the revised version replaces all previous versions.

---

# 41. SIPRI access method

Provider flow:

```text
GET SIPRI Military Expenditure Database page
          ↓
Read release/revision date
          ↓
Find current Excel link
          ↓
Download XLSX
          ↓
Parse worksheets
          ↓
Normalise country × year × metric
```

Do not hard-code the workbook filename.

The discovery page is canonical because SIPRI can replace/revise the workbook.

---

# 42. SIPRI parser strategy

The first provider implementation must profile:

```text
sheet names
country row layout
year columns
units
footnote markers
missing-value markers
estimated-value markers if present
```

Metrics likely include:

```text
military expenditure local currency
military expenditure current USD
military expenditure constant USD
share of GDP
per capita
share of government expenditure
```

Only support metrics whose sheet structure is stable and tested.

---

# 43. SIPRI revision handling

Because SIPRI can revise historical years, do not perform incremental latest-year-only updates.

When the release/revision identifier changes:

```text
download current workbook
re-parse full supported series
compare with stored series
update revisions
```

The dataset is small enough that full annual re-import is acceptable.

---

# 44. SIPRI status semantics

SIPRI is an independent research dataset based on open sources.

Do not label all values as:

```text
official actual
```

Use source-specific status/metadata.

Where SIPRI marks estimates, preserve those markers.

Where no explicit value-level status exists, identify the source as:

```text
SIPRI military expenditure series
```

and avoid inventing a certainty category.

---

# 45. Source F — TED from Phase 1/2

**Provider status:** already implemented  
**Role:** Near-current publicly reported awarded defence procurement.

No new TED provider is needed in Phase 3.

Phase 3 should reuse:

```text
awarded contract value
buyer country
award/result date
strategic category
source notice
```

from Phase 2.

TED remains conceptually separate from spending data.

---

# 46. Source hierarchy by question

Use sources according to the question, not a global "best source".

## What is Sweden spending right now?

Primary:

```text
Statskontoret monthly outturn
```

## What contracts are being awarded right now?

Primary:

```text
TED
```

## How does Sweden compare with EU countries on harmonised government defence spending/investment?

Primary:

```text
Eurostat gov_ev
```

## How does Sweden compare with NATO allies?

Primary:

```text
NATO Defence Expenditure
```

## How does Sweden compare on EU defence/equipment procurement concepts?

Primary:

```text
EDA
```

## What is the long historical/global trend?

Primary:

```text
SIPRI
```

No source should silently substitute for another question.

---

# 47. Comparability metadata

Each metric definition should carry:

```text
comparison_group
comparison_allowed_with
comparison_not_allowed_with
```

Example:

```yaml
metric: nato_defence_expenditure
comparison_allowed_with:
  - nato_defence_expenditure
comparison_not_allowed_with:
  - statskontoret_outturn
  - ted_awarded_value
  - eda_equipment_procurement
```

This can remain internal metadata but should guide entity calculations.

---

# 48. Country ranking rule

A ranking must use:

```text
one source
one metric definition
one reference period
one unit
one comparable status class where practical
```

Valid:

```text
NATO 2026 estimate defence expenditure ranking
```

Valid:

```text
Eurostat 2025 defence investment ranking
```

Invalid:

```text
Sweden Statskontoret Aug-2026 actual
Germany NATO 2026 estimate
France Eurostat 2025 actual
```

No cross-source rankings.

---

# 49. Preferred international rankings

Phase 3 should eventually support:

## Eurostat

```text
defence expenditure
defence expenditure % GDP
defence investment
```

## NATO

```text
defence expenditure
defence expenditure % GDP
major equipment expenditure
major equipment share
```

## EDA

Only metrics confirmed in the country-level workbook, prioritising:

```text
defence expenditure
equipment procurement
defence investment
```

## SIPRI

```text
military expenditure
military expenditure % GDP
historical/global rank
```

Sweden must always be visible even when outside the top-N display.

---

# 50. Sweden-first comparison output

For every international ranking, calculate:

```text
Sweden value
Sweden rank
population size
top-ranked country
top-ranked value
population median
reference year
source status
source age
```

Optional where meaningful:

```text
Sweden vs Nordic median
Sweden vs source-population median
```

Do not calculate these when required peer values are missing.

---

# 51. Nordic comparison

When source coverage permits, provide a natural Nordic comparison:

```text
Sweden
Finland
Denmark
Norway
```

Use only values from the same source/metric/year.

Do not fill missing values from another source.

Iceland may be included only where the metric/population makes sense.

---

# 52. Swedish monthly spending trend

Statskontoret should eventually support:

```text
monthly defence-related outturn
monthly materiel-acquisition outturn
YTD defence-related outturn
YTD materiel-acquisition outturn
```

Compare:

```text
current year month-by-month
previous year month-by-month
```

This is likely the most current factual spending chart in the integration.

---

# 53. Swedish budget utilisation

If the Statskontoret source consistently provides a current annual budget denominator:

```text
budget utilisation =
YTD outturn / current annual budget
```

Label:

```text
Budget utilisation
```

not:

```text
Budget execution performance
```

If annual budget is not reliably available in the open-data CSV, either:

- derive it from an official Statskontoret budget source with separate provenance, or
- omit the metric.

Do not infer the budget from YTD data.

---

# 54. Year-on-year calculations

Swedish monthly data should support:

```text
latest month vs same month previous year
YTD vs same YTD period previous year
```

Use nominal values.

Do not silently inflation-adjust.

Label:

```text
nominal change
```

where ambiguity exists.

---

# 55. International trend calculations

For NATO/EDA/Eurostat/SIPRI:

Prefer:

```text
latest comparable actual year
vs
previous comparable actual year
```

Keep forecast/projection comparisons separate.

For example:

```text
NATO estimate 2026 vs NATO actual 2025
```

may be shown, but the status difference must be explicit.

---

# 56. Freshness model

Every datapoint should expose enough metadata to calculate:

```text
publication_age
reference_age
retrieval_age
```

## `publication_age`

```text
now - published_at
```

## `reference_age`

```text
now - reference_period_end
```

For annual data, use the documented end of the reference year unless the source defines another period.

## `retrieval_age`

```text
now - retrieved_at
```

This indicates only when the integration checked the source.

It is not source freshness.

---

# 57. Freshness relative to source cadence

Use source-specific expectations.

Initial expected cadences:

| Source | Expected cadence |
|---|---|
| Statskontoret | Monthly |
| TED | Near-daily / business days |
| Eurostat `gov_ev` | Twice-yearly dissemination |
| NATO | Periodic / annual |
| EDA | Annual |
| SIPRI | Annual |

A 10-month-old annual EDA datapoint may still be the current official release.

A 2-month-old Statskontoret datapoint may be late.

Do not use a universal freshness threshold.

---

# 58. Freshness state

Optional internal state:

```text
current
expected
late
unknown
```

Calculation must use:

```text
source cadence
latest known official release
current date
reference period
```

Always expose absolute ages as well.

---

# 59. Freshness survives composites

A combined Sweden overview may eventually show:

```text
Materiel outturn YTD       Statskontoret
Awarded contracts 12m      TED
Defence investment         Eurostat
Equipment procurement      EDA
Major equipment            NATO
Military expenditure       SIPRI
```

Each row must retain:

```text
source
reference period
status
publication date/age
```

The composite is a presentation layer only.

---

# 60. No synthetic master number

Do not create:

```text
Swedish defence activity =
Statskontoret + TED + NATO + EDA + Eurostat + SIPRI
```

These overlap and use different definitions.

Do not average sources into a consensus.

The integration should preserve separate perspectives.

---

# 61. Source disagreement

Differences are expected.

For the same year:

```text
NATO defence expenditure
EDA defence expenditure
Eurostat defence expenditure
SIPRI military expenditure
```

may differ.

The integration should:

1. retain each value,
2. retain each definition/source,
3. retain each status/reference year,
4. avoid deciding which source is "correct".

A factual multi-source view may show the differences side by side.

---

# 62. Revision detection

Every provider must support revisions where practical.

Logical identity:

```text
source_id
metric_id
country
reference_period
unit
```

If the same logical datapoint later changes:

```text
update current value
record source revision
retain previous value in revision metadata/history if practical
```

This is especially relevant for:

```text
Eurostat
EDA
SIPRI
Statskontoret December
```

---

# 63. Retrieval preference

For each source, use in this order:

1. official REST/API,
2. official CSV,
3. official XLSX,
4. official structured HTML,
5. official PDF only if no better representation exists.

Current Phase 3 plan avoids PDF parsing for all core providers.

That is intentional.

---

# 64. Failure handling

A provider failure must not invalidate other providers.

Example:

```text
NATO workbook temporarily unavailable
```

should not make:

```text
Statskontoret
Eurostat
TED
```

unavailable.

Maintain per-provider health.

Conceptual states:

```text
available
stale_but_cached
temporarily_unavailable
parser_error
schema_changed
```

---

# 65. Schema-change policy

Do not silently continue after a structural source change.

Examples:

```text
Statskontoret CSV expected identifier column missing
NATO workbook table title not found
EDA workbook no longer has expected sheet
Eurostat metric code disappears
SIPRI year headers cannot be found
```

In such cases:

- retain last known valid data,
- mark provider update failed,
- expose a diagnostics error,
- do not emit zero/empty replacement values.

---

# 66. Local persistence

Reuse the existing integration storage patterns where practical.

Store normalised datapoints, not complete raw workbooks indefinitely.

Suggested logical records:

```text
source releases
normalised spending datapoints
revision metadata
provider last-success metadata
```

Keep enough historical values to:

```text
build time-series
detect revisions
calculate rankings
compare years
```

Annual datasets are small enough to retain fully normalised history.

---

# 67. Source release metadata

Persist one record per fetched source release:

```yaml
source_id: nato_defence_expenditure
release_id: "2026-07-07"
published_at: 2026-07-07
retrieved_at: ...
reference_periods:
  - 2025
  - 2026
download_url: ...
canonical_url: ...
format: xlsx
checksum: ...
parse_status: success
```

Checksums help detect silent file replacement.

---

# 68. Provider documentation

Each provider must have a short technical document:

```text
docs/providers/statskontoret.md
docs/providers/eurostat.md
docs/providers/nato.md
docs/providers/eda.md
docs/providers/sipri.md
```

Each document should include:

```text
canonical discovery URL
current verified example
download/API format
metric mapping
status semantics
reference period semantics
publication date source
parser assumptions
known weaknesses
fixture files
```

---

# 69. Phase 3A — provider feasibility and profiling

Implement providers in this order:

```text
1. Statskontoret
2. Eurostat gov_ev
3. NATO
4. EDA
5. SIPRI
```

Reason:

```text
Statskontoret → freshest Sweden data
Eurostat      → cleanest international API
NATO          → high-value alliance comparison
EDA           → valuable equipment-procurement concepts
SIPRI         → longest history, lowest freshness need
```

TED is already available.

---

# 70. Phase 3A deliverable

Produce:

```text
docs/phase3-source-profile.md
```

It must include, for every provider:

```text
technical access confirmed: yes/no
discovery method
format
latest release found
latest reference period
available countries
available metrics
actual/estimate/projection distinctions
source publication date available: yes/no
revision behaviour
missing data
parser risk
```

Do not proceed to final sensor design until this document exists.

---

# 71. Phase 3B — factual data validation

After all feasible providers ingest successfully, produce a development report that can answer:

## Statskontoret

```text
Latest Swedish reference month?
Latest Swedish materiel YTD?
Previous-year comparable value?
Publication date?
Status?
```

## Eurostat

```text
Latest defence-expenditure year?
Latest defence-investment year?
Sweden rank?
Population size?
Status?
```

## NATO

```text
Latest comparable year/estimate?
Sweden total defence expenditure?
Sweden equipment measure?
Sweden rank?
```

## EDA

```text
Which country-level metrics are truly available?
Is equipment procurement available for Sweden and peers?
Latest actual year?
```

## SIPRI

```text
Latest year?
How far back is Sweden available?
Which measures parse reliably?
```

---

# 72. Phase 3C — final sensor design

Only after Phase 3B should the sensor set be frozen.

Likely device groups:

```text
Sweden — Current Spending
Sweden — International Position
Defence Spending — EU
Defence Spending — NATO
Defence Spending — Historical
```

TED/Phase 2 devices remain separate.

---

# 73. Candidate Sweden current-spending sensors

These are candidates pending profiling:

```text
Sweden defence-related outturn — latest month
Sweden defence-related outturn — YTD
Sweden defence-related outturn — YTD YoY %

Sweden materiel acquisition — latest month
Sweden materiel acquisition — YTD
Sweden materiel acquisition — YTD YoY %
Sweden materiel acquisition — annual budget
Sweden materiel acquisition — budget utilised %
```

Every sensor must expose:

```text
source
reference period
publication date
status
age
```

---

# 74. Candidate international sensors

## Eurostat

```text
Sweden defence expenditure
Sweden defence expenditure rank
Sweden defence investment
Sweden defence investment rank
```

## NATO

```text
Sweden NATO defence expenditure
Sweden NATO defence expenditure rank
Sweden NATO major equipment
Sweden NATO major equipment rank
```

## EDA

Only if data profiling supports them:

```text
Sweden EDA defence expenditure
Sweden EDA equipment procurement
Sweden EDA equipment procurement rank
```

## SIPRI

```text
Sweden SIPRI military expenditure
Sweden SIPRI military expenditure rank
Sweden SIPRI % GDP
```

---

# 75. Ranking sensor attributes

A ranking sensor should expose:

```yaml
source: NATO
metric: defence_expenditure
reference_year: 2026
status: estimate
published_at: 2026-07-07
retrieved_at: ...

sweden:
  rank: ...
  value: ...

ranking:
  - rank: 1
    country: ...
    value: ...
  - ...
```

Do not mix values from other providers.

---

# 76. Compact factual text sensors

A few presentation helpers may be useful.

Example:

```text
Sweden spending snapshot
"Materiel YTD SEK 48.2bn · +31% YoY · Statskontoret · through Aug"
```

Example:

```text
Sweden NATO position
"SE #N · EUR X.Xbn · Y% GDP · NATO 2026 estimate"
```

No interpretation.

---

# 77. Combined Sweden view

The desired long-term view is:

```text
SWEDEN

CURRENT ACTUAL
Materiel outturn YTD
Statskontoret · actual · through latest month

PROCUREMENT
Awarded contract value 12m
TED · rolling through today

EU COMPARISON
Defence expenditure / investment
Eurostat · same-year harmonised data

EU DEFENCE BENCHMARK
Equipment procurement
EDA · annual

ALLIANCE
Defence / major equipment
NATO · actual/estimate clearly labelled

HISTORY
Military expenditure
SIPRI · annual historical series
```

Every line retains its source and age.

---

# 78. Home Assistant source attributes

For every Phase 3 sensor, standardise a shared attribute model where practical:

```yaml
source: Statskontoret
source_id: statskontoret_monthly_outturn
source_url: ...
reference_start: ...
reference_end: ...
reference_label: "Jan–Aug 2026"
status: actual
published_at: ...
publication_age_days: ...
reference_age_days: ...
retrieved_at: ...
unit_definition: ...
```

Avoid dumping large source metadata into every entity if it creates Recorder bloat.

A common helper/base class can select a compact set of attributes.

Detailed provenance can also be exposed through diagnostics.

---

# 79. Freshness sensors

Do not create one generic integration freshness sensor only.

Potential default-disabled diagnostic sensors:

```text
Statskontoret data age
Eurostat data age
NATO data age
EDA data age
SIPRI data age
```

However, per-datapoint metadata remains authoritative.

---

# 80. Diagnostics

Add Phase 3 diagnostics:

```text
provider status
last discovery attempt
last successful release
latest reference period
published_at
retrieved_at
release URL
checksum
records parsed
countries parsed
metrics parsed
parse warnings
revision count
schema version
```

No raw full workbook dumps.

---

# 81. Tests — Statskontoret

Mandatory fixtures/tests:

```text
normal monthly CSV
December preliminary CSV
December definitive CSV
older historical CSV
missing expected appropriation
renamed display label with same stable ID
```

Tests:

```text
latest month discovery
CSV link extraction
publication date extraction
appropriation filtering
YTD extraction
status mapping
revision replacement
```

---

# 82. Tests — Eurostat

Mandatory tests:

```text
gov_ev JSON-stat fixture
dimension-order independence
country filtering
metric filtering
unit filtering
updated timestamp
missing country-year
status flags
```

Do not write tests that depend on fixed JSON array position.

---

# 83. Tests — NATO

Mandatory fixtures:

```text
2026 workbook
one earlier workbook with different layout if available
```

Tests:

```text
Excel-link discovery
sheet discovery
header detection
country mapping
metric extraction
actual/estimate status
publication date
layout-change failure
```

---

# 84. Tests — EDA

Mandatory tests:

```text
latest workbook
historical workbook
```

Test each metric independently.

A missing metric should disable that metric, not fabricate a value.

---

# 85. Tests — SIPRI

Mandatory tests:

```text
current workbook
revision timestamp discovery
Sweden row
missing values
footnotes/estimate markers
```

Test full re-import when release revision changes.

---

# 86. Source-update polling

Source-specific update schedules should be conservative.

Suggested defaults:

## Statskontoret

```text
daily discovery check
```

because releases are monthly and the check is inexpensive.

## Eurostat

```text
daily or weekly
```

The API is cheap, but source changes only periodically.

## NATO

```text
daily landing-page check
```

or weekly outside expected release windows.

## EDA

```text
daily/weekly portal check
```

Annual source; weekly is sufficient.

## SIPRI

```text
weekly
```

Annual source.

Do not download unchanged large files repeatedly if:

```text
release URL
ETag
Last-Modified
checksum
```

indicates no change.

---

# 87. HTTP caching

Where supported, use:

```text
ETag
If-None-Match
Last-Modified
If-Modified-Since
```

This is especially useful for XLSX providers.

If the publisher does not expose cache headers, compare:

```text
discovered release URL
published date
content checksum
```

---

# 88. No hidden scraping dependency

For official HTML discovery pages, parsing the page to find an official CSV/XLSX link is acceptable.

Do not depend on:

- browser automation,
- JavaScript execution,
- login,
- private endpoints,
- OCR,
- unofficial mirrors.

If a source later requires one of these, mark the provider degraded/unsupported until reassessed.

---

# 89. Relation to Phase 2

Phase 2 remains the source for:

```text
publicly reported awarded procurement
which countries award most
what categories they buy
largest awards
```

Phase 3 adds:

```text
actual Swedish budget outturn
harmonised EU spending/investment
NATO spending/equipment comparison
EDA equipment/defence benchmark
long historical/global comparison
```

The user should ultimately be able to move between:

```text
HOW MUCH IS SWEDEN SPENDING?
            ↓
WHAT IS SWEDEN BUYING?
            ↓
HOW DOES SWEDEN COMPARE?
```

---

# 90. What Phase 3 deliberately does not do

Do not add:

- news sentiment,
- minister/media prediction,
- NATO vendor opportunities,
- EU funding opportunities,
- AI summaries,
- unexplained composite scores,
- synthetic merged spending totals,
- cross-source rankings,
- unsupported national estimates.

Phase 3 is about **reliable spending facts with transparent provenance**.

---

# 91. Canonical source links

## Statskontoret

Monthly budget outturn open data:

```text
https://www.statskontoret.se/analys-och-statistik/oppna-data/manadsutfall/
```

Human-readable budget outturn:

```text
https://www.statskontoret.se/analys-och-statistik/utfall/utfall-for-statens-budget/
```

## Eurostat

`gov_ev` metadata:

```text
https://ec.europa.eu/eurostat/cache/metadata/en/gov_ev_esms.htm
```

Statistics API:

```text
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_ev
```

API documentation:

```text
https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction
```

## NATO

Current 2026 Defence Investment Update:

```text
https://www.nato.int/en/news-and-events/articles/news/2026/07/07/defence-investment-update-record-spending-in-europe-and-canada
```

Verified 2026 workbook example:

```text
https://www.nato.int/content/dam/nato/webready/documents/finance/def-exp-2026-en.xlsx
```

## EDA

Defence Data Portal:

```text
https://www.eda.europa.eu/publications-and-data/defence-data
```

Verified 2025 workbook example:

```text
https://www.eda.europa.eu/docs/default-source/documents/defence-data/final-defence-data-2025-1.xlsx
```

## SIPRI

Military Expenditure Database:

```text
https://www.sipri.org/databases/milex
```

## TED

Reuse Phase 1/2 implementation and documentation.

---

# 92. Implementation sequence

## Step 1 — Statskontoret feasibility + provider

Build the provider first.

Deliver:

```text
discovery parser
CSV parser
historical fixtures
Sweden monthly datapoints
freshness/status handling
```

## Step 2 — Eurostat `gov_ev`

Implement direct REST provider.

Deliver:

```text
all-country harmonised dataset
Sweden ranking support
source updated timestamp
```

## Step 3 — NATO

Implement publication discovery + XLSX parser.

Deliver:

```text
latest workbook discovery
country metrics
actual/estimate metadata
```

## Step 4 — EDA

Implement portal discovery + workbook profiler.

First deliver:

```text
docs/providers/eda.md
```

Then enable only verified metrics.

## Step 5 — SIPRI

Implement landing-page discovery + annual full workbook import.

## Step 6 — Phase 3 source profile

Generate:

```text
docs/phase3-source-profile.md
```

## Step 7 — factual validation

Demonstrate the questions in section 3 can be answered.

## Step 8 — final sensor design

Only now freeze the Home Assistant entity set.

---

# 93. Acceptance criteria for the complete Phase 3 data layer

Phase 3 data ingestion is complete when the integration can answer, with provenance:

## Sweden current

```text
What is the latest available Swedish defence-related monthly/YTD outturn?
What is the latest available Swedish materiel-acquisition monthly/YTD outturn?
What period does each value cover?
When was it published?
How old is it?
Is it preliminary or actual?
```

## EU comparison

```text
What is Sweden's latest Eurostat defence-expenditure value and rank?
What is Sweden's latest Eurostat defence-investment value and rank?
Which year/status is being compared?
```

## NATO comparison

```text
What is Sweden's latest NATO defence-expenditure value and rank?
What is Sweden's latest NATO major-equipment measure and rank?
Is the value actual or estimated?
```

## EDA comparison

```text
Which country-level EDA metrics are reliably available?
Is equipment procurement available for Sweden and peers?
What is Sweden's rank for each verified metric?
```

## History

```text
How has Swedish military/defence expenditure changed over time according to SIPRI and the other annual sources?
```

## Technical provenance

For every answer:

```text
source
definition
reference period
publication date
retrieval time
status
age
source URL
```

must be available.

---

# 94. Definition of done for each provider

A provider is not "done" merely because it successfully parsed one current file.

It is done when:

```text
discovery is automatic
current release works
historical fixture works
source status is preserved
freshness metadata is preserved
revisions are handled
schema changes fail safely
tests exist
documentation exists
```

This is a hard Phase 3 requirement.

---

# 95. Summary

Phase 3 creates a Sweden-centred defence-spending layer with verified automated access to authoritative public sources.

The model is:

```text
                           SWEDEN
                              │
       ┌──────────────────────┼──────────────────────┐
       │                      │                      │
       ▼                      ▼                      ▼
 CURRENT ACTUAL          PROCUREMENT            COMPARISON
 Statskontoret              TED               Eurostat/NATO
                                                      │
                                                      ▼
                                                     EDA
                                                      │
                                                      ▼
                                                    SIPRI
                                                   HISTORY
```

The key technical principle is:

> **No source is accepted until the integration can automatically discover, retrieve, parse, date and classify its data.**

The key data principle is:

> **Every displayed value carries its source, definition, reference period, status, publication date and age.**

The key analytical principle is:

> **Different definitions are shown side by side, not merged into a synthetic total.**

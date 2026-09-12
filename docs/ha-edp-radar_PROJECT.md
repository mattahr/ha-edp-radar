# ha-edp-radar

## European Defence Procurement Radar for Home Assistant

**Repository:** `ha-edp-radar`  
**Home Assistant integration name:** `European Defence Procurement Radar`  
**Domain:** `edp_radar`  
**Primary data source:** Tenders Electronic Daily (TED) Search API  
**Secondary data source:** European Central Bank (ECB) reference exchange rates  
**Status:** Implementation plan  
**Document date:** 2026-09-12

---

# 1. Purpose

`ha-edp-radar` is a read-only Home Assistant integration that turns public European procurement data into a compact strategic view of defence procurement activity.

The integration is not intended to be a generic TED reader and not primarily a feed of individual procurement notices.

Its purpose is to answer, with **hard public facts**, questions such as:

- What is happening in European defence procurement?
- Which countries and capability areas are increasing or decreasing activity?
- What is publicly visible about a selected organisation?
- How does that public footprint compare with selected peers?
- How competitive do published procurement results appear?
- Which suppliers are receiving large awards?
- Where is supplier concentration high?
- What has changed recently that is quantitatively unusual?
- What large actions by other countries or organisations are visible right now?

The integration must **not** produce speculative conclusions, policy advice, media analysis, management advice, or generated interpretations.

The user is expected to interpret the facts.

---

# 2. Core design principle

The product is not:

> "A list of procurement notices."

The product is:

> "A factual external radar built from public procurement data."

The primary perspectives are:

```text
                  PUBLIC PROCUREMENT DATA
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
  PUBLIC FOOTPRINT       PEERS            MARKET
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                 COMPARISONS & CHANGES
                           │
                           ▼
                    HARD FACTS ONLY
```

The integration may calculate:

- counts,
- sums,
- medians,
- ratios,
- percentage changes,
- percentage-point changes,
- rankings,
- percentiles,
- concentration metrics,
- rolling period comparisons,
- statistical outliers with explicit mathematical definitions.

The integration must not produce sentences such as:

- "This is worrying."
- "This is likely to attract media attention."
- "Country X is falling behind."
- "You should be prepared to explain this."
- "The market cannot handle the demand."

Instead it should expose the underlying facts, for example:

```text
Air & missile defence, 90 days

Sweden        EUR 0.42bn   +12%
Finland       EUR 1.10bn   +81%
Germany       EUR 4.80bn   +96%
Poland        EUR 3.60bn  +143%
```

---

# 3. Non-goals

The following are explicitly outside the initial scope:

- Internal organisational data.
- Authentication to any employer or government system.
- Classified, protected, restricted, or non-public data.
- Generative AI or LLM-based interpretation.
- News scraping.
- Social-media monitoring.
- Prediction of political or media behaviour.
- Evaluation of operational military capability.
- Claims about whether a procurement programme is "successful".
- Claims about actual delivery performance unless explicitly represented by public procurement data.
- Procurement booking, submission, bidding, or any write action.
- A custom Lovelace card in the first version.
- NATO and EU defence-funding data; those should remain separate future integrations.

---

# 4. Primary source: TED Search API

TED is the official EU Tenders Electronic Daily service.

The Search API is intended for reuse and analysis and does not require authentication.

Production operation:

```http
POST /v3/notices/search
```

Official documentation:

- https://docs.ted.europa.eu/api/latest/search.html
- https://docs.ted.europa.eu/ODS/latest/reuse/search-api.html
- https://docs.ted.europa.eu/ODS/latest/reuse/field-list.html

Important API characteristics verified in September 2026:

- Expert-search query syntax.
- Client specifies which fields to return.
- Maximum 250 notices per page.
- Maximum 10,000 returned fields per page.
- Page-number mode has a 15,000-notice retrieval ceiling.
- Iteration/scroll mode has no overall notice-count ceiling.
- No authentication is required.
- Published OJ S editions normally appear Monday-Friday.
- TED states that daily publication is available on the website between 00:01 and 09:00 on publication days.

Use `ITERATION` mode for historical/backfill queries.

Use page-number mode only for small bounded queries where the result count is guaranteed to remain comfortably below the limit.

The API client must calculate a safe page size:

```text
page_size <= min(250, floor(10000 / number_of_requested_fields))
```

Do not rely on an undocumented fixed page size.

---

# 5. What counts as defence procurement?

A procurement is considered relevant when at least one configured defence signal matches.

The default broad query is the union of three independent signals.

## 5.1 Signal A — defence buyer activity

TED field:

```text
authority-main-activity
```

Relevant value:

```text
defence
```

This is important because defence organisations also buy:

- IT,
- transport,
- buildings,
- training,
- consultancy,
- health services,
- engineering,
- logistics,
- machinery,

whose CPV codes may not look military.

---

## 5.2 Signal B — defence/security procurement legal basis

TED field:

```text
legal-basis
```

Important legal basis:

```text
32009L0081
```

This corresponds to Directive 2009/81/EC for defence and sensitive security procurement.

The exact search value and query syntax must be validated against the current TED API before implementation is frozen.

---

## 5.3 Signal C — curated defence-related CPV taxonomy

TED fields include:

```text
classification-cpv
main-classification-proc
additional-classification-proc
main-classification-lot
additional-classification-lot
```

Do not simply match all security/fire/police CPV codes.

Maintain an explicit, versioned, reviewable taxonomy.

Initial taxonomy should cover at least:

- weapons,
- ammunition,
- explosives,
- military vehicles,
- military aircraft,
- missiles,
- warships,
- military electronics,
- defence R&D,
- radar and military sensors where identifiable,
- relevant military support equipment.

Store the taxonomy as repository data, not scattered Python conditionals.

Suggested file:

```text
custom_components/edp_radar/data/defence_cpv.json
```

---

# 6. Relevance modes

Config flow should expose a simple user-facing relevance mode.

## Strict defence

Match:

```text
authority-main-activity = defence
OR
legal-basis = 32009L0081
```

This should be the recommended default for a high signal-to-noise ratio.

## Broad defence

Match strict defence plus the curated CPV taxonomy.

This finds relevant procurement outside organisations explicitly classified as defence buyers.

Each normalized record must retain the reason or reasons it matched:

```python
match_reasons = {
    "defence_buyer",
    "defence_legal_basis",
    "defence_cpv",
}
```

This supports diagnostics and later tuning.

---

# 7. Lifecycle model

The integration must distinguish procurement lifecycle events.

Conceptual lifecycle:

```text
PLANNING
   ↓
COMPETITION
   ↓
CHANGE
   ↓
RESULT / AWARD
   ↓
CONTRACT MODIFICATION
   ↓
COMPLETION
```

TED eForms use different notice/form/subtype codes.

Implementation must create a tested mapping layer from TED codes to internal semantic categories rather than spreading TED-specific codes throughout the integration.

Suggested enum:

```python
class NoticeStage(StrEnum):
    PLANNING = "planning"
    COMPETITION = "competition"
    CHANGE = "change"
    RESULT = "result"
    MODIFICATION = "modification"
    COMPLETION = "completion"
    OTHER = "other"
```

Important identifiers:

```text
notice-identifier
notice-version
publication-number
procedure-identifier
```

Rules:

- `notice-identifier + notice-version` identifies a published notice version.
- `procedure-identifier` links lifecycle information belonging to the same procedure where available.
- Keep the latest version of a notice.
- Never count multiple versions of the same notice as separate new procurements.
- Never count a change notice as a new competition.
- Count unique procedures rather than raw notices wherever the metric is conceptually procedure-based.

---

# 8. Requested TED fields

The first implementation should request only fields needed by normalization and metrics.

The exact final list must be validated against the current TED field catalogue.

Candidate fields include:

## Identity and lifecycle

```text
publication-number
publication-date
notice-identifier
notice-version
notice-type
notice-subtype
form-type
procedure-identifier
previous-notice-id-proc
```

## Procedure

```text
title-proc
description-proc
internal-identifier-proc
procedure-type
contract-nature
```

## Buyer

```text
buyer-name
buyer-identifier
buyer-country
buyer-legal-type
authority-main-activity
```

## Legal/classification

```text
legal-basis
classification-cpv
main-classification-proc
additional-classification-proc
main-classification-lot
additional-classification-lot
```

## Estimated value

```text
estimated-value-proc
estimated-value-cur-proc
estimated-value-lot
estimated-value-cur-lot
```

## Results

```text
result-value-notice
result-value-cur-notice
result-value-lot
result-value-cur-lot
winner-name
winner-identifier
winner-country
winner-size
winner-decision-date
winner-selection-status
received-submissions-type-code
received-submissions-type-val
non-award-justification
tender-value
tender-value-cur
tender-value-lowest
tender-value-highest
```

## Changes

```text
change-description
change-reason-code
change-reason-description
change-procurement-documents
change-procurement-documents-date
```

## Contract modifications

```text
modification-description
modification-justification
modification-reason-description
modification-previous-notice-identifier
```

## Deadlines

Use the current TED field catalogue to select the correct lot-level tender deadline fields.

Do not depend on guessed field names.

---

# 9. Normalized internal model

All API-specific parsing belongs in the API/model layer.

The metrics layer must not work with raw TED JSON.

Suggested models:

```python
@dataclass(frozen=True)
class ProcurementNotice:
    notice_id: str
    notice_version: str | None
    publication_number: str | None
    publication_date: date
    procedure_id: str | None
    stage: NoticeStage

    title: str | None
    description: str | None

    buyer: Buyer
    legal_basis: tuple[str, ...]
    cpv_codes: tuple[str, ...]
    match_reasons: frozenset[str]

    estimated_value: Money | None
    result_value: Money | None

    tender_statistics: TenderStatistics | None
    winners: tuple[Winner, ...]

    change: ChangeInfo | None
    modification: ModificationInfo | None

    source_url: str | None
```

Supporting models:

```text
Buyer
Winner
Money
TenderStatistics
ChangeInfo
ModificationInfo
ProcedureSummary
```

Missing values must remain missing.

Never turn unknown values into:

```text
0
false
""
```

unless TED explicitly states those values.

---

# 10. Currency normalization

Cross-country monetary statistics are meaningless if currencies are simply added.

All cross-currency aggregated metrics must therefore use normalized EUR values.

Use official ECB euro reference exchange rates.

Official source:

- https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/

ECB normally updates reference rates on working days.

## Conversion rule

Keep both:

```text
original_amount
original_currency
```

and:

```text
normalized_eur_amount
fx_rate
fx_rate_date
```

For historical normalization:

- use the ECB reference rate for the relevant event date;
- if that date has no rate, use the latest previous available reference rate;
- estimated procurement value: use notice publication date;
- award/result value: prefer award decision date when present, otherwise result notice publication date.

Do not silently use today's FX rate for old notices.

If a currency cannot be converted:

- keep the original amount;
- exclude it from EUR aggregate values;
- reduce the metric's value-coverage ratio.

---

# 11. Data quality and coverage

Many TED fields are optional or context-dependent.

Every analytical metric must have an explicit population and coverage.

Examples:

```text
Single-bid share
value: 24%
sample_size: 184 lot results
bid_count_coverage: 71%
```

```text
Estimated value, 90d
value: EUR 8.4bn
procedures: 328
value_available_for: 211
value_coverage: 64.3%
```

Where useful, expose coverage in entity attributes:

```yaml
period_days: 90
sample_size: 328
covered_records: 211
coverage_pct: 64.3
```

Do not compare metrics if their denominator definitions differ.

Do not label a missing monetary field as zero value.

---

# 12. Own organisation: public footprint

The integration may optionally configure one **own organisation**.

This is not an internal-data feature.

It represents only what the public TED dataset exposes about the selected organisation.

The purpose is:

> "What can an external observer see in the public procurement record?"

The own organisation must be optional.

If it is not configured, the integration still provides the European market radar.

## Identification

Prefer a stable published organisation/buyer identifier when possible.

Store:

```text
identifier
country
canonical_name
known_aliases
```

Do not rely on name string alone if a stable identifier is available.

If the public data uses inconsistent identifiers, create a resolver layer and retain matched aliases.

---

# 13. Peer groups

The user should be able to configure peer comparison at two levels.

## Country peers

Multi-select, for example:

```text
Sweden
Finland
Denmark
Norway
Germany
Poland
...
```

Provide useful presets:

```text
Nordic
EU
Selected countries
```

Do not silently include or exclude countries.

## Organisation peers

Optional advanced feature.

Allow users to select specific public buyers.

Organisation comparison is particularly appropriate for process metrics such as:

- median number of tenders,
- single-bid share,
- public competition-to-result time,
- non-award share.

Raw total procurement value should not be presented as a "performance" comparison between organisations of different size.

---

# 14. Strategic categories

The market view becomes much more useful if activity can be grouped into defence-relevant capability categories.

Initial categories:

```text
Air & missile defence
Ammunition & explosives
Land systems
Naval & maritime
Air systems
UAS / C-UAS
C4ISR & communications
Sensors, radar & electronic warfare
Cyber & IT
Space
Logistics & support
Defence R&D
Other defence
```

Classification must be deterministic and auditable.

## Phase 1 classification

Use CPV rules only.

## Phase 2 classification

Optionally add versioned multilingual keyword rules over titles/descriptions.

Example:

```json
{
  "category": "uas_cuas",
  "cpv_prefixes": ["..."],
  "keywords": {
    "en": ["counter-uas", "counter drone", "unmanned aerial"],
    "de": ["..."],
    "fr": ["..."],
    "sv": ["..."]
  }
}
```

No LLM classification in the integration.

A notice may belong to more than one strategic category.

Always retain:

```text
classification_basis
classification_rule_version
```

for diagnostics.

---

# 15. Time windows

Use consistent rolling windows throughout the integration.

Core periods:

```text
7 days
30 days
90 days
365 days
```

Comparisons:

```text
current 30d vs previous 30d
current 90d vs previous 90d
```

Avoid comparing an incomplete current calendar month with a complete previous calendar month.

Default historical backfill should cover at least:

```text
400 days
```

This supports:

- 365-day absolute metrics,
- 90d vs previous 90d,
- 30d vs previous 30d,
- recent rolling trends.

An advanced option may increase retention/backfill later.

---

# 16. Core metrics

The metrics are grouped by the question they answer, not by TED data type.

---

## 16.1 European market activity

### `market_new_competitions_30d`

Count of unique relevant procedures with a competition first published during the last 30 days.

Do not count:

- change notices,
- new versions of an existing notice,
- result notices.

Attributes:

```yaml
previous_30d: 142
change_count: 31
change_pct: 21.8
```

### `market_new_competitions_90d`

Same definition over 90 days.

Attributes include previous 90 days and change percentage.

### `market_estimated_value_30d`

Sum of normalized estimated EUR values for new competitions in the period.

Attributes must include coverage.

### `market_estimated_value_90d`

Same over 90 days.

### `market_award_value_30d`

Result/award value observed during the period.

Do not mix:

- estimated procurement value,
- maximum framework value,
- actual awarded/result value.

### `market_award_value_90d`

Same over 90 days.

---

## 16.2 External radar

When an own organisation is configured, "external" metrics exclude that organisation.

### `external_new_competitions_7d`

Number of new relevant competitions outside the own organisation.

Attributes contain at most the 10 most significant/recent records.

### `largest_external_competition_7d`

State:

```text
normalized EUR estimated value
```

Attributes:

```yaml
title:
buyer:
country:
publication_date:
original_value:
original_currency:
value_eur:
category:
ted_url:
```

If no comparable value exists, entity should be `unknown`.

### `largest_external_award_7d`

Equivalent for published result/award values.

This is intentionally outward-looking.

---

## 16.3 Country landscape

### `top_country_by_value_90d`

State:

```text
ISO country code
```

Attributes contain top 10:

```yaml
ranking:
  - rank: 1
    country: DE
    value_eur: ...
    procedures: ...
    change_pct: ...
  - ...
```

### `fastest_growing_country_90d`

State is country code.

Growth definition:

```text
current 90d vs immediately preceding 90d
```

Apply minimum activity thresholds to prevent a tiny baseline from creating meaningless extreme percentages.

Initial eligibility recommendation:

```text
current period >= 5 relevant procedures
OR
current normalized value >= EUR 50m
```

The exact threshold should be a named constant and covered by tests.

Attributes contain top growth ranking.

---

## 16.4 Capability/category landscape

### `top_category_by_value_90d`

State is category ID/name.

Attributes contain ranking.

### `fastest_growing_category_90d`

State is category ID/name.

Use the same current-90d vs previous-90d definition and minimum activity rule.

### Optional category-specific sensors

The config flow can allow users to pin selected categories.

For each pinned category create a device or entity group with:

```text
competition count 30d
competition count change %
estimated value 90d
estimated value change %
award value 90d
```

Do not create dozens of category sensors by default.

---

## 16.5 Public footprint of the selected organisation

Only create these entities if an own organisation is configured.

### `own_public_competitions_30d`

Unique new competitions publicly visible in TED.

### `own_public_estimated_value_30d`

Normalized EUR value, with original-currency details where useful.

### `own_public_awards_30d`

Count of result/award events.

### `own_public_award_value_30d`

Normalized result value.

### `own_public_changes_30d`

Number of public change notices.

### `own_public_modifications_365d`

Number of public contract-modification notices.

The integration must describe these as **public footprint metrics**, not internal business metrics.

---

# 17. Competition/process metrics

These are potentially highly useful but must use precise definitions.

---

## 17.1 Median tenders

TED represents received submissions using a type code plus a numeric value.

Do not assume every `received-submissions-type-val` means "number of tenders".

Implement and test a mapping from the official TED codelist.

### `market_median_tenders_365d`

Median valid tender-count observation for relevant result lots.

Attributes:

```yaml
sample_size:
coverage_pct:
```

### `own_median_tenders_365d`

Same for the selected organisation.

### `peer_median_tenders_365d`

Same for selected organisation peers.

---

## 17.2 Single-bid share

A lot result is single-bid only if the applicable TED submission statistic explicitly indicates exactly one tender under the selected comparable tender-count definition.

### `market_single_bid_share_365d`

```text
single_bid_lot_results / lot_results_with_comparable_bid_count
```

### `own_single_bid_share_365d`

Same for own public footprint.

### `peer_single_bid_share_365d`

Same for organisation peers.

For comparison entities, expose factual differences:

```yaml
own_pct: 24.0
peer_pct: 13.0
difference_percentage_points: 11.0
```

Do not label this "good", "bad", "low competition", or "high competition".

---

## 17.3 Public competition-to-result time

Avoid claiming this equals total procurement lead time.

Define the metric explicitly as:

> days from first observed competition publication to first observed result publication for the same procedure.

### `market_median_public_time_to_result_365d`

Unit:

```text
days
```

### `own_median_public_time_to_result_365d`

### `peer_median_public_time_to_result_365d`

Expose sample size and procedure-link coverage.

A separate future metric may use winner decision date when sufficiently complete, but do not mix the two definitions.

---

## 17.4 Non-award share

TED result notices can state a non-award justification.

Define:

```text
non_awarded_lot_results / decided_lot_results
```

Create only after fixture research confirms reliable parsing across relevant notice types.

Candidate entities:

```text
market_non_award_share_365d
own_non_award_share_365d
peer_non_award_share_365d
```

Phase 2 unless data-quality testing demonstrates high coverage.

---

# 18. Supplier landscape

Supplier metrics are based only on public result/award information.

## `top_supplier_by_award_value_365d`

State:

```text
supplier display name
```

Attributes contain top 10 supplier/award groups and normalized award values.

Take care with:

- joint tenders,
- consortiums,
- multiple winners,
- framework agreements,
- repeated organisation aliases.

Do not double-count the same tender value once per consortium member.

## `supplier_top5_share_365d`

Share of comparable awarded value represented by the top five supplier/consortium groups.

## `supplier_concentration_hhi_365d`

Optional Phase 2 metric.

HHI:

```text
sum(market_share_i ** 2)
```

Document whether shares are expressed as fractions or percentage points before calculating.

Only publish HHI when:

- award-value coverage is above a configured minimum,
- winner identification coverage is above a configured minimum,
- consortium grouping is reliable.

Attributes must expose coverage.

Do not attach qualitative labels such as "dangerous concentration".

---

# 19. Comparative/ranking metrics

The integration should expose comparison facts without interpretation.

Useful examples:

```text
Sweden rank by estimated defence procurement value, 90d
Sweden percentile by new competition count, 90d
Selected organisation median bids
Peer median bids
Difference
```

Candidate sensors:

```text
selected_country_value_rank_90d
selected_country_activity_rank_90d
selected_country_value_percentile_90d
own_vs_peer_single_bid_delta_pp
own_vs_peer_median_tenders_delta
own_vs_peer_public_time_to_result_delta_days
```

Ranking population must be explicit in attributes:

```yaml
population: "configured peer countries"
population_size: 8
```

or:

```yaml
population: "EU countries with >= 5 eligible procedures"
population_size: 23
```

---

# 20. Factual change/outlier view

The integration should help surface facts that are easy to miss without claiming why they matter.

Avoid:

```text
media_attention_score
minister_attention_score
likely_question
```

Instead expose measurable change.

## `largest_country_change_90d`

State:

```text
country code
```

Attributes:

```yaml
current_value_eur:
previous_value_eur:
change_eur:
change_pct:
current_procedures:
previous_procedures:
```

## `largest_category_change_90d`

Same for strategic category.

## `public_footprint_largest_change`

If an own organisation is configured, expose the own metric with the largest absolute standardized change from its own recent baseline.

Phase 2 only.

If implemented, use an explicit statistical method such as:

- robust z-score using median absolute deviation, or
- percentile of rolling historical observations.

The method must be documented and all raw values must be exposed.

Never turn it into a narrative.

---

# 21. Recommended Home Assistant entity model

Use one config entry for the radar configuration.

Create service-type devices to group related entities.

Suggested devices:

```text
European Defence Market
External Radar
Selected Organisation      (optional)
Peer Comparison            (optional)
Supplier Landscape         (optional)
Pinned Category: <name>    (zero or more)
```

Manufacturer:

```text
TED / Publications Office of the European Union
```

Do not pretend that TED itself produced the derived metrics.

Model for derived devices can be:

```text
EDP Radar Analytics
```

Use `_attr_has_entity_name = True`.

---

# 22. Core MVP entity set

Keep enabled-by-default entities limited.

## European Defence Market

```text
sensor.market_new_competitions_30d
sensor.market_new_competitions_90d
sensor.market_estimated_value_30d
sensor.market_estimated_value_90d
sensor.market_award_value_30d
sensor.market_award_value_90d
sensor.top_country_by_value_90d
sensor.fastest_growing_country_90d
sensor.top_category_by_value_90d
sensor.fastest_growing_category_90d
```

## External Radar

```text
sensor.external_new_competitions_7d
sensor.largest_external_competition_7d
sensor.largest_external_award_7d
```

## Selected Organisation, if configured

```text
sensor.own_public_competitions_30d
sensor.own_public_estimated_value_30d
sensor.own_public_awards_30d
sensor.own_public_award_value_30d
sensor.own_public_changes_30d
```

## Competition metrics, enabled only when sufficient data exists

```text
sensor.market_median_tenders_365d
sensor.market_single_bid_share_365d
sensor.market_median_public_time_to_result_365d
```

Own/peer equivalents can be enabled when the corresponding configuration exists.

Less important or experimental sensors should be disabled by default.

---

# 23. Event entities

Use Home Assistant event entities for newly observed procurement lifecycle events.

Suggested event entity:

```text
event.procurement_activity
```

Event types:

```text
new_competition
change
result
contract_modification
```

Event attributes should contain only hard facts:

```yaml
notice_id:
procedure_id:
stage:
title:
buyer:
buyer_country:
publication_date:
estimated_value:
estimated_currency:
estimated_value_eur:
result_value:
result_currency:
result_value_eur:
categories:
match_reasons:
source_url:
```

A second optional event entity can represent watchlist matches:

```text
event.watchlist_activity
```

No event should contain generated interpretation.

---

# 24. Watchlists

Configurable watchlists should make the integration personally useful without changing the objective nature of the data.

Allow watchlists for:

```text
countries
buyers
strategic categories
suppliers       (Phase 2)
minimum estimated value
minimum award value
```

Example event condition:

```text
country = PL
category = air_missile_defence
estimated_value_eur >= 500_000_000
```

The integration emits the matching factual event.

The user can then create their own Home Assistant notification automation.

---

# 25. Text/display sensors

A small number of compact factual text sensors are useful for mobile dashboards.

They must not interpret the numbers.

Examples:

## `market_snapshot_text`

```text
"184 competitions / 90d · EUR 31.4bn · +26.6% vs previous 90d"
```

## `external_latest_text`

```text
"DE · Air defence · EUR 640m · published 2026-09-11"
```

## `country_ranking_text`

```text
"DE EUR 8.4bn · PL EUR 6.1bn · FR EUR 4.9bn · SE EUR 2.0bn"
```

These are convenience representations.

The structured numeric sensors remain the source of truth.

---

# 26. Visualization goals

The integration should expose entities that work well with native Home Assistant dashboards.

A custom card is not required for MVP.

Recommended dashboard concepts:

## 26.1 Snapshot

```text
┌─────────────────────────────────────┐
│ EUROPEAN DEFENCE PROCUREMENT        │
│                                     │
│ New competitions 30d      184       │
│ vs previous 30d          +22%       │
│ Estimated value         €8.7bn      │
│ Award value             €6.4bn      │
└─────────────────────────────────────┘
```

Use:

- Tile cards,
- Entities cards,
- Gauge only when there is a meaningful fixed range.

Avoid arbitrary red/yellow/green thresholds.

---

## 26.2 Trend

Use Home Assistant history/statistics graphs for numeric rolling sensors:

```text
market_new_competitions_30d
market_estimated_value_30d
market_award_value_30d
```

This provides a simple visible trend without a custom frontend.

---

## 26.3 Country comparison

Expose top-10 country ranking in attributes.

README should provide an example using a Markdown/template card.

A later companion custom card may render bars, but is not part of this repository's MVP.

---

## 26.4 Capability comparison

Same approach as countries:

```text
category
value 90d
change vs previous 90d
procedure count
```

Top/faster-growing category sensors should be enough for a small mobile view.

---

## 26.5 Public footprint

Recommended compact panel:

```text
Selected organisation — public TED footprint

Competitions 30d
Estimated value 30d
Awards 30d
Award value 30d
Change notices 30d

Median tenders 365d
Single-bid share 365d
Public time to result 365d
```

No qualitative rating.

---

## 26.6 Peer comparison

Present:

```text
OWN        PEER MEDIAN        DIFFERENCE
```

for comparable process metrics.

Example:

```text
Median tenders
3.2            4.1             -0.9

Single-bid share
24%            13%             +11 pp

Public time to result
171 d          146 d            +25 d
```

The dashboard lets the user draw the conclusion.

---

# 27. Config flow

All setup must be UI based.

No YAML configuration.

Suggested flow:

## Step 1 — relevance mode

```text
Defence relevance

○ Strict defence
  Defence buyers + Defence/Security Directive

● Broad defence
  Strict defence + curated defence CPV codes
```

Default:

```text
Strict defence
```

The user can later switch to broad mode in Options.

---

## Step 2 — market scope

Select country universe.

Presets:

```text
EU
Nordic
Custom
```

For broad European market analytics, default to countries covered by TED where defence data is present.

The exact country inclusion list must be explicit and stored in config.

---

## Step 3 — own organisation

Optional:

```text
Do you want to track a selected organisation's public footprint?
```

If yes:

1. enter/select country;
2. enter search term;
3. integration queries TED for recent buyer records;
4. show candidate buyer names and identifiers;
5. user selects exact public buyer identity.

Do not save an unvalidated free-text organisation name if a stable identifier can be resolved.

---

## Step 4 — peers

Optional.

Country peer presets:

```text
Nordic
Selected EU countries
Custom
```

Organisation peers should be advanced/optional.

---

## Step 5 — strategic categories

Optional multi-select:

```text
Air & missile defence
Ammunition & explosives
Land systems
Naval & maritime
Air systems
UAS / C-UAS
C4ISR & communications
Sensors, radar & EW
Cyber & IT
Space
Logistics & support
Defence R&D
```

Selected categories receive dedicated entities.

---

## Step 6 — watchlist

Optional:

```text
countries
buyers
minimum value
```

Supplier watchlist can be Phase 2.

---

# 28. Options flow

The following should be changeable without deleting the integration:

```text
relevance mode
market countries
own organisation
peer countries
peer organisations
pinned categories
watchlist
minimum event thresholds
```

Changing the own organisation must update device/entity registry cleanly.

Use ConfigEntry options for settings that are not required to establish basic API connectivity.

Follow current Home Assistant config-flow conventions.

---

# 29. Update strategy

TED is not a real-time source.

Default polling:

```text
every 4 hours
```

Reasons:

- OJ S normally publishes Monday-Friday.
- TED states notices become available during the publication morning.
- Four-hour polling is frequent enough for a private external radar.
- It places negligible unnecessary load on a public API.

On Home Assistant startup, refresh immediately unless a very recent successful cache exists.

Do not poll every few minutes.

---

# 30. Historical bootstrap and incremental updates

The integration needs local history to compute rolling metrics efficiently.

## Initial bootstrap

Fetch at least:

```text
last 400 days
```

using TED iteration/scroll mode.

Filter server-side to the configured defence universe before downloading.

Request only necessary fields.

Normalize all retrieved records.

---

## Incremental refresh

Maintain:

```text
last_successful_publication_date
last_seen_notice_versions
```

Each refresh queries with a small overlap:

```text
from = last_successful_publication_date - 2 days
```

The overlap handles:

- republished versions,
- late changes,
- date-boundary issues.

Deduplicate locally.

Never assume that a previously seen notice cannot get a new version.

---

# 31. Local persistence

Do not depend on Home Assistant Recorder as the integration's source database.

Recorder is for HA state history and may be disabled, purged, or configured differently.

Use Home Assistant's storage helper.

Avoid one unbounded giant JSON document.

Recommended approach:

```text
edp_radar.index
edp_radar.notices.2026-09
edp_radar.notices.2026-08
...
edp_radar.fx
```

Store normalized records partitioned by publication month.

Benefits:

- bounded writes,
- simple retention,
- easy migration,
- simple removal of expired history,
- no custom database dependency.

Use versioned schemas.

Example index metadata:

```json
{
  "schema_version": 1,
  "last_successful_update": "...",
  "last_publication_date": "...",
  "retention_days": 400
}
```

Use delayed/batched saves where appropriate.

---

# 32. Retention

Default:

```text
400 days
```

Prune whole monthly partitions once all records fall outside retention.

Do not retain full raw TED responses.

Persist only normalized fields needed for:

- metrics,
- lifecycle linking,
- deduplication,
- event reproduction,
- diagnostics.

---

# 33. Coordinator architecture

Use Home Assistant `DataUpdateCoordinator`.

Suggested runtime flow:

```text
DataUpdateCoordinator
        │
        ├── TED client
        ├── ECB FX client
        ├── local store
        ├── normalizer
        ├── lifecycle index
        └── metrics engine
                  │
                  ▼
             RadarSnapshot
```

Entities read only from `RadarSnapshot`.

Entities must never make their own HTTP calls.

---

# 34. Suggested repository structure

```text
ha-edp-radar/
├── custom_components/
│   └── edp_radar/
│       ├── __init__.py
│       ├── api.py
│       ├── config_flow.py
│       ├── const.py
│       ├── coordinator.py
│       ├── diagnostics.py
│       ├── entity.py
│       ├── event.py
│       ├── fx.py
│       ├── lifecycle.py
│       ├── manifest.json
│       ├── metrics.py
│       ├── models.py
│       ├── normalizer.py
│       ├── sensor.py
│       ├── storage.py
│       ├── strings.json
│       ├── taxonomy.py
│       ├── data/
│       │   ├── defence_cpv.json
│       │   └── strategic_categories.json
│       └── translations/
│           └── sv.json
├── tests/
│   ├── fixtures/
│   ├── test_api.py
│   ├── test_config_flow.py
│   ├── test_fx.py
│   ├── test_lifecycle.py
│   ├── test_metrics.py
│   ├── test_normalizer.py
│   ├── test_sensor.py
│   ├── test_storage.py
│   └── test_taxonomy.py
├── hacs.json
├── pyproject.toml
├── README.md
├── LICENSE
└── PROJECT.md
```

---

# 35. API client

Use Home Assistant's shared aiohttp client:

```python
async_get_clientsession(hass)
```

Suggested interface:

```python
class TedApiClient:
    async def async_search_notices(
        self,
        query: str,
        fields: Sequence[str],
        *,
        pagination_mode: PaginationMode,
    ) -> AsyncIterator[dict]:
        ...

    async def async_validate_query(self, query: str) -> None:
        ...
```

FX interface:

```python
class FxProvider:
    async def async_get_eur_rate(
        self,
        currency: str,
        date: date,
    ) -> FxRate | None:
        ...
```

Set explicit connect/read timeouts.

Handle HTTP 429 and 5xx as temporary failures.

No aggressive retry loop.

---

# 36. Query builder

Never assemble expert queries ad hoc throughout the code.

Implement:

```python
class TedQueryBuilder:
    def defence_universe(...)
    def publication_range(...)
    def buyer(...)
    def countries(...)
    def combine_and(...)
    def combine_or(...)
```

Query builder tests are mandatory.

The defence-universe query should be constructed from configuration and versioned taxonomy.

---

# 37. Metrics engine

`metrics.py` should be pure Python where possible.

Input:

```text
normalized notices/procedures
configuration
current date
```

Output:

```python
@dataclass(frozen=True)
class RadarSnapshot:
    market: MarketMetrics
    external: ExternalMetrics
    own: OrganisationMetrics | None
    peers: PeerMetrics | None
    suppliers: SupplierMetrics | None
    categories: Mapping[str, CategoryMetrics]
    quality: DataQualityMetrics
```

Pure functions make statistical calculations independently testable.

No Home Assistant entity code in the metrics layer.

---

# 38. Procedure linking

Build a lifecycle index keyed primarily by:

```text
procedure_id
```

For each procedure track:

```text
first planning publication
first competition publication
latest competition version
change notices
first result publication
latest result
modification notices
completion notices
```

If `procedure_id` is absent, do not invent a cross-notice link based only on similar title.

Such records can still contribute to notice-level metrics but not lifecycle-duration metrics.

---

# 39. Monetary aggregation rules

Avoid double counting.

## Estimated value

Preferred hierarchy:

1. procedure-level estimated value;
2. if missing, sum complete unique lot-level estimated values only when doing so is structurally safe;
3. otherwise unknown.

Do not add procedure and lot totals together.

## Result/award value

Preferred hierarchy:

1. notice-level result value;
2. if missing, sum unique lot-result values where structurally safe;
3. otherwise unknown.

Framework maximum values are a separate concept.

Do not mix them into award values.

Add dedicated framework metrics only in a later version.

---

# 40. Tender-count parsing

`received-submissions-type-code` and `received-submissions-type-val` must be parsed as pairs.

Create explicit domain objects:

```python
@dataclass(frozen=True)
class SubmissionStatistic:
    type_code: str
    value: int
```

Map only official type codes that represent comparable tender counts into the competition metrics.

Fixtures must include:

- total tenders,
- electronic tenders,
- SME tenders,
- tenders from other countries,
- requests to participate,

so tests prove that the wrong subtype is not used.

---

# 41. Supplier identity

Supplier names are not guaranteed to be globally normalized.

Initial identity hierarchy:

1. stable winner identifier where available;
2. normalized `(country, identifier)`;
3. normalized name + country as fallback.

Never merge suppliers solely through fuzzy matching in MVP.

Keep alias reconciliation conservative.

Expose unknown/ambiguous identities rather than over-merging them.

---

# 42. Event deduplication

An event should be emitted once when a previously unseen relevant notice version is ingested.

Key:

```text
notice_id + notice_version
```

If a new version appears, it may generate an update event depending on stage.

Persist emitted keys or a recent bounded event index so restart does not replay old events.

Initial bootstrap must **not** emit hundreds of historical events.

Events begin after bootstrap completes.

---

# 43. Failure handling

## TED unavailable

Coordinator raises `UpdateFailed`.

Existing entity state should remain available according to normal Coordinator behavior.

## ECB unavailable

TED ingestion may continue.

New monetary records with currencies requiring unavailable rates remain unnormalized until a later refresh.

Do not fail the entire integration solely because FX normalization is temporarily unavailable.

## Malformed notice

Skip only the affected notice where possible.

Record diagnostic count:

```text
parse_errors
```

Log enough identity data to debug without dumping entire payloads.

## Schema change

Required identity fields missing repeatedly should produce a clear integration error.

Do not allow silent widespread metric corruption.

---

# 44. Diagnostics

Support Home Assistant diagnostics.

Include:

```text
integration version
config mode
country universe
peer configuration
taxonomy version
last TED update
last ECB update
last publication date observed
stored notice count
stored procedure count
records by stage
parse error count
unlinked result count
FX conversion coverage
value coverage
bid-count coverage
storage schema version
```

Do not dump all stored notices.

Include a few redacted/sample record schemas only if needed.

There are no credentials in normal operation.

---

# 45. Data freshness

Create a diagnostic/default-disabled timestamp sensor:

```text
sensor.ted_data_last_updated
```

State:

```text
last successful API refresh
```

Attributes:

```yaml
latest_publication_date:
stored_notices:
```

Do not mark the whole integration unavailable merely because there are no new notices over a weekend.

---

# 46. Home Assistant conventions

Follow current Home Assistant integration practices:

- UI config flow.
- `ConfigEntry.data` for connection/identity essentials.
- `ConfigEntry.options` for user-tunable analytics/watchlist settings.
- `DataUpdateCoordinator`.
- common base entity in `entity.py`.
- full async I/O.
- shared aiohttp session.
- `_attr_has_entity_name = True`.
- config-flow tests.
- diagnostics.
- translations.
- explicit polling documentation.
- typed code.
- Ruff/mypy-style cleanliness appropriate to the repository.
- no blocking network or disk I/O in the event loop.

Target at least Home Assistant's current Bronze-quality expectations even though this begins as a HACS integration.

Relevant current docs:

- https://developers.home-assistant.io/docs/core/integration/config_flow/
- https://developers.home-assistant.io/docs/core/integration-quality-scale/
- https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow/
- https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/common-modules/
- https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-data-update/

---

# 47. Testing strategy

Tests are not optional because the project derives statistics from imperfect public data.

## API fixtures

Collect representative, redistributable fixtures or minimized synthetic fixtures based on actual schemas for:

```text
planning notice
competition notice
change notice
result notice
non-awarded result
contract modification
completion notice
multi-lot procedure
multi-winner result
joint tender/consortium
missing estimated value
missing procedure ID
multiple notice versions
non-EUR currency
received-submission statistics with several type codes
```

Avoid retaining unnecessary personal/contact fields in fixtures.

---

## Query tests

Test:

- strict defence query,
- broad defence query,
- country filter,
- buyer filter,
- date filter,
- operator precedence,
- escaping,
- maximum page-size calculation.

---

## Normalizer tests

Test:

- missing fields,
- lists vs scalars,
- multilingual values,
- multiple buyers,
- multiple CPVs,
- multiple winners,
- stage mapping,
- value extraction,
- URLs,
- malformed records.

---

## Lifecycle tests

Test:

```text
competition → change → result
competition v1 → competition v2
planning → competition → result → modification
result without known competition
missing procedure ID
```

---

## Metrics tests

Use small deterministic datasets with hand-calculated expected outputs.

Mandatory:

- unique procedure counting,
- period boundaries,
- current vs previous period,
- median,
- percentage change,
- percentage-point difference,
- value coverage,
- ranking ties,
- percentile definition,
- category multi-label behaviour,
- own organisation exclusion from external radar,
- minimum-volume filters,
- no double counting of lot + procedure values,
- no double counting consortium awards.

---

## FX tests

Test:

- EUR passthrough,
- SEK conversion,
- PLN conversion,
- weekend fallback,
- missing currency,
- unavailable ECB data,
- historical rate selection.

---

## Config flow tests

Test:

- successful no-own-org setup,
- own-organisation selection,
- peer setup,
- API unavailable,
- invalid buyer selection,
- no matching buyer,
- duplicate config entry,
- options updates.

---

## Storage tests

Test:

- bootstrap,
- restart,
- monthly partition load/save,
- schema migration,
- retention pruning,
- deduplication,
- historical event suppression.

---

# 48. Security and privacy

The integration reads public data only.

It should not require user credentials.

Do not send Home Assistant data to TED beyond the public search query necessary for the configured radar.

Do not add analytics/telemetry.

Do not use external AI services.

Do not infer private organisational information from the public data.

---

# 49. Performance requirements

The integration must be reasonable on normal Home Assistant hardware.

Goals:

- No repeated 400-day backfill after successful initialization.
- Incremental refresh normally fetches only a few publication days.
- Metrics run against normalized compact data.
- Avoid O(n²) procedure matching.
- Index by notice ID, procedure ID, buyer ID, publication date, country, category.
- Do not create one HA entity per procurement notice.
- Limit ranking attributes to top 10.
- Limit recent-item attributes to top 10.
- Avoid giant `extra_state_attributes`, because Recorder stores attributes with entity state history.

---

# 50. Suggested implementation phases

## Phase 0 — API research harness

Before Home Assistant code:

Create a small developer script/test harness that can:

```text
query TED
download 30/90/400 day samples
list field coverage
show notice-stage distribution
show buyer identifiers
show currency distribution
show bid-count statistic type codes
show result-value coverage
```

Deliver:

```text
docs/data-profile.md
```

This profile must quantify actual data quality before advanced metrics are enabled.

---

## Phase 1 — API + normalization

Implement:

```text
TedApiClient
TedQueryBuilder
normalizer
models
defence relevance matching
stage mapping
```

No sensors yet.

Acceptance:

- representative API fixtures parse;
- strict/broad query works;
- records are stable typed models.

---

## Phase 2 — storage + bootstrap

Implement:

```text
400-day bootstrap
monthly partition storage
incremental overlap refresh
deduplication
retention
```

Acceptance:

- restart does not trigger full backfill;
- latest versions replace old versions correctly;
- no historical events emitted.

---

## Phase 3 — core market metrics

Implement:

```text
new competitions 30d/90d
estimated value 30d/90d
award value 30d/90d
country ranking
category ranking
fastest-growing country
fastest-growing category
coverage attributes
```

Add ECB FX normalization.

Acceptance:

- all monetary cross-country totals are normalized;
- missing values never become zero;
- metrics pass deterministic unit tests.

---

## Phase 4 — Home Assistant shell

Implement:

```text
manifest
config flow
coordinator
devices
sensor platform
translations
diagnostics
```

Create core MVP entities.

---

## Phase 5 — external radar + events

Implement:

```text
external_new_competitions_7d
largest_external_competition_7d
largest_external_award_7d
event.procurement_activity
watchlist events
```

Own organisation must be excluded correctly from external radar when configured.

---

## Phase 6 — own public footprint + peers

Implement:

```text
own public footprint entities
country peer comparisons
organisation peer selection
```

No interpretation.

---

## Phase 7 — competition/process metrics

Only after field coverage is measured.

Implement:

```text
median tenders
single-bid share
public competition-to-result time
```

Enable a metric only when its parser and denominator are explicit and tested.

---

## Phase 8 — supplier landscape

Implement:

```text
winner normalization
top suppliers
top-five share
optional HHI
```

Do not release concentration metrics until consortium handling is verified.

---

## Phase 9 — HACS release

Add:

```text
README
HACS metadata
screenshots
example dashboard
release workflow
issue templates
```

Document:

- data source,
- update cadence,
- metric definitions,
- public-data limitations,
- currency conversion,
- coverage,
- lack of narrative interpretation.

---

# 51. MVP definition

The first useful release should include:

```text
Config flow
Strict/broad defence relevance
Country scope
Optional selected organisation
Optional peer countries
Pinned strategic categories

400-day historical bootstrap
4-hour incremental updates
ECB EUR normalization

Market:
  competitions 30d / 90d
  estimated value 30d / 90d
  award value 30d / 90d
  top country
  fastest-growing country
  top category
  fastest-growing category

External:
  new competitions 7d
  largest competition 7d
  largest award 7d

Selected organisation:
  public competitions 30d
  public estimated value 30d
  public awards 30d
  public award value 30d
  public changes 30d

Event entity:
  new competition
  change
  result
  modification

Diagnostics and coverage
```

Competition metrics such as single-bid share may be included in the first public release only if Phase 0 demonstrates sufficient data quality.

---

# 52. Important implementation rules

1. **Hard facts only.**
2. **No LLMs.**
3. **No generated interpretation.**
4. **Never sum mixed currencies without historical FX normalization.**
5. **Never replace missing data with zero.**
6. **Always expose sample size/coverage for incomplete statistics.**
7. **Use unique procedures, not raw notice counts, for procedure metrics.**
8. **Do not count change notices as new procurements.**
9. **Do not double-count procedure and lot values.**
10. **Do not equate TED publication timing with complete procurement lead time.**
11. **Do not call external public data an internal performance measure.**
12. **Own-organisation data is a public footprint, not an internal dashboard.**
13. **External radar should primarily surface what other actors are doing.**
14. **Keep taxonomy deterministic, versioned, and auditable.**
15. **No arbitrary red/yellow/green judgement thresholds.**

---

# 53. Open research questions before advanced metrics

These do not block the core MVP but must be answered before enabling some analytics.

## Tender-count semantics

Confirm all relevant values for:

```text
received-submissions-type-code
```

and which represent comparable numbers of actual tenders.

## Result value semantics

Measure how often:

```text
result-value-notice
result-value-lot
tender-value
```

are available and how they relate across notice types.

## Buyer identity stability

Measure:

- identifier coverage,
- alias changes,
- organisation renaming,
- duplicate public identities.

## Procedure-link coverage

Measure percentage of result notices that can be reliably linked to a competition through `procedure-identifier`.

## Supplier identity

Measure stable winner-identifier coverage before supplier concentration metrics.

## Category classification quality

Measure how much strategic-category coverage CPV-only rules provide.

Only then decide whether multilingual keyword rules are required.

---

# 54. Data-quality research report required from the first coding agent

Before implementing advanced statistics, generate a reproducible report using at least a recent 90-day sample and, if practical, the full 400-day bootstrap window.

The report should include:

```text
relevant notice count
unique procedure count

stage distribution

share matched by:
  defence buyer activity
  defence legal basis
  defence CPV
  combinations of the above

country distribution

estimated-value coverage
result-value coverage
currency distribution
FX-convertible coverage

procedure-ID coverage
buyer-ID coverage
winner-ID coverage

bid-count coverage
received-submission type-code distribution

change-notice count
modification-notice count
non-award coverage

top CPV groups
unclassified strategic-category share
```

This report is a development artifact and should drive which optional sensors are enabled.

Do not assume field completeness from the formal schema alone.

---

# 55. Source documentation

## TED

Search API:

https://docs.ted.europa.eu/api/latest/search.html

Search API reuse/pagination:

https://docs.ted.europa.eu/ODS/latest/reuse/search-api.html

Search field list:

https://docs.ted.europa.eu/ODS/latest/reuse/field-list.html

Competition results:

https://docs.ted.europa.eu/eforms/latest/schema/competition-results.html

Documents/forms/notices:

https://docs.ted.europa.eu/eforms/latest/schema/documents-forms-and-notices.html

TED publication/data reuse:

https://ted.europa.eu/en/help/data-reuse

OJ S release calendar:

https://ted.europa.eu/en/release-calendar

## ECB

Euro reference rates:

https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/

## Home Assistant

Config flow:

https://developers.home-assistant.io/docs/core/integration/config_flow/

Integration Quality Scale:

https://developers.home-assistant.io/docs/core/integration-quality-scale/

Config-flow quality rule:

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow/

Common modules / Coordinator pattern:

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/common-modules/

Data-update documentation rule:

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-data-update/

---

# 56. Definition of success

The integration is successful when a user can open Home Assistant on a phone and, within seconds, see factual answers to:

```text
How active is European defence procurement right now?

Which countries are most active?

Which areas are growing fastest?

What large procurement activity outside my organisation appeared recently?

What does the public TED record show about my selected organisation?

How do selected comparable public process metrics differ from peers?

Which suppliers are receiving the largest publicly reported awards?

How complete is the underlying data for each statistic?
```

The user should not need the integration to tell them what those facts mean.

That judgement remains with the user.

# European Defence Procurement Radar for Home Assistant

A read-only [Home Assistant](https://www.home-assistant.io/) custom integration
that turns the public EU procurement feed ([TED – Tenders Electronic
Daily](https://ted.europa.eu/)) into a small set of factual sensors about
European defence procurement. Its primary question is **which countries buy
the most defence materiel** – how much, what, and how that is changing – seen
from one country you pick as *My country*. Around that it reports how many
competitions were published, for how much money, in which categories, how
contested they were, and what one selected organisation (for example your own
agency) has made public.

> **Awarded value is publicly reported TED contract-award value.** It is not
> defence expenditure, budget or cash paid, and every total carries the share
> of awards that actually reported a usable value.

It is a **radar, not an analyst**: every number is a count, a sum, a median or
a share of what TED actually reports, each value sensor carries its coverage
ratio, and there are no ratings, forecasts or traffic lights. Interpretation is
left to the person looking at the dashboard.

No API key, account or YAML is needed. The TED Search API and the ECB reference
rates are public.

## What you get

| Device | Contents |
| --- | --- |
| **My Country: …** | Awarded contract value of the country you selected – 12 months, previous 12 months, change, rank, share of the European total, coverage, categories, largest awards, monthly series |
| **European Purchasing** | The European total (attributable + joint), largest buyer, joint/multinational value, largest award, quarantined implausible values |
| **Country Ranking** | The ordered country table by awarded value (12 months and 90 days), My country always included, and the fastest-growing countries |
| **European Defence Market** | Market activity, value, country and category rankings, competition metrics, data freshness, the `procurement_activity` event |
| **External Radar** | The last 7 days seen from the outside: new competitions and the largest competition/award |
| **Selected Organisation** *(optional)* | The public TED footprint of one buyer you pick in the config flow |
| **Peer Comparison** *(optional)* | Competition metrics for a peer group of countries, the rank of one selected country, and own-vs-peer deltas |
| **Supplier Landscape** | Top supplier group by award value and top-5 share (disabled by default) |
| **Pinned Category: …** *(optional, one per category)* | Competitions and values for a strategic category you pin |
| **Raw Data: …** *(optional, one per country)* | The latest notices of each kind for one buyer country, unaggregated, plus breakdowns of everything stored for it |
| **Statskontoret**, **Eurostat**, **NATO**, **EDA**, **SIPRI** | Defence spending – 27 sensors across five devices reading official statistics for Sweden: value, change, rank and share per source, two one-line text summaries, and a disabled-by-default data-age diagnostic per device (see *Defence spending* below) |

## Data sources and update cadence

- **Notices:** `POST https://api.ted.europa.eu/v3/notices/search` (TED Search
  API v3, eForms notices). On first setup the integration fetches the last
  **760 days** (24 months of awards plus publication lag, so that the rolling
  12 months can be compared with the previous 12) of defence-relevant notices
  in a background task (about 48 000 notices, ≈350 requests, ten to fifteen
  minutes; entities show `unknown` until it finishes). After that it polls
  **every 4 hours** for notices published since the last known publication
  date (with a two-day overlap). TED publishes Monday to Friday; a quiet
  weekend is not an error. An installation bootstrapped over a shorter window
  (before Phase 2: 400 days) bootstraps once more after upgrading; stored
  notices are kept.
- **Currency rates:** ECB euro reference rates (`eurofxref-hist.zip` once at
  bootstrap, `eurofxref-hist-90d.xml` on every refresh).
- **Storage:** normalized notices are kept in Home Assistant's `.storage`
  as monthly partitions (`edp_radar.<entry>.notices.<YYYY-MM>`, roughly
  120 MB for 760 days), pruned to the retention window on every refresh, and
  deleted when the integration is removed.
- **Failures:** if TED is unreachable during a refresh the sensors keep their
  last values computed from stored data and the error is shown in diagnostics
  and on the `TED data last updated` sensor. The integration only fails to set
  up when nothing is stored yet and TED cannot be reached.

## Installation

### HACS (recommended)

1. In HACS, open **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/mattahr/ha-edp-radar` with category **Integration**.
3. Install **European Defence Procurement Radar** and restart Home Assistant.

### Manual

Copy `custom_components/edp_radar` into your Home Assistant
`config/custom_components/` directory and restart Home Assistant.

## Configuration

**Settings → Devices & services → Add integration → European Defence
Procurement Radar**. Only one instance can be configured. Every step can be
changed later under **Configure** on the entry (the entry reloads and the
affected devices appear or disappear).

1. **Procurement universe** – *Strict* (buyers whose main activity is defence,
   or notices under the defence and security directive 2009/81/EC) or *Broad*
   (strict plus a curated list of defence CPV codes). Market: EU member
   states, Nordic countries, all TED countries, or a custom selection.
2. **My country** – the country the radar is centred on. Any TED country can
   be chosen (your Home Assistant country is pre-selected when TED publishes
   for it); it is stored as an ISO code and controls presentation only – every
   country in the data is still processed so yours can be compared with all of
   them. Existing installations get it from the Home Assistant country on
   upgrade, or set it here.
3. **Selected organisation** *(optional)* – search TED by country and name;
   candidates are grouped by their stable buyer identifier (for example the
   Swedish organisation number) so the match is exact, not fuzzy.
4. **Peer comparison** *(optional)* – a peer group (Nordic, EU or custom
   countries) for the competition metrics; My country is also ranked inside
   the market here.
5. **Pinned categories** *(optional)* – strategic categories that get their own
   device.
6. **Raw data countries** *(optional)* – countries whose notices you want to
   see one by one (see *Raw Data* below).
7. **Watchlist** *(optional)* – countries and minimum EUR values that make a
   new notice fire the separate `watchlist_activity` event.

My country, the countries of the peer group, the selected organisation, the
raw-data devices and the watchlist are always fetched, even when they lie
outside the market.

## Entities

Entity ids are derived from the device and entity names, for example
`sensor.european_defence_market_new_competitions_30_d`. Rolling windows are
half-open: "30 d" means *published after today − 30 days, up to and including
today*; "previous period" is the 30 days before that. Every EUR sensor exposes
`sample_size`, `covered_records` and `coverage_pct` – the share of records
that carried a usable amount – so a large value with 40 % coverage is visible
as such.

### My Country: …

The country purchasing picture for the country you selected (Phase 2). All
periods are by **award date** – the earliest winner decision date when TED
gives one within a year before publication, else the publication date; the
share on decision-date basis is in the attributes.

| Entity | State | Attributes |
| --- | --- | --- |
| `Awarded value 12 m` | Sum in EUR of the usable Notice Values of awarded, non-framework results in the rolling 12 months | `awards`, `valued_awards`, `value_coverage_pct`, `framework_results`, `non_awarded_results`, `quarantined_results`, `unconvertible_results`, `unverified_large_results`, `previous_period_eur`, `change_eur`, `change_pct`, `decision_date_basis_pct`, `monthly` (24 months of value and award counts) |
| `Awarded value previous 12 m`, `Awarded value change` | The 12 months before, and the percentage change | – |
| `Country rank 12 m`, `Share of European total 12 m` | Position among countries with a usable value; share of the European total | `population_size`, `countries_active`, `value_status` (`ranked`, `value unknown`, `no awards in the period`) |
| `Awards 12 m`, `Value coverage 12 m` | Awarded results; share of them with a usable value | same counts as above |
| `Top category 12 m` | Strategic category with the largest awarded value | `categories` (value, share and awards per category, unclassified included), `unclassified_share_pct` |
| `Largest award 12 m` | EUR value of the largest award | the award's facts and `largest_awards` (10) with `ted_url` |
| `Awarded value 90 d` | The same for 90 days | as 12 m, plus `value_30d_eur` |
| `Summary`, `Categories` | `SE · EUR 6.1bn / 12m · #5 · 6.0% · +29.8%`; `Ammunition & explosives EUR 1.4bn · …` | – |

A country with awards but no usable value has state `unknown` and is not
ranked (`value_status`); a country with no awards in the period has EUR 0.
`unknown` is never zero.

### European Purchasing

| Entity | State | Attributes |
| --- | --- | --- |
| `Total awarded value 12 m`, `Total awarded value 90 d` | Country-attributable + joint/multinational (+ unknown-country) awarded value | `country_attributable_eur`, `joint_multinational_eur`, `unknown_country_eur`, `previous_period_eur`, `change_pct`, `awards`, `valued_awards`, `value_coverage_pct`, `framework_results`, `quarantined_results`, `countries_with_value`, `countries_active`, `categories` (12 m), `value_30d_eur` (90 d) |
| `Largest buyer country 12 m`, `Largest buyer value 12 m` | Alpha-2 code and value of the top-ranked country | its ranking row |
| `Countries with attributable value 12 m` | Countries with at least one usable value | `countries_active`, `unranked` |
| `Joint/multinational value 12 m` | Awards whose buyers span several countries, counted once under `MULTI` | `joint_awards`, `unknown_country_eur` |
| `Largest award 12 m` | The largest single award in Europe | `largest_awards` (10) |
| `Quarantined awards` *(diagnostic)* | Number of awards excluded by the plausibility rules (all stored periods) | the 15 largest with `flags` and `ted_url`, `rules` |
| `Top buyers` | `DE EUR 18.4bn · PL EUR 14.7bn · …` | – |

### Country Ranking

| Entity | State | Attributes |
| --- | --- | --- |
| `Country ranking 12 m`, `Country ranking 90 d` | Alpha-2 code of the largest buyer | `ranking` (top 10 **plus My country wherever it ranks**, each with value, share, previous value, change, awards, coverage, framework/quarantined/unverified counts, top category, `is_my_country`), `all_countries` (every ranked country, compact), `unranked` (active countries without a usable value), `my_country`, `population_size`, `total_value_eur` |
| `Fastest-growing countries 12 m` | Alpha-2 code of the fastest-growing eligible country | `ranking` of eligible countries by `change_pct`; eligibility: at least 5 valued awards or EUR 50m awarded in the current period (so near-zero previous periods do not produce absurd percentages). The value ranking never applies this threshold. |

The complete country/category matrix behind these sensors is available from
the action **`edp_radar.get_country_purchasing`** (see below).

### European Defence Market

| Entity | Definition | Attributes |
| --- | --- | --- |
| `New competitions 30 d` / `90 d` | Unique procedures whose first original competition notice was published in the window. Change notices, later versions and results are not counted. | `previous_period`, `change`, `change_pct`, `period_days` |
| `Estimated value 30 d` / `90 d` | Sum of the procedure-level estimated value (else the lot values) of those competitions, normalized to EUR at the publication-date rate. | `previous_period_eur`, `change_pct`, `sample_size`, `covered_records`, `coverage_pct` |
| `Award value 30 d` / `90 d` | Sum of reported award values of result notices published in the window (framework ceilings excluded, see below). | as above |
| `Top country by value 90 d` | Buyer country (ISO alpha-2) with the largest normalized estimated value of new competitions in the last 90 days. | `ranking` (top 10: `rank`, `key`, `label`, `value_eur`, `procedures`, `previous_value_eur`, `change_pct`), `population`, `population_size` |
| `Fastest growing country 90 d` | Country with the largest percentage change versus the previous 90 days among countries with at least 5 procedures or EUR 50 m in the current period. | growth ranking, same shape |
| `Top category by value 90 d` / `Fastest growing category 90 d` | Same, per strategic category (a procedure can belong to several). | ranking with category ids as keys and labels |
| `Largest country change 90 d` / `Largest category change 90 d` | Key with the largest absolute EUR change between the two periods. | `current_value_eur`, `previous_value_eur`, `change_eur`, `change_pct`, `current_procedures`, `previous_procedures` |
| `Snapshot`, `Country ranking` | One-line texts for tile cards, e.g. `2025 competitions / 90d · EUR 21.2bn · +14.3% vs previous 90d`. | – |
| `Median tenders per lot 365 d` | Median of the `tenders` count over lot results published in the last 365 days. | `sample_size`, `coverage_pct`, `population` |
| `Single-bid share 365 d` | Share of those lot results that received exactly one tender. | `single_bid_lot_results`, `lot_results_with_bid_count`, `coverage_pct` |
| `Median public time to result 365 d` | Median days from the first competition notice to the first result notice of the same procedure, for procedures decided in the window. | `sample_size`, `decided_procedures`, `procedure_link_coverage_pct` |
| `Non-award share 365 d` *(disabled)* | Closed-without-winner lots as a share of decided lots. | `non_awarded_lot_results`, `decided_lot_results`, `coverage_pct` |
| `TED data last updated` *(diagnostic, disabled)* | Timestamp of the last successful TED refresh. | `latest_publication_date`, `stored_notices`, `stored_procedures`, `bootstrap_complete`, `bootstrap_progress`, `last_ted_error`, `last_fx_error`, `fx_latest_date` |

### External Radar

| Entity | Definition | Attributes |
| --- | --- | --- |
| `New competitions 7 d` | Procedures with a first competition in the last 7 days, excluding the selected organisation. | `recent`: up to 10 highlights by value |
| `Largest competition 7 d` / `Largest award 7 d` | Normalized EUR value of the largest one; `unknown` when no comparable value exists. | `title`, `buyer`, `country`, `publication_date`, `original_value`, `original_currency`, `value_eur`, `categories`, `ted_url` |
| `Latest competition` | Text: `ES · Air systems · EUR 11m · published 2026-09-11`. | – |

### Selected Organisation

`Public competitions 30 d`, `Public awards 30 d`, `Public changes 30 d`,
`Contract modifications 365 d`, `Estimated value 30 d`, `Award value 30 d`
and the four competition metrics, computed over the notices whose buyer
identifier matches the selected organisation (identifier-less notices fall
back to an exact normalized name match in the same country).

### Peer Comparison

`Peer median tenders per lot 365 d`, `Peer single-bid share 365 d` and `Peer
median public time to result 365 d` over the peer group (attributes name the
population); `Selected country value rank 90 d`, `activity rank` and `value
percentile` inside the market; and, when both an organisation and a peer group
are configured, `Own vs peer …` deltas with `own_value` and `peer_value`.

### Supplier Landscape (disabled by default)

`Top supplier by award value 365 d` (a consortium counts as one group) and
`Top 5 supplier share 365 d`, with the top-10 `ranking`, `coverage_pct`,
`total_award_value_eur` and `groups`. Fuel and other framework-heavy supplies
dominate this view; the coverage attribute says how much of the award value
could be attributed.

### Pinned categories

Per pinned category: `Competitions 30 d`, `Competitions change` (%),
`Estimated value 90 d`, `Estimated value change` (%) and `Award value 90 d`.

### Raw Data: one device per selected country

For people who want to see the notices themselves rather than sums. Each
sensor's state is a count and its `notices` attribute lists the latest
15 notices of that kind (newest first) with plain facts: `publication_number`,
`publication_date`, `stage`, `is_change`, `title`, `buyer`, `buyer_identifier`,
`estimated_value` / `estimated_currency` / `estimated_value_eur`,
`result_value` / `result_currency` / `result_value_eur`, `is_framework`,
`categories`, `winners`, `tenders` and `ted_url`. Central purchasing notices
are included here (the raw view hides nothing).

| Entity | State | `notices` attribute |
| --- | --- | --- |
| `Notices 7 d` | Notice versions published in the last 7 days | Latest 15 of any kind, changes included |
| `Competitions 30 d`, `Results 30 d`, `Planning notices 30 d`, `Direct awards 30 d`, `Contract modifications 30 d` | Original notices of that kind published in the last 30 days | Latest 15 of that kind |
| `Changes 30 d` | Change notices (corrigenda, cancellations, …) in the last 30 days | Latest 15 changes |
| `Stored notices` | Notices stored for the country (whole retention window) | `stored_versions`, `by_stage`, `by_month`, `by_category`, `top_buyers` (20) |

The lists are capped so the attributes stay under Home Assistant's 16 kB
recorder limit. For everything else there is the action
**`edp_radar.get_notices`** (Developer tools → Actions), which returns up to
500 stored notices as JSON with every stored field (identifiers, CPV codes,
legal basis, winners with identifiers, tender counts, selection statuses,
decision dates, change reasons, framework ceilings, …):

```yaml
action: edp_radar.get_notices
data:
  country: SE          # optional, alpha-2
  stage: competition   # optional: competition, result, planning, direct_award, modification, change, other
  since: "2026-08-01"  # optional, inclusive
  until: "2026-09-12"  # optional, inclusive
  category: cyber_it   # optional strategic category id
  buyer_identifier: "202100-0340"  # optional
  limit: 200           # 1–500, default 100
```

The response is `{count, returned, notices: [...]}`, newest first, restricted to
the configured relevance mode. Use it from a script with `response_variable`
or from a template.

**`edp_radar.get_country_purchasing`** returns the purchasing picture of one
country – or of every country – for a period, with the full category split and
the largest awards, so a dashboard can compare My country with any other
without a device per country:

```yaml
action: edp_radar.get_country_purchasing
data:
  country: PL   # optional alpha-2; "all" for the whole ranking; default: My country
  period: 12m   # 12m (default), 90d or 30d, by award date
```

For one country the response carries the same fields as the *My Country*
attributes (`awarded_value_eur`, `rank`, `share_pct`, `change_pct`, coverage
counts, `categories`, `unclassified_share_pct`, `largest_awards`, and for 12 m
`monthly`). For `all` it carries `europe`, `ranking`, `growth` and `unranked`.

### Events

| Entity | Fires when | Attributes |
| --- | --- | --- |
| `event.european_defence_market_procurement_activity` | A notice version new to the store is ingested during a refresh (never during the bootstrap). Event types: `new_competition`, `change`, `result`, `contract_modification`. | `notice_id`, `publication_number`, `procedure_id`, `stage`, `title`, `buyer`, `buyer_country`, `publication_date`, `estimated_value(_eur)`, `result_value(_eur)`, `categories`, `match_reasons`, `own_organisation`, `source_url` |
| `event.european_defence_market_watchlist_activity` | The same, but only for notices matching every watchlist filter. Created only when a watchlist is configured. | same |

```yaml
automation:
  - alias: "Large new defence competition"
    triggers:
      - trigger: state
        entity_id: event.european_defence_market_procurement_activity
    conditions:
      - condition: template
        value_template: >
          {{ trigger.to_state.attributes.event_type == 'new_competition'
             and (trigger.to_state.attributes.estimated_value_eur or 0) > 100000000 }}
    actions:
      - action: notify.mobile_app_phone
        data:
          message: >
            {{ trigger.to_state.attributes.buyer_country }} ·
            {{ trigger.to_state.attributes.title }} ·
            EUR {{ '%.0f' | format(trigger.to_state.attributes.estimated_value_eur / 1e6) }}m
```

## How the numbers are made

### Awarded value (country purchasing)

> Awarded value is publicly reported TED contract-award value. It is **not**
> defence expenditure, budget, planned procurement, a tender estimate, a
> framework ceiling, an invoiced amount or cash paid.

- **One purchase = one result notice's Notice Value (BT-161)**: the value of
  all contracts awarded in that notice, counted once. Lot values and tender
  values are never summed on top of it, and no lower level is used as a
  fallback (in the profiled data lot-level result values never occur on
  non-framework results and tender values over-count). A missing value stays
  missing – *missing is preferable to wrong* – and lowers the coverage.
- **Framework agreements are never purchases.** TED reports the framework's
  ceiling or estimate as the "result value" of a framework result notice
  (sometimes multiplied by the number of winners, sometimes repeated in every
  call-off notice), so framework results count as awarded results without a
  usable value. About a third of results are frameworks; countries that buy
  through frameworks (France, Germany, Romania, Czechia) therefore show a low
  value coverage, and the `framework_results` count says how much is missing.
- **The purchasing country is the buyer country**, never the winner's. A notice
  whose buyers come from several countries is *joint/multinational*: its value
  is counted once under `MULTI`, never divided or duplicated (TED does not say
  which lot belongs to which buyer). The European total is attributable +
  joint (+ unknown-country) value, and `Σ countries + MULTI = total` is tested.
- **Non-awarded procedures are EUR 0**, not unknown: a result whose lots all
  ended without a winner reports no purchase. Direct awards, negotiated
  procedures and every other valid procedure type count like open competition.
- **Time basis is the award date**: the earliest winner decision date when TED
  gives one and it lies at most a year before publication, otherwise the
  publication date. Every award records which one was used. Windows are
  half-open rolling periods (12 months = 365 days) compared with the equal
  period before; 90 and 30 days are secondary views.
- **Currency**: every amount is converted to EUR at the ECB reference rate of
  the award date; the original amount and currency are kept. Nothing is summed
  across currencies.
- **Plausibility quarantine.** Unit errors (values entered ×1000) are the
  dominant data-quality problem. Four deterministic rules exclude a value from
  every total while keeping the record listed and traceable: above EUR 10bn;
  more than 100× a real (≥ 10 000) estimate of the same procedure in the same
  currency; more than 100× the notice's own winning tender values (unless a
  real estimate corroborates the Notice Value); or the same value repeated in
  another original result notice of the same procedure. Placeholder estimates
  and tender values such as `1` or `100` are never compared. Awards of
  EUR 250m or more that no real estimate corroborates stay counted but are
  marked `unverified_large`, so a country's total can be read together with
  how much of it rests on unverified records.
- **Categories** use the strategic category of the procedure's main CPV code
  (one category per award, so shares sum to 100 %); awards whose main CPV maps
  to no category are *Unclassified* and that share is always exposed.

The 24-month data profile behind these rules, with every anomaly found, is in
[`docs/country-purchasing-data-profile.md`](docs/country-purchasing-data-profile.md)
(reproducible with `scripts/country_purchasing_profile.py`).

### Other metrics

- **Currency normalization.** Amounts are converted with the ECB euro
  reference rate of the event date (publication date for estimates, decision
  date for awards), falling back to the latest earlier rate within ten days
  (weekends, holidays). EUR passes through; former currencies of euro members
  (BGN, HRK, …) use their fixed conversion rates. Amounts in currencies the ECB
  does not publish stay unconverted and reduce the coverage ratio.
- **Framework agreements.** Result notices for framework agreements report the
  framework ceiling, sometimes multiplied by the number of winners, as the
  "result value". These are never counted as award value; the ceiling is stored
  separately and the excluded share is visible in the coverage ratio (about a
  third of results are frameworks).
- **Central purchasing bodies.** A notice listing more than ten buyers whose
  only defence signal is a defence buyer somewhere in that list is a central
  purchasing body buying for everyone. Such notices are stored and counted in
  diagnostics but excluded from the market metrics and events.
- **Versions and changes.** Every published version is stored. Counts use the
  first original publication per procedure; change notices (corrigenda,
  cancellations) count as changes, never as new competitions. TED only serves
  the latest version of an amended notice, so a stored version above 1 is
  treated as the original.
- **Tender counts.** Only the `tenders` submission statistic is used (one
  observation per lot result); sub-counts such as SME or e-submission tenders
  are ignored. Lots without tenders carry no statistic, so single-bid and
  median-tender denominators contain awarded lots only.

## Limitations

- Public data only. TED shows what buyers publish; classified procurement,
  below-threshold contracts and many direct awards never appear.
- The publication date is when TED published the notice, not when the
  procedure started; "public time to result" measures the visible gap.
- Categories are CPV-based. Roughly 55 % of relevant notices (construction,
  furniture, medical, cleaning bought by defence buyers) get no strategic
  category and are reported as unclassified.
- Estimated-value coverage is about 45–50 % and award-value coverage about
  55 %; value rankings therefore describe the reported part of the market.
  For country purchasing the coverage differs sharply by country: Poland,
  Estonia, Spain and Czechia report a value on almost every non-framework
  award, while Germany (18 %), Romania (19 %), France (33 %) and the
  Netherlands (38 %) publish few values or buy mostly through frameworks. The
  ranking shows the coverage next to every value; read them together.
- Buyers make unit errors (values ×1000). The quarantine rules catch the ones
  that contradict the procedure's own estimate or tender values; large awards
  without any such reference are only marked `unverified_large`.
- Multi-buyer notices are flattened by TED, so the defence buyer inside a
  central purchasing list cannot be singled out.

## Defence spending

Version 0.3.0 adds five devices that read official spending statistics —
one device per source, because the sources define "defence expenditure"
differently and are never ranked against each other. Sweden is the focus
country of every sensor. Every value sensor carries the same provenance
attributes: `source` (the publisher's short name, for example
`Statskontoret` or `European Defence Agency`), `source_id`, `source_url`,
`reference_label`, `reference_start`, `reference_end`,
`reference_period_complete`, `status` (`actual`, `preliminary`,
`provisional`, `estimate`, `projection`, `budget`), `published_at`,
`publication_age_days`, `reference_age_days` (empty while the reference
year is still running), `retrieved_at`, `release_id` and
`unit_definition`. Money is exposed in whole currency units of the source
(`SEK`, `EUR`, `USD`); nothing is converted.

Ranking sensors show Sweden's rank as the state and expose `ranking` (at most
40 rows, Sweden always included), `population` (countries ranked),
`population_total` (countries the source reports at all), `missing`,
`excluded_zero` (a true zero such as Iceland's is not a rank), `top`,
`median_*`, `nordic` with `nordic_median_*`, `sweden` and `statuses`.

Sources refresh on their own cadence — Statskontoret and Eurostat daily,
NATO, EDA and SIPRI weekly — inside a 6-hour tick; a source that fails is
retried at the next tick and its sensors keep the last stored values.

### Statskontoret

Monthly Swedish budget outturn (SEK) from the open-data page: appropriation
6:1:3 *Anskaffning av materiel och anläggningar* and all defence
appropriations 6:1:1–6:1:14. `Materiel acquisition YTD` and
`Defence appropriations YTD` sum January to the latest month and carry
`monthly_current_year` / `monthly_previous_year` for a month-by-month
chart; `… latest month` and `… YTD change` give the newest month and the
year-on-year change. December of the previous year stays `preliminary`
until Statskontoret publishes the definitive December file (late March).
`Spending snapshot` is a one-line text.

### Eurostat

`gov_ev` general government defence expenditure and investment (EUR,
ESA 2010) for EU member states. The latest year usually has fewer reporters
than the year before; the rank sensors say how many (`population` of
`population_total`, with `missing`).

### NATO

Defence expenditure at current prices (USD), share of GDP and the equipment
share, for all 31 allies; the newest year is an estimate and the sensors say
so (`status: estimate`, `reference_period_complete: false`,
`latest_actual`). `NATO position` is a one-line text.

### EDA

Total defence expenditure and defence investment (EUR) at member-state
level from the annual Defence Data workbooks (2022 onwards); equipment
procurement is not exposed because EDA stopped publishing it per country
after 2021.

### SIPRI

Military expenditure at constant prices (USD, base year in
`price_base_year`) and share of GDP, stored from 1990 (`annual_series`),
with a world ranking (top 40 plus Sweden) and a ten-year change.

### Data age

Each device has a default-disabled diagnostic `… data age` sensor: days
since the source's publication, with `freshness_state` (`current`,
`expected`, `late`, `unknown`), `reference_overdue`, `next_release_expected`,
the provider's health and its last error.

## Dashboard examples

See [`docs/dashboard-example.yaml`](docs/dashboard-example.yaml) for a full
view. The pieces:

**Snapshot tiles**

```yaml
type: grid
columns: 2
cards:
  - type: tile
    entity: sensor.european_defence_market_new_competitions_30_d
  - type: tile
    entity: sensor.european_defence_market_estimated_value_30_d
  - type: tile
    entity: sensor.european_defence_market_award_value_30_d
  - type: tile
    entity: sensor.european_defence_market_top_country_by_value_90_d
```

**Trend** – a history graph of the 30-day sensors shows the rolling window
moving without any custom frontend.

**My country** – tiles for the *My Country* device answer the phone-screen
questions (how much, rank, share, previous 12 months, change), and a history
graph of `Awarded value 12 m` draws the rolling 12-month line.

```yaml
type: grid
columns: 2
cards:
  - type: tile
    entity: sensor.my_country_sweden_awarded_value_12_m
  - type: tile
    entity: sensor.my_country_sweden_country_rank_12_m
  - type: tile
    entity: sensor.my_country_sweden_share_of_european_total_12_m
  - type: tile
    entity: sensor.my_country_sweden_awarded_value_change
```

**Who buys the most** – a Markdown card over the *Country Ranking* sensor
draws horizontal bars and marks My country wherever it ranks:

```yaml
type: markdown
title: Awarded defence contract value — 12 months
content: >
  {% set s = states.sensor.country_ranking_country_ranking_12_m %}
  {% set top = s.attributes.ranking[0].value_eur or 1 %}
  {% for r in s.attributes.ranking %}
  {% set bar = ((r.value_eur or 0) / top * 20) | round(0, 'ceil') | int %}
  {{ '**' if r.is_my_country }}{{ r.rank }}. {{ r.country }}{{ '**' if r.is_my_country }}
  `{{ '█' * bar }}{{ '░' * (20 - bar) }}` EUR {{ '%.1f' | format((r.value_eur or 0) / 1e9) }} bn
  · {{ r.share_pct }} % · coverage {{ r.value_coverage_pct }} %
  {% endfor %}
```

**Country ranking (competitions)** – a Markdown card iterating the `ranking`
attribute of the market device:

```yaml
type: markdown
title: Countries by estimated value, last 90 days
content: >
  {% set s = states.sensor.european_defence_market_top_country_by_value_90_d %}
  | # | Country | EUR | Procedures | vs prev. |
  |---|---|---|---|---|
  {% for r in s.attributes.ranking %}
  | {{ r.rank }} | {{ r.key }} | {{ '%.1f' | format((r.value_eur or 0) / 1e9) }} bn | {{ r.procedures }} | {{ r.change_pct if r.change_pct is not none else '–' }} % |
  {% endfor %}
```

**Peer comparison** – an entities card with the own, peer and delta sensors
side by side; the dashboard, not the integration, draws the conclusion.

**Raw notices** – a Markdown card over a raw-data sensor's `notices` attribute:

```yaml
type: markdown
title: Latest Swedish competitions
content: >
  {% for n in state_attr('sensor.raw_data_sweden_competitions_30_d', 'notices') or [] %}
  - **{{ n.publication_date }}** [{{ n.title }}]({{ n.ted_url }}) — {{ n.buyer }}
    {% if n.estimated_value_eur %}· EUR {{ '%.1f' | format(n.estimated_value_eur / 1e6) }}m{% endif %}
  {% endfor %}
```

## Development

Requirements: Python ≥ 3.14, [uv](https://docs.astral.sh/uv/), Docker (for the
live Home Assistant).

```bash
uv sync --group dev                       # .venv with Home Assistant + test tooling
uv run pytest                             # unit + integration tests, no network
uv run ruff check . && uv run ruff format --check .
uv run mypy custom_components/edp_radar   # strict
PYTHONPATH=. uv run python scripts/data_profile.py --days 90   # live TED data profile
```

### Run it in a real Home Assistant with F5

`docker-compose.yml` starts `ghcr.io/home-assistant/home-assistant:stable`
with `custom_components/` mounted into the container and
[debugpy](https://www.home-assistant.io/integrations/debugpy/) enabled.

1. Open the folder in VS Code (install the recommended extensions).
2. Press **F5** (*Home Assistant (Docker): attach*). The pre-launch task
   `ha: up` starts the container and waits until debugpy answers; then the
   debugger attaches, so breakpoints in `custom_components/` hit.
3. Open http://localhost:8125, finish onboarding, then **Add integration →
   European Defence Procurement Radar**. Watch `ha: logs` for the bootstrap.
4. After editing code, run the task **ha: restart** and press F5 again.

The dev container uses ports **8125** (Home Assistant) and **5679** (debugpy)
so it can run next to other Home Assistant dev containers; `ha: up` refuses to
start when a port is taken and names the holder. Override with `.env` (copy
`.env.example`; if you change `DEBUGPY_PORT`, update `.vscode/launch.json`).
The container's state lives in `dev/config/` (git-ignored except
`configuration.yaml`).

### Project layout

```
custom_components/edp_radar/
  api.py           paced, retrying TED Search API client
  query.py         expert-search query builder
  normalizer.py    raw TED notice → ProcurementNotice (models.py)
  taxonomy.py      defence signals and strategic categories (data/*.json)
  lifecycle.py     procedures, versions, first competition / first result
  fx_rates.py, fx.py   ECB rate table and client
  periods.py       rolling windows and numeric helpers
  purchasing.py    country purchasing model (Phase 2): awarded value, attribution,
                   plausibility quarantine, periods, ranking, categories
  purchasing_attrs.py  plain-dict views of the model for sensors and actions
  metrics.py       pure metrics engine → RadarSnapshot (includes the model)
  storage.py       monthly partitions over HA Store
  config.py        ConfigEntry options → typed configuration
  coordinator.py   bootstrap, incremental refresh, events
  config_flow.py, entity.py, sensor.py, event.py, services.py, diagnostics.py
docs/              design spec, addendum, Phase 2 plan, data profiles, dashboard example
scripts/           data_profile.py (Phase 0), country_purchasing_profile.py (Phase 2),
                   fixture fetcher
tests/             pytest-homeassistant-custom-component tests with real TED notices
```

Design decisions with the verified API facts are recorded in
[`docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md`](docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md);
measured data quality in [`docs/data-profile-400d.md`](docs/data-profile-400d.md)
and, for country purchasing, in
[`docs/country-purchasing-data-profile.md`](docs/country-purchasing-data-profile.md).

## License

MIT – see [LICENSE](LICENSE).

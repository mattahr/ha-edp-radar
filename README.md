# European Defence Procurement Radar for Home Assistant

A read-only [Home Assistant](https://www.home-assistant.io/) custom integration
that turns the public EU procurement feed ([TED – Tenders Electronic
Daily](https://ted.europa.eu/)) into a small set of factual sensors about
European defence procurement: how many competitions were published, for how
much money, in which countries and categories, how contested they were, and
what one selected organisation (for example your own agency) has made public.

It is a **radar, not an analyst**: every number is a count, a sum, a median or
a share of what TED actually reports, each value sensor carries its coverage
ratio, and there are no ratings, forecasts or traffic lights. Interpretation is
left to the person looking at the dashboard.

No API key, account or YAML is needed. The TED Search API and the ECB reference
rates are public.

## What you get

| Device | Contents |
| --- | --- |
| **European Defence Market** | Market activity, value, country and category rankings, competition metrics, data freshness, the `procurement_activity` event |
| **External Radar** | The last 7 days seen from the outside: new competitions and the largest competition/award |
| **Selected Organisation** *(optional)* | The public TED footprint of one buyer you pick in the config flow |
| **Peer Comparison** *(optional)* | Competition metrics for a peer group of countries, the rank of one selected country, and own-vs-peer deltas |
| **Supplier Landscape** | Top supplier group by award value and top-5 share (disabled by default) |
| **Pinned Category: …** *(optional, one per category)* | Competitions and values for a strategic category you pin |
| **Raw Data: …** *(optional, one per country)* | The latest notices of each kind for one buyer country, unaggregated, plus breakdowns of everything stored for it |

## Data sources and update cadence

- **Notices:** `POST https://api.ted.europa.eu/v3/notices/search` (TED Search
  API v3, eForms notices). On first setup the integration fetches the last
  **400 days** of defence-relevant notices in a background task (about 25 000
  notices, ≈150 requests, two to three minutes; entities show `unknown` until
  it finishes). After that it polls **every 4 hours** for notices published
  since the last known publication date (with a two-day overlap). TED
  publishes Monday to Friday; a quiet weekend is not an error.
- **Currency rates:** ECB euro reference rates (`eurofxref-hist.zip` once at
  bootstrap, `eurofxref-hist-90d.xml` on every refresh).
- **Storage:** normalized notices are kept in Home Assistant's `.storage`
  as monthly partitions (`edp_radar.<entry>.notices.<YYYY-MM>`, roughly 60 MB
  for 400 days), pruned to the retention window on every refresh, and deleted
  when the integration is removed.
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
2. **Selected organisation** *(optional)* – search TED by country and name;
   candidates are grouped by their stable buyer identifier (for example the
   Swedish organisation number) so the match is exact, not fuzzy.
3. **Peer comparison** *(optional)* – a peer group (Nordic, EU or custom
   countries) and/or one selected country to rank inside the market.
4. **Pinned categories** *(optional)* – strategic categories that get their own
   device.
5. **Raw data countries** *(optional)* – countries whose notices you want to
   see one by one (see *Raw Data* below).
6. **Watchlist** *(optional)* – countries and minimum EUR values that make a
   new notice fire the separate `watchlist_activity` event.

The countries of the peer group, the selected organisation, the raw-data
devices and the watchlist are always fetched, even when they lie outside the
market.

## Entities

Entity ids are derived from the device and entity names, for example
`sensor.european_defence_market_new_competitions_30_d`. Rolling windows are
half-open: "30 d" means *published after today − 30 days, up to and including
today*; "previous period" is the 30 days before that. Every EUR sensor exposes
`sample_size`, `covered_records` and `coverage_pct` – the share of records
that carried a usable amount – so a large value with 40 % coverage is visible
as such.

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
- Multi-buyer notices are flattened by TED, so the defence buyer inside a
  central purchasing list cannot be singled out.

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

**Country ranking** – a Markdown card iterating the `ranking` attribute:

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
  metrics.py       pure metrics engine → RadarSnapshot
  storage.py       monthly partitions over HA Store
  config.py        ConfigEntry options → typed configuration
  coordinator.py   bootstrap, incremental refresh, events
  config_flow.py, entity.py, sensor.py, event.py, diagnostics.py
docs/              design spec, addendum, data profiles, dashboard example
scripts/           data_profile.py (Phase 0 harness), fixture fetcher
tests/             pytest-homeassistant-custom-component tests with real TED notices
```

Design decisions with the verified API facts are recorded in
[`docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md`](docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md);
measured data quality in [`docs/data-profile-400d.md`](docs/data-profile-400d.md).

## License

MIT – see [LICENSE](LICENSE).

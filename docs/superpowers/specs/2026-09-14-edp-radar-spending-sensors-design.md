# ha-edp-radar — Phase 3 Plan 2: defence-spending sensors (design)

Date: 2026-09-14. Builds on `docs/ha-edp-radar_PHASE3_SWEDEN_DEFENCE_SPENDING.md`
(the plan; `§n` below) and on the data layer described in
`2026-09-12-edp-radar-design-addendum.md` §7 (decisions `S1`–`S29`). This
spec covers plan steps §72–§79: the devices, sensors, attributes and the
data-layer changes they require. Decisions made here are numbered `S30` …
and are copied into the addendum as §7.4 when implementation starts.

## 1. Purpose and scope

Expose the five spending sources already fetched by `SpendingCoordinator`
as Home Assistant entities so that a dashboard can answer plan §3:
*what is Sweden spending now*, *how does it move over time*, *where does
Sweden stand among comparable countries*, each line carrying its source and
age. Sweden is the fixed focus country (`S2`).

In scope: five devices, 27 sensors, a shared attribute model, the
calculations they need, the data-layer prerequisites (`S26`–`S29` and the
deferred minors from `docs/superpowers/NEXT-SESSION.md`), translations,
README, dashboard example, version 0.3.0.

Out of scope (unchanged from `S20`/`S16`): FX conversion, budget
utilisation, cross-source numbers, EDA equipment procurement/R&D sensors
(country-level data ends 2021, `S24a`), `gov_10a_exp`, any threshold or
verdict in an attribute (§76 "no interpretation").

## 2. Decisions

**S30 — One device per source.** Devices `Statskontoret`, `Eurostat`,
`NATO`, `EDA`, `SIPRI` (`DeviceKind.SPENDING_STATSKONTORET` …), identifiers
`(DOMAIN, f"{entry_id}_spending_{source_id}")`, `model` =
`SourceSpec.display_name`, `configuration_url` = `SourceSpec.canonical_url`.
Rankings never cross sources (`S8`) and freshness is per source (`S15`), so
the source is the grouping; the combined Sweden view (§77) is a dashboard
card, not a device. The plan's question-oriented groups (§72) are not used.

**S31 — Phase 2 granularity.** Value, change-%, rank and share are separate
sensors so each number can be graphed or gauged directly, exactly as the
Phase 2 `my_country_*` sensors. Rankings expose Sweden's rank as the state
and the full population as attributes. Two text sensors (§76) and five
default-disabled data-age diagnostics (§79). 27 sensors in total (§5).

**S32 — Units.** Money is exposed in whole currency units with
`SensorDeviceClass.MONETARY`, as Phase 2's `_money` does for EUR:
Statskontoret `SEK` (MSEK × 10⁶), Eurostat and EDA `EUR` (MIO × 10⁶), NATO
`USD` at current prices, SIPRI `USD` at constant prices with
`price_base_year` as an attribute. Percentages use `%`, ranks are unitless
integers, data age is `d`. Source units (`SEK_MILLION` …) stay in the data
layer and are named in `unit_definition`.

**S33 — Availability and unknown.** A spending sensor is a
`CoordinatorEntity[SpendingCoordinator]`; `available` follows
`last_update_success`, which the coordinator only clears when *no* source
has data (`S14`). A source that fails but has cached data keeps its values
and its provenance attributes say how old they are. A sensor whose input is
missing (source never loaded, Sweden absent from the latest reference,
month missing from the YTD run) reports `unknown` (`None`), matching the
"entities show unknown until bootstrap finishes" rule of the TED layer.

**S34 — Latest reference.** For annual sources a sensor uses the newest
reference year in which Sweden has a value for that metric and unit
(rankings require the focus country, `S8`). For NATO that is the 2026
estimate: the value sensor labels it `status: estimate`,
`reference_period_complete: false`, and adds `latest_actual`
(`{year, value}`) so a dashboard can show either (`S24c`). For
Statskontoret it is the newest month present.

**S35 — Zero is not a rank.** `rank()` excludes datapoints whose value is
`0` and lists them in `Ranking.excluded_zero`; a ranking attribute shows
them as `excluded_zero: ["IS"]` (`S24d`). The Nordic summary is computed
from the ranking's entries, so Iceland never enters a Nordic median.

**S36 — Ranking rows.** The `ranking` attribute holds at most
`RANKING_ROWS = 40` rows; Sweden is appended when it lies outside (§49).
Eurostat (≤ 27), NATO (31) and EDA (27) are therefore complete; SIPRI
(~170) shows the top 40 plus Sweden. Rows carry `rank`, `country`, the
ranked value and at most two companion values (`pct_gdp`, `usd`,
`per_capita_eur`). The Phase 2 recorder test (`< 16 kB`) is repeated for
the largest ranking.

**S37 — Coverage.** Every ranking exposes `population` (countries ranked),
`population_total` (countries ever seen for that metric in the source) and
`missing` (the difference), because Eurostat's latest year has fewer
reporters than the year before (`S24b`).

**S38 — `S26` implemented.** Statskontoret discovery also reads
`?year=<Y-1>` and records whether a `Definitiv` December entry exists.
`parse_release` labels December Y-1 `preliminary` until it does. The flag
lives on the provider instance between discovery and parse of the same
refresh (the pattern of `S22`), never in `SourceRelease`.

**S39 — `S27` implemented: base year from the sheet, unit supersedes.**
SIPRI reads the base year from the sheet name (`Constant (2024) US$`), NATO
from the table subtitle (`constant 2021 prices`); the unit becomes
`USD_MILLION_CONSTANT_<year>` and the registry's `MetricSpec.unit` for
these metrics is the prefix `USD_MILLION_CONSTANT` (display names drop the
year). `unit` stays in the datapoint key (`S5`), but `SpendingStore.apply_release`
removes an existing datapoint whose key differs from a new one *only* in
`unit`, records a `Revision` under the new key with the old value, and adds
one health warning per release (`unit changed USD_MILLION_CONSTANT_2024 →
…_2025 for N datapoints`). Sensors read the unit from Sweden's datapoint and
rank with that unit, so a base-year change replaces the series instead of
duplicating it.

**S40 — `S28` implemented: separate health store.** Provider health moves
to `edp_radar.<entry_id>.spending.health` (`{source_id: health}`), written
on every tick; a series store is written only when its release or
datapoints changed. On load, a missing health store falls back to the
`health` key still present in old series files; that key is ignored
otherwise and disappears on the next series write. No schema-version bump.

**S41 — `S29` implemented: conditional GET removed.** `async_fetch_bytes`
loses its `previous=` parameter, the `If-None-Match`/`If-Modified-Since`
headers and the 304 branch, together with their tests. Re-download
avoidance stays where it is exercised: discovery (`S14`, HEAD validators in
the release id).

**S42 — Freshness gets a second signal.** `next_release_deadline` keeps
`published_at + period` for annual/twice-yearly sources (Eurostat publishes
twice a year without moving the reference year, so a reference-based
deadline would show `late` for six months). `expected_lag_days` is used for
`reference_overdue`: the newest period end `E` with
`E + expected_lag_days <= today` should be present; when
`latest_reference_end < E` the state is `late` even if the release deadline
has not passed. `reference_period_complete` = `reference_end <= today`.

**S43 — Sensor code lives in `spending/`** (`S1`: `sensor.py` and
`metrics.py` do not grow). `sensor.py`'s `async_setup_entry` gains one call
into `spending.sensors`.

**S44 — Retry interval removed.** `SPENDING_RETRY_INTERVAL` has no effect
under the 6-hour tick and is deleted; a failed source is retried at the
next tick, which the README states.

## 3. Module layout

```text
custom_components/edp_radar/
  entity.py                 DeviceKind + device_info for the five source devices
  sensor.py                 + one call: async_setup_spending_sensors(...)
  spending/
    calculations.py         + annual_series, latest_year, ytd_change, month_change,
                              value_at, coverage, change_over_years, nordic_summary,
                              rank() zero exclusion
    freshness.py            + expected_reference_end, reference_overdue,
                              reference_period_complete
    attrs.py                NEW  provenance_attrs, ranking_attrs, nordic_attrs,
                                 monthly_series_attrs, annual_series_attrs
    text.py                 NEW  format_amount, statskontoret_snapshot_text,
                                 nato_position_text
    sensors.py              NEW  SpendingSensorEntityDescription, SpendingSensor,
                                 SPENDING_SENSORS, async_setup_spending_sensors
    store.py                health store, refresh_release, unit supersedes, caps
    coordinator.py          ValueError on unknown source, configured-only
                            UpdateFailed, refresh_release
    providers/…             S38, S39, minors (§8)
  strings.json, translations/en.json, translations/sv.json
  manifest.json             version 0.3.0
```

`attrs.py`, `text.py` and `calculations.py` import nothing from Home
Assistant and are tested without the harness.

## 4. Entity model

```python
@dataclass(frozen=True, kw_only=True)
class SpendingSensorEntityDescription(SensorEntityDescription):
    source_id: str
    value_fn: Callable[[SourceSeries, date], StateType]
    attributes_fn: Callable[[SourceSeries, date, datetime], dict[str, Any]] = ...
```

`SpendingSensor(CoordinatorEntity[SpendingCoordinator], SensorEntity)`:
`_attr_has_entity_name = True`, `unique_id = f"{entry_id}_spending_{key}"`,
`translation_key = key`, `device_info` from `S30`. `native_value` and
`extra_state_attributes` call the description with
`coordinator.data.get(source_id)`, `dt_util.now().date()` and
`dt_util.utcnow()`. Money descriptions are built by a `_money(key, source,
currency, value_fn, attributes_fn)` helper mirroring Phase 2's; percentages
by `_pct`, ranks by `_rank`, text by `_text`.

All 27 sensors exist whenever the integration is set up (there is no
spending configuration); the five data-age sensors are
`EntityCategory.DIAGNOSTIC` and `entity_registry_enabled_default=False`.

## 5. Sensor catalogue

"SE" is always Sweden. Attributes listed are *in addition to* the
provenance set of §6. English names are the `strings.json` names; Swedish
translations are written in the implementation.

### 5.1 Statskontoret (monthly, SEK)

| Key | Name | State | Attributes |
| --- | --- | --- | --- |
| `statskontoret_materiel_ytd` | Materiel acquisition YTD | SEK, Jan → latest month | `months_included`, `previous_year_ytd_sek`, `change_pct`, `monthly_current_year` `[{month, sek}]`, `monthly_previous_year` (§52 chart) |
| `statskontoret_materiel_latest_month` | Materiel acquisition latest month | SEK, latest month | `month_label`, `same_month_previous_year_sek`, `change_pct` |
| `statskontoret_materiel_ytd_change_pct` | Materiel acquisition YTD change | % | `current_sek`, `previous_sek`, `change_sek` |
| `statskontoret_defence_ytd` | Defence appropriations YTD | SEK (`uo6_defence_outturn`) | as materiel + `uo6_total_ytd_sek` |
| `statskontoret_defence_latest_month` | Defence appropriations latest month | SEK | as materiel |
| `statskontoret_defence_ytd_change_pct` | Defence appropriations YTD change | % | as materiel |
| `statskontoret_snapshot_text` | Spending snapshot | `"Materiel YTD SEK 48.2bn · +31% YoY · Statskontoret · through Jul 2026"` | — |
| `statskontoret_data_age` | Statskontoret data age | d | §6.2 |

`reference_label` is `"Jan–Jul 2026"` for YTD sensors and `"Jul 2026"` for
latest-month sensors. `status` is the latest month's status
(`preliminary` for a Preliminär release, and for December Y-1 per `S38`).

### 5.2 Eurostat (annual, EUR, EU-27)

| Key | Name | State | Attributes |
| --- | --- | --- | --- |
| `eurostat_defence_expenditure` | Defence expenditure | SE EUR | `reference_year`, `pct_gdp`, `nac_million`, `previous_year_eur`, `change_pct`, `rank`, `pct_gdp_rank`, `population` |
| `eurostat_defence_expenditure_rank` | Defence expenditure rank | int | `ranking` `[{rank, country, eur, pct_gdp}]`, `population`, `population_total`, `missing`, `top` `{country, eur}`, `median_eur`, `nordic` `[{country, rank, eur}]`, `nordic_median_eur`, `sweden` `{rank, eur}`, `statuses` |
| `eurostat_defence_investment` | Defence investment | SE EUR (P51G) | as expenditure |
| `eurostat_defence_investment_rank` | Defence investment rank | int | as expenditure rank |
| `eurostat_data_age` | Eurostat data age | d | §6.2 |

### 5.3 NATO (annual, USD current prices, 31 allies)

| Key | Name | State | Attributes |
| --- | --- | --- | --- |
| `nato_defence_expenditure` | Defence expenditure | SE USD | `reference_year`, `nac_million`, `usd_constant`, `price_base_year`, `pct_gdp`, `latest_actual` `{year, usd}`, `previous_year_usd`, `change_pct`, `rank`, `population` |
| `nato_defence_expenditure_pct_gdp` | Defence expenditure share of GDP | SE % | `reference_year`, `rank`, `population`, `alliance_median_pct_gdp` |
| `nato_defence_expenditure_pct_gdp_rank` | Defence expenditure share of GDP rank | int | `ranking` `[{rank, country, pct_gdp, usd}]`, `population`, `population_total`, `missing`, `top`, `median_pct_gdp`, `nordic`, `nordic_median_pct_gdp`, `sweden`, `statuses` |
| `nato_equipment_share_pct` | Equipment share of defence expenditure | SE % | `reference_year`, `equipment_usd`, `rank`, `population` |
| `nato_position_text` | NATO position | `"SE #N of 31 · USD X.Xbn · Y.Y% GDP · NATO 2026 estimate"` | — |
| `nato_data_age` | NATO data age | d | §6.2 |

### 5.4 EDA (annual, EUR, EU-27)

| Key | Name | State | Attributes |
| --- | --- | --- | --- |
| `eda_defence_expenditure` | Defence expenditure | SE EUR | `reference_year`, `pct_gdp`, `pct_government`, `per_capita_eur`, `investment_eur`, `previous_year_eur`, `change_pct`, `rank`, `population` |
| `eda_defence_expenditure_rank` | Defence expenditure rank | int | `ranking` `[{rank, country, eur, pct_gdp, per_capita_eur}]`, coverage, `top`, `median_eur`, `nordic`, `nordic_median_eur`, `sweden`, `statuses` |
| `eda_defence_investment_rank` | Defence investment rank | int | `ranking` `[{rank, country, eur}]`, coverage, `top`, `median_eur`, `nordic`, `sweden`, `statuses` |
| `eda_data_age` | EDA data age | d | §6.2 |

### 5.5 SIPRI (annual, USD constant prices, world)

| Key | Name | State | Attributes |
| --- | --- | --- | --- |
| `sipri_military_expenditure` | Military expenditure | SE USD (constant) | `reference_year`, `price_base_year`, `flags`, `pct_gdp`, `previous_year_usd`, `change_pct`, `value_10y_ago_usd`, `change_10y_pct`, `annual_series` `[{year, usd}]` from 1990, `rank`, `population` |
| `sipri_military_expenditure_rank` | Military expenditure rank | int | `ranking` top 40 + SE `[{rank, country, usd, pct_gdp}]`, `population`, `population_total`, `missing`, `excluded_zero`, `top`, `median_usd`, `nordic`, `nordic_median_usd`, `sweden`, `statuses` |
| `sipri_military_expenditure_pct_gdp` | Military expenditure share of GDP | SE % | `reference_year`, `rank`, `population` |
| `sipri_data_age` | SIPRI data age | d | §6.2 |

## 6. Shared attributes

### 6.1 Provenance (§78) — on every value, percentage, rank and text sensor

```yaml
source: Statskontoret                 # SourceSpec.display_name
source_id: statskontoret
source_url: https://…                 # the datapoint's own URL
reference_label: "Jan–Jul 2026"
reference_start: "2026-01-01"
reference_end: "2026-07-31"
reference_period_complete: true       # false → reference_age_days is null (S24c)
status: actual                        # DatapointStatus of the state's datapoint
published_at: "2026-08-24"
publication_age_days: 21
reference_age_days: 45
retrieved_at: "2026-09-14T13:40:21+00:00"
release_id: "2026-07-definitiv-2026-08-24"
unit_definition: "Monthly outturn of appropriation 6:1:3 …"   # MetricSpec.definition
```

No etag, checksum, download URL or layout fingerprint on entities; those
stay in diagnostics.

### 6.2 Data age (§79) — `<source>_data_age`

State `publication_age_days` (`d`, `SensorStateClass.MEASUREMENT`).
Attributes: `freshness_state` (`current | expected | late | unknown`),
`reference_overdue`, `next_release_expected`, `latest_reference_end`,
`reference_age_days`, `published_at`, `retrieved_at`, `release_id`,
`health_state`, `last_check_at`, `last_success_at`, `last_error`,
`datapoints`, `revisions`. Available whenever the coordinator has run,
including while the source is `temporarily_unavailable`.

## 7. Calculations and freshness additions

All pure, in `spending/calculations.py` unless stated:

| Function | Returns | Used by |
| --- | --- | --- |
| `annual_series(points, metric_id, country)` | `{year: point}` for calendar-year references (`start == Jan 1`, `end == Dec 31`) | every annual source |
| `latest_year(points, metric_id, country, *, unit=None)` | newest annual point, optionally of one unit | value sensors |
| `ytd_change(points, metric_id, country, year, through_month)` | `YtdChange(current, previous, change, pct)`; `None` when a month is missing in either year | Statskontoret YTD + change |
| `month_change(series, year, month)` | `MonthChange(current, previous, pct)` | Statskontoret latest month |
| `value_at(points, metric_id, country, reference, unit)` | `Decimal \| None` | companion values in rows |
| `coverage(points, metric_id, reference)` | `Coverage(present, ever_seen, missing)` | `population_total`, `missing` |
| `change_over_years(series, year, years_back)` | `(then_value, pct)` or `None` | SIPRI 10-year change |
| `rank(...)` (extended) | `Ranking` gains `excluded_zero: tuple[str, ...]`; zero values never enter `entries` | all rankings |
| `nordic_summary(ranking)` | `NordicSummary(entries, median)`; median over the Nordic entries present | `nordic*` attributes |

`spending/freshness.py`: `expected_reference_end(spec, today)`,
`reference_overdue(spec, latest_reference_end, today)`,
`reference_period_complete(reference_end, today)`; `freshness_state`
returns `late` when either signal fires (`S42`).

`spending/text.py`: `format_amount(currency, amount)` (`"SEK 48.2bn"`,
`"USD 12.3bn"`, `"EUR 850m"`, the `format_eur` thresholds generalised;
`format_eur` in `periods.py` is left as is), `statskontoret_snapshot_text`,
`nato_position_text`.

## 8. Data-layer prerequisites

Done before any sensor code, each as its own commit with tests:

| Area | Change |
| --- | --- |
| Store | `S40` health store; `refresh_release(source_id, release, retrieved_at)` replaces the coordinator's direct `store.series[...]` write on the unchanged path; `S39` unit supersedes; duplicate key within one release → parse warning (last value wins, counted); `revisions` capped at the newest `MAX_REVISIONS = 1000` per source; `async_load` tolerates non-dict data (warning, treated as empty) |
| Coordinator | `async_refresh_source` with an unknown id raises `ValueError`; `UpdateFailed` only when no *configured* provider has data; `S44` retry constant removed; `expected_lag_days` no longer dead |
| Freshness | `S42` |
| Statskontoret | `S38`; rows shorter than the header → parse warning with the row number; `DiscoveredRelease.heading` removed; `today` is a parameter (no `date.today()`) |
| Eurostat | the `freq` dimension must contain exactly `A`, else `SchemaChangedError` |
| NATO, SIPRI | `S39` base year from the sheet/subtitle; SIPRI `highly_uncertain` tested against a real fixture row |
| EDA | `SKIP_LABELS` check; `resolve_country` distinguishes skipped from unknown (`resolve_country(label) -> str \| None` plus `is_skipped_label(label) -> bool`); the three duplicated column tuples merged; `for label in ("year",)` and the no-op `.replace` removed; test on `-` cells; separate trimmed fixtures for 2023 and 2024 (from `.cache/spending/eda/`) |
| HTTP base | `S41`; test for the `async_head_metadata` exception branch; `MAX_PAYLOAD_BYTES = 50 MB` on responses and on each zip member → `SourceUnavailableError` |
| Diagnostics | field names per `S17` (`datapoints_count`, `revision_count`); `layout_fingerprint` stored with the release and shown |
| Profile script | explains a negative reference age; writes `—` for a provider with zero datapoints |

## 9. Translations, README, dashboard, version

- `strings.json` = `translations/en.json` (test-enforced); `sv.json` gets
  the same 27 keys in Swedish (e.g. "Materielanskaffning hittills i år",
  "Försvarsutgifter, andel av BNP", "Rangordning försvarsutgifter").
- README: the section "Defence spending data layer (Phase 3, data only)"
  is replaced by "Defence spending" with one subsection per device in the
  style of "My Country: …", the shared attribute model, the data-age
  sensors, and the cadence/retry rule (`S44`). "What you get" and the
  entity count are updated.
- `docs/dashboard-example.yaml`: a "Sweden defence spending" card in the
  §77 layout (Statskontoret YTD, TED 12m from Phase 2, Eurostat, EDA, NATO,
  SIPRI — each line with its `source` and `reference_label`).
- Addendum §7.4 lists `S30`–`S44`; NEXT-SESSION.md is rewritten for the
  state after this plan.
- `manifest.json` `version` 0.3.0.

## 10. Testing

- Unit (no harness): every function in §7; `attrs.py` (provenance from a
  datapoint, ranking rows incl. Sweden appended beyond 40, coverage,
  Nordic without Iceland, `reference_age_days` null for an unfinished
  period); `text.py` formatting incl. `n/a` paths.
- Data layer: `S38` window (January release with and without a Definitiv
  December), `S39` (a 2025 base-year workbook replaces the 2024 series and
  records revisions + one warning), `S40` round-trip and fallback from an
  old series file, `S41` removal, `S42` (`reference_overdue` true/false),
  each minor in §8 with a regression test.
- HA: `tests/test_spending_sensors.py` sets up the entry with mock
  providers (`tests/spending/mocks.py`), then asserts per device: states and
  units of every sensor, `unknown` when Sweden is absent or a YTD month is
  missing, cached values with `health_state` after a provider failure,
  data-age sensors disabled by default yet registered, translations resolve
  for all 27 keys (`test_translations.py` key-set test covers `sv.json`),
  the SIPRI ranking attribute stays under 16 kB, diagnostics field names.
- Live: the dev container (`dev/ha.sh`) is restarted on the final code;
  the entities are read through the REST API and the log is checked for
  errors before the work is called done.

## 11. Order of work

1. §8 data-layer prerequisites (store → coordinator → freshness →
   providers → HTTP base → diagnostics/script).
2. §7 calculations, `attrs.py`, `text.py`.
3. `entity.py` devices, `sensors.py`, `sensor.py` hook, translations.
4. README, dashboard example, addendum §7.4, NEXT-SESSION, version.
5. Live check.

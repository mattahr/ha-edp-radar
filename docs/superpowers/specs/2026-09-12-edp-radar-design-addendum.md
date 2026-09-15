# ha-edp-radar — design addendum (Phase 0 findings and decisions)

**Date:** 2026-09-12
**Complements:** `docs/ha-edp-radar_PROJECT.md` (the plan). This addendum records what was verified against the live TED and ECB services and every decision that refines or deviates from the plan. Where this document and the plan disagree, this document wins.

---

## 1. Verified API facts (TED Search API v3, 2026-09-12)

Source of truth: the OpenAPI document served at `https://api.ted.europa.eu/api-v3.yaml` and live queries.

| Topic | Verified fact |
| --- | --- |
| Endpoint | `POST https://api.ted.europa.eu/v3/notices/search`, JSON body, no auth. |
| Request parameters | `query`, `fields[]`, `page` (≥1), `limit` (≤250), `scope` (`ALL`/`LATEST`/`ACTIVE`), `paginationMode` (`PAGE_NUMBER`/`ITERATION`), `iterationNextToken`, `onlyLatestVersions`, `checkQuerySyntax`. |
| Response | `notices[]`, `totalNoticeCount`, `iterationNextToken`, `timedOut`. Every notice also carries a `links` object even when not requested. |
| Fields-per-page limit | The server counts `links` as a field. 175 × 57 requested fields was rejected as 10 150 > 10 000. **Safe page size = `min(250, 10000 // (len(fields) + 1))`.** |
| Page-number ceiling | 15 000 notices. Strict universe is ~25 700 notices / 400 days, so bootstrap must use `ITERATION`. |
| Iteration token lifetime | Point-in-time expires at next OJ S release + 24 h. |
| Rate limiting | HTTP 429 (nginx HTML body, not JSON) observed after ~15 rapid requests. Client must back off and pace requests. |
| Date syntax | `PD>=20250809` (`yyyymmdd`) or `today(-400)`. ISO dates are rejected. |
| Field names | All 57 candidate fields in plan §8 exist. Additional useful fields: `change-notice-version-identifier` (BT-758, links a change to the notice it changes), `identifier-lot`, `framework-*`, `notice-title`. |
| Country values | `buyer-country` and `winner-country` use ISO 3166-1 **alpha-3** (`SWE`); `SE` is rejected. |
| Legal basis | `legal-basis=32009L0081` works. Other values seen: `32014L0024`, `32014L0023`, `other`. |
| Buyer search | `buyer-name ~ (försvar*)` (full-text) and `buyer-identifier=202100-0340` work. Swedish buyers carry stable organisation numbers (FMV = `202100-0340`, Försvarsmakten = `202100-4615`, FOI = `2021005182`). |
| Query validation | `checkQuerySyntax: true` returns 200 with empty `notices` on success, 400 with `error.type = QUERY_SYNTAX_ERROR` and a location on failure. |
| Volumes (strict) | 90 d ≈ 6 100 notices (≈5 400 latest versions); 400 d ≈ 25 700. Broad mode (CPV 35* etc.) adds roughly +50 %. |

### 1.1 Shapes of returned values (from a 516-notice strict sample)

- Scalars: `publication-number`, `publication-date` (`2026-09-11+02:00` — date plus TZ suffix), `notice-identifier` (UUID), `notice-version` (int), `notice-type`, `notice-subtype`, `form-type`, `procedure-identifier`, `procedure-type`, `estimated-value-proc` (**string** number, e.g. `"1475225.00"`), `estimated-value-cur-proc`, `result-value-notice`, `result-value-cur-notice`, `change-reason-code`.
- Multilingual text: `title-proc`, `description-proc`, `change-description` → `{"deu": "…"}`; `buyer-name`, `winner-name` → `{"swe": ["FMV"]}` (dict of lists). Language keys are ISO 639-2 three-letter codes.
- Lists (flattened across buyers/lots/winners, **not index-aligned with each other**): `buyer-identifier`, `buyer-country`, `buyer-legal-type`, `authority-main-activity`, `legal-basis`, `classification-cpv`, all `*-lot` fields, all `winner-*` fields, `received-submissions-type-code/-val`, `non-award-justification`, `tender-value*`.
- Currency lists collapse duplicates: `estimated-value-lot = ["516459.48", "633039.72"]` with `estimated-value-cur-lot = ["EUR"]`.
- `received-submissions-type-code` and `-val` had equal lengths in every sampled notice; pairs are `(code[i], val[i])`.

### 1.2 Code values observed

- `form-type`: `planning`, `competition`, `result`, `dir-awa-pre` (voluntary ex-ante transparency / direct award), `cont-modif`. eForms only in the whole 400-day window; legacy TED-schema notices no longer appear.
- `notice-type`: `pin-buyer`, `pin-only`, `pin-rtl`, `pin-cfc-social`, `cn-standard`, `cn-social`, `can-standard`, `can-social`, `can-desg`, `veat`, `can-modif`.
- Change notices: `change-reason-code` present on 75/516. Most (63) are **version 1 with a new `notice-identifier`**; 12 are higher versions of an existing identifier. Values: `update-add`, `cor-buy`, `cor-pub`, `susp-review`, `cancel-intent`, `info-release`.
- `received-submissions-type-code`: `tenders` (total), `t-esubm`, `t-sme`, `t-oth-eea`, `t-no-eea`, `t-verif-inad`, `t-verif-inad-low`, `t-no-verif`, `part-req`, `t-med`, `t-small`, `t-micro`. **Only `tenders` is a comparable tender count.**
- `winner-selection-status`: `selec-w`, `clos-nw`, `open-nw`. `non-award-justification`: `no-rece`, `all-rej`, `tch-pr-error`, `ins-fund`, `one-admis`, `no-signed`, `chan-need`, `other`.
- Currencies: EUR, PLN, CZK, RON, NOK, SEK, DKK, BGN, CHF, HUF expected. ECB has no BGN/HRK rates any more (euro members) — BGN needs the fixed conversion rate (1 EUR = 1.95583 BGN) as a documented constant.
- Multi-buyer notices: 17/516 had > 10 buyers (up to 552) — central purchasing bodies listing every end user. Arrays are flattened, so the defence buyer cannot be singled out.

### 1.3 ECB

- Daily XML: `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml` (one date, ~30 currencies).
- Last 90 days XML: `…/eurofxref-hist-90d.xml`.
- Full history CSV: `…/eurofxref-hist.zip` (≈640 KB, `Date,USD,…` with `N/A` gaps). Needed once for the 400-day bootstrap.

---

## 2. Decisions and deviations from the plan

Numbered so the implementation plan and code comments can reference them (`D1`, `D2`, …).

**D1 — Page size.** `page_size = min(250, 10000 // (len(fields) + 1))`. Tested.

**D2 — Country codes.** Config entries, entity states and attributes use alpha-2 (`SE`) because Home Assistant's `CountrySelector` and users expect it. The query builder converts to alpha-3; the normalizer converts back. A static alpha-2↔alpha-3 table for the ~45 TED countries lives in `const.py`; unknown alpha-3 values are kept verbatim.

**D3 — Stage model.** `NoticeStage` is derived from `form-type` only: `planning`, `competition`, `result`, `direct_award` (`dir-awa-pre`), `modification` (`cont-modif`), `completion` (`compl`), `other`. A change notice keeps the stage of the notice it changes and carries `change: ChangeInfo` (reason code, description, changed notice id from `change-notice-version-identifier`). `ProcurementNotice.is_change` is `change is not None`. Rationale: the plan's `CHANGE` stage would hide which family the change belongs to, and the data shows changes arrive mostly as new v1 notices. All lifecycle/metric rules that say "not a change notice" use `is_change`.

**D4 — Versions.** Every `(notice_id, notice_version)` is stored; the lifecycle index uses the latest version per `notice_id` for state values and the earliest non-change competition publication per procedure for "first competition" dates. Bootstrap and incremental refreshes do **not** set `onlyLatestVersions` (it would drop the original publication date of amended notices).

**D5 — Multi-buyer notices.** Ingestion stores every matched notice with `buyer_count` and the full `match_reasons`. The metrics layer applies `CENTRAL_PURCHASING_BUYER_THRESHOLD = 10`: a notice with more buyers than the threshold and `match_reasons == {"defence_buyer"}` is excluded from market/external/country/category metrics and events, but remains in storage and diagnostics (`excluded_central_purchasing`). This follows the "complete model underneath, ready-served sensors on top" principle.

**D6 — Lot value safety.** Lot-level monetary fields are used only when `len(values) == len(currencies)` (pair by index) or `len(currencies) == 1` (apply to all). Otherwise the lot total is unknown. Procedure-level value always wins when present (plan §39).

**D7 — Tender counts.** `SubmissionStatistic(type_code, value)` pairs by index. Only `tenders` feeds median/single-bid metrics; each `tenders` entry is one lot-result observation. `part-req` and the sub-type counts are retained on the notice for diagnostics only.

**D8 — Bootstrap runs in the background.** `async_setup_entry` loads the store and starts the coordinator immediately. If the store is empty (or `last_publication_date` is older than `retention_days`), a background task performs the 400-day iteration fetch, saving each month partition as it fills. Entities exist from setup but report `unknown` until the first `RadarSnapshot` with `bootstrap_complete = True`. The freshness sensor exposes `bootstrap_progress`. No events are emitted for notices ingested during bootstrap (plan §42).

**D9 — Request pacing.** Minimum 0.5 s between search calls; on 429 or 5xx wait `min(60, 2 ** attempt)` seconds, at most 4 attempts per page, then `UpdateFailed`. Connect timeout 10 s, read timeout 60 s.

**D10 — Description text is not persisted.** Only `title` (truncated to 200 chars) is stored. Phase-2 keyword classification would need a separate design. Saves roughly half the storage.

**D11 — FX data.** `FxProvider` keeps a `{date: {currency: rate}}` table in `edp_radar.fx`. Bootstrap loads the ECB history zip once (only dates inside retention are kept); each refresh fetches the daily XML. Lookup uses the exact date or the latest previous available date (weekend/holiday fallback), never a later date. EUR passthrough. BGN uses the fixed rate above. Unconvertible currencies leave `normalized_eur_amount = None` and lower the coverage ratio.

**D12 — Storage layout.** Keys `edp_radar.<entry_id>.index`, `edp_radar.<entry_id>.notices.<YYYY-MM>`, `edp_radar.<entry_id>.fx`, `edp_radar.<entry_id>.events`. Each partition holds normalized notices as compact dicts with a `schema_version`. Partitions are pruned when the whole month is outside retention. Saves use `Store.async_delay_save` (30 s) except at the end of bootstrap and on unload.

**D13 — Repository/tooling.** Python ≥ 3.14.2, Home Assistant `2026.9.2`, `pytest-homeassistant-custom-component 0.13.365`, `uv` with a `dev` dependency group, `ruff` (line length 88, HA-style rule set) and `mypy --strict` for `custom_components/edp_radar`. No GitHub workflows, no issue templates (owner decision). The plan itself stays at `docs/ha-edp-radar_PROJECT.md` (not moved to the root).

**D14 — Phase 0 harness.** `scripts/data_profile.py` (standard library only, runnable with `uv run`) reproduces the report `docs/data-profile.md` from a chosen window and mode. It uses the same query builder and normalizer as the integration by importing `custom_components.edp_radar` modules that do not import Home Assistant.

**D15 — Language.** Code, `strings.json`, README and docs in English. `translations/sv.json` provides Swedish UI text. Entity names are translated via `translation_key`.

**D16 — Entity naming.** Devices: European Defence Market, External Radar, Selected Organisation, Peer Comparison, Supplier Landscape, Pinned Category: `<name>`. Manufacturer `TED / Publications Office of the European Union`, model `EDP Radar Analytics`. Unique IDs: `<entry_id>_<metric_key>`; pinned categories `<entry_id>_cat_<category_id>_<metric_key>`.

**D17 — Own organisation identity.** Stored in `ConfigEntry.options` as `{identifiers: [...], country: "SE", canonical_name: "FMV", aliases: ["Försvarets materielverk"]}`. A notice belongs to the own organisation when any stored identifier is in `buyer_identifiers`, or (identifier-less fallback) when the primary buyer's country matches and a normalized name equals the canonical name or an alias. The config flow resolves candidates with `buyer-name ~ (term*) AND buyer-country=XXX` over the last 400 days and groups results by identifier.

**D18 — Competition and supplier metrics ship in MVP.** Measured coverage supports them: `tenders` present on most results, `winner-selection-status` on all sampled results, `winner-identifier` on ~85 % of results with winners. Supplier entities (`top_supplier_by_award_value_365d`, `supplier_top5_share_365d`) are created but `entity_registry_enabled_default = False`. HHI stays out of MVP.

**D19 — Live Home Assistant dev container.** Same pattern as `../ha-battaxi`: `docker-compose.yml` runs `ghcr.io/home-assistant/home-assistant:stable` (container `ha-edp-radar`) with `./custom_components` mounted at `/config/custom_components` and `./dev/config` at `/config`; `dev/config/configuration.yaml` enables `default_config`, `debugpy` and debug logging for `custom_components.edp_radar`; `dev/ha.sh up|down|restart|logs|status` manages the container and refuses to start on occupied ports; `.vscode/launch.json` attaches debugpy (pre-launch task `ha: up`) and `.vscode/tasks.json` exposes the `ha:` tasks and `uv run pytest`. Default ports are `HA_PORT=8125` and `DEBUGPY_PORT=5679` (8123/5678 are taken by other dev containers on this machine); `.env` overrides. `dev/config/` is git-ignored except `configuration.yaml`. The README documents the F5 flow.

**D20 — Non-positive amounts are unknown.** TED writes ``-1`` (and sometimes ``0``) for undisclosed lot values, so `Money.parse` returns `None` for any amount `<= 0`.

**D21 — Framework ceilings never count as awards.** Result notices with `framework-agreement-lot` set (`fa-mix`, `fa-w-rc`, `fa-wo-rc`) report the framework ceiling — occasionally multiplied by the number of winners (EUR 316.8 m × 55 winners = EUR 17.4 bn in a Spanish works framework) — in `result-value-notice`, while every `tender-value` is `0`. The normalizer therefore requests `framework-agreement-lot`, `result-framework-maximum-value-notice` and its currency, sets `is_framework`, stores the declared ceiling (else the reported value) as `framework_value`, and leaves `result_value = None` for framework results. Award metrics thus exclude frameworks (34 % of results in the 90-day sample) and the coverage ratio says so; a dedicated framework-ceiling metric can be built later from the stored `framework_value`.

**D22 — Winner arrays have different cardinalities.** `winner-name` is repeated once per winning tender (lot × winner), whereas `winner-identifier`, `winner-country` and `winner-size` are listed once per organisation record. Winners are therefore the unique names in order of first appearance; identifiers are attached only when their count equals the number of unique names; country and size may additionally be collapsed when every entry is identical. Roughly 10 % of results with winners end up without identifiers and fall back to `country:normalized name` identity keys.

**D23 — Buyer-name search syntax.** A quoted phrase combined with a wildcard never matches in TED expert search; `buyer-name ~ (försvarets* materiel*)` (one unquoted wildcard token per word, non-word characters dropped) does. The config flow uses this form.

**D24 — Lots without tenders carry no submission statistics.** Non-awarded lots (`clos-nw` with `no-rece`) have no `received-submissions` entries, so the single-bid and median-tender denominators contain awarded lots only, while the non-award share uses `winner-selection-status` per lot (`clos-nw` / (`clos-nw` + `selec-w`); `open-nw` lots are undecided and excluded).

**D25 — Stale data beats unavailable.** When an incremental refresh fails (TED 429/5xx/timeout) and the store already holds notices, the coordinator logs the error, records it as `last_ted_error` (diagnostics and the freshness sensor expose it) and returns the snapshot computed from stored data, so entities stay available. `UpdateFailed` is raised only when nothing is stored yet. This is the reading of plan §43 that keeps "existing entity state available".

**D26 — TED serves only the latest notice version.** In the 400-day sample 721 of 748 notices with `notice-version > 1` have no earlier version in the results: an amended notice replaces its predecessor in the search index. A stored version above 1 therefore implies a real original that is no longer retrievable. `ProcedureIndex` treats such notice ids as originals (the change published as a *new* notice always has version 1 and stays a change) and uses the lowest stored version's publication date as the first-publication approximation. Without this rule ~7 % of competitions (those amended before bootstrap) would never be counted. Republished notices can also reuse the same version number with a later date; the store keeps the last one seen per `(notice_id, version)`.

---

## 3. Layering (unchanged from the plan, made explicit)

```text
api.py (TedApiClient)  fx.py (EcbFxClient)   ← aiohttp, HA session
        │                     │
query.py (TedQueryBuilder)    │
        │                     │
normalizer.py ────────────────┼──► models.py (frozen dataclasses)
        │                     │
storage.py (partitions) ◄─────┘
        │
lifecycle.py (ProcedureIndex)   taxonomy.py (relevance + categories, JSON data)
        │
metrics.py (pure functions) ──► RadarSnapshot
        │
coordinator.py ──► sensor.py / event.py / diagnostics.py  (entity.py base)
```

`models.py`, `normalizer.py`, `query.py`, `lifecycle.py`, `taxonomy.py`, `metrics.py` and `fx_rates.py` (pure rate table) import nothing from Home Assistant, so the Phase 0 script and unit tests run without the HA test harness.

---

## 4. Phase 0 findings that need an owner decision

Measured on 6 138 strict-mode notices from the last 90 days (`docs/data-profile.md`):

- **56 % of relevant notices get no strategic category** with CPV-only rules. The unclassified mass is construction (CPV 45, 44, 71), furniture (39), medical (33), cleaning/environment (90), agriculture (03) and business services (79) bought by defence buyers. Options: leave unclassified (current; the share is reported), add an "Infrastructure & facilities" category (45/44/71/90), or add keyword rules later. No change is made without a decision.
- **Estimated-value coverage is 47 %** for competitions and **award-value coverage 54 %** for results (after excluding frameworks). Every value sensor exposes its coverage, as the plan requires.
- **Public time to result** is measurable: in the 400-day profile (`docs/data-profile-400d.md`, 25 750 notices) 41 % of results link to a competition, giving a median of 102 days on n = 3 714 (only 5 % / 55 days in the 90-day window). Bid-count coverage is 82–88 %, selection statuses 99.9 %: the competition metrics ship enabled (D18 confirmed).
- **Supplier landscape is dominated by fuel**: the top supplier over 365 days is ORLEN S.A. and the top-5 share is 88 %, because fuel frameworks/awards by defence buyers are huge. A per-category supplier view is a candidate follow-up; for now the sensor states the fact and its coverage.
- **Broad mode adds only ~7 %** of notices (441 CPV-only hits in 90 days), mostly land systems, ammunition and defence R&D.
- **Poland dominates estimated value** (EUR 14.7 bn of EUR 23.3 bn in 90 days). This is what TED reports; the ranking attributes show it explicitly.

## 5. Deferred (explicitly out of the first release)

- Keyword-based category classification (needs descriptions, see D10).
- Framework-agreement ceiling metrics (the data is stored as `framework_value`, D21).
- HHI concentration metric.
- `public_footprint_largest_change` (robust z-score).
- Organisation peers beyond selection by identifier (fuzzy matching stays out).

---

## 6. Phase 2 — country purchasing decisions (2026-09-12)

Implemented per `docs/ha-edp-radar_PHASE2_COUNTRY_PURCHASING.md`; the data
behind each decision is in `docs/country-purchasing-data-profile.md`
(47 934 notices, 760 days). Code comments reference these as `P1` …

**P1 — Notice Value only.** The awarded value of a result notice is BT-161
(`result-value-notice`), once. `result-value-lot` never occurs positive on
non-framework results and tender values over-count, so there is no fallback;
the normalizer no longer sums result lot values.

**P2 — Framework results carry no award value** (extends D21): the Notice
Value of a framework result is the framework's estimate/ceiling or a repeated
call-off total. They count as awarded results without a usable value and are
reported per country as `framework_results`.

**P3 — Buyer-country attribution.** `Buyer.countries` keeps every distinct
buyer country; one country attributes the whole value, several attribute it
once to `MULTI`, none to `??`. European total = attributable + MULTI + unknown.

**P4 — Award date.** `ProcurementNotice.award_date` is the earliest winner
decision date when 0–365 days before publication, else the publication date;
`award_date_basis` records which. Used for periods and for FX.

**P5 — Absolute cap.** Awards above EUR 10bn are quarantined.

**P6 — Internal contradictions.** An award more than 100× a real estimate of
its procedure (same currency) is quarantined; so is one more than 100× the
notice's own winning tender values (`tender_value_total`, stored by the
normalizer when every tender value is positive, the currency is unambiguous
and no awarded lot lacks a value) unless a real estimate corroborates the
Notice Value.

**P7 — Duplicates.** The same Notice Value in several original result notices
of one procedure counts once (earliest award date); later ones are quarantined.

**P8 — Placeholders.** Estimates and tender totals below 10 000 in their
currency (1, 98, 100 …) are never used as references.

**P9 — Unverified large.** Awards of EUR 250m or more with no comparable
estimate stay counted but carry `unverified_large`; per-country count and sum
are exposed.

**P10 — Zero versus unknown.** No awarded results in a period → EUR 0; awarded
results without any usable value → unknown (`None`), unranked and listed.

**P11 — Category split.** One category per award from the main procedure CPV
(`cpv_codes[0]`, verified equal to `main-classification-proc` on every result);
no match → `unclassified`, always exposed.

**P12 — Presentation.** Devices *My Country: <name>* (one identifier, renamed
with the country), *European Purchasing* and *Country Ranking*; the selected
country is always ingested; `edp_radar.get_country_purchasing` exposes the
full country/category matrix. Retention and bootstrap grow to 760 days and a
store bootstrapped over fewer days re-bootstraps without discarding notices.
Config entry version 2 derives My country from the Home Assistant country.

---

## 7. Phase 3 — Sweden defence spending data layer (2026-09-12)

Designed per `docs/ha-edp-radar_PHASE3_SWEDEN_DEFENCE_SPENDING.md` (the plan;
section numbers below refer to it). This section covers the **data layer
only** (plan steps 1–7): providers, storage, coordinator, diagnostics and the
source profile. Devices and sensors (plan §72–79) are specified in §7.4.
Code comments reference these decisions as `S1` …

### 7.1 Verified source facts (2026-09-12)

| Source | Verified |
| --- | --- |
| Statskontoret | `…/oppna-data/manadsutfall/?year=2026` lists, per month, `GetFile?documentType=Utgift&fileType=Zip&…&Year=2026&month=7&status=Definitiv` (and `fileType=Excel`). Latest: **July 2026, definitiv**. The Zip holds one CSV covering **January 2006 → latest month** (10.5 MB, 2 MB zipped): `;`-delimited, `utf-8-sig`, decimal comma, 31 columns — `Utgiftsområde`, `Anslag` (`0601003` = UO6 1:3), `Anslagspost`, `Anslagsdelpost`, `Myndighet`, `Organisationsnummer`, `År`, `Utfall januari` … `Utfall december` (MSEK), plus the same identifiers "utfallsår". Every `Senast uppdaterad` label is on the page. **No budget column.** |
| Eurostat `gov_ev` | `…/statistics/1.0/data/gov_ev?geo=SE&lang=en` returns JSON-stat 2.0 with `updated: 2026-04-27T23:00:00+0200`; dimensions `freq=A`, `expend=DEF|NAT_COFIN_EU`, `na_item=TE|P51G`, `unit=MIO_EUR|MIO_NAC|PC_GDP`, `time=2021…2025`. No `status` object in the SE response. |
| NATO | The 2026 Defence Investment Update article links `/content/dam/nato/webready/documents/finance/def-exp-2026-en.xlsx`. The article URL is year-specific; a stable index page is to be identified in profiling. |
| EDA | The portal links `thematic-policy-reports/eda-defence-data-2025-2026` and historical Excel collections (`eda-collective-and-national-defence-data-2005-2014-(excel).xlsx` etc., single-quoted `href`). The 2025 country-level workbook is to be located in profiling. |
| SIPRI | The landing page links `//www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2025_v1.2.xlsx` and states "revised on 27 April 2026 at 19:00 CET … replaces all previous versions". |

All five hosts answered plain HTTPS GETs from the development machine.

### 7.2 Decisions

**S1 — Separate subsystem.** Package `custom_components/edp_radar/spending/`
with its own `SpendingCoordinator`, `SpendingStore` and models. The TED
coordinator, its bootstrap gate and `RadarStore` are untouched; `metrics.py`
and `sensor.py` do not grow. `entry.runtime_data` becomes
`RuntimeData(radar, spending)`; the four readers (`diagnostics`, `event`,
`services`, `sensor`) use `.radar`.

**S2 — Sweden is hard-coded** (`"SE"`) as the focus country of the spending
layer, per plan §2. The Phase 2 "My country" setting is not consulted.

**S3 — openpyxl.** XLSX workbooks (NATO, EDA, SIPRI) are read with `openpyxl`
in read-only mode; pinned in `manifest.json` `requirements` and in the `dev`
dependency group. It is the integration's first third-party requirement.

**S4 — Data model** (`spending/models.py`, frozen dataclasses, no Home
Assistant imports): `DatapointStatus` (`actual | preliminary | provisional |
estimate | projection | budget`), `ReferencePeriod(start, end, label)`,
`SourceRelease(source_id, release_id, published_at, download_url,
canonical_url, format, etag, last_modified, checksum, retrieved_at)`,
`SpendingDataPoint(source_id, metric_id, country, reference, value: Decimal,
unit, status, published_at, retrieved_at, source_url, release_id, flags)`,
`MetricSpec(metric_id, source_id, display_name, definition, unit,
comparison_group)`, `SourceSpec(source_id, display_name, publisher, official,
canonical_url, cadence, expected_lag_days, formats)` and
`Revision(key, previous_value, previous_release_id, detected_at)`.

**S5 — Identity and revisions.** The logical key of a datapoint is
`(source_id, metric_id, country, reference.start, reference.end, unit)`. A
changed value on an existing key updates the value and records one `Revision`
per key and release, keeping the previous value.

**S6 — Units and currencies.** Values are stored as `Decimal` in the source's
unit (Statskontoret `SEK_MILLION`, Eurostat `EUR_MILLION` / `PCT_GDP` /
`NAC_MILLION`, NATO and SIPRI as the workbook states, e.g.
`USD_MILLION_CONSTANT_<year>`). No FX conversion and no rounding in the data
layer; rankings never cross sources (plan §48), so none is needed.

**S7 — Countries.** Alpha-2 (D2). Each provider maps its own labels
("Sweden", "Türkiye", "United States") through an explicit table; an unknown
label is a parse warning and the row is skipped — never guessed.

**S8 — Comparison groups.** `MetricSpec.comparison_group == source_id`. A
ranking or median accepts datapoints only when `source_id`, `metric_id`,
reference period and unit are identical and Sweden is present; this
implements plan §47–48 without separate allow/deny lists.

**S9 — Statskontoret metrics.** `uo6_total_outturn` (all UO6 appropriations),
`uo6_defence_outturn` (appropriations `0601xxx`, i.e. 1:1–1:14) and
`materiel_outturn` (`0601003`), identified by the `Anslag` column, summed over
`Anslagspost`/`Anslagsdelpost`/`Myndighet`. One datapoint per (metric, year,
month) for every year in the file; YTD, same-period-previous-year and
year-on-year are computed from monthly datapoints, never stored as separate
datapoints. Status from the link's `status=` (`Definitiv → actual`,
`Preliminär → preliminary`); `published_at` from `Senast uppdaterad`.
Discovery: `?year=<current year>`, falling back to the previous year when the
current year lists no month; the highest `month=` for `documentType=Utgift`
wins; Zip → CSV is the runtime format, Excel is not used.

**S10 — Eurostat.** No discovery step: one fixed Statistics API request
filtering `expend=DEF`, `na_item=TE,P51G`, `unit=MIO_EUR,PC_GDP,MIO_NAC`, all
`geo`. JSON-stat is decoded through `id`/`size`/`dimension` (never array
positions). `updated` is both `release_id` and `published_at`. Metrics
`defence_expenditure` (TE) and `defence_investment` (P51G) per unit. Eurostat
observation flags in the `status` object map `p → provisional`,
`e → estimate`, `f → projection`, otherwise `actual`.

**S11 — NATO, EDA, SIPRI parsing.** Tables are located by sheet name and
header text, years by header cells, countries through S7 tables; fixed cell
coordinates are not used. Source markers (NATO `e`, SIPRI bracket/italic
conventions, EDA footnotes) are kept in `flags` and mapped to `status` only
where the workbook defines the marker. EDA metrics are enabled one at a time
after `docs/providers/eda.md` exists (plan §36, §39). SIPRI re-imports the
whole supported series when the release identifier changes (plan §43).

**S12 — Provider contract.** `discover_latest(session) → SourceRelease`,
`fetch_release(session, release) → bytes` (sends `If-None-Match` /
`If-Modified-Since` when the previous release carried them) and
`parse_release(payload, release) → ParseResult(datapoints, warnings,
layout_fingerprint)`. Parsing is pure and synchronous (runs in the executor);
discovery and fetch take the Home Assistant aiohttp session. A missing
expected column, sheet, table title or dimension code raises
`SchemaChangedError` — never empty or zero values (plan §65).

**S13 — Storage.** One `Store` per source, key
`edp_radar.<entry_id>.spending.<source_id>`, holding `schema_version`,
`release`, `health`, `datapoints` and `revisions`. Full series are kept (the
datasets are small). `async_delay_save` as in D12; `async_remove_entry`
removes these stores too.

**S14 — Coordinator.** `update_interval` 6 h. Each refresh runs only the
providers whose `health.next_check_at` has passed: Statskontoret and Eurostat
daily, NATO, EDA and SIPRI weekly. Unchanged `release_id` + `etag`/`checksum`
→ `skipped_unchanged` without download. A provider failure is logged, stored
in its `health` (`available | stale_but_cached | temporarily_unavailable |
parser_error | schema_changed`, `last_error`) and does not affect the other
providers; `UpdateFailed` is raised only when no source has data. There is no
background bootstrap: the first refresh fetches everything (≈10 MB in total).
`SpendingSnapshot = {source_id: SourceSeries(datapoints, release, health)}`
plus `retrieved_at` is what entities will read.

**S15 — Freshness.** Pure functions `publication_age`, `reference_age`,
`retrieval_age` and `freshness_state(spec, latest_reference_end,
published_at, today) → current | expected | late | unknown` derived from the
source cadence and `expected_lag_days` (Statskontoret: last business day of
the month after the reference month, plan §14). Absolute ages are always
available alongside the state.

**S16 — Calculations.** `spending/calculations.py`: `ytd`,
`same_period_previous_year`, `nominal_change_pct`, `rank` (S8 rules, Sweden
always included), `nordic_subset` (SE, FI, DK, NO; IS only where present) and
`population_median`. Budget utilisation (plan §53) is added only if profiling
finds an official budget source; it is never derived from YTD data.

**S17 — Diagnostics.** New `spending` section: per source `health`,
`release`, `datapoints_count`, `countries`, `metrics`, `latest_reference`,
`parse_warnings`, `revision_count`, `schema_version`. No raw payloads.

**S18 — Scripts and documents** (pattern D14, `PYTHONPATH=. uv run python
scripts/…`): `scripts/spending_profile.py [--no-fetch]` caches every source
under `.cache/spending/<source>/<release_id>.*`, runs the providers and writes
`docs/phase3-source-profile.md` containing both the plan §70 profile and the
§71 factual validation report; `scripts/fetch_spending_fixtures.py` trims
cached files into `tests/fixtures/spending/<source>/`. Each provider gets
`docs/providers/<source>.md` (plan §68), EDA's before its parser.

**S19 — Tests.** Unit tests without the HA harness for models, every
provider's discovery and parse (real trimmed fixtures, schema-change failure,
status and country mapping, Eurostat dimension-order independence,
Statskontoret preliminary → definitive replacement, revision diff), freshness
and calculations; HA tests for the store round-trip, the coordinator with mock
providers (isolated failure, unchanged release skipped, cadence gating) and
diagnostics. Quality gate unchanged.

**S20 — Out of scope for this plan.** Entities, devices, translations and the
version bump (0.3.0 with the sensors); `gov_10a_exp` (plan §25); budget
utilisation without a source; any EDA metric not verified in profiling.

### 7.3 Findings from the source profile and execution rulings (2026-09-13)

**S21 — Provider exceptions are fully isolated.**
`SpendingCoordinator._async_refresh_provider` catches `SourceUnavailableError`
and `SchemaChangedError` explicitly, then any other `Exception` (→
`parser_error`, logged with `_LOGGER.exception` for the traceback);
`asyncio.CancelledError` is a `BaseException`, not an `Exception`, and still
propagates. This replaces the plan's closed exception list so the isolation
in plan §64 holds for exception types the plan did not foresee.

**S22 — A cache miss returns the release that describes the fetched
payload, never the one requested.** `EurostatProvider.async_fetch_release`
re-derives the release from the fresh JSON's `updated` field when its
discovery cache is empty (e.g. after a Home Assistant restart);
`EdaProvider.async_fetch_release` re-discovers and returns the freshly
discovered release when its per-year link cache is empty;
`SipriProvider.async_fetch_release` keeps the HEAD-discovered
ETag/Last-Modified only when the GET response carries none of its own. In
every case a stale requested
release is never stamped onto newly fetched bytes.

**S23 — HTTP helper details.** `async_fetch_bytes` and `async_head_metadata`
(`spending/providers/base.py`) wrap the request in `async with` on both the
timeout and the response, so every path — success, timeout, HTTP error —
releases the aiohttp response; the keyword parameter is `request_timeout`,
not `timeout` (ruff `ASYNC109` flags the shadowed name otherwise).
`SpendingStore.async_save(immediate=True)` also rewrites sources whose
delayed write is still pending, not only the ones marked dirty since the
last save, so an unload never loses the last fetched release.

**S24 — Profile findings that shape Plan 2 (sensors).**

(a) EDA publishes country-level equipment procurement and R&D expenditure
only through 2021 (`Billions` sheet, frozen history); the 2022–2025
workbooks add total expenditure, investment, % GDP, % government
expenditure and per-capita spending but carry no country-level
equipment/R&D breakdown for those years.

(b) Eurostat's latest year has fewer reporting countries than the year
before it: the live `gov_ev` release covers 22 of 27 member states for 2025
(ES, IT, NL, CY, IE missing) against 25 of 27 for 2024 (IT, CY missing) —
Sweden ranks #4 of 22 for 2025 but #6 of 25 for 2024, so a ranking sensor
must expose the population it was computed over, not just the rank.

(c) NATO's 2025 and 2026 figures are estimates; for the still-unfinished
2026 reference year the reference age computed against today is negative,
which needs explicit labelling rather than being read as a data error.

(d) SIPRI stores Iceland's military expenditure as 0 (it has no armed
forces); Nordic comparison sensors should label or exclude it rather than
let a true zero skew a median or a "lowest" ranking.

(e) The human-readable Statskontoret outturn page exposes the `SB + ÄB`
budget column only at the aggregate (whole-budget) level — the UO6 row
itself is absent — so there is still no per-expenditure-area budget figure
with provenance. Budget utilisation (plan §53) stays omitted (S16) unless
another official source with per-area figures is found.

(f) SIPRI is stored from `MIN_YEAR = 1990` onward, to bound storage size;
the source workbook itself covers 1949 onward.

**S25 — Statskontoret fixture fetching needs its own HTTP handling.**
Python 3.14's `urllib`/`http.client` default to `Accept-Encoding: identity`,
which statskontoret.se rejects; `scripts/fetch_spending_fixtures.py`
therefore requests `gzip, deflate` explicitly and decompresses the response
itself. The runtime provider fetches through the Home Assistant aiohttp
session, which negotiates encoding normally, so it is unaffected.

**S26 — Statskontoret December status window.** Between the January release
(published mid-February, e.g. 2026-02-18) and the definitive December release
(late March, e.g. 2026-03-24), discovery selects `?year=<Y>` whose December
Y-1 column still holds the preliminary figure, yet it is labelled `actual`
because only the release month gets the release status; revisions capture the
later value change. Fix (owner decision, Plan 2): read `?year=<Y-1>` as well
and label December `preliminary` until a `Definitiv` December entry exists.

**S27 — Constant-price sheet and unit years are hard-coded.** SIPRI
`Constant (2024) US$` / `USD_MILLION_CONSTANT_2024` and NATO "constant 2021" /
`USD_MILLION_CONSTANT_2021` are literals. The next SIPRI edition (April 2027,
base year 2025) will raise `schema_changed` until the constant is updated,
and because `unit` is part of the datapoint key the old series would be
carried over next to the new one rather than replaced. Before sensors depend
on `unit` (Plan 2): discover the base year from the sheet name and decide the
carry-over policy for unit changes.

**S28 — Health updates rewrite the whole series file.** `set_health` marks
the source dirty, so every unchanged-release check rewrites the full store
file (≈5 MB for SIPRI). Acceptable for now; Plan 2 should split health into a
small separate store or skip persistence on the unchanged path.

**S29 — Conditional GET is not exercised at runtime.** No caller passes
`previous=` to `async_fetch_bytes`; re-download avoidance comes from
discovery (HEAD validators inside the release id), which is sufficient.
Either wire the stored release into `async_fetch_release` or remove the
`previous` path in Plan 2.

S14's "no background bootstrap" still holds — one full fetch, not a trickle —
but the *first* refresh after setup runs as an entry background task
(`entry.async_create_background_task`, `custom_components/edp_radar/__init__.py`)
so a slow source never delays setup.

### 7.4 Phase 3 Plan 2 — sensors (2026-09-14)

Designed per
`docs/superpowers/specs/2026-09-14-edp-radar-spending-sensors-design.md`
(the sensors spec; section numbers below refer to it). This section covers
plan steps §72–§79: the five spending devices, their 27 sensors, and the
data-layer prerequisites carried over from §7.3 (`S26`–`S29`, implemented
here as `S38`–`S41`). Code comments reference these decisions as `S30` …

**S30 — One device per source.** Devices `Statskontoret`, `Eurostat`,
`NATO`, `EDA`, `SIPRI` (`DeviceKind.SPENDING_STATSKONTORET` …; implemented
as `spending_device_info(entry_id, source_id)`, no `DeviceKind` members
added), identifiers `(DOMAIN, f"{entry_id}_spending_{source_id}")`, `model`
= `SourceSpec.display_name`, `configuration_url` = `SourceSpec.canonical_url`.
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

S26 → S38, S27 → S39, S28 → S40, S29 → S41 (implemented).

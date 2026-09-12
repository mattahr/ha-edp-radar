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
- **Only 5 % of results link to a competition inside a 90-day window**; the 400-day profile (`docs/data-profile-400d.md`) is the one that matters for the public time-to-result metric.
- **Poland dominates estimated value** (EUR 14.7 bn of EUR 23.3 bn in 90 days). This is what TED reports; the ranking attributes show it explicitly.

## 5. Deferred (explicitly out of the first release)

- Keyword-based category classification (needs descriptions, see D10).
- Framework-agreement ceiling metrics (the data is stored as `framework_value`, D21).
- HHI concentration metric.
- `public_footprint_largest_change` (robust z-score).
- Organisation peers beyond selection by identifier (fuzzy matching stays out).

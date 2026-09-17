# Status och start-prompt för nästa session

Vi bygger Home Assistant-integrationen **ha-edp-radar** (domän `edp_radar`, European Defence Procurement Radar: TED Search API + ECB-valutakurser).

## Läge 2026-09-17

- Plan 1 (kärnbibliotek), Plan 2 (HA-skal), **Fas 2 – Country Purchasing Intelligence** (`docs/ha-edp-radar_PHASE2_COUNTRY_PURCHASING.md`) och **Fas 3 – försvarsutgifter** är implementerade på `main`.
- Fas 3 dataskiktet (S1–S20, plan `docs/superpowers/plans/2026-09-12-edp-radar-spending-data-layer.md`): paketet `custom_components/edp_radar/spending/` (modeller, länder, registry, xlsx-hjälpare, fem leverantörer – Statskontoret, Eurostat, NATO, EDA, SIPRI), `SpendingStore`, `SpendingCoordinator` (tick var 6:e timme, per-källa kadens), diagnostiksektionen `spending`. Besluten S1–S20 står i tillägget §7.2; profilfynden och exekveringsavgörandena S21–S25 i §7.3.
- **Fas 3 Plan 2 – sensorer** (plan `docs/superpowers/specs/2026-09-14-edp-radar-spending-sensors-design.md`, S30–S44) är implementerad: fem enheter (Statskontoret, Eurostat, NATO, EDA, SIPRI) med 27 sensorer – värde, förändring, rankning och andel per källa, två radtexter och en avstängd-som-standard `Data age`-diagnossensor per enhet. Ägarbesluten S26/S27 är genomförda som S38 (Statskontorets decemberstatus läser även `?year=<Y-1>`) och S39 (fastprisbasår läses från kalkylbladet/rubriken i stället för att vara hårdkodat; en ny basår ersätter den lagrade serien i stället för att dubblera den). Besluten S30–S44 står i tillägget §7.4.
- README, `docs/dashboard-example.yaml`, tillägget §7.4 och leverantörsdokumenten `docs/providers/nato.md`/`sipri.md` är uppdaterade; version `0.3.0`.
- Alla commits ligger på `main` men är **inte pushade** – jag pushar när jag säger till.
- Kvalitetsgrind: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components` (353 tester).

## Nästa steg

- **Öppna ägarbeslut från Fas 2** (profilens "Open for the owner", ännu ej implementerade):
  - Domänregel för förbrukningsvaror (livsmedel/städ/avfall) för att fånga de polska ×1000-felen från 2024 som saknar estimat.
  - Kategorin "Infrastructure & facilities" (CPV 45/44/71/90) för den ~55 % stora oklassade massan.
- **GitHub-workflows och issue-templates** – repot saknar båda; behövs nu när det blir publikt.

## Uppskjutna småsaker från Plan 2 (sensorer)

De ~25 småfelen från uppgiftsgranskningarna åtgärdades 2026-09-17 i fyra batchar (`10f92e5`, `8781d01`, `5beffa1`, `fec3667`): datalager (health-store-closure, `_diff_release`, corrupt zip, cachad decemberflagga, Eurostat-pinning), providers (ordgräns i basårsregexen, tvetydiga bladprefix, `is_skipped_label` överallt), rena hjälpare (negativa belopp, `+0.0%`, `month_abbreviation`) och sensorlagret (`_pct_rank_attrs`, `_annual_core_attrs`, `price_base_year` bara med matchande punkt, S33-test, `temporarily_unavailable`-test).

Medvetet kvar:

- Upprepade attributscanningar per tillståndsskrivning — mätt till ~18 ms för alla 27 sensorer mot verklig SIPRI-data; ingen åtgärd.
- `sensors.py` (~985 rader) delas inte — helhetsgranskaren bedömde blockstrukturen som sund.
- Polish från batchgranskningarna: `sheet_by_prefix` använder samma feltyp för noll och flera träffar; `_pct_text` tolkar den avrundade strängen för nolltestet; D4-vakten i `_nato_value_attrs` kunde vara en variabel; zip-testet antar tomt extra-fält; versionslitteralen i `test_diagnostics` kunde läsas ur `manifest.json`.

## Så här arbetar du

- `superpowers:executing-plans` inline, direkt på `main` (godkänt), conventional commits med `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`, push först när jag säger till.
- TDD; kod/strings/README på engelska, `translations/sv.json` på svenska; prata svenska med mig.
- Skript körs med `PYTHONPATH=. uv run python scripts/...`.

# Status och start-prompt för nästa session

Vi bygger Home Assistant-integrationen **ha-edp-radar** (domän `edp_radar`, European Defence Procurement Radar: TED Search API + ECB-valutakurser).

## Läge 2026-09-13

- Plan 1 (kärnbibliotek), Plan 2 (HA-skal) och **Fas 2 – Country Purchasing Intelligence** (`docs/ha-edp-radar_PHASE2_COUNTRY_PURCHASING.md`) är implementerade på `main`.
- Fas 2 i korthet: `purchasing.py` (inköpsmodell), `purchasing_attrs.py`, `periods.py`; devices *My Country*, *European Purchasing*, *Country Ranking*; wizard-steget *My country* (config entry version 2 med migrering); action `edp_radar.get_country_purchasing`; retention 760 dagar med om-bootstrap; dataprofil `docs/country-purchasing-data-profile.md` (skript `scripts/country_purchasing_profile.py --no-fetch` återskapar den från `.cache/profile/strict-760d-all.json`). Besluten P1–P12 står i tillägget §6.
- **Fas 3 – försvarsutgifter, dataskiktet** (S1–S20, plan `docs/superpowers/plans/2026-09-12-edp-radar-spending-data-layer.md`) är implementerat på `main`: paketet `custom_components/edp_radar/spending/` (modeller, länder, registry, xlsx-hjälpare, fem leverantörer — Statskontoret, Eurostat, NATO, EDA, SIPRI — med riktiga trimmade fixtures under `tests/fixtures/spending/`), `SpendingStore` (en store per källa, release-diff, revisions), `SpendingCoordinator` (tick var 6:e timme, per-källa kadens — Statskontoret och Eurostat dagligen, NATO/EDA/SIPRI veckovis — varje leverantörsfel isolerat), diagnostiksektionen `spending`, skripten `scripts/fetch_spending_fixtures.py` och `scripts/spending_profile.py`, samt den genererade `docs/phase3-source-profile.md` och leverantörsdokumenten i `docs/providers/`. Besluten S1–S20 står i tillägget §7.2; fynden från den levande profilen och exekveringsavgöranden (S21–S25) i §7.3.
- Fas 3-commitarna ligger på `main` men är **inte pushade** – jag pushar när jag säger till.
- Kvalitetsgrind: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components/edp_radar` (281 tester).

## Nästa steg

- **Plan 2 för Fas 3 – sensorer/devices** (plan §72–§79, skild från Plan 2/HA-skalet under "Läge" ovan) är näst på tur. Börja med en brainstorm-runda (`superpowers:brainstorming`) på profilfynden i tillägget §7.3 (S24): EDA:s landsnivådata för materielanskaffning och FoU slutar 2021 (2022–2025 har bara totalsumma, investering, %BNP, %statsutgifter och per capita); Eurostats senaste år har färre rapporterande länder (2025: 22 av 27, Sverige #4; 2024: 25 av 27, Sverige #6) så rankningssensorer måste exponera populationen; NATO 2025/2026 är estimat och referensåldern för det ännu inte avslutade 2026 blir negativ; SIPRI lagrar Island som 0 (inga väpnade styrkor); budgetutfall (S16) uteblir tills vidare — den mänskligt läsbara Statskontoret-sidan visar `SB + ÄB` bara på aggregerad nivå, inte per utgiftsområde.
- `PYTHONPATH=. uv run python scripts/spending_profile.py --no-fetch` återskapar `docs/phase3-source-profile.md` från `.cache/spending/profile/` utan nya nätverksanrop.

## Ägarbeslut som Fas 3 väntar på (tillägget §7.3)

- **S26** – Statskontorets decemberstatus: mellan januarireleasen (mitten av februari) och den definitiva decemberreleasen (slutet av mars) märks december året innan `actual` fast värdet är preliminärt. Fixen kräver att `?year=<Y-1>` också läses.
- **S27** – Fastprisbasår hårdkodade (SIPRI `Constant (2024) US$`, NATO "constant 2021") och `unit` ingår i datapunktsnyckeln: SIPRI:s nästa utgåva (april 2027) ger `schema_changed` och en unit-ändring skulle dubblera serien. Bestäm carry-over-policy innan sensorer bygger på `unit`.

## Småsaker uppskjutna till Plan 2 (från uppgiftsgranskningarna)

- `resolve_country` returnerar `None` både för okända och överhoppade etiketter; EDA-parsern saknar `SKIP_LABELS`-kontroll (NATO/SIPRI har den). Dubbla nycklar inom en release kollapsar tyst i `SpendingStore.apply_release`; `revisions` växer obegränsat; `async_load` antar dict-data.
- Koordinatorn skriver `store.series[...]` direkt på `unchanged_checksum`-vägen (ingen `refresh_release`-metod); `async_refresh_source` med okänt id ger `StopIteration`; `UpdateFailed`-kontrollen tittar på alla lagrade källor, inte bara konfigurerade leverantörer; `SPENDING_RETRY_INTERVAL` (1 h) är verkningslös under 6-timmarsticken; `expected_lag_days` i `SourceSpec` används inte av `freshness.py`.
- Statskontoret: rader kortare än rubriken släpps utan varning; `DiscoveredRelease.heading` används inte; `date.today()` i stället för `dt_util`. Eurostat: `freq`-dimensionen tar första kategorin utan kontroll. EDA: tre duplicerade kolumntupler, `for label in ("year",)`, no-op `.replace`, inget test på `-`-celler, leverantörstestet serverar 2022-boken för 2023/2024. SIPRI: `highly_uncertain` testas bara syntetiskt. HTTP: 304-testet kontrollerar inte medförda validators; `async_head_metadata`:s undantagsgren saknar test; ingen storleksgräns på svar/zip-medlemmar.
- Diagnostik: fältnamnen avviker från S17 (`datapoints`/`revisions` i stället för `datapoints_count`/`revision_count`); `layout_fingerprint` sparas inte. Profilskriptet: NATO:s negativa referensålder skrivs utan förklaring; en leverantör med noll datapunkter ger tomma celler.

## Öppna ägarbeslut

- Domänregel för förbrukningsvaror (livsmedel/städ/avfall) för att fånga de polska ×1000-felen från 2024 som saknar estimat – ej implementerat (profilens "Open for the owner").
- Kategorin "Infrastructure & facilities" (CPV 45/44/71/90) för den ~55 % stora oklassade massan.
- Inga GitHub-workflows eller issue templates.

## Så här arbetar du

- `superpowers:executing-plans` inline, direkt på `main` (godkänt), conventional commits med `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`, push först när jag säger till.
- TDD; kod/strings/README på engelska, `translations/sv.json` på svenska; prata svenska med mig.
- Skript körs med `PYTHONPATH=. uv run python scripts/...`.

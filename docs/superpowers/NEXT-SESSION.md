# Status och start-prompt för nästa session

Vi bygger Home Assistant-integrationen **ha-edp-radar** (domän `edp_radar`, European Defence Procurement Radar: TED Search API + ECB-valutakurser).

## Läge 2026-09-13

- Plan 1 (kärnbibliotek), Plan 2 (HA-skal) och **Fas 2 – Country Purchasing Intelligence** (`docs/ha-edp-radar_PHASE2_COUNTRY_PURCHASING.md`) är implementerade på `main`.
- Fas 2 i korthet: `purchasing.py` (inköpsmodell), `purchasing_attrs.py`, `periods.py`; devices *My Country*, *European Purchasing*, *Country Ranking*; wizard-steget *My country* (config entry version 2 med migrering); action `edp_radar.get_country_purchasing`; retention 760 dagar med om-bootstrap; dataprofil `docs/country-purchasing-data-profile.md` (skript `scripts/country_purchasing_profile.py --no-fetch` återskapar den från `.cache/profile/strict-760d-all.json`). Besluten P1–P12 står i tillägget §6.
- **Fas 3 – försvarsutgifter, dataskiktet** (S1–S20, plan `docs/superpowers/plans/2026-09-12-edp-radar-spending-data-layer.md`) är implementerat på `main`: paketet `custom_components/edp_radar/spending/` (modeller, länder, registry, xlsx-hjälpare, fem leverantörer — Statskontoret, Eurostat, NATO, EDA, SIPRI — med riktiga trimmade fixtures under `tests/fixtures/spending/`), `SpendingStore` (en store per källa, release-diff, revisions), `SpendingCoordinator` (tick var 6:e timme, per-källa kadens — Statskontoret och Eurostat dagligen, NATO/EDA/SIPRI veckovis — varje leverantörsfel isolerat), diagnostiksektionen `spending`, skripten `scripts/fetch_spending_fixtures.py` och `scripts/spending_profile.py`, samt den genererade `docs/phase3-source-profile.md` och leverantörsdokumenten i `docs/providers/`. Besluten S1–S20 står i tillägget §7.2; fynden från den levande profilen och exekveringsavgöranden (S21–S25) i §7.3.
- Fas 3-kommitarna ligger på `main` men är **inte pushade** – jag pushar när jag säger till.
- Kvalitetsgrind: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components/edp_radar` (279 tester).

## Nästa steg

- **Plan 2 – sensorer och devices** (plan §72–§79) är näst på tur. Börja med en brainstorm-runda (`superpowers:brainstorming`) på profilfynden i tillägget §7.3 (S24): EDA:s landsnivådata för materielanskaffning och FoU slutar 2021 (2022–2025 har bara totalsumma, investering, %BNP, %statsutgifter och per capita); Eurostats senaste år har färre rapporterande länder (2025: 22 av 27, Sverige #4; 2024: 25 av 27, Sverige #6) så rankningssensorer måste exponera populationen; NATO 2025/2026 är estimat och referensåldern för det ännu inte avslutade 2026 blir negativ; SIPRI lagrar Island som 0 (inga väpnade styrkor); budgetutfall (S16) uteblir tills vidare — den mänskligt läsbara Statskontoret-sidan visar `SB + ÄB` bara på aggregerad nivå, inte per utgiftsområde.
- `PYTHONPATH=. uv run python scripts/spending_profile.py --no-fetch` återskapar `docs/phase3-source-profile.md` från `.cache/spending/profile/` utan nya nätverksanrop.

## Öppna ägarbeslut

- Domänregel för förbrukningsvaror (livsmedel/städ/avfall) för att fånga de polska ×1000-felen från 2024 som saknar estimat – ej implementerat (profilens "Open for the owner").
- Kategorin "Infrastructure & facilities" (CPV 45/44/71/90) för den ~55 % stora oklassade massan.
- Inga GitHub-workflows eller issue templates.

## Så här arbetar du

- `superpowers:executing-plans` inline, direkt på `main` (godkänt), conventional commits med `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`, push först när jag säger till.
- TDD; kod/strings/README på engelska, `translations/sv.json` på svenska; prata svenska med mig.
- Skript körs med `PYTHONPATH=. uv run python scripts/...`.

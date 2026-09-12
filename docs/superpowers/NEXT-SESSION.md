# Status och start-prompt för nästa session

Vi bygger Home Assistant-integrationen **ha-edp-radar** (domän `edp_radar`, European Defence Procurement Radar: TED Search API + ECB-valutakurser).

## Läge 2026-09-12

- Plan 1 (kärnbibliotek), Plan 2 (HA-skal) och **Fas 2 – Country Purchasing Intelligence** (`docs/ha-edp-radar_PHASE2_COUNTRY_PURCHASING.md`) är implementerade på `main`.
- Fas 2 i korthet: `purchasing.py` (inköpsmodell), `purchasing_attrs.py`, `periods.py`; devices *My Country*, *European Purchasing*, *Country Ranking*; wizard-steget *My country* (config entry version 2 med migrering); action `edp_radar.get_country_purchasing`; retention 760 dagar med om-bootstrap; dataprofil `docs/country-purchasing-data-profile.md` (skript `scripts/country_purchasing_profile.py --no-fetch` återskapar den från `.cache/profile/strict-760d-all.json`). Besluten P1–P12 står i tillägget §6.
- Kvalitetsgrind: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components/edp_radar` (200 tester).

## Öppna ägarbeslut

- Domänregel för förbrukningsvaror (livsmedel/städ/avfall) för att fånga de polska ×1000-felen från 2024 som saknar estimat – ej implementerat (profilens "Open for the owner").
- Kategorin "Infrastructure & facilities" (CPV 45/44/71/90) för den ~55 % stora oklassade massan.
- Inga GitHub-workflows eller issue templates.

## Så här arbetar du

- `superpowers:executing-plans` inline, direkt på `main` (godkänt), conventional commits med `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`, push först när jag säger till.
- TDD; kod/strings/README på engelska, `translations/sv.json` på svenska; prata svenska med mig.
- Skript körs med `PYTHONPATH=. uv run python scripts/...`.

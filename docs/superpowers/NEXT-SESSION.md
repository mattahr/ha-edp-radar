# Status och start-prompt för nästa session

Vi bygger Home Assistant-integrationen **ha-edp-radar** (domän `edp_radar`, European Defence Procurement Radar: TED Search API + ECB-valutakurser).

## Läge 2026-09-14

- Plan 1 (kärnbibliotek), Plan 2 (HA-skal), **Fas 2 – Country Purchasing Intelligence** (`docs/ha-edp-radar_PHASE2_COUNTRY_PURCHASING.md`) och **Fas 3 – försvarsutgifter** är implementerade på `main`.
- Fas 3 dataskiktet (S1–S20, plan `docs/superpowers/plans/2026-09-12-edp-radar-spending-data-layer.md`): paketet `custom_components/edp_radar/spending/` (modeller, länder, registry, xlsx-hjälpare, fem leverantörer – Statskontoret, Eurostat, NATO, EDA, SIPRI), `SpendingStore`, `SpendingCoordinator` (tick var 6:e timme, per-källa kadens), diagnostiksektionen `spending`. Besluten S1–S20 står i tillägget §7.2; profilfynden och exekveringsavgörandena S21–S25 i §7.3.
- **Fas 3 Plan 2 – sensorer** (plan `docs/superpowers/specs/2026-09-14-edp-radar-spending-sensors-design.md`, S30–S44) är implementerad: fem enheter (Statskontoret, Eurostat, NATO, EDA, SIPRI) med 27 sensorer – värde, förändring, rankning och andel per källa, två radtexter och en avstängd-som-standard `Data age`-diagnossensor per enhet. Ägarbesluten S26/S27 är genomförda som S38 (Statskontorets decemberstatus läser även `?year=<Y-1>`) och S39 (fastprisbasår läses från kalkylbladet/rubriken i stället för att vara hårdkodat; en ny basår ersätter den lagrade serien i stället för att dubblera den). Besluten S30–S44 står i tillägget §7.4.
- README, `docs/dashboard-example.yaml`, tillägget §7.4 och leverantörsdokumenten `docs/providers/nato.md`/`sipri.md` är uppdaterade; version `0.3.0`.
- Alla commits ligger på `main` men är **inte pushade** – jag pushar när jag säger till.
- Kvalitetsgrind: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components` (334 tester).

## Nästa steg

- **Öppna ägarbeslut från Fas 2** (profilens "Open for the owner", ännu ej implementerade):
  - Domänregel för förbrukningsvaror (livsmedel/städ/avfall) för att fånga de polska ×1000-felen från 2024 som saknar estimat.
  - Kategorin "Infrastructure & facilities" (CPV 45/44/71/90) för den ~55 % stora oklassade massan.
- **GitHub-workflows och issue-templates** – repot saknar båda; behövs nu när det blir publikt.

## Uppskjutna småsaker från Plan 2 (sensorer)

Fynd från uppgiftsgranskningarna under Plan 2 (S30–S44) som medvetet sköts upp – se `.superpowers/sdd/2026-09-14-edp-radar-spending-sensors/progress.md` (git-ignorerad) för fullständiga rullningar:

- Task 1: `async_save`-docstringen överdriver executor-användningen för health-store; `_static`/`_static_health`-closurerna dupliceras.
- Task 2: inget test för "gammal nyckel finns även i inkommande"-vakten; inget blandat supersede+carry-over-test; `apply_release` är ~90 rader.
- Task 3: `self.store.get(source_id)` upprepas i `UpdateFailed`-blocket.
- Task 4: den sammansatta `freshness_state`-overdue-vägen testas bara för TWICE_YEARLY; `_month_end` skulle kunna återanvändas av `last_business_day`.
- Task 5: `zipfile.BadZipFile` från `archive.read` fångas inte (fanns redan innan Plan 2).
- Task 6: föregående års Statskontoret-sida hämtas ovillkorligt varje daglig tick i stället för att cachas efter definitiv release; pluralbugg i loggtexten "1 rows … were skipped".
- Task 7: Eurostats `.get(dim) or next(iter(index))` blandar ihop saknat och falskt värde; `_index(data, "freq")` beräknas två gånger i samma vakt.
- Task 8: NATO:s basårs-härledning testas bara mot 2021; `sheet_by_prefix` tar tyst den första träffen; `trim_sipri_workbook` antar att `KEEP_ROW` kommer före `KEEP_FROM`; `_BASE_YEAR`-regexen saknar ordgräns.
- Task 9: `wanted`-parametrar skrivs fortfarande ut i klartext i stället för `Column`-aliaset; `nato.py`/`sipri.py` implementerar `SKIP_LABELS`-kontrollen själva i stället för att återanvända `is_skipped_label`.
- Task 10: lokal re-import av `SourceRelease` i `test_models`; em-dash-grenen i release-id är otestad.
- Task 11: `rank()` ger `None` när fokuslandet självt är nollan (avsiktligt enligt S35, men oprövat om Sverige någonsin rapporterar 0 – profilskriptets textrad kan då bli missvisande); `month_change`s saknad-föregående-gren och `change_over_years`s nollbas-gren är otestade; `annual_series` utan angiven `unit` skriver tyst över tidigare punkt.
- Task 12: `monthly_series_attrs` tolkar visningsetiketten för att hitta månadsförkortningen i stället för att använda `start.month`; `scaled` har ett flyttalstak kring 2^53 (ej nåbart med dagens data).
- Task 13: negativa belopp faller igenom oskalade i `format_amount` (samma brist fanns redan i `format_eur`); `-0.0%` kan visas för mycket små negativa ändringar.
- Task 14: upprepade attributscanningar per tillståndsskrivning; testet för "okänt före första refresh" täcker tom serie men inte `data is None`; S33:s tillgänglighetsregel (`available` följer `last_update_success`) är otestad; enhetsnamn-dicten nycklas på strängliteraler; `_pct_value`-aliaset.
- Task 15: `_focus_rank` rankar om separat för `pct_gdp_rank`; värde- och rank-sensorer räknar var sin rankning i stället för att dela en; `sensors.py` är 616 rader och växande (delningskandidat).
- Task 16: `price_base_year` rapporteras även när `usd_constant` är null (inaktuell punkt); `_nato_value_attrs` scannar `annual_series` två gånger; `_nato_pct_attrs`/`_nato_equipment_attrs` delar en form som en generisk byggare skulle kunna täcka.
- Task 17: `_eda_value_attrs` speglar `_eurostat_value_attrs` nästan rakt av; EDA:s `change_pct` testas bara som "is not None", inte mot ett exakt värde.
- Task 18: `_year_over_year` räknar om en `annual_series` som redan finns lokalt tillgänglig; `_sipri_pct_attrs` speglar `_nato_pct_attrs`; `statuses` testas bara som mängd, inte innehåll.
- Task 19: data-age-testet kontrollerar inte `entity_category`/`state_class`; `temporarily_unavailable`-vägen för hälsotillståndet är otestad; `_latest_reference_end` bygger upp en lista i stället för att strömma; ett negativt `reference_age_days` på ålderssensorn (NATO 2026) förklaras inte i attributen.

## Så här arbetar du

- `superpowers:executing-plans` inline, direkt på `main` (godkänt), conventional commits med `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`, push först när jag säger till.
- TDD; kod/strings/README på engelska, `translations/sv.json` på svenska; prata svenska med mig.
- Skript körs med `PYTHONPATH=. uv run python scripts/...`.

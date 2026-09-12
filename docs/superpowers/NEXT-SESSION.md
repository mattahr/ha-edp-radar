# Start-prompt för nästa session

Vi bygger Home Assistant-integrationen **ha-edp-radar** (domän `edp_radar`, European Defence Procurement Radar: TED Search API + ECB-valutakurser). Plan 1 (kärnbiblioteket) är klar, testad och pushad till `main`. Nu ska du genomföra **Plan 2 – Home Assistant-skalet**.

## Läs först, i denna ordning

1. `docs/superpowers/plans/2026-09-12-edp-radar-ha-shell.md` – Plan 2 (8 tasks). Det är den du ska exekvera.
2. `docs/superpowers/specs/2026-09-12-edp-radar-design-addendum.md` – verifierade API-fakta och besluten D1–D26. Vid konflikt med huvudplanen vinner tillägget.
3. `docs/ha-edp-radar_PROJECT.md` – huvudplanen/specen (§21–29, §33, §42–46, §50–51 är relevanta för Plan 2).
4. `docs/data-profile-400d.md` – uppmätt datakvalitet (25 750 verkliga notiser). Styr vilka sensorer som är aktiverade.
5. `../ha-battaxi` – mitt tidigare HA-integrationsrepo. Följ dess mönster för `manifest.json`, `hacs.json`, `coordinator.py` (`type XConfigEntry = ConfigEntry[...]`, `entry.runtime_data`), `entity.py`, `sensor.py` (`EntityDescription` med `value_fn`/`attributes_fn`), `config_flow.py`, `strings.json` + `translations/{en,sv}.json` + `icons.json`, `tests/conftest.py` (`aioclient_mock`, `MockConfigEntry`, `freezer`), `tests/test_translations.py`, `docker-compose.yml`, `dev/ha.sh`, `.vscode/` och README.

## Så här arbetar du

- Använd `superpowers:executing-plans`, **inline** i sessionen (inte subagenter), direkt på `main` (jag har godkänt det), commit per task med conventional commits och attributionsraden `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`. Pusha när jag säger till.
- TDD: test först, sedan implementation. Före varje commit: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components/edp_radar` (kör mypy utan pipe så exit-koden syns).
- Verktyg: Python 3.14, `uv sync --group dev`, HA 2026.9.2, `pytest-homeassistant-custom-component==0.13.365`. `ruff` är exkluderad från `docs/` (den formaterar annars kodblock i markdown).
- Skript körs med `PYTHONPATH=. uv run python scripts/...`.
- Mindre avsteg från planen är OK; större vill jag diskutera först. Inga GitHub-workflows eller issue templates.
- Skriv kod, `strings.json` och README på engelska; `translations/sv.json` på svenska med korrekta å/ä/ö. Prata med mig på svenska.

## Kärnbibliotekets gränssnitt (Plan 1, färdigt – ändra inte utan skäl)

`custom_components/edp_radar/`: `const.py` (DOMAIN, CONF_*-nycklar, landstabeller, `RelevanceMode`, `MarketPreset`), `models.py` (`ProcurementNotice` m.fl., `to_dict`/`from_dict`), `query.py` (`TedQueryBuilder`), `api.py` (`TedApiClient.async_search_notices/async_validate_query/async_count_notices`, `TedApiError`, `TedApiTemporaryError`, `TedQueryError`), `normalizer.py` (`REQUESTED_FIELDS`, `normalize_many`), `taxonomy.py` (`Taxonomy.load()`), `fx_rates.py`/`fx.py` (`FxRateTable`, `EcbFxClient.async_fetch_recent/async_fetch_history`), `lifecycle.py` (`ProcedureIndex`), `metrics.py` (`MetricsConfig`, `OwnOrganisation`, `WatchlistConfig`, `compute_snapshot` → `RadarSnapshot`, `event_type_for`, `notice_event_attributes`, `watchlist_matches`), `storage.py` (`RadarStore` över HA `Store`: `async_load/upsert/upsert_many/prune/mark_events_emitted/was_event_emitted/update_fx/async_save/async_remove`, `index.bootstrap_complete`). Testfabriker i `tests/factories.py`, 18 verkliga TED-notiser i `tests/fixtures/ted/real_notices.json`.

## Öppna ägarbeslut (fråga mig när du når dem)

- LICENSE: anta MIT, "Mattias Ahrens 2026" om jag inte säger annat (Task 8).
- Eventuell ny kategori "Infrastructure & facilities" (CPV 45/44/71/90) för den ~55 % stora oklassade massan – inte utan mitt OK (addendum §4).
- D25 (behåll senaste snapshot vid TED-fel i stället för `UpdateFailed` när lagrad data finns) är beslutat men ska in i Task 2:s tester.

## Startkommando

Börja med att köra `uv sync --group dev && uv run pytest -q` (förväntat: 114 passed), läs Plan 2, skapa todo-lista över dess 8 tasks och börja med Task 1. Rapportera kort vid fasgränserna (efter Task 2, efter Task 6, efter Task 8) – jag avbryter om jag vill stanna.

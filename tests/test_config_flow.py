"""Tests for the config flow and the options flow."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.edp_radar.config_flow import (
    CONF_CANDIDATE,
    CONF_SEARCH,
    CONF_TRACK_ORGANISATION,
    BuyerCandidate,
    group_buyer_candidates,
)
from custom_components.edp_radar.const import (
    CONF_MARKET_COUNTRIES,
    CONF_MARKET_PRESET,
    CONF_OWN_ALIASES,
    CONF_OWN_COUNTRY,
    CONF_OWN_IDENTIFIERS,
    CONF_OWN_NAME,
    CONF_OWN_ORGANISATION,
    CONF_PEER_COUNTRIES,
    CONF_PEER_PRESET,
    CONF_PINNED_CATEGORIES,
    CONF_RAW_COUNTRIES,
    CONF_RELEVANCE_MODE,
    CONF_SELECTED_COUNTRY,
    CONF_WATCHLIST_COUNTRIES,
    CONF_WATCHLIST_MIN_ESTIMATED_EUR,
    DOMAIN,
    NAME,
    RelevanceMode,
)

from .conftest import TED_SEARCH_URL

FMV = {
    "buyer-name": {"swe": ["Försvarets materielverk"]},
    "buyer-identifier": ["202100-0340"],
    "buyer-country": ["SWE"],
}
FMV_SHORT = {
    "buyer-name": {"swe": ["FMV"], "eng": ["Swedish Defence Materiel Administration"]},
    "buyer-identifier": ["202100-0340"],
    "buyer-country": ["SWE"],
}
FORSVARSMAKTEN = {
    "buyer-name": {"swe": ["Försvarsmakten"]},
    "buyer-identifier": ["202100-4615"],
    "buyer-country": ["SWE"],
}
CENTRAL = {
    "buyer-name": {"swe": [f"Kommun {i}" for i in range(12)]},
    "buyer-identifier": [f"1{i:09d}" for i in range(12)],
    "buyer-country": ["SWE"] * 12,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    with patch(
        "custom_components.edp_radar.async_setup_entry", return_value=True
    ) as mock:
        yield mock


@pytest.fixture
def ted(
    aioclient_mock: AiohttpClientMocker, fast_ted_client: None
) -> AiohttpClientMocker:
    """TED: query validation succeeds; buyer searches return three FMV/FM hits."""

    async def handler(
        method: str, url: Any, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        if data.get("checkQuerySyntax"):
            return AiohttpClientMockResponse(method, url, json={"notices": []})
        assert "buyer-name ~ (" in data["query"]
        return AiohttpClientMockResponse(
            method,
            url,
            json={"notices": [FMV, FMV_SHORT, FORSVARSMAKTEN], "totalNoticeCount": 3},
        )

    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    return aioclient_mock


def option_values(result: dict, field: str) -> list[str]:
    schema = result["data_schema"].schema
    selector = next(value for key, value in schema.items() if key == field)
    return [
        option["value"] if isinstance(option, dict) else option
        for option in selector.config["options"]
    ]


async def start_user_flow(hass: HomeAssistant) -> dict:
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def configure(hass: HomeAssistant, result: dict, data: dict) -> dict:
    return await hass.config_entries.flow.async_configure(result["flow_id"], data)


def test_group_buyer_candidates() -> None:
    candidates = group_buyer_candidates([FMV, FORSVARSMAKTEN, FMV_SHORT, CENTRAL])
    assert candidates == [
        BuyerCandidate(
            identifiers=("202100-0340",),
            country="SE",
            names=(
                "Försvarets materielverk",
                "FMV",
                "Swedish Defence Materiel Administration",
            ),
            notices=2,
        ),
        BuyerCandidate(
            identifiers=("202100-4615",),
            country="SE",
            names=("Försvarsmakten",),
            notices=1,
        ),
    ]
    assert candidates[0].label == "Försvarets materielverk · 202100-0340"
    assert candidates[0].as_options() == {
        CONF_OWN_IDENTIFIERS: ["202100-0340"],
        CONF_OWN_COUNTRY: "SE",
        CONF_OWN_NAME: "Försvarets materielverk",
        CONF_OWN_ALIASES: ["FMV", "Swedish Defence Materiel Administration"],
    }


def test_group_buyer_candidates_without_identifiers_uses_name() -> None:
    raw = {"buyer-name": {"deu": ["Bundeswehr"]}, "buyer-country": ["DEU"]}
    (candidate,) = group_buyer_candidates([raw, raw])
    assert candidate.identifiers == ()
    assert candidate.names == ("Bundeswehr",)
    assert candidate.notices == 2
    assert candidate.label == "Bundeswehr"


async def test_full_flow_with_defaults(
    hass: HomeAssistant, ted: AiohttpClientMocker, mock_setup_entry: AsyncMock
) -> None:
    result = await start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert option_values(result, CONF_RELEVANCE_MODE) == ["strict", "broad"]
    assert option_values(result, CONF_MARKET_PRESET) == [
        "eu",
        "nordic",
        "ted",
        "custom",
    ]

    result = await configure(
        hass, result, {CONF_RELEVANCE_MODE: "strict", CONF_MARKET_PRESET: "eu"}
    )
    assert result["step_id"] == "organisation"
    result = await configure(hass, result, {CONF_TRACK_ORGANISATION: False})
    assert result["step_id"] == "peers"
    result = await configure(hass, result, {CONF_PEER_PRESET: "none"})
    assert result["step_id"] == "categories"
    assert "land_systems" in option_values(result, CONF_PINNED_CATEGORIES)
    result = await configure(hass, result, {CONF_PINNED_CATEGORIES: []})
    assert result["step_id"] == "raw_data"
    result = await configure(hass, result, {})
    assert result["step_id"] == "watchlist"
    result = await configure(hass, result, {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {}
    assert result["options"] == {
        CONF_RELEVANCE_MODE: "strict",
        CONF_MARKET_PRESET: "eu",
        CONF_PEER_PRESET: "none",
        CONF_PINNED_CATEGORIES: [],
        CONF_RAW_COUNTRIES: [],
    }
    assert result["result"].unique_id == DOMAIN
    assert mock_setup_entry.call_count == 1
    validations = [c for c in ted.mock_calls if c[2].get("checkQuerySyntax")]
    assert len(validations) == 1
    assert validations[0][2]["query"].startswith("PD>=")


async def test_full_flow_with_everything(
    hass: HomeAssistant, ted: AiohttpClientMocker, mock_setup_entry: AsyncMock
) -> None:
    result = await start_user_flow(hass)
    result = await configure(
        hass, result, {CONF_RELEVANCE_MODE: "broad", CONF_MARKET_PRESET: "custom"}
    )
    assert result["step_id"] == "countries"
    assert "SE" in option_values(result, CONF_MARKET_COUNTRIES)
    result = await configure(hass, result, {CONF_MARKET_COUNTRIES: ["SE", "FI"]})
    assert result["step_id"] == "organisation"
    result = await configure(hass, result, {CONF_TRACK_ORGANISATION: True})
    assert result["step_id"] == "organisation_search"
    result = await configure(
        hass, result, {CONF_OWN_COUNTRY: "SE", CONF_SEARCH: "försvarets materiel"}
    )
    assert result["step_id"] == "organisation_select"
    assert result["errors"] == {}
    schema = result["data_schema"].schema
    selector = next(v for k, v in schema.items() if k == CONF_CANDIDATE)
    labels = [o["label"] for o in selector.config["options"]]
    assert labels == [
        "Försvarets materielverk · 202100-0340",
        "Försvarsmakten · 202100-4615",
    ]
    search_query = next(
        c[2]["query"] for c in ted.mock_calls if "buyer-name" in c[2].get("query", "")
    )
    assert "buyer-name ~ (försvarets* materiel*)" in search_query
    assert "buyer-country IN (SWE)" in search_query

    result = await configure(hass, result, {CONF_CANDIDATE: "0"})
    assert result["step_id"] == "peers"
    result = await configure(
        hass, result, {CONF_PEER_PRESET: "custom", CONF_SELECTED_COUNTRY: "SE"}
    )
    assert result["step_id"] == "peer_countries"
    result = await configure(hass, result, {CONF_PEER_COUNTRIES: ["PL", "DE"]})
    assert result["step_id"] == "categories"
    result = await configure(
        hass, result, {CONF_PINNED_CATEGORIES: ["land_systems", "cyber_it"]}
    )
    assert result["step_id"] == "raw_data"
    assert "SE" in option_values(result, CONF_RAW_COUNTRIES)
    result = await configure(hass, result, {CONF_RAW_COUNTRIES: ["SE"]})
    assert result["step_id"] == "watchlist"
    result = await configure(
        hass,
        result,
        {CONF_WATCHLIST_COUNTRIES: ["PL"], CONF_WATCHLIST_MIN_ESTIMATED_EUR: 1e8},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    options = result["options"]
    assert options[CONF_RELEVANCE_MODE] == "broad"
    assert options[CONF_MARKET_PRESET] == "custom"
    assert options[CONF_MARKET_COUNTRIES] == ["SE", "FI"]
    assert options[CONF_OWN_ORGANISATION] == {
        CONF_OWN_IDENTIFIERS: ["202100-0340"],
        CONF_OWN_COUNTRY: "SE",
        CONF_OWN_NAME: "Försvarets materielverk",
        CONF_OWN_ALIASES: ["FMV", "Swedish Defence Materiel Administration"],
    }
    assert options[CONF_PEER_PRESET] == "custom"
    assert options[CONF_PEER_COUNTRIES] == ["PL", "DE"]
    assert options[CONF_SELECTED_COUNTRY] == "SE"
    assert options[CONF_PINNED_CATEGORIES] == ["land_systems", "cyber_it"]
    assert options[CONF_RAW_COUNTRIES] == ["SE"]
    assert options[CONF_WATCHLIST_COUNTRIES] == ["PL"]
    assert options[CONF_WATCHLIST_MIN_ESTIMATED_EUR] == 1e8


async def test_organisation_search_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, fast_ted_client: None
) -> None:
    aioclient_mock.post(TED_SEARCH_URL, status=503)
    result = await start_user_flow(hass)
    result = await configure(
        hass, result, {CONF_RELEVANCE_MODE: "strict", CONF_MARKET_PRESET: "nordic"}
    )
    result = await configure(hass, result, {CONF_TRACK_ORGANISATION: True})
    result = await configure(
        hass, result, {CONF_OWN_COUNTRY: "SE", CONF_SEARCH: "försvar"}
    )
    assert result["step_id"] == "organisation_search"
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    aioclient_mock.post(TED_SEARCH_URL, json={"notices": [], "totalNoticeCount": 0})
    result = await configure(
        hass, result, {CONF_OWN_COUNTRY: "SE", CONF_SEARCH: "nonexistent"}
    )
    assert result["step_id"] == "organisation_search"
    assert result["errors"] == {"base": "no_matches"}

    aioclient_mock.clear_requests()
    aioclient_mock.post(TED_SEARCH_URL, json={"notices": [CENTRAL]})
    result = await configure(
        hass, result, {CONF_OWN_COUNTRY: "SE", CONF_SEARCH: "kommun"}
    )
    assert result["step_id"] == "organisation_search"
    assert result["errors"] == {"base": "no_matches"}


async def test_invalid_query_is_reported_on_the_last_step(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, fast_ted_client: None
) -> None:
    aioclient_mock.post(
        TED_SEARCH_URL,
        status=400,
        json={"message": "bad", "error": {"type": "QUERY_SYNTAX_ERROR"}},
    )
    result = await start_user_flow(hass)
    result = await configure(
        hass, result, {CONF_RELEVANCE_MODE: "strict", CONF_MARKET_PRESET: "eu"}
    )
    result = await configure(hass, result, {CONF_TRACK_ORGANISATION: False})
    result = await configure(hass, result, {CONF_PEER_PRESET: "none"})
    result = await configure(hass, result, {CONF_PINNED_CATEGORIES: []})
    result = await configure(hass, result, {})
    result = await configure(hass, result, {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "watchlist"
    assert result["errors"] == {"base": "invalid_query"}

    aioclient_mock.clear_requests()
    aioclient_mock.post(TED_SEARCH_URL, status=503)
    result = await configure(hass, result, {})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_second_entry_is_refused(
    hass: HomeAssistant, ted: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    result = await start_user_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def start_options(hass: HomeAssistant, entry: MockConfigEntry) -> dict:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"
    assert list(result["menu_options"]) == [
        "universe",
        "organisation",
        "peers",
        "categories",
        "raw_data",
        "watchlist",
    ]
    return result


async def options_configure(hass: HomeAssistant, result: dict, data: dict) -> dict:
    return await hass.config_entries.options.async_configure(result["flow_id"], data)


async def test_options_universe_reloads_entry(
    hass: HomeAssistant,
    mock_backend: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert config_entry.runtime_data.config.relevance_mode is RelevanceMode.STRICT

    result = await start_options(hass, config_entry)
    result = await options_configure(hass, result, {"next_step_id": "universe"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "universe"
    result = await options_configure(
        hass, result, {CONF_RELEVANCE_MODE: "broad", CONF_MARKET_PRESET: "custom"}
    )
    assert result["step_id"] == "countries"
    result = await options_configure(hass, result, {CONF_MARKET_COUNTRIES: ["SE"]})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_RELEVANCE_MODE] == "broad"
    assert config_entry.options[CONF_MARKET_COUNTRIES] == ["SE"]
    coordinator = config_entry.runtime_data
    assert coordinator.config.relevance_mode is RelevanceMode.BROAD
    assert coordinator.config.market_countries == frozenset({"SE"})


async def test_options_organisation_set_and_clear(
    hass: HomeAssistant, ted: AiohttpClientMocker, mock_setup_entry: AsyncMock
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test-entry",
        unique_id=DOMAIN,
        data={},
        options={CONF_MARKET_PRESET: "nordic", CONF_PINNED_CATEGORIES: ["space"]},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    result = await start_options(hass, entry)
    result = await options_configure(hass, result, {"next_step_id": "organisation"})
    result = await options_configure(hass, result, {CONF_TRACK_ORGANISATION: True})
    assert result["step_id"] == "organisation_search"
    result = await options_configure(
        hass, result, {CONF_OWN_COUNTRY: "SE", CONF_SEARCH: "försvarsmakten"}
    )
    assert result["step_id"] == "organisation_select"
    result = await options_configure(hass, result, {CONF_CANDIDATE: "1"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_OWN_ORGANISATION][CONF_OWN_NAME] == "Försvarsmakten"
    assert entry.options[CONF_PINNED_CATEGORIES] == ["space"]

    result = await start_options(hass, entry)
    result = await options_configure(hass, result, {"next_step_id": "organisation"})
    result = await options_configure(hass, result, {CONF_TRACK_ORGANISATION: False})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_OWN_ORGANISATION not in entry.options
    assert entry.options[CONF_MARKET_PRESET] == "nordic"


async def test_options_peers_categories_and_watchlist(
    hass: HomeAssistant, ted: AiohttpClientMocker, mock_setup_entry: AsyncMock
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id="test-entry", unique_id=DOMAIN, data={}, options={}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    result = await start_options(hass, entry)
    result = await options_configure(hass, result, {"next_step_id": "peers"})
    result = await options_configure(
        hass, result, {CONF_PEER_PRESET: "nordic", CONF_SELECTED_COUNTRY: "FI"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_PEER_PRESET] == "nordic"
    assert entry.options[CONF_SELECTED_COUNTRY] == "FI"

    result = await start_options(hass, entry)
    result = await options_configure(hass, result, {"next_step_id": "categories"})
    result = await options_configure(
        hass, result, {CONF_PINNED_CATEGORIES: ["naval_maritime"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_PINNED_CATEGORIES] == ["naval_maritime"]

    result = await start_options(hass, entry)
    result = await options_configure(hass, result, {"next_step_id": "raw_data"})
    result = await options_configure(hass, result, {CONF_RAW_COUNTRIES: ["SE", "FI"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RAW_COUNTRIES] == ["SE", "FI"]

    result = await start_options(hass, entry)
    result = await options_configure(hass, result, {"next_step_id": "watchlist"})
    result = await options_configure(hass, result, {CONF_WATCHLIST_COUNTRIES: ["DK"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_WATCHLIST_COUNTRIES] == ["DK"]
    assert CONF_WATCHLIST_MIN_ESTIMATED_EUR not in entry.options
    assert entry.options[CONF_PEER_PRESET] == "nordic"

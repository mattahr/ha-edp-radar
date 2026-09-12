from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.edp_radar.api import (
    PaginationMode,
    TedApiClient,
    TedApiError,
    TedApiTemporaryError,
    TedQueryError,
    safe_page_size,
)

from .conftest import TED_SEARCH_URL

FIELDS = ["publication-number", "notice-identifier"]


def test_safe_page_size_counts_the_links_field() -> None:
    assert safe_page_size(57) == 172
    assert safe_page_size(1) == 250
    assert safe_page_size(20000) == 1


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _client(
    hass: HomeAssistant, **kwargs: Any
) -> tuple[TedApiClient, AsyncMock, FakeClock]:
    sleep = AsyncMock()
    clock = FakeClock()

    async def fake_sleep(seconds: float) -> None:
        await sleep(seconds)
        clock.now += seconds

    client = TedApiClient(
        async_get_clientsession(hass), sleep=fake_sleep, clock=clock, **kwargs
    )
    return client, sleep, clock


def _page(numbers: list[str], token: str | None, total: int) -> dict[str, Any]:
    return {
        "notices": [{"publication-number": n, "links": {}} for n in numbers],
        "totalNoticeCount": total,
        "iterationNextToken": token,
        "timedOut": False,
    }


async def test_iteration_mode_follows_tokens_and_stops_on_short_page(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    pages = {None: _page(["1", "2"], "t1", 3), "t1": _page(["3"], "t2", 3)}
    bodies: list[dict[str, Any]] = []

    async def handler(
        method: str, url: Any, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        bodies.append(data)
        return AiohttpClientMockResponse(
            method, url, json=pages[data.get("iterationNextToken")]
        )

    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    client, _sleep, _clock = _client(hass)
    seen: list[tuple[int, int | None]] = []
    numbers = [
        n["publication-number"]
        async for n in client.async_search_notices(
            "PD>=20260101",
            FIELDS,
            page_size=2,
            progress=lambda done, total: seen.append((done, total)),
        )
    ]
    assert numbers == ["1", "2", "3"]
    assert seen == [(2, 3), (3, 3)]
    assert bodies[0]["paginationMode"] == "ITERATION"
    assert bodies[0]["limit"] == 2
    assert bodies[0]["fields"] == FIELDS
    assert "iterationNextToken" not in bodies[0]
    assert bodies[1]["iterationNextToken"] == "t1"
    assert bodies[0]["onlyLatestVersions"] is False


async def test_page_number_mode_increments_pages(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    pages = {1: _page(["1", "2"], None, 3), 2: _page(["3"], None, 3)}

    async def handler(
        method: str, url: Any, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        return AiohttpClientMockResponse(method, url, json=pages[data["page"]])

    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    client, _sleep, _clock = _client(hass)
    numbers = [
        n["publication-number"]
        async for n in client.async_search_notices(
            "PD>=20260101",
            FIELDS,
            pagination_mode=PaginationMode.PAGE_NUMBER,
            page_size=2,
        )
    ]
    assert numbers == ["1", "2", "3"]


async def test_default_page_size_uses_safe_formula(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    captured: list[dict[str, Any]] = []

    async def handler(
        method: str, url: Any, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        captured.append(data)
        return AiohttpClientMockResponse(method, url, json=_page([], None, 0))

    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    client, _sleep, _clock = _client(hass)
    fields = [f"f{i}" for i in range(57)]
    assert [n async for n in client.async_search_notices("q", fields)] == []
    assert captured[0]["limit"] == 172


async def test_requests_are_paced(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    pages = {
        None: _page(["1", "2"], "t1", 4),
        "t1": _page(["3", "4"], "t2", 4),
        "t2": _page([], None, 4),
    }

    async def handler(
        method: str, url: Any, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        return AiohttpClientMockResponse(
            method, url, json=pages[data.get("iterationNextToken")]
        )

    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    client, sleep, _clock = _client(hass, min_interval=0.5)
    fetched = [n async for n in client.async_search_notices("q", FIELDS, page_size=2)]
    assert len(fetched) == 4
    # three requests; the first is immediate, the next two wait the full interval
    assert [round(call.args[0], 3) for call in sleep.await_args_list] == [0.5, 0.5]


async def test_429_then_success_backs_off(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    calls = 0

    async def handler(
        method: str, url: Any, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            return AiohttpClientMockResponse(
                method, url, status=429, text="<html>429</html>"
            )
        return AiohttpClientMockResponse(method, url, json=_page(["1"], None, 1))

    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    client, sleep, _clock = _client(hass, min_interval=0)
    assert await client.async_count_notices("q") == 1
    assert calls == 2
    assert sleep.await_args_list[0].args[0] == 1  # 2 ** 0


async def test_persistent_5xx_raises_temporary_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(TED_SEARCH_URL, status=503, text="down")
    client, sleep, _clock = _client(hass, min_interval=0, max_attempts=3)
    with pytest.raises(TedApiTemporaryError):
        await client.async_count_notices("q")
    assert [call.args[0] for call in sleep.await_args_list] == [1, 2]


async def test_query_error_is_not_retried(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(
        TED_SEARCH_URL,
        status=400,
        json={
            "message": "Syntax error in expert query at line 1, col 21",
            "error": {"type": "QUERY_SYNTAX_ERROR", "location": {"beginColumn": 21}},
        },
    )
    client, sleep, _clock = _client(hass, min_interval=0)
    with pytest.raises(TedQueryError, match="Syntax error"):
        await client.async_validate_query("PD>=20250809 AND (foo")
    assert sleep.await_count == 0
    assert aioclient_mock.mock_calls[-1][2]["checkQuerySyntax"] is True


async def test_other_400_is_generic_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(
        TED_SEARCH_URL,
        status=400,
        json={
            "message": "Value (10150) exceeds",
            "error": {"type": "SEARCH_FIELDS_PER_PAGE_EXCEEDS_MAX_LIMIT"},
        },
    )
    client, _sleep, _clock = _client(hass, min_interval=0)
    with pytest.raises(TedApiError, match="10150") as info:
        await client.async_count_notices("q")
    assert not isinstance(info.value, TedQueryError)


async def test_connection_error_becomes_temporary(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(TED_SEARCH_URL, exc=ClientError("boom"))
    client, _sleep, _clock = _client(hass, min_interval=0, max_attempts=2)
    with pytest.raises(TedApiTemporaryError):
        await client.async_count_notices("q")


async def test_validate_query_ok(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(TED_SEARCH_URL, json={"notices": [], "totalNoticeCount": None})
    client, _sleep, _clock = _client(hass, min_interval=0)
    await client.async_validate_query("PD>=20250809")

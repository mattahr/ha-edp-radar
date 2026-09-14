"""HTTP helper: payload cap, errors, checksums, HEAD metadata (S12, S41)."""

from __future__ import annotations

from datetime import date

import pytest
from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.spending.providers.base import (
    SourceUnavailableError,
    async_fetch_bytes,
    async_head_metadata,
    http_date_to_date,
    sha256_hex,
)

URL = "https://example.org/data.xlsx"


async def test_fetch_returns_payload_headers_and_checksum(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        URL,
        content=b"hello",
        headers={"ETag": '"xyz"', "Last-Modified": "Mon, 27 Apr 2026 15:20:25 GMT"},
    )
    result = await async_fetch_bytes(async_get_clientsession(hass), URL)
    assert result.payload == b"hello"
    assert result.etag == '"xyz"'
    assert result.last_modified == "Mon, 27 Apr 2026 15:20:25 GMT"
    assert result.checksum == sha256_hex(b"hello")
    assert "If-None-Match" not in aioclient_mock.mock_calls[0][3]


async def test_fetch_errors_are_wrapped(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(URL, status=503)
    with pytest.raises(SourceUnavailableError, match="HTTP 503"):
        await async_fetch_bytes(async_get_clientsession(hass), URL)
    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, exc=ClientError("boom"))
    with pytest.raises(SourceUnavailableError, match="boom"):
        await async_fetch_bytes(async_get_clientsession(hass), URL)


async def test_oversized_payload_is_unavailable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from custom_components.edp_radar.spending.providers import base

    monkeypatch.setattr(base, "MAX_PAYLOAD_BYTES", 4)
    aioclient_mock.get(URL, content=b"12345")
    with pytest.raises(SourceUnavailableError, match="larger than 4 bytes"):
        await async_fetch_bytes(async_get_clientsession(hass), URL)
    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, content=b"123", headers={"Content-Length": "999"})
    with pytest.raises(SourceUnavailableError, match="larger than 4 bytes"):
        await async_fetch_bytes(async_get_clientsession(hass), URL)


async def test_head_metadata_tolerates_failures(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.head(URL, headers={"ETag": '"e"', "Last-Modified": "x"})
    assert await async_head_metadata(async_get_clientsession(hass), URL) == ('"e"', "x")
    aioclient_mock.clear_requests()
    aioclient_mock.head(URL, status=405)
    assert await async_head_metadata(async_get_clientsession(hass), URL) == (None, None)


async def test_head_metadata_client_error_returns_nothing(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.head(URL, exc=ClientError("boom"))
    assert await async_head_metadata(async_get_clientsession(hass), URL) == (None, None)


def test_http_date_parsing() -> None:
    assert http_date_to_date("Fri, 10 Jul 2026 09:55:14 GMT") == date(2026, 7, 10)
    assert http_date_to_date("garbage") is None
    assert http_date_to_date(None) is None

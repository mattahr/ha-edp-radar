"""HTTP helper: conditional requests, 304, errors, checksums (S12, plan §87)."""

from __future__ import annotations

from datetime import date

import pytest
from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.spending.models import SourceRelease
from custom_components.edp_radar.spending.providers.base import (
    SourceUnavailableError,
    async_fetch_bytes,
    async_head_metadata,
    http_date_to_date,
    sha256_hex,
)

URL = "https://example.org/data.xlsx"


def _release(**overrides: object) -> SourceRelease:
    base: dict[str, object] = {
        "source_id": "nato",
        "release_id": "2026",
        "published_at": None,
        "download_url": URL,
        "canonical_url": "https://example.org/",
        "format": "xlsx",
        "etag": '"abc"',
        "last_modified": "Fri, 10 Jul 2026 09:55:14 GMT",
    }
    base.update(overrides)
    return SourceRelease(**base)  # type: ignore[arg-type]


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
    assert result.not_modified is False
    assert "If-None-Match" not in aioclient_mock.mock_calls[0][3]


async def test_fetch_sends_conditional_headers_and_handles_304(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(URL, status=304)
    result = await async_fetch_bytes(
        async_get_clientsession(hass), URL, previous=_release()
    )
    assert result.not_modified is True
    assert result.payload == b""
    headers = aioclient_mock.mock_calls[0][3]
    assert headers["If-None-Match"] == '"abc"'
    assert headers["If-Modified-Since"] == "Fri, 10 Jul 2026 09:55:14 GMT"


async def test_conditional_headers_only_for_the_same_url(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(URL, content=b"x")
    await async_fetch_bytes(
        async_get_clientsession(hass),
        URL,
        previous=_release(download_url="https://example.org/other.xlsx"),
    )
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


async def test_head_metadata_tolerates_failures(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.head(URL, headers={"ETag": '"e"', "Last-Modified": "x"})
    assert await async_head_metadata(async_get_clientsession(hass), URL) == ('"e"', "x")
    aioclient_mock.clear_requests()
    aioclient_mock.head(URL, status=405)
    assert await async_head_metadata(async_get_clientsession(hass), URL) == (None, None)


def test_http_date_parsing() -> None:
    assert http_date_to_date("Fri, 10 Jul 2026 09:55:14 GMT") == date(2026, 7, 10)
    assert http_date_to_date("garbage") is None
    assert http_date_to_date(None) is None

"""Shared pytest fixtures."""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from aiohttp import ClientSession
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.edp_radar.api import TedApiClient
from custom_components.edp_radar.const import (
    DOMAIN,
    ECB_90D_URL,
    ECB_HISTORY_URL,
    NAME,
    TED_API_BASE_URL,
)

FIXTURES = Path(__file__).parent / "fixtures"
TED_SEARCH_URL = f"{TED_API_BASE_URL}/notices/search"


@pytest.fixture
def real_notices() -> list[dict[str, Any]]:
    """Real TED notices captured 2026-09-12 (see scripts/fetch_fixture_notices.py)."""
    return json.loads((FIXTURES / "ted" / "real_notices.json").read_text())


@pytest.fixture
def real_notice(
    real_notices: list[dict[str, Any]],
) -> Callable[[str], dict[str, Any]]:
    """Return a lookup by publication number (deep-copied per call)."""
    by_number = {n["publication-number"]: n for n in real_notices}

    def _get(publication_number: str) -> dict[str, Any]:
        return json.loads(json.dumps(by_number[publication_number]))

    return _get


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of custom_components in every test."""


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A config entry with default options (EU market, strict mode, no extras)."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="test-entry",
        title=NAME,
        unique_id=DOMAIN,
        data={},
        options={},
    )


@pytest.fixture
def fast_ted_client() -> Generator[None]:
    """Build TED clients without pacing or backoff sleeps.

    ``freezer`` freezes the event-loop clock, so any real ``asyncio.sleep`` would
    never return; the integration tests therefore never sleep.
    """

    async def no_sleep(_: float) -> None:
        return None

    def build(session: ClientSession, **kwargs: Any) -> TedApiClient:
        kwargs.setdefault("min_interval", 0)
        kwargs.setdefault("sleep", no_sleep)
        return TedApiClient(session, **kwargs)

    with (
        patch("custom_components.edp_radar.TedApiClient", side_effect=build),
        patch(
            "custom_components.edp_radar.config_flow.TedApiClient", side_effect=build
        ),
    ):
        yield


def ecb_history_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "eurofxref-hist.csv", (FIXTURES / "ecb" / "hist.csv").read_text()
        )
    return buffer.getvalue()


@pytest.fixture
def mock_backend(
    aioclient_mock: AiohttpClientMocker,
    real_notices: list[dict[str, Any]],
    fast_ted_client: None,
) -> AiohttpClientMocker:
    """TED answers every search with the 18 real notices; ECB with fixtures."""

    async def handler(
        method: str, url: Any, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        if data.get("checkQuerySyntax"):
            return AiohttpClientMockResponse(
                method, url, json={"notices": [], "totalNoticeCount": None}
            )
        if data.get("iterationNextToken") or data.get("page", 1) > 1:
            return AiohttpClientMockResponse(
                method, url, json={"notices": [], "totalNoticeCount": 18}
            )
        return AiohttpClientMockResponse(
            method,
            url,
            json={
                "notices": real_notices,
                "totalNoticeCount": 18,
                "iterationNextToken": "t",
            },
        )

    aioclient_mock.post(TED_SEARCH_URL, side_effect=handler)
    aioclient_mock.get(
        ECB_90D_URL, text=(FIXTURES / "ecb" / "hist-90d.xml").read_text()
    )
    aioclient_mock.get(ECB_HISTORY_URL, content=ecb_history_zip())
    return aioclient_mock

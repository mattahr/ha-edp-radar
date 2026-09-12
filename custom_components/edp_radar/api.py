"""Async client for the TED Search API (plan §35; addendum §1, D1, D9)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from enum import StrEnum
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import (
    TED_API_BASE_URL,
    TED_MAX_ATTEMPTS,
    TED_MAX_FIELDS_PER_PAGE,
    TED_MAX_PAGE_SIZE,
    TED_MIN_REQUEST_INTERVAL,
    TED_PAGE_NUMBER_CEILING,
)

_LOGGER = logging.getLogger(__name__)
_MAX_BACKOFF_SECONDS = 60


class PaginationMode(StrEnum):
    PAGE_NUMBER = "PAGE_NUMBER"
    ITERATION = "ITERATION"


class TedApiError(Exception):
    """Base error for the TED Search API."""


class TedApiTemporaryError(TedApiError):
    """429, 5xx, timeout or connection problem: retry later (plan §43)."""


class TedQueryError(TedApiError):
    """The expert query was rejected (HTTP 400 with a QUERY_* error type)."""


def safe_page_size(field_count: int) -> int:
    """Largest page size within the 10 000 fields-per-page limit (D1).

    The server counts the always-present ``links`` object as one more field.
    """
    return max(1, min(TED_MAX_PAGE_SIZE, TED_MAX_FIELDS_PER_PAGE // (field_count + 1)))


class TedApiClient:
    """Thin, paced, retrying client around ``POST /v3/notices/search``."""

    def __init__(
        self,
        session: ClientSession,
        *,
        base_url: str = TED_API_BASE_URL,
        min_interval: float = TED_MIN_REQUEST_INTERVAL,
        max_attempts: int = TED_MAX_ATTEMPTS,
        request_timeout: float = 90.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session = session
        self._url = f"{base_url.rstrip('/')}/notices/search"
        self._min_interval = min_interval
        self._max_attempts = max(1, max_attempts)
        self._timeout = request_timeout
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None

    async def async_search_notices(
        self,
        query: str,
        fields: Sequence[str],
        *,
        pagination_mode: PaginationMode = PaginationMode.ITERATION,
        page_size: int | None = None,
        only_latest_versions: bool = False,
        progress: Callable[[int, int | None], None] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield raw notices page by page."""
        limit = page_size or safe_page_size(len(fields))
        base: dict[str, Any] = {
            "query": query,
            "fields": list(fields),
            "limit": limit,
            "scope": "ALL",
            "paginationMode": pagination_mode.value,
            "onlyLatestVersions": only_latest_versions,
        }
        token: str | None = None
        page = 1
        fetched = 0
        while True:
            body = dict(base)
            if pagination_mode is PaginationMode.ITERATION:
                if token:
                    body["iterationNextToken"] = token
            else:
                body["page"] = page
            data = await self._async_post(body)
            notices: list[dict[str, Any]] = data.get("notices") or []
            fetched += len(notices)
            if progress is not None:
                progress(fetched, data.get("totalNoticeCount"))
            for notice in notices:
                yield notice
            if not notices or len(notices) < limit:
                return
            if pagination_mode is PaginationMode.ITERATION:
                token = data.get("iterationNextToken")
                if not token:
                    return
            else:
                page += 1
                if page * limit > TED_PAGE_NUMBER_CEILING:
                    return

    async def async_count_notices(self, query: str) -> int:
        data = await self._async_post(
            {"query": query, "fields": ["publication-number"], "limit": 1}
        )
        return int(data.get("totalNoticeCount") or 0)

    async def async_validate_query(self, query: str) -> None:
        """Raise TedQueryError if TED rejects the expert query syntax."""
        await self._async_post(
            {
                "query": query,
                "fields": ["publication-number"],
                "limit": 1,
                "checkQuerySyntax": True,
            }
        )

    async def _async_pace(self) -> None:
        if self._last_request is not None:
            wait = self._min_interval - (self._clock() - self._last_request)
            if wait > 0:
                await self._sleep(wait)
        self._last_request = self._clock()

    async def _async_post(self, body: dict[str, Any]) -> dict[str, Any]:
        last_error: TedApiError | None = None
        for attempt in range(self._max_attempts):
            if attempt:
                await self._sleep(min(_MAX_BACKOFF_SECONDS, 2 ** (attempt - 1)))
            await self._async_pace()
            try:
                async with asyncio.timeout(self._timeout):
                    response = await self._session.post(
                        self._url, json=body, headers={"Accept": "application/json"}
                    )
                    status = response.status
                    text = await response.text()
            except TimeoutError as err:
                last_error = TedApiTemporaryError("Timeout talking to TED")
                last_error.__cause__ = err
                continue
            except ClientError as err:
                last_error = TedApiTemporaryError(f"Error talking to TED: {err}")
                last_error.__cause__ = err
                continue
            if status == 200:
                try:
                    result: dict[str, Any] = json.loads(text)
                except ValueError as err:
                    raise TedApiError("TED returned invalid JSON") from err
                return result
            if status == 429 or status >= 500:
                _LOGGER.debug("TED returned HTTP %s (attempt %s)", status, attempt + 1)
                last_error = TedApiTemporaryError(f"TED returned HTTP {status}")
                continue
            raise _client_error(status, text)
        assert last_error is not None
        raise last_error


def _client_error(status: int, text: str) -> TedApiError:
    message = text[:300]
    error_type = ""
    try:
        payload = json.loads(text)
        message = str(payload.get("message") or message)
        error_type = str((payload.get("error") or {}).get("type") or "")
    except ValueError:
        pass
    if status == 400 and error_type.startswith("QUERY_"):
        return TedQueryError(message)
    return TedApiError(f"TED returned HTTP {status}: {message}")

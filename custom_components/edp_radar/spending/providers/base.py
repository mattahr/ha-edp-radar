"""Provider contract and shared HTTP helpers (S12; plan §10, §65, §87).

Parsing is synchronous and pure so it can run in an executor and in scripts
without Home Assistant; discovery and fetching take the aiohttp session.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Protocol

from aiohttp import ClientError, ClientSession

from ..models import SourceRelease, SourceSpec, SpendingDataPoint

type Payload = bytes | Mapping[str, bytes]

USER_AGENT = "ha-edp-radar (Home Assistant integration; +https://github.com/mattahr/ha-edp-radar)"
DEFAULT_TIMEOUT = 120.0


class SpendingProviderError(Exception):
    """Base class for provider failures."""


class SourceUnavailableError(SpendingProviderError):
    """HTTP error, timeout or connection problem: try again later."""


class SchemaChangedError(SpendingProviderError):
    """The source layout no longer matches the parser (plan §65)."""


@dataclass(frozen=True, slots=True)
class ParseResult:
    datapoints: tuple[SpendingDataPoint, ...]
    warnings: tuple[str, ...]
    layout_fingerprint: str


@dataclass(frozen=True, slots=True)
class FetchResult:
    payload: bytes
    etag: str | None
    last_modified: str | None
    checksum: str
    not_modified: bool = False


class SpendingProvider(Protocol):
    """What the coordinator needs from every source (plan §10)."""

    spec: SourceSpec

    async def async_discover_latest(self, session: ClientSession) -> SourceRelease: ...

    async def async_fetch_release(
        self, session: ClientSession, release: SourceRelease
    ) -> tuple[SourceRelease, Payload]: ...

    def parse_release(
        self, payload: Payload, release: SourceRelease
    ) -> ParseResult: ...


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def http_date_to_date(value: str | None) -> date | None:
    """``Last-Modified`` header → date, ``None`` when absent or unparsable."""
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date()
    except TypeError, ValueError:
        return None


def _conditional_headers(url: str, previous: SourceRelease | None) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if previous is None or previous.download_url != url:
        return headers
    if previous.etag:
        headers["If-None-Match"] = previous.etag
    if previous.last_modified:
        headers["If-Modified-Since"] = previous.last_modified
    return headers


async def async_fetch_bytes(
    session: ClientSession,
    url: str,
    *,
    previous: SourceRelease | None = None,
    request_timeout: float = DEFAULT_TIMEOUT,
) -> FetchResult:
    """GET ``url``; conditional when ``previous`` has validators for the same URL."""
    try:
        async with asyncio.timeout(request_timeout):
            response = await session.get(
                url, headers=_conditional_headers(url, previous), allow_redirects=True
            )
            if response.status == 304:
                return FetchResult(
                    payload=b"",
                    etag=previous.etag if previous else None,
                    last_modified=previous.last_modified if previous else None,
                    checksum=(previous.checksum or "") if previous else "",
                    not_modified=True,
                )
            if response.status != 200:
                raise SourceUnavailableError(f"HTTP {response.status} for {url}")
            payload = await response.read()
    except TimeoutError as err:
        raise SourceUnavailableError(f"Timeout fetching {url}") from err
    except ClientError as err:
        raise SourceUnavailableError(f"Error fetching {url}: {err}") from err
    return FetchResult(
        payload=payload,
        etag=response.headers.get("ETag"),
        last_modified=response.headers.get("Last-Modified"),
        checksum=sha256_hex(payload),
    )


async def async_head_metadata(
    session: ClientSession, url: str, *, request_timeout: float = 30.0
) -> tuple[str | None, str | None]:
    """``(ETag, Last-Modified)`` from a HEAD request.

    Returns ``(None, None)`` on any failure.
    """
    try:
        async with asyncio.timeout(request_timeout):
            response = await session.head(
                url, headers={"User-Agent": USER_AGENT}, allow_redirects=True
            )
            if response.status != 200:
                return (None, None)
            return (response.headers.get("ETag"), response.headers.get("Last-Modified"))
    except TimeoutError, ClientError:
        return (None, None)

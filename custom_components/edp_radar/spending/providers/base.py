"""Provider contract and shared HTTP helpers (S12; plan §10, §65, §87).

Parsing is synchronous and pure so it can run in an executor and in scripts
without Home Assistant; discovery and fetching take the aiohttp session.
Discovery decides whether a download is needed; the fetch helper only caps
size and wraps errors.
"""

from __future__ import annotations

import asyncio
import dataclasses
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

# Largest response (and zip member) a provider accepts; the biggest real
# source is the 10 MB Statskontoret CSV.
MAX_PAYLOAD_BYTES = 50 * 1024 * 1024


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


def _declared_length(header: str | None) -> int | None:
    try:
        return None if header is None else int(header)
    except ValueError:
        return None


async def async_fetch_bytes(
    session: ClientSession,
    url: str,
    *,
    request_timeout: float = DEFAULT_TIMEOUT,
) -> FetchResult:
    """GET ``url``; re-download avoidance lives in discovery (S14, S41)."""
    try:
        async with asyncio.timeout(request_timeout):
            async with session.get(
                url, headers={"User-Agent": USER_AGENT}, allow_redirects=True
            ) as response:
                if response.status != 200:
                    raise SourceUnavailableError(f"HTTP {response.status} for {url}")
                declared = _declared_length(response.headers.get("Content-Length"))
                if declared is not None and declared > MAX_PAYLOAD_BYTES:
                    raise SourceUnavailableError(
                        f"{url} is larger than {MAX_PAYLOAD_BYTES} bytes ({declared})"
                    )
                payload = await response.read()
                if len(payload) > MAX_PAYLOAD_BYTES:
                    raise SourceUnavailableError(
                        f"{url} is larger than {MAX_PAYLOAD_BYTES} bytes "
                        f"({len(payload)})"
                    )
                return FetchResult(
                    payload=payload,
                    etag=response.headers.get("ETag"),
                    last_modified=response.headers.get("Last-Modified"),
                    checksum=sha256_hex(payload),
                )
    except TimeoutError as err:
        raise SourceUnavailableError(f"Timeout fetching {url}") from err
    except ClientError as err:
        raise SourceUnavailableError(f"Error fetching {url}: {err}") from err


def with_fetch_metadata(release: SourceRelease, fetched: FetchResult) -> SourceRelease:
    """Copy of ``release`` carrying the validators and checksum of ``fetched``."""
    return dataclasses.replace(
        release,
        etag=fetched.etag,
        last_modified=fetched.last_modified,
        checksum=fetched.checksum,
    )


async def async_head_metadata(
    session: ClientSession, url: str, *, request_timeout: float = 30.0
) -> tuple[str | None, str | None]:
    """``(ETag, Last-Modified)`` from a HEAD request.

    Returns ``(None, None)`` on any failure.
    """
    try:
        async with asyncio.timeout(request_timeout):
            async with session.head(
                url, headers={"User-Agent": USER_AGENT}, allow_redirects=True
            ) as response:
                if response.status != 200:
                    return (None, None)
                return (
                    response.headers.get("ETag"),
                    response.headers.get("Last-Modified"),
                )
    except TimeoutError, ClientError:
        return (None, None)

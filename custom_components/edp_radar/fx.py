"""Async client for ECB euro reference rates (plan §35, D11)."""

from __future__ import annotations

import asyncio
import zipfile
from xml.etree import ElementTree

from aiohttp import ClientError, ClientSession

from .const import ECB_90D_URL, ECB_DAILY_URL, ECB_HISTORY_URL
from .fx_rates import RateTable, parse_ecb_history_zip, parse_ecb_xml


class EcbFxError(Exception):
    """ECB data could not be fetched or parsed."""


class EcbFxClient:
    def __init__(
        self, session: ClientSession, *, request_timeout: float = 60.0
    ) -> None:
        self._session = session
        self._timeout = request_timeout

    async def async_fetch_recent(self) -> RateTable:
        """Last ~90 days of rates (idempotent gap filler for each refresh)."""
        return self._parse_xml(await self._async_get(ECB_90D_URL))

    async def async_fetch_daily(self) -> RateTable:
        return self._parse_xml(await self._async_get(ECB_DAILY_URL))

    async def async_fetch_history(self) -> RateTable:
        """Full history zip (bootstrap only); parsed off the event loop."""
        data = await self._async_get(ECB_HISTORY_URL)
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, parse_ecb_history_zip, data)
        except (
            zipfile.BadZipFile,
            StopIteration,
            UnicodeDecodeError,
            ValueError,
        ) as err:
            raise EcbFxError(f"ECB history archive is invalid: {err}") from err

    async def _async_get(self, url: str) -> bytes:
        try:
            async with asyncio.timeout(self._timeout):
                response = await self._session.get(url)
                if response.status != 200:
                    raise EcbFxError(f"ECB returned HTTP {response.status} for {url}")
                return await response.read()
        except TimeoutError as err:
            raise EcbFxError(f"Timeout fetching {url}") from err
        except ClientError as err:
            raise EcbFxError(f"Error fetching {url}: {err}") from err

    @staticmethod
    def _parse_xml(data: bytes) -> RateTable:
        try:
            return parse_ecb_xml(data.decode("utf-8"))
        except (ElementTree.ParseError, UnicodeDecodeError, ValueError) as err:
            raise EcbFxError(f"ECB XML is invalid: {err}") from err

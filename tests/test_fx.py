import io
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.const import (
    ECB_90D_URL,
    ECB_DAILY_URL,
    ECB_HISTORY_URL,
)
from custom_components.edp_radar.fx import EcbFxClient, EcbFxError

ECB = Path(__file__).parent / "fixtures" / "ecb"


async def test_fetch_recent_and_daily(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(ECB_90D_URL, text=(ECB / "hist-90d.xml").read_text())
    aioclient_mock.get(ECB_DAILY_URL, text=(ECB / "daily.xml").read_text())
    client = EcbFxClient(async_get_clientsession(hass))
    recent = await client.async_fetch_recent()
    assert recent[date(2026, 9, 10)]["SEK"] == Decimal("11.1995")
    daily = await client.async_fetch_daily()
    assert list(daily) == [date(2026, 9, 11)]


async def test_fetch_history_zip(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("eurofxref-hist.csv", (ECB / "hist.csv").read_text())
    aioclient_mock.get(ECB_HISTORY_URL, content=buffer.getvalue())
    history = await EcbFxClient(async_get_clientsession(hass)).async_fetch_history()
    assert len(history) == 3


async def test_errors_are_wrapped(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(ECB_90D_URL, status=503)
    aioclient_mock.get(ECB_DAILY_URL, exc=ClientError("boom"))
    aioclient_mock.get(ECB_HISTORY_URL, text="not a zip")
    client = EcbFxClient(async_get_clientsession(hass))
    with pytest.raises(EcbFxError):
        await client.async_fetch_recent()
    with pytest.raises(EcbFxError):
        await client.async_fetch_daily()
    with pytest.raises(EcbFxError):
        await client.async_fetch_history()


async def test_invalid_xml_is_wrapped(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(ECB_DAILY_URL, text="<not xml")
    with pytest.raises(EcbFxError):
        await EcbFxClient(async_get_clientsession(hass)).async_fetch_daily()

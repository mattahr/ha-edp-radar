"""EDA discovery and multi-workbook parsing (S11; plan §34–§39, §84)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.spending.models import DatapointStatus, SourceRelease
from custom_components.edp_radar.spending.providers.base import SchemaChangedError
from custom_components.edp_radar.spending.providers.eda import (
    MIN_YEAR,
    PORTAL_URL,
    EdaProvider,
    discover_workbooks,
    parse_eda_workbooks,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spending" / "eda"
URL_2025 = "https://eda.europa.eu/docs/default-source/documents/defence-data/final-defence-data-2025-1.xlsx"
URL_2022 = "https://eda.europa.eu/docs/default-source/documents/defence-data/eda-2022-defence-data.xlsx"


def _release() -> SourceRelease:
    return SourceRelease(
        "eda", "2025:test", date(2026, 9, 4), URL_2025, PORTAL_URL, "xlsx"
    )


def _payload() -> dict[str, bytes]:
    return {
        "2025": (FIXTURES / "defence-data-2025.xlsx").read_bytes(),
        "2022": (FIXTURES / "defence-data-2022.xlsx").read_bytes(),
    }


def test_discover_lists_workbooks_by_year() -> None:
    links = discover_workbooks(
        (FIXTURES / "portal.html").read_text(encoding="utf-8"), PORTAL_URL
    )
    assert sorted(links) == [2020, 2021, 2022, 2023, 2024, 2025]
    assert links[2025] == URL_2025
    assert links[2022] == URL_2022
    assert MIN_YEAR == 2022
    with pytest.raises(SchemaChangedError, match="Defence Data"):
        discover_workbooks("<html></html>", PORTAL_URL)


def test_member_states_sheets_and_estimates() -> None:
    result = parse_eda_workbooks(_payload(), _release())
    points = {
        (p.metric_id, p.country, p.reference.start.year): p for p in result.datapoints
    }
    se = points[("defence_expenditure", "SE", 2025)]
    assert se.value == Decimal("14788.962566848055")
    assert se.status is DatapointStatus.ACTUAL
    assert se.unit == "EUR_MILLION"
    assert points[("defence_investment", "SE", 2025)].value == Decimal(
        "4227.901618627983"
    )
    assert (
        points[("defence_expenditure_pct_gdp", "SE", 2025)].value
        == Decimal("0.024880146027005542") * 100
    )
    assert (
        points[("defence_expenditure_pct_government", "SE", 2025)].value
        == Decimal("0.05697066959157698") * 100
    )
    assert points[("defence_expenditure_per_capita", "SE", 2025)].value == Decimal(
        "1386.9598218459764"
    )
    assert (
        points[("defence_expenditure", "DK", 2025)].status is DatapointStatus.ESTIMATE
    )
    assert points[("defence_expenditure", "LU", 2025)].flags == ("note_2",)
    assert points[("defence_expenditure", "SI", 2025)].flags == ("note_3",)
    assert points[("defence_expenditure", "HR", 2025)].country == "HR"
    assert points[("defence_expenditure", "SE", 2022)].value == Decimal("7872")
    assert points[("defence_expenditure", "DK", 2022)].status is DatapointStatus.ACTUAL
    assert (
        len({p.country for p in result.datapoints if p.reference.start.year == 2025})
        == 27
    )


def test_billions_history_from_newest_workbook_only() -> None:
    result = parse_eda_workbooks(_payload(), _release())
    points = {
        (p.metric_id, p.country, p.reference.start.year): p for p in result.datapoints
    }
    assert points[("equipment_procurement", "SE", 2021)].value == Decimal("1500")
    assert points[("equipment_procurement", "SE", 2020)].value == Decimal("1454.37")
    assert points[("defence_rnd", "SE", 2021)].value == Decimal("88.2")
    assert points[("defence_expenditure", "SE", 2005)].value == Decimal("4433.18031115")
    assert points[("defence_expenditure", "SE", 2021)].flags == ("sheet:billions",)
    assert ("equipment_procurement", "SE", 2025) not in points
    assert ("defence_expenditure", "DK", 2021) not in points
    assert (
        len(
            {
                p.country
                for p in result.datapoints
                if p.metric_id == "equipment_procurement"
            }
        )
        == 26
    )
    assert result.warnings == ()
    assert "member states 2025" in result.layout_fingerprint.casefold()


def test_missing_sheet_or_column_fails() -> None:
    payload = _payload()
    with pytest.raises(SchemaChangedError):
        parse_eda_workbooks({"2025": b"not a workbook"}, _release())
    import io

    from openpyxl import Workbook

    book = Workbook()
    book.active.title = "Member States 2030"
    book.active.append(["EU MS", "Year", "Total Defence Expenditure"])
    book.create_sheet("Billions").append(["PMS", "Year"])
    buffer = io.BytesIO()
    book.save(buffer)
    with pytest.raises(SchemaChangedError, match="Defence Investment"):
        parse_eda_workbooks(
            {"2030": buffer.getvalue()},
            SourceRelease("eda", "2030:test", None, URL_2025, PORTAL_URL, "xlsx"),
        )
    del payload["2025"]
    with pytest.raises(SchemaChangedError, match="newest"):
        parse_eda_workbooks(
            payload, SourceRelease("eda", "2025:x", None, URL_2025, PORTAL_URL, "xlsx")
        )


async def test_provider_discovers_and_fetches_every_recent_workbook(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        PORTAL_URL, text=(FIXTURES / "portal.html").read_text(encoding="utf-8")
    )
    links = discover_workbooks(
        (FIXTURES / "portal.html").read_text(encoding="utf-8"), PORTAL_URL
    )
    for year, url in links.items():
        aioclient_mock.head(
            url,
            headers={"Last-Modified": f"Fri, 04 Sep 2026 10:13:{year % 60:02d} GMT"},
        )
        fixture = FIXTURES / f"defence-data-{year}.xlsx"
        aioclient_mock.get(
            url,
            content=fixture.read_bytes()
            if fixture.exists()
            else (FIXTURES / "defence-data-2022.xlsx").read_bytes(),
        )
    provider = EdaProvider()
    session = async_get_clientsession(hass)
    release = await provider.async_discover_latest(session)
    assert release.release_id.startswith("2025:")
    assert release.published_at == date(2026, 9, 4)
    assert release.download_url == URL_2025
    fetched, payload = await provider.async_fetch_release(session, release)
    assert isinstance(payload, dict) and sorted(payload) == [
        "2022",
        "2023",
        "2024",
        "2025",
    ]
    assert fetched.checksum
    result = provider.parse_release(payload, fetched)
    assert any(p.reference.start.year == 2025 for p in result.datapoints)

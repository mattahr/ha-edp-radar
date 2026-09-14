"""Register every spending source on the aiohttp mocker using the real fixtures."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.edp_radar.spending.providers.eda import (
    PORTAL_URL,
    discover_workbooks,
)
from custom_components.edp_radar.spending.providers.eurostat import API_URL
from custom_components.edp_radar.spending.providers.nato import (
    TOPIC_URL,
    discover_workbook,
)
from custom_components.edp_radar.spending.providers.sipri import (
    LANDING_URL,
    discover_release,
)
from custom_components.edp_radar.spending.providers.statskontoret import (
    DISCOVERY_URL,
    parse_discovery_page,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spending"


def mock_spending_sources(
    aioclient_mock: AiohttpClientMocker, *, today: date | None = None
) -> None:
    today = today or date.today()
    page = (FIXTURES / "statskontoret" / "discovery-2026.html").read_text(
        encoding="utf-8"
    )
    page_2025 = (FIXTURES / "statskontoret" / "discovery-2025.html").read_text(
        encoding="utf-8"
    )
    aioclient_mock.get(f"{DISCOVERY_URL}?year=2025", text=page_2025)
    for year in {today.year, today.year - 1, 2026} - {2025}:
        aioclient_mock.get(f"{DISCOVERY_URL}?year={year}", text=page)
    csv = (FIXTURES / "statskontoret" / "utgifter-2026-07.csv").read_bytes()
    for release in parse_discovery_page(page, f"{DISCOVERY_URL}?year=2026"):
        aioclient_mock.get(release.csv_url, content=csv)

    aioclient_mock.get(
        API_URL, content=(FIXTURES / "eurostat" / "gov_ev-defence.json").read_bytes()
    )

    topic = (FIXTURES / "nato" / "topic-page.html").read_text(encoding="utf-8")
    aioclient_mock.get(TOPIC_URL, text=topic)
    _year, nato_xlsx = discover_workbook(topic, TOPIC_URL)
    aioclient_mock.head(
        nato_xlsx,
        headers={"ETag": '"nato"', "Last-Modified": "Fri, 10 Jul 2026 09:55:14 GMT"},
    )
    aioclient_mock.get(
        nato_xlsx, content=(FIXTURES / "nato" / "def-exp-2026-en.xlsx").read_bytes()
    )

    portal = (FIXTURES / "eda" / "portal.html").read_text(encoding="utf-8")
    aioclient_mock.get(PORTAL_URL, text=portal)
    for year, url in discover_workbooks(portal, PORTAL_URL).items():
        aioclient_mock.head(
            url, headers={"Last-Modified": "Fri, 04 Sep 2026 10:13:18 GMT"}
        )
        name = f"defence-data-{min(max(year, 2022), 2025)}.xlsx"
        aioclient_mock.get(url, content=(FIXTURES / "eda" / name).read_bytes())

    landing = (FIXTURES / "sipri" / "landing.html").read_text(encoding="utf-8")
    aioclient_mock.get(LANDING_URL, text=landing)
    sipri_xlsx, _revised = discover_release(landing, LANDING_URL)
    aioclient_mock.head(sipri_xlsx, headers={"ETag": '"sipri"'})
    aioclient_mock.get(
        sipri_xlsx, content=(FIXTURES / "sipri" / "milex-trimmed.xlsx").read_bytes()
    )

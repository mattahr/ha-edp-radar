"""Statskontoret discovery and CSV parsing against real trimmed fixtures (S9)."""

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

from custom_components.edp_radar.spending.models import DatapointStatus
from custom_components.edp_radar.spending.providers.base import SchemaChangedError
from custom_components.edp_radar.spending.providers.statskontoret import (
    DISCOVERY_URL,
    MATERIEL_APPROPRIATION,
    StatskontoretProvider,
    parse_discovery_page,
    parse_outturn_csv,
    release_from,
    select_latest,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spending" / "statskontoret"
PAGE_2026 = f"{DISCOVERY_URL}?year=2026"
PAGE_2025 = f"{DISCOVERY_URL}?year=2025"


def _page(year: int) -> str:
    return (FIXTURES / f"discovery-{year}.html").read_text(encoding="utf-8")


def _csv(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_discovery_lists_expenditure_releases_newest_last() -> None:
    releases = parse_discovery_page(_page(2026), PAGE_2026)
    assert [(r.year, r.month) for r in releases] == [(2026, m) for m in range(1, 8)]
    latest = select_latest(releases)
    assert (latest.year, latest.month, latest.status_raw) == (2026, 7, "Definitiv")
    assert latest.updated == date(2026, 8, 24)
    assert latest.csv_url.startswith(
        "https://www.statskontoret.se/OpenDataManadsUtfallPage/GetFile?"
    )
    assert "fileType=Zip" in latest.csv_url and "month=7" in latest.csv_url


def test_december_definitive_wins_over_preliminary() -> None:
    releases = parse_discovery_page(_page(2025), PAGE_2025)
    december = [r for r in releases if r.month == 12]
    assert sorted(r.status_raw for r in december) == ["Definitiv", "Preliminär 1"]
    latest = select_latest(releases)
    assert latest.status_raw == "Definitiv"
    assert latest.updated == date(2026, 3, 24)
    release = release_from(latest, PAGE_2025)
    assert release.release_id == "2025-12-definitiv-2026-03-24"
    assert release.published_at == date(2026, 3, 24)
    assert release.format == "csv"
    prelim = release_from(
        next(r for r in december if r.status_raw != "Definitiv"), PAGE_2025
    )
    assert prelim.release_id == "2025-12-preliminar-2026-01-28"


def test_parse_july_2026_file() -> None:
    release = release_from(
        select_latest(parse_discovery_page(_page(2026), PAGE_2026)), PAGE_2026
    )
    result = parse_outturn_csv(_csv("utgifter-2026-07.csv"), release)
    points = {
        (p.metric_id, p.reference.start.year, p.reference.start.month): p
        for p in result.datapoints
    }
    assert points[("materiel_outturn", 2026, 7)].value == Decimal("3753.54717975")
    assert points[("uo6_defence_outturn", 2026, 1)].value == Decimal("6676.43315691")
    assert points[("uo6_total_outturn", 2026, 7)].value == Decimal("11050.09591378")
    assert points[("materiel_outturn", 2025, 12)].value == Decimal("23327.02469578")
    assert ("materiel_outturn", 2026, 8) not in points
    assert {p.status for p in result.datapoints} == {DatapointStatus.ACTUAL}
    assert {p.country for p in result.datapoints} == {"SE"}
    assert {p.unit for p in result.datapoints} == {"SEK_MILLION"}
    assert points[("materiel_outturn", 2026, 7)].reference.label == "Jul 2026"
    assert points[("materiel_outturn", 2026, 7)].release_id == release.release_id
    assert points[("materiel_outturn", 2026, 7)].published_at == date(2026, 8, 24)
    assert result.layout_fingerprint.startswith(
        "Utgiftsområde;Utgiftsområdesnamn;Anslag"
    )
    assert result.warnings == ()
    assert len(result.datapoints) == 3 * (12 + 7)


def test_preliminary_december_marks_only_december() -> None:
    releases = parse_discovery_page(_page(2025), PAGE_2025)
    prelim = release_from(
        next(r for r in releases if r.month == 12 and r.status_raw != "Definitiv"),
        PAGE_2025,
    )
    result = parse_outturn_csv(_csv("utgifter-2025-12-preliminar.csv"), prelim)
    by_month = {(p.metric_id, p.reference.start.month): p for p in result.datapoints}
    assert by_month[("materiel_outturn", 12)].value == Decimal("19729.43332150")
    assert by_month[("materiel_outturn", 12)].status is DatapointStatus.PRELIMINARY
    assert by_month[("materiel_outturn", 11)].status is DatapointStatus.ACTUAL
    definitive = release_from(select_latest(releases), PAGE_2025)
    final = parse_outturn_csv(_csv("utgifter-2025-12-definitiv.csv"), definitive)
    dec = next(
        p
        for p in final.datapoints
        if p.metric_id == "materiel_outturn" and p.reference.start.month == 12
    )
    assert dec.value == Decimal("23327.02469578")
    assert dec.status is DatapointStatus.ACTUAL
    assert dec.key == by_month[("materiel_outturn", 12)].key


def test_schema_changes_fail_loudly() -> None:
    release = release_from(
        select_latest(parse_discovery_page(_page(2026), PAGE_2026)), PAGE_2026
    )
    text = _csv("utgifter-2026-07.csv").decode("utf-8-sig")
    renamed = text.replace("Anslag;", "Anslagskod;", 1).encode("utf-8")
    with pytest.raises(SchemaChangedError, match="Anslag"):
        parse_outturn_csv(renamed, release)
    header_only = text.splitlines()[0].encode("utf-8")
    with pytest.raises(SchemaChangedError, match="utgiftsområde 06"):
        parse_outturn_csv(header_only, release)
    assert MATERIEL_APPROPRIATION == "0601003"


async def test_provider_discovers_and_fetches(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(PAGE_2026, text=_page(2026))
    provider = StatskontoretProvider(today=lambda: date(2026, 9, 12))
    session = async_get_clientsession(hass)
    release = await provider.async_discover_latest(session)
    assert release.release_id == "2026-07-definitiv-2026-08-24"
    aioclient_mock.get(release.download_url, content=_csv("utgifter-2026-07.csv"))
    fetched, payload = await provider.async_fetch_release(session, release)
    assert fetched.checksum is not None
    assert isinstance(payload, bytes)
    result = provider.parse_release(payload, fetched)
    assert len(result.datapoints) == 57


async def test_provider_falls_back_to_previous_year_in_january(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        f"{DISCOVERY_URL}?year=2027", text="<html><body><ul></ul></body></html>"
    )
    aioclient_mock.get(f"{DISCOVERY_URL}?year=2026", text=_page(2026))
    provider = StatskontoretProvider(today=lambda: date(2027, 1, 5))
    release = await provider.async_discover_latest(async_get_clientsession(hass))
    assert release.release_id == "2026-07-definitiv-2026-08-24"
    assert release.canonical_url == f"{DISCOVERY_URL}?year=2026"

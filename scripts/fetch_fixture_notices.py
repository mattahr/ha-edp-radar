"""Re-fetch the real TED notices used as test fixtures.

Usage: uv run python scripts/fetch_fixture_notices.py
Writes tests/fixtures/ted/real_notices.json. Long multilingual text is trimmed and
multi-buyer arrays are cut to 12 entries to keep the file small; nothing personal
is requested (organisation names and public identifiers only).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiohttp

from custom_components.edp_radar.api import TedApiClient
from custom_components.edp_radar.normalizer import REQUESTED_FIELDS
from custom_components.edp_radar.query import TedQueryBuilder as Q

PUBLICATION_NUMBERS = [
    "626028-2026",
    "626977-2026",
    "626146-2026",
    "626585-2026",
    "626359-2026",
    "626569-2026",
    "628113-2026",
    "626136-2026",
    "627236-2026",
    "627671-2026",
    "628418-2026",
    "627391-2026",
    "626308-2026",
    "619411-2026",
    "626862-2026",
    "613361-2026",
    "626208-2026",
    "627092-2026",
]
OUT = Path("tests/fixtures/ted/real_notices.json")
MULTI_BUYER_FIELDS = (
    "buyer-identifier",
    "buyer-country",
    "buyer-legal-type",
    "authority-main-activity",
)


def _trim(notice: dict[str, Any]) -> dict[str, Any]:
    notice["links"] = {"xml": {"MUL": notice["links"]["xml"]["MUL"]}}
    if notice.get("description-proc"):
        notice["description-proc"] = {
            k: (v[:200] + "…" if len(v) > 200 else v)
            for k, v in notice["description-proc"].items()
        }
    names = notice.get("buyer-name") or {}
    if any(len(v) > 12 for v in names.values()):
        notice["buyer-name"] = {k: v[:12] for k, v in names.items()}
        for field in MULTI_BUYER_FIELDS:
            if isinstance(notice.get(field), list):
                notice[field] = notice[field][:12]
    return notice


async def fetch() -> list[dict[str, Any]]:
    async with aiohttp.ClientSession() as session:
        client = TedApiClient(session)
        notices = []
        for number in PUBLICATION_NUMBERS:
            async for raw in client.async_search_notices(
                Q.publication_number(number), REQUESTED_FIELDS
            ):
                notices.append(_trim(raw))
    return notices


def main() -> None:
    notices = asyncio.run(fetch())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(notices, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(notices)} notices to {OUT}")


if __name__ == "__main__":
    main()

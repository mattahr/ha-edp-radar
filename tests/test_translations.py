"""Tests that the translation files are complete and consistent."""

import json
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import async_get_translations

from custom_components.edp_radar.const import DOMAIN
from custom_components.edp_radar.taxonomy import Taxonomy

PACKAGE = Path(__file__).parent.parent / "custom_components" / "edp_radar"
TRANSLATIONS = PACKAGE / "translations"


def _keys(obj: object, prefix: str = "") -> set[str]:
    if not isinstance(obj, dict):
        return {prefix}
    return {
        key for name, value in obj.items() for key in _keys(value, f"{prefix}.{name}")
    }


def _load(name: str) -> dict:
    return json.loads((TRANSLATIONS / name).read_text(encoding="utf-8"))


def test_strings_and_english_translation_are_identical() -> None:
    strings = json.loads((PACKAGE / "strings.json").read_text(encoding="utf-8"))
    assert strings == _load("en.json")


def test_swedish_and_english_have_the_same_keys() -> None:
    assert _keys(_load("en.json")) == _keys(_load("sv.json"))


def test_every_category_has_a_selector_label() -> None:
    en = _load("en.json")
    assert set(en["selector"]["category"]["options"]) == set(
        Taxonomy.load().category_ids
    )


async def test_swedish_entity_names_are_loaded(hass: HomeAssistant) -> None:
    translations = await async_get_translations(hass, "sv", "entity", {DOMAIN})
    assert (
        translations[
            f"component.{DOMAIN}.entity.sensor.market_new_competitions_30d.name"
        ]
        == "Nya upphandlingar 30 d"
    )
    assert (
        translations[
            f"component.{DOMAIN}.entity.sensor.largest_external_competition_7d.name"
        ]
        == "Största upphandling 7 d"
    )
    assert (
        translations[f"component.{DOMAIN}.entity.event.procurement_activity.name"]
        == "Upphandlingsaktivitet"
    )

"""UI configuration: a step-wise config flow and a menu-based options flow.

Plan §27–28 and addendum D2, D17, D23. Every user-tunable value lives in
``ConfigEntry.options``; the update listener in ``__init__`` reloads the entry
when the options flow finishes.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryBaseFlow,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    CountrySelector,
    CountrySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import dt as dt_util

from .api import TedApiClient, TedApiError, TedQueryError
from .config import PEER_PRESET_CUSTOM, PEER_PRESET_NONE, PEER_PRESETS, RadarConfig
from .const import (
    ALPHA2_TO_ALPHA3,
    CENTRAL_PURCHASING_BUYER_THRESHOLD,
    CONF_MARKET_COUNTRIES,
    CONF_MARKET_PRESET,
    CONF_OWN_ALIASES,
    CONF_OWN_COUNTRY,
    CONF_OWN_IDENTIFIERS,
    CONF_OWN_NAME,
    CONF_OWN_ORGANISATION,
    CONF_PEER_COUNTRIES,
    CONF_PEER_PRESET,
    CONF_PINNED_CATEGORIES,
    CONF_RELEVANCE_MODE,
    CONF_SELECTED_COUNTRY,
    CONF_WATCHLIST_COUNTRIES,
    CONF_WATCHLIST_MIN_AWARD_EUR,
    CONF_WATCHLIST_MIN_ESTIMATED_EUR,
    DEFAULT_BOOTSTRAP_DAYS,
    DOMAIN,
    NAME,
    MarketPreset,
    RelevanceMode,
    to_alpha2,
)
from .models import normalize_name
from .normalizer import as_strings
from .query import TedQueryBuilder
from .taxonomy import Taxonomy

_LOGGER = logging.getLogger(__name__)

# Flow-only keys (never stored in options).
CONF_TRACK_ORGANISATION = "track_organisation"
CONF_SEARCH = "search"
CONF_CANDIDATE = "candidate"

BUYER_SEARCH_FIELDS = ("buyer-name", "buyer-identifier", "buyer-country")
BUYER_SEARCH_LIMIT = 500
MAX_CANDIDATES = 25

UNIVERSE_KEYS = (CONF_RELEVANCE_MODE, CONF_MARKET_PRESET, CONF_MARKET_COUNTRIES)
PEER_KEYS = (CONF_PEER_PRESET, CONF_PEER_COUNTRIES, CONF_SELECTED_COUNTRY)
WATCHLIST_KEYS = (
    CONF_WATCHLIST_COUNTRIES,
    CONF_WATCHLIST_MIN_ESTIMATED_EUR,
    CONF_WATCHLIST_MIN_AWARD_EUR,
)


# --------------------------------------------------------------------- buyers


@dataclass(frozen=True)
class BuyerCandidate:
    """One public buyer found in TED, grouped by its stable identifiers (D17)."""

    identifiers: tuple[str, ...]
    country: str | None
    names: tuple[str, ...]
    notices: int

    @property
    def label(self) -> str:
        name = self.names[0] if self.names else "?"
        if not self.identifiers:
            return name
        return f"{name} · {', '.join(self.identifiers)}"

    def as_options(self) -> dict[str, Any]:
        return {
            CONF_OWN_IDENTIFIERS: list(self.identifiers),
            CONF_OWN_COUNTRY: self.country,
            CONF_OWN_NAME: self.names[0] if self.names else None,
            CONF_OWN_ALIASES: list(self.names[1:]),
        }


def _buyer_names(raw: Mapping[str, Any]) -> tuple[str, ...]:
    value = raw.get("buyer-name")
    names: dict[str, None] = {}
    if isinstance(value, Mapping):
        for entry in value.values():
            for name in as_strings(entry):
                if name:
                    names.setdefault(name, None)
    else:
        for name in as_strings(value):
            if name:
                names.setdefault(name, None)
    return tuple(names)


def group_buyer_candidates(
    raws: Iterable[Mapping[str, Any]],
) -> list[BuyerCandidate]:
    """Group raw hits by identifier tuple (else country + name), busiest first.

    Notices listing more buyers than the central-purchasing threshold are
    skipped: they cannot identify a single organisation (D5).
    """
    groups: dict[
        tuple[str, ...], tuple[tuple[str, ...], str | None, dict[str, None], list[int]]
    ] = {}
    for raw in raws:
        identifiers = tuple(i for i in as_strings(raw.get("buyer-identifier")) if i)
        names = _buyer_names(raw)
        if max(len(identifiers), len(names)) > CENTRAL_PURCHASING_BUYER_THRESHOLD:
            continue
        countries = as_strings(raw.get("buyer-country"))
        country = to_alpha2(countries[0]) if countries else None
        if identifiers:
            key = ("id", *identifiers)
        elif names:
            key = ("name", country or "", normalize_name(names[0]))
        else:
            continue
        group = groups.setdefault(key, (identifiers, country, {}, [0]))
        for name in names:
            group[2].setdefault(name, None)
        group[3][0] += 1
    candidates = [
        BuyerCandidate(identifiers, country, tuple(names), count[0])
        for identifiers, country, names, count in groups.values()
    ]
    candidates.sort(key=lambda c: (-c.notices, c.names[0] if c.names else ""))
    return candidates


async def async_find_buyers(
    client: TedApiClient, country: str, term: str
) -> list[BuyerCandidate]:
    """Search TED for buyers by country and name over the retention window (D23)."""
    name_filter = TedQueryBuilder.buyer_name_search(term)
    if not name_filter:
        return []
    since = dt_util.now().date() - timedelta(days=DEFAULT_BOOTSTRAP_DAYS)
    query = TedQueryBuilder.combine_and(
        TedQueryBuilder.publication_range(since),
        name_filter,
        TedQueryBuilder.countries([country]),
    )
    raws: list[dict[str, Any]] = []
    async for raw in client.async_search_notices(query, BUYER_SEARCH_FIELDS):
        raws.append(raw)
        if len(raws) >= BUYER_SEARCH_LIMIT:
            break
    return group_buyer_candidates(raws)[:MAX_CANDIDATES]


# --------------------------------------------------------------------- schemas


def _select(options: Iterable[str], key: str, *, radio: bool = False) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=list(options),
            mode=SelectSelectorMode.LIST if radio else SelectSelectorMode.DROPDOWN,
            translation_key=key,
        )
    )


def _multi_countries() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=sorted(ALPHA2_TO_ALPHA3),
            multiple=True,
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="country",
            sort=True,
        )
    )


def _country() -> CountrySelector:
    return CountrySelector(CountrySelectorConfig(countries=sorted(ALPHA2_TO_ALPHA3)))


def _eur() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=0, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="EUR"
        )
    )


def universe_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_RELEVANCE_MODE, default=RelevanceMode.STRICT.value): (
                _select(
                    [m.value for m in RelevanceMode], CONF_RELEVANCE_MODE, radio=True
                )
            ),
            vol.Required(CONF_MARKET_PRESET, default=MarketPreset.EU.value): _select(
                [p.value for p in MarketPreset], CONF_MARKET_PRESET
            ),
        }
    )


def countries_schema() -> vol.Schema:
    return vol.Schema({vol.Required(CONF_MARKET_COUNTRIES): _multi_countries()})


def organisation_schema(tracking: bool) -> vol.Schema:
    return vol.Schema(
        {vol.Required(CONF_TRACK_ORGANISATION, default=tracking): BooleanSelector()}
    )


def organisation_search_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_OWN_COUNTRY): _country(),
            vol.Required(CONF_SEARCH): TextSelector(),
        }
    )


def organisation_select_schema(candidates: list[BuyerCandidate]) -> vol.Schema:
    options = [
        SelectOptionDict(value=str(index), label=candidate.label)
        for index, candidate in enumerate(candidates)
    ]
    return vol.Schema(
        {
            vol.Required(CONF_CANDIDATE): SelectSelector(
                SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
            )
        }
    )


def peers_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_PEER_PRESET, default=PEER_PRESET_NONE): _select(
                [str(p) for p in PEER_PRESETS], CONF_PEER_PRESET
            ),
            vol.Optional(CONF_SELECTED_COUNTRY): _country(),
        }
    )


def peer_countries_schema() -> vol.Schema:
    return vol.Schema({vol.Required(CONF_PEER_COUNTRIES): _multi_countries()})


def categories_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_PINNED_CATEGORIES, default=[]): SelectSelector(
                SelectSelectorConfig(
                    options=list(Taxonomy.load().category_ids),
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                    translation_key="category",
                )
            )
        }
    )


def watchlist_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_WATCHLIST_COUNTRIES): _multi_countries(),
            vol.Optional(CONF_WATCHLIST_MIN_ESTIMATED_EUR): _eur(),
            vol.Optional(CONF_WATCHLIST_MIN_AWARD_EUR): _eur(),
        }
    )


def merge_section(
    options: Mapping[str, Any], keys: Iterable[str], user_input: Mapping[str, Any]
) -> dict[str, Any]:
    """Replace one section of the options: keys the form omitted are cleared."""
    merged = {k: v for k, v in options.items() if k not in set(keys)}
    merged.update(user_input)
    return merged


# --------------------------------------------------------------------- flows


class OrganisationStepsMixin(ConfigEntryBaseFlow):
    """The buyer search/select steps shared by the config and options flows."""

    _candidates: list[BuyerCandidate]
    _client: TedApiClient | None = None

    @property
    def ted_client(self) -> TedApiClient:
        if self._client is None:
            self._client = TedApiClient(async_get_clientsession(self.hass))
        return self._client

    async def _async_organisation_chosen(
        self, organisation: dict[str, Any]
    ) -> ConfigFlowResult:
        raise NotImplementedError

    async def async_step_organisation_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._candidates = await async_find_buyers(
                    self.ted_client,
                    user_input[CONF_OWN_COUNTRY],
                    user_input[CONF_SEARCH],
                )
            except TedApiError as err:
                _LOGGER.warning("Buyer search failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if self._candidates:
                    return await self.async_step_organisation_select()
                errors["base"] = "no_matches"
        return self.async_show_form(
            step_id="organisation_search",
            data_schema=self.add_suggested_values_to_schema(
                organisation_search_schema(), user_input
            ),
            errors=errors,
        )

    async def async_step_organisation_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                candidate = self._candidates[int(user_input[CONF_CANDIDATE])]
            except ValueError, IndexError:
                errors["base"] = "invalid_selection"
            else:
                return await self._async_organisation_chosen(candidate.as_options())
        return self.async_show_form(
            step_id="organisation_select",
            data_schema=organisation_select_schema(self._candidates),
            errors=errors,
        )


class EdpRadarConfigFlow(OrganisationStepsMixin, ConfigFlow, domain=DOMAIN):
    """Initial setup: universe → organisation → peers → categories → watchlist."""

    VERSION = 1

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}
        self._candidates = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> EdpRadarOptionsFlow:
        return EdpRadarOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            self._options.update(user_input)
            if user_input[CONF_MARKET_PRESET] == MarketPreset.CUSTOM:
                return await self.async_step_countries()
            return await self.async_step_organisation()
        return self.async_show_form(step_id="user", data_schema=universe_schema())

    async def async_step_countries(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_organisation()
        return self.async_show_form(step_id="countries", data_schema=countries_schema())

    async def async_step_organisation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            if user_input[CONF_TRACK_ORGANISATION]:
                return await self.async_step_organisation_search()
            return await self.async_step_peers()
        return self.async_show_form(
            step_id="organisation", data_schema=organisation_schema(False)
        )

    async def _async_organisation_chosen(
        self, organisation: dict[str, Any]
    ) -> ConfigFlowResult:
        self._options[CONF_OWN_ORGANISATION] = organisation
        return await self.async_step_peers()

    async def async_step_peers(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            if user_input[CONF_PEER_PRESET] == PEER_PRESET_CUSTOM:
                return await self.async_step_peer_countries()
            return await self.async_step_categories()
        return self.async_show_form(step_id="peers", data_schema=peers_schema())

    async def async_step_peer_countries(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_categories()
        return self.async_show_form(
            step_id="peer_countries", data_schema=peer_countries_schema()
        )

    async def async_step_categories(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_watchlist()
        return self.async_show_form(
            step_id="categories", data_schema=categories_schema()
        )

    async def async_step_watchlist(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._options = merge_section(self._options, WATCHLIST_KEYS, user_input)
            errors = await self._async_validate_universe()
            if not errors:
                return self.async_create_entry(
                    title=NAME, data={}, options=self._options
                )
        return self.async_show_form(
            step_id="watchlist",
            data_schema=self.add_suggested_values_to_schema(
                watchlist_schema(), user_input
            ),
            errors=errors,
        )

    async def _async_validate_universe(self) -> dict[str, str]:
        """Let TED check the query the coordinator is about to use."""
        config = RadarConfig.from_options(self._options)
        query = config.universe_query(Taxonomy.load(), dt_util.now().date())
        try:
            await self.ted_client.async_validate_query(query)
        except TedQueryError as err:
            _LOGGER.warning("TED rejected the universe query %r: %s", query, err)
            return {"base": "invalid_query"}
        except TedApiError as err:
            _LOGGER.warning("Could not validate the universe query: %s", err)
            return {"base": "cannot_connect"}
        return {}


class EdpRadarOptionsFlow(OrganisationStepsMixin, OptionsFlow):
    """Menu of sections; each section rewrites its own keys and reloads."""

    def __init__(self) -> None:
        self._candidates = []
        self._pending: dict[str, Any] = {}

    @property
    def options(self) -> Mapping[str, Any]:
        return self.config_entry.options

    def _finish(
        self, keys: Iterable[str], changes: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return self.async_create_entry(data=merge_section(self.options, keys, changes))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "universe",
                "organisation",
                "peers",
                "categories",
                "watchlist",
            ],
        )

    async def async_step_universe(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._pending = dict(user_input)
            if user_input[CONF_MARKET_PRESET] == MarketPreset.CUSTOM:
                return await self.async_step_countries()
            return self._finish(UNIVERSE_KEYS, self._pending)
        return self.async_show_form(
            step_id="universe",
            data_schema=self.add_suggested_values_to_schema(
                universe_schema(), self.options
            ),
        )

    async def async_step_countries(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._finish(UNIVERSE_KEYS, {**self._pending, **user_input})
        return self.async_show_form(
            step_id="countries",
            data_schema=self.add_suggested_values_to_schema(
                countries_schema(), self.options
            ),
        )

    async def async_step_organisation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            if user_input[CONF_TRACK_ORGANISATION]:
                return await self.async_step_organisation_search()
            return self._finish((CONF_OWN_ORGANISATION,), {})
        return self.async_show_form(
            step_id="organisation",
            data_schema=organisation_schema(CONF_OWN_ORGANISATION in self.options),
        )

    async def _async_organisation_chosen(
        self, organisation: dict[str, Any]
    ) -> ConfigFlowResult:
        return self._finish(
            (CONF_OWN_ORGANISATION,), {CONF_OWN_ORGANISATION: organisation}
        )

    async def async_step_peers(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._pending = dict(user_input)
            if user_input[CONF_PEER_PRESET] == PEER_PRESET_CUSTOM:
                return await self.async_step_peer_countries()
            return self._finish(PEER_KEYS, self._pending)
        return self.async_show_form(
            step_id="peers",
            data_schema=self.add_suggested_values_to_schema(
                peers_schema(), self.options
            ),
        )

    async def async_step_peer_countries(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._finish(PEER_KEYS, {**self._pending, **user_input})
        return self.async_show_form(
            step_id="peer_countries",
            data_schema=self.add_suggested_values_to_schema(
                peer_countries_schema(), self.options
            ),
        )

    async def async_step_categories(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._finish((CONF_PINNED_CATEGORIES,), user_input)
        return self.async_show_form(
            step_id="categories",
            data_schema=self.add_suggested_values_to_schema(
                categories_schema(), self.options
            ),
        )

    async def async_step_watchlist(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._finish(WATCHLIST_KEYS, user_input)
        return self.async_show_form(
            step_id="watchlist",
            data_schema=self.add_suggested_values_to_schema(
                watchlist_schema(), self.options
            ),
        )

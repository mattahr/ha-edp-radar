"""Config flow (minimal placeholder; the full UI flow lands with Task 3)."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN, NAME


class EdpRadarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single radar entry with default options."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=NAME, data={}, options={})

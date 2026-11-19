"""Config flow for HA-nnounce."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CHIMES,
    CONF_ANNOUNCE_VOLUME,
    CONF_CHIME,
    CONF_INTERCOM,
    CONF_MAX_DURATION,
    CONF_NORMALIZE,
    CONF_SET_VOLUME,
    CONF_SHOW_PANEL,
    CONF_SPEAKERS,
    CONF_VOLUME,
    DEFAULT_ANNOUNCE_VOLUME,
    DEFAULT_CHIME,
    DEFAULT_INTERCOM,
    DEFAULT_MAX_DURATION,
    DEFAULT_NORMALIZE,
    DEFAULT_SET_VOLUME,
    DEFAULT_SHOW_PANEL,
    DEFAULT_VOLUME,
    DOMAIN,
    MAX_DURATION_LIMIT,
    MIN_DURATION,
)


def _options_schema(options: dict[str, Any]) -> vol.Schema:
    """Return the options form, prefilled with the current values."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_SPEAKERS, default=list(options.get(CONF_SPEAKERS, []))
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=MEDIA_PLAYER_DOMAIN, multiple=True
                )
            ),
            vol.Optional(
                CONF_SET_VOLUME,
                default=options.get(CONF_SET_VOLUME, DEFAULT_SET_VOLUME),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_VOLUME, default=options.get(CONF_VOLUME, DEFAULT_VOLUME)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5,
                    max=100,
                    step=5,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Optional(
                CONF_ANNOUNCE_VOLUME,
                default=options.get(CONF_ANNOUNCE_VOLUME, DEFAULT_ANNOUNCE_VOLUME),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_CHIME, default=options.get(CONF_CHIME, DEFAULT_CHIME)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(CHIMES),
                    translation_key=CONF_CHIME,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_NORMALIZE,
                default=options.get(CONF_NORMALIZE, DEFAULT_NORMALIZE),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_MAX_DURATION,
                default=options.get(CONF_MAX_DURATION, DEFAULT_MAX_DURATION),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_DURATION,
                    max=MAX_DURATION_LIMIT,
                    step=1,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_SHOW_PANEL,
                default=options.get(CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_INTERCOM,
                default=options.get(CONF_INTERCOM, DEFAULT_INTERCOM),
            ): selector.BooleanSelector(),
        }
    )


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Store numbers as integers."""
    data = dict(user_input)
    for key in (CONF_VOLUME, CONF_MAX_DURATION):
        if key in data:
            data[key] = int(data[key])
    return data


class HannounceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the integration once."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the entry with the chosen options."""
        if user_input is not None:
            return self.async_create_entry(
                title="HA-nnounce", data={}, options=_clean(user_input)
            )
        return self.async_show_form(step_id="user", data_schema=_options_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Return the options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlowWithReload):
    """Change the options; the entry reloads afterwards."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the options."""
        if user_input is not None:
            return self.async_create_entry(data=_clean(user_input))
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(dict(self.config_entry.options)),
        )

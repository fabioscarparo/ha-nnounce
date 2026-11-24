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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import (
    ALL_CHIMES,
    CHIME_CUSTOM,
    CONF_ALEXA_SUPPORT,
    CONF_ANNOUNCE_VOLUME,
    CONF_CHIME,
    CONF_CUSTOM_CHIME,
    CONF_INTERCOM,
    CONF_MAX_DURATION,
    CONF_NORMALIZE,
    CONF_QUIET_END,
    CONF_QUIET_ENTITY,
    CONF_QUIET_HOURS,
    CONF_QUIET_MODE,
    CONF_QUIET_SPEAKERS,
    CONF_QUIET_START,
    CONF_QUIET_VOLUME,
    CONF_RESUME_PLAYBACK,
    CONF_SET_VOLUME,
    CONF_SHOW_PANEL,
    CONF_SPEAKERS,
    CONF_TTS_ENTITY,
    CONF_VOICE_ENHANCEMENT,
    CONF_VOLUME,
    DEFAULT_ALEXA_SUPPORT,
    DEFAULT_ANNOUNCE_VOLUME,
    DEFAULT_CHIME,
    DEFAULT_INTERCOM,
    DEFAULT_MAX_DURATION,
    DEFAULT_NORMALIZE,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_HOURS,
    DEFAULT_QUIET_MODE,
    DEFAULT_QUIET_START,
    DEFAULT_QUIET_VOLUME,
    DEFAULT_RESUME_PLAYBACK,
    DEFAULT_SET_VOLUME,
    DEFAULT_SHOW_PANEL,
    DEFAULT_VOICE_ENHANCEMENT,
    DEFAULT_VOLUME,
    DOMAIN,
    MAX_DURATION_LIMIT,
    MIN_DURATION,
    QUIET_MODES,
)
from .settings import async_check_allowed_file


def _suggested(value: Any) -> dict[str, Any] | None:
    """Return a schema description dict when a suggested value is set."""
    return {"suggested_value": value} if value else None


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
                CONF_RESUME_PLAYBACK,
                default=options.get(CONF_RESUME_PLAYBACK, DEFAULT_RESUME_PLAYBACK),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_CHIME, default=options.get(CONF_CHIME, DEFAULT_CHIME)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(ALL_CHIMES),
                    translation_key=CONF_CHIME,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_CUSTOM_CHIME,
                description=_suggested(options.get(CONF_CUSTOM_CHIME)),
            ): selector.TextSelector(),
            vol.Optional(
                CONF_NORMALIZE,
                default=options.get(CONF_NORMALIZE, DEFAULT_NORMALIZE),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_VOICE_ENHANCEMENT,
                default=options.get(CONF_VOICE_ENHANCEMENT, DEFAULT_VOICE_ENHANCEMENT),
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
                CONF_TTS_ENTITY,
                description=_suggested(options.get(CONF_TTS_ENTITY)),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="tts")
            ),
            vol.Optional(
                CONF_QUIET_HOURS,
                default=options.get(CONF_QUIET_HOURS, DEFAULT_QUIET_HOURS),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_QUIET_START,
                default=options.get(CONF_QUIET_START, DEFAULT_QUIET_START),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_QUIET_END,
                default=options.get(CONF_QUIET_END, DEFAULT_QUIET_END),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_QUIET_MODE,
                default=options.get(CONF_QUIET_MODE, DEFAULT_QUIET_MODE),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(QUIET_MODES),
                    translation_key=CONF_QUIET_MODE,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_QUIET_VOLUME,
                default=options.get(CONF_QUIET_VOLUME, DEFAULT_QUIET_VOLUME),
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
                CONF_QUIET_SPEAKERS,
                default=list(options.get(CONF_QUIET_SPEAKERS, [])),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=MEDIA_PLAYER_DOMAIN, multiple=True
                )
            ),
            vol.Optional(
                CONF_QUIET_ENTITY,
                description=_suggested(options.get(CONF_QUIET_ENTITY)),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["input_boolean", "binary_sensor"]
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
            vol.Optional(
                CONF_ALEXA_SUPPORT,
                default=options.get(CONF_ALEXA_SUPPORT, DEFAULT_ALEXA_SUPPORT),
            ): selector.BooleanSelector(),
        }
    )


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize form values before storing them in entry options."""
    data = dict(user_input)
    for key in (CONF_VOLUME, CONF_MAX_DURATION, CONF_QUIET_VOLUME):
        if key in data:
            data[key] = int(data[key])
    for key in (CONF_CUSTOM_CHIME, CONF_TTS_ENTITY, CONF_QUIET_ENTITY):
        value = str(data.get(key) or "").strip()
        if value:
            data[key] = value
        else:
            data.pop(key, None)
    return data


async def _async_validate(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate option paths and combinations."""
    errors: dict[str, str] = {}
    custom_chime = data.get(CONF_CUSTOM_CHIME)
    if custom_chime and (
        path_error := await async_check_allowed_file(hass, custom_chime)
    ):
        errors[CONF_CUSTOM_CHIME] = path_error
    if data.get(CONF_CHIME) == CHIME_CUSTOM and not custom_chime:
        errors[CONF_CHIME] = "custom_chime_missing"
    if data.get(CONF_ALEXA_SUPPORT):
        try:
            get_url(hass, allow_internal=False, allow_ip=False, require_ssl=True)
        except NoURLAvailableError:
            errors[CONF_ALEXA_SUPPORT] = "external_https_required"
    return errors


class HannounceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the integration once."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the entry with the chosen options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            cleaned = _clean(user_input)
            errors = await _async_validate(self.hass, cleaned)
            if not errors:
                return self.async_create_entry(
                    title="HA-nnounce", data={}, options=cleaned
                )
        return self.async_show_form(
            step_id="user",
            data_schema=_options_schema(user_input or {}),
            errors=errors,
        )

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
        errors: dict[str, str] = {}
        if user_input is not None:
            cleaned = _clean(user_input)
            errors = await _async_validate(self.hass, cleaned)
            if not errors:
                return self.async_create_entry(data=cleaned)
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(
                user_input if user_input is not None else dict(self.config_entry.options)
            ),
            errors=errors,
        )

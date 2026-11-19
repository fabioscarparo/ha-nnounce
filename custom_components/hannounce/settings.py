"""Settings of the integration, read from the config entry options."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)

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
    MEDIA_SOURCE_PLATFORMS,
)

CAST_GROUP_MODEL = "Google Cast Group"


@dataclass(frozen=True)
class AnnounceSettings:
    """The options in a typed form."""

    speakers: tuple[str, ...]
    set_volume: bool
    volume: int
    chime: str
    normalize: bool
    max_duration: int
    show_panel: bool
    intercom: bool
    announce_volume: bool

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> AnnounceSettings:
        """Build the settings from the options, with defaults."""
        chime = options.get(CONF_CHIME, DEFAULT_CHIME)
        return cls(
            speakers=tuple(options.get(CONF_SPEAKERS) or ()),
            set_volume=bool(options.get(CONF_SET_VOLUME, DEFAULT_SET_VOLUME)),
            volume=int(options.get(CONF_VOLUME, DEFAULT_VOLUME)),
            chime=chime if chime in CHIMES else DEFAULT_CHIME,
            normalize=bool(options.get(CONF_NORMALIZE, DEFAULT_NORMALIZE)),
            max_duration=int(options.get(CONF_MAX_DURATION, DEFAULT_MAX_DURATION)),
            show_panel=bool(options.get(CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL)),
            intercom=bool(options.get(CONF_INTERCOM, DEFAULT_INTERCOM)),
            announce_volume=bool(
                options.get(CONF_ANNOUNCE_VOLUME, DEFAULT_ANNOUNCE_VOLUME)
            ),
        )

    @property
    def volume_level(self) -> float | None:
        """Return the announcement volume as 0..1, or None to keep it."""
        return self.volume / 100 if self.set_volume else None


def speaker_ids(hass: HomeAssistant, settings: AnnounceSettings) -> list[str]:
    """Return the speakers offered to the user.

    The chosen list or, when none is chosen, every media player of an
    integration known to play audio from Home Assistant, except televisions.
    """
    if settings.speakers:
        return [
            entity_id
            for entity_id in settings.speakers
            if hass.states.get(entity_id) is not None
            or er.async_get(hass).async_get(entity_id) is not None
        ]
    registry = er.async_get(hass)
    return sorted(
        entry.entity_id
        for entry in registry.entities.values()
        if entry.domain == MEDIA_PLAYER_DOMAIN
        and entry.platform in MEDIA_SOURCE_PLATFORMS
        and not entry.disabled
        and not entry.hidden
        and (entry.device_class or entry.original_device_class)
        != MediaPlayerDeviceClass.TV
    )


def describe_speakers(hass: HomeAssistant, entity_ids: list[str]) -> list[dict]:
    """Return what the frontend shows for each speaker."""
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    areas = ar.async_get(hass)
    result = []
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        entry = entities.async_get(entity_id)
        device = devices.async_get(entry.device_id) if entry and entry.device_id else None
        area_id = (entry.area_id if entry else None) or (device.area_id if device else None)
        area = areas.async_get_area(area_id) if area_id else None
        name = (
            state.attributes.get("friendly_name")
            if state
            else (entry.name or entry.original_name if entry else None)
        ) or entity_id
        result.append(
            {
                "entity_id": entity_id,
                "name": name,
                "area": area.name if area else None,
                "group": bool(
                    (device and device.model == CAST_GROUP_MODEL)
                    or (entry and entry.platform == "group")
                ),
                "platform": entry.platform if entry else None,
                "available": bool(state and state.state != STATE_UNAVAILABLE),
            }
        )
    return result

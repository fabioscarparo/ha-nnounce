"""Settings of the integration, read from the config entry options."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import time
from typing import Any

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
)
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
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
from homeassistant.util import dt as dt_util

from .const import (
    ALL_CHIMES,
    CHIME_CUSTOM,
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
    CONF_SET_VOLUME,
    CONF_SHOW_PANEL,
    CONF_SPEAKERS,
    CONF_TTS_ENTITY,
    CONF_VOICE_ENHANCEMENT,
    CONF_VOLUME,
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
    DEFAULT_SET_VOLUME,
    DEFAULT_SHOW_PANEL,
    DEFAULT_VOICE_ENHANCEMENT,
    DEFAULT_VOLUME,
    MEDIA_SOURCE_PLATFORMS,
    QUIET_MODES,
)

CAST_GROUP_MODEL = "Google Cast Group"


def parse_clock(value: str | None) -> time | None:
    """Parse an HH:MM or HH:MM:SS clock string, returning None if invalid."""
    if not value or not isinstance(value, str):
        return None
    try:
        return time.fromisoformat(value.strip())
    except ValueError:
        return None


def is_in_time_window(current: time, start: time, end: time) -> bool:
    """Return True when current falls in [start, end), supporting overnight windows."""
    if start == end:
        return False
    if start < end:
        return start <= current < end
    return current >= start or current < end


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
    voice_enhancement: bool = DEFAULT_VOICE_ENHANCEMENT
    custom_chime: str | None = None
    tts_entity: str | None = None
    quiet_hours: bool = DEFAULT_QUIET_HOURS
    quiet_start: str = DEFAULT_QUIET_START
    quiet_end: str = DEFAULT_QUIET_END
    quiet_mode: str = DEFAULT_QUIET_MODE
    quiet_volume: int = DEFAULT_QUIET_VOLUME
    quiet_speakers: tuple[str, ...] = ()
    quiet_entity: str | None = None

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> AnnounceSettings:
        """Build the settings from the options, with defaults."""
        custom_chime = str(options.get(CONF_CUSTOM_CHIME) or "").strip() or None
        chime = options.get(CONF_CHIME, DEFAULT_CHIME)
        if chime not in ALL_CHIMES or (chime == CHIME_CUSTOM and not custom_chime):
            chime = DEFAULT_CHIME
        quiet_mode = options.get(CONF_QUIET_MODE, DEFAULT_QUIET_MODE)
        if quiet_mode not in QUIET_MODES:
            quiet_mode = DEFAULT_QUIET_MODE
        tts_entity = str(options.get(CONF_TTS_ENTITY) or "").strip() or None
        quiet_entity = str(options.get(CONF_QUIET_ENTITY) or "").strip() or None
        quiet_start = str(options.get(CONF_QUIET_START) or DEFAULT_QUIET_START)
        quiet_end = str(options.get(CONF_QUIET_END) or DEFAULT_QUIET_END)
        return cls(
            speakers=tuple(options.get(CONF_SPEAKERS) or ()),
            set_volume=bool(options.get(CONF_SET_VOLUME, DEFAULT_SET_VOLUME)),
            volume=int(options.get(CONF_VOLUME, DEFAULT_VOLUME)),
            chime=chime,
            normalize=bool(options.get(CONF_NORMALIZE, DEFAULT_NORMALIZE)),
            voice_enhancement=bool(
                options.get(CONF_VOICE_ENHANCEMENT, DEFAULT_VOICE_ENHANCEMENT)
            ),
            max_duration=int(options.get(CONF_MAX_DURATION, DEFAULT_MAX_DURATION)),
            show_panel=bool(options.get(CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL)),
            intercom=bool(options.get(CONF_INTERCOM, DEFAULT_INTERCOM)),
            announce_volume=bool(
                options.get(CONF_ANNOUNCE_VOLUME, DEFAULT_ANNOUNCE_VOLUME)
            ),
            custom_chime=custom_chime,
            tts_entity=tts_entity,
            quiet_hours=bool(options.get(CONF_QUIET_HOURS, DEFAULT_QUIET_HOURS)),
            quiet_start=quiet_start,
            quiet_end=quiet_end,
            quiet_mode=quiet_mode,
            quiet_volume=int(options.get(CONF_QUIET_VOLUME, DEFAULT_QUIET_VOLUME)),
            quiet_speakers=tuple(options.get(CONF_QUIET_SPEAKERS) or ()),
            quiet_entity=quiet_entity,
        )

    @property
    def volume_level(self) -> float | None:
        """Return the announcement volume as 0..1, or None to keep it."""
        return self.volume / 100 if self.set_volume else None

    @property
    def quiet_volume_level(self) -> float:
        """Return the quiet hours volume cap as 0..1."""
        return self.quiet_volume / 100

    def is_quiet_active(self, hass: HomeAssistant, now: time | None = None) -> bool:
        """Return True when quiet hours are enabled and currently active."""
        if not self.quiet_hours:
            return False
        if self.quiet_entity and hass.states.is_state(self.quiet_entity, STATE_ON):
            return True
        start = parse_clock(self.quiet_start)
        end = parse_clock(self.quiet_end)
        if start is None or end is None:
            return False
        current = now if now is not None else dt_util.now().time().replace(tzinfo=None)
        return is_in_time_window(current, start, end)

    def affects_speaker(self, entity_id: str) -> bool:
        """Return True if quiet hours apply to the given speaker."""
        return not self.quiet_speakers or entity_id in self.quiet_speakers


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
                "area_id": area.id if area else None,
                "area_icon": area.icon if area else None,
                "group": bool(
                    (device and device.model == CAST_GROUP_MODEL)
                    or (entry and entry.platform == "group")
                ),
                "platform": entry.platform if entry else None,
                "available": bool(state and state.state != STATE_UNAVAILABLE),
            }
        )
    return result

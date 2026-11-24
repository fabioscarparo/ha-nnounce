"""Diagnostics support for HA-nnounce.

Safe to attach to a public issue: no raw URLs, file paths, tokens, user IDs, or audio data.
"""

from __future__ import annotations

import shutil
from typing import Any
from urllib.parse import urlparse

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    MediaPlayerEntityFeature,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.loader import async_get_integration

from . import HannounceConfigEntry
from .const import CONF_CUSTOM_CHIME, DOMAIN
from .settings import describe_speakers


def _labs_two_way_audio(hass: HomeAssistant) -> bool | None:
    """Return whether the Home Assistant Labs two-way audio flag is enabled."""
    try:
        from homeassistant.components.labs import (  # noqa: PLC0415
            async_is_preview_feature_enabled,
        )

        return async_is_preview_feature_enabled(hass, "camera", "two_way_audio")
    except ImportError:
        return None


def _url_status(hass: HomeAssistant) -> dict[str, Any]:
    """Return whether Home Assistant exposes a reachable URL without leaking it."""
    try:
        parsed = urlparse(get_url(hass))
    except NoURLAvailableError:
        return {"available": False, "scheme": None}
    return {"available": True, "scheme": parsed.scheme or None}


def _external_https_available(hass: HomeAssistant) -> bool:
    """Return whether Home Assistant exposes an external HTTPS URL without leaking it."""
    try:
        get_url(hass, allow_internal=False, allow_ip=False, require_ssl=True)
    except NoURLAvailableError:
        return False
    return True


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HannounceConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    integration = await async_get_integration(hass, DOMAIN)
    runtime = getattr(entry, "runtime_data", None)

    safe_options = dict(entry.options)
    if safe_options.get(CONF_CUSTOM_CHIME):
        safe_options[CONF_CUSTOM_CHIME] = "**REDACTED**"

    diagnostics: dict[str, Any] = {
        "integration_version": str(integration.version),
        "home_assistant_version": HA_VERSION,
        "language": hass.config.language,
        "entry": {
            "state": entry.state.value,
            "options": safe_options,
        },
        "url": _url_status(hass),
    }

    if runtime is not None:
        ffmpeg_binary = runtime.announcer.ffmpeg_binary
        ffmpeg_found = await hass.async_add_executor_job(shutil.which, ffmpeg_binary)
        speaker_rows: list[dict[str, Any]] = []
        for speaker in describe_speakers(hass, runtime.speakers()):
            state = hass.states.get(speaker["entity_id"])
            features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0) if state else 0
            volume = state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) if state else None
            muted = state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) if state else None
            speaker_rows.append(
                {
                    "entity_id": speaker["entity_id"],
                    "platform": speaker["platform"],
                    "available": speaker["available"],
                    "group": speaker["group"],
                    "state": state.state if state else None,
                    "volume_level": round(float(volume), 3) if volume is not None else None,
                    "is_volume_muted": muted,
                    "features": {
                        "media_announce": bool(
                            features & MediaPlayerEntityFeature.MEDIA_ANNOUNCE
                        ),
                        "volume_set": bool(
                            features & MediaPlayerEntityFeature.VOLUME_SET
                        ),
                        "volume_mute": bool(
                            features & MediaPlayerEntityFeature.VOLUME_MUTE
                        ),
                        "seek": bool(features & MediaPlayerEntityFeature.SEEK),
                    },
                }
            )
        diagnostics["runtime"] = {
            "ffmpeg": {
                "found": bool(ffmpeg_found),
            },
            "custom_chime_configured": bool(runtime.settings.custom_chime),
            "resume_playback": runtime.settings.resume_playback,
            "alexa": {
                "enabled": runtime.settings.alexa_support,
                "external_https_available": _external_https_available(hass),
            },
            "tts": runtime.tts_info(),
            "quiet": runtime.quiet_info(),
            "intercom": {
                "enabled": runtime.settings.intercom,
                "ready": runtime.intercom_ready,
                "labs_two_way_audio": _labs_two_way_audio(hass),
            },
            "recent_announcements": len(runtime.announcer.recent()),
            "speakers": speaker_rows,
        }

    return diagnostics

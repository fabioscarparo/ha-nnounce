"""Service actions: announce a file, URL or text message, and replay the last message."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    ENTITY_MATCH_ALL,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)

from .audio import AudioError, NoVoiceError
from .const import (
    ALL_CHIMES,
    ATTR_FILE,
    ATTR_FORCE,
    ATTR_LANGUAGE,
    ATTR_MESSAGE,
    ATTR_TTS_ENTITY,
    ATTR_URL,
    CHIME_CUSTOM,
    CONF_CHIME,
    CONF_VOLUME,
    DOMAIN,
    MAX_MESSAGE_LENGTH,
    MAX_UPLOAD_BYTES,
    SERVICE_ANNOUNCE,
    SERVICE_REPLAY,
)

TARGET_KEYS = (
    ATTR_ENTITY_ID,
    ATTR_DEVICE_ID,
    ATTR_AREA_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
)
INDIRECT_TARGET_KEYS = (
    ATTR_DEVICE_ID,
    ATTR_AREA_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
)

ANNOUNCE_SCHEMA = vol.All(
    vol.Schema(
        {
            **cv.ENTITY_SERVICE_FIELDS,
            vol.Exclusive(ATTR_FILE, "source"): cv.string,
            vol.Exclusive(ATTR_URL, "source"): cv.url,
            vol.Exclusive(ATTR_MESSAGE, "source"): vol.All(
                cv.string, vol.Length(min=1, max=MAX_MESSAGE_LENGTH)
            ),
            vol.Optional(ATTR_TTS_ENTITY): cv.string,
            vol.Optional(ATTR_LANGUAGE): cv.string,
            vol.Optional(CONF_VOLUME): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=100)
            ),
            vol.Optional(CONF_CHIME): vol.In(ALL_CHIMES),
            vol.Optional(ATTR_FORCE, default=False): cv.boolean,
        }
    ),
    cv.has_at_least_one_key(ATTR_FILE, ATTR_URL, ATTR_MESSAGE),
)

REPLAY_SCHEMA = vol.Schema(
    {
        **cv.ENTITY_SERVICE_FIELDS,
        vol.Optional(CONF_VOLUME): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=100)
        ),
        vol.Optional(ATTR_FORCE, default=False): cv.boolean,
    }
)


def _runtime(hass: HomeAssistant):
    if (runtime := hass.data.get(DOMAIN)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_set_up"
        )
    return runtime


def _resolve_targets(
    hass: HomeAssistant,
    runtime,
    data: Mapping[str, Any],
    default: list[str],
) -> list[str]:
    """Resolve explicit media players and area, floor, device, or label targets."""
    if not any(data.get(key) for key in TARGET_KEYS):
        return default

    targets: list[str] = []
    raw_entities = data.get(ATTR_ENTITY_ID)
    if raw_entities:
        if raw_entities == ENTITY_MATCH_ALL or raw_entities == [ENTITY_MATCH_ALL]:
            targets.extend(runtime.speakers())
        else:
            entity_list = (
                [raw_entities] if isinstance(raw_entities, str) else list(raw_entities)
            )
            targets.extend(
                entity_id
                for entity_id in entity_list
                if entity_id.startswith(f"{MEDIA_PLAYER_DOMAIN}.")
            )

    if any(data.get(key) for key in INDIRECT_TARGET_KEYS):
        selected = async_extract_referenced_entity_ids(hass, TargetSelection(data))
        indirect = selected.indirectly_referenced
        targets.extend(
            entity_id for entity_id in runtime.speakers() if entity_id in indirect
        )

    return list(dict.fromkeys(targets))


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register the service actions."""

    async def announce(call: ServiceCall) -> ServiceResponse:
        runtime = _runtime(hass)
        announcer = runtime.announcer
        targets = _resolve_targets(hass, runtime, call.data, runtime.speakers())
        volume = (
            call.data[CONF_VOLUME] / 100
            if CONF_VOLUME in call.data
            else runtime.settings.volume_level
        )
        chime = call.data.get(CONF_CHIME)
        if chime == CHIME_CUSTOM and not runtime.settings.custom_chime:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="custom_chime_missing"
            )
        force = bool(call.data.get(ATTR_FORCE, False))

        if message := call.data.get(ATTR_MESSAGE):
            runtime.plan_playback(targets, volume, force=force)
            try:
                announcement = await runtime.async_create_tts(
                    message,
                    source_kind="service",
                    user_id=call.context.user_id,
                    chime=chime,
                    tts_entity=call.data.get(ATTR_TTS_ENTITY),
                    language=call.data.get(ATTR_LANGUAGE),
                )
            except NoVoiceError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="no_voice"
                ) from err
            except AudioError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="audio_error",
                    translation_placeholders={"error": str(err)},
                ) from err
            used = runtime.play(announcement, targets, volume, force=force)
            return {**announcement.as_dict(), "targets": used}

        downloaded: Path | None = None
        if file := call.data.get(ATTR_FILE):
            source = Path(file)
            if not hass.config.is_allowed_path(str(source)):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="path_not_allowed",
                    translation_placeholders={"path": file},
                )
            if not await hass.async_add_executor_job(source.is_file):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="file_not_found",
                    translation_placeholders={"path": file},
                )
            runtime.plan_playback(targets, volume, force=force)
        else:
            runtime.plan_playback(targets, volume, force=force)
            source = downloaded = await _async_download(
                hass, announcer, call.data[ATTR_URL]
            )
        try:
            announcement = await announcer.async_create(
                source,
                runtime.settings,
                source_kind="service",
                user_id=call.context.user_id,
                chime=chime,
            )
        except NoVoiceError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="no_voice"
            ) from err
        except AudioError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="audio_error",
                translation_placeholders={"error": str(err)},
            ) from err
        finally:
            if downloaded is not None:
                await hass.async_add_executor_job(downloaded.unlink, True)
        used = runtime.play(announcement, targets, volume, force=force)
        return {**announcement.as_dict(), "targets": used}

    async def replay(call: ServiceCall) -> ServiceResponse:
        runtime = _runtime(hass)
        last = runtime.announcer.last
        if last is None or runtime.announcer.get(last.id) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_message"
            )
        volume = (
            call.data[CONF_VOLUME] / 100
            if CONF_VOLUME in call.data
            else runtime.settings.volume_level
        )
        targets = _resolve_targets(hass, runtime, call.data, last.targets)
        used = runtime.play(
            last, targets, volume, force=bool(call.data.get(ATTR_FORCE, False))
        )
        return {**last.as_dict(), "targets": used}

    hass.services.async_register(
        DOMAIN,
        SERVICE_ANNOUNCE,
        announce,
        schema=ANNOUNCE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REPLAY,
        replay,
        schema=REPLAY_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def _async_download(hass: HomeAssistant, announcer, url: str) -> Path:
    """Download an audio file to the working folder."""
    session = async_get_clientsession(hass)
    data = bytearray()
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            response.raise_for_status()
            async for chunk in response.content.iter_chunked(256 * 1024):
                data += chunk
                if len(data) > MAX_UPLOAD_BYTES:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN, translation_key="too_large"
                    )
    except (aiohttp.ClientError, TimeoutError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="download_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    target = announcer.folder / f"in_{announcer.new_id()}"
    await hass.async_add_executor_job(target.write_bytes, bytes(data))
    return target

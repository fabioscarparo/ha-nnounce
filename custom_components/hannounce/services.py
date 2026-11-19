"""Service actions: announce a file or a URL, replay the last message."""

from __future__ import annotations

from pathlib import Path

import aiohttp
import voluptuous as vol
from homeassistant.const import ATTR_ENTITY_ID
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

from .audio import AudioError, NoVoiceError
from .const import (
    ATTR_FILE,
    ATTR_URL,
    CHIMES,
    CONF_CHIME,
    CONF_VOLUME,
    DOMAIN,
    MAX_UPLOAD_BYTES,
    SERVICE_ANNOUNCE,
    SERVICE_REPLAY,
)

ANNOUNCE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Exclusive(ATTR_FILE, "source"): cv.string,
            vol.Exclusive(ATTR_URL, "source"): cv.url,
            vol.Optional(CONF_VOLUME): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            vol.Optional(CONF_CHIME): vol.In(CHIMES),
        }
    ),
    cv.has_at_least_one_key(ATTR_FILE, ATTR_URL),
)

REPLAY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(CONF_VOLUME): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
    }
)


def _runtime(hass: HomeAssistant):
    if (runtime := hass.data.get(DOMAIN)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_set_up"
        )
    return runtime


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register the service actions."""

    async def announce(call: ServiceCall) -> ServiceResponse:
        runtime = _runtime(hass)
        announcer = runtime.announcer
        targets = call.data.get(ATTR_ENTITY_ID) or runtime.speakers()
        volume = (
            call.data[CONF_VOLUME] / 100
            if CONF_VOLUME in call.data
            else runtime.settings.volume_level
        )
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
        else:
            source = downloaded = await _async_download(hass, announcer, call.data[ATTR_URL])
        try:
            announcement = await announcer.async_create(
                source,
                runtime.settings,
                source_kind="service",
                user_id=call.context.user_id,
                chime=call.data.get(CONF_CHIME),
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
        used = runtime.play(announcement, targets, volume)
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
        used = runtime.play(last, call.data.get(ATTR_ENTITY_ID) or last.targets, volume)
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
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
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

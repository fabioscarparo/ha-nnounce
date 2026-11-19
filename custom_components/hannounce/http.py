"""HTTP endpoints: upload a recording, serve the encoded audio to the speakers."""

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from typing import TYPE_CHECKING

from aiohttp import BodyPartReader, web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.exceptions import HomeAssistantError

from .audio import AudioError, NoVoiceError
from .const import API_ANNOUNCE, API_AUDIO, CHIMES, DOMAIN, MAX_UPLOAD_BYTES

if TYPE_CHECKING:
    from . import HannounceData

_LOGGER = logging.getLogger(__name__)

AUDIO_SUFFIXES = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/3gpp": ".3gp",
    "audio/amr": ".amr",
    "audio/flac": ".flac",
    "video/webm": ".webm",
    "video/mp4": ".mp4",
}


class BadRequest(ValueError):
    """A field of the upload is not valid."""


def _runtime(request: web.Request) -> HannounceData | None:
    """Return the runtime data, None when the integration is not set up."""
    return request.app[KEY_HASS].data.get(DOMAIN)


def _parse_targets(raw: str) -> list[str]:
    """Accept a JSON list or a comma separated list."""
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            value = json.loads(raw)
        except ValueError as err:
            raise BadRequest("targets is not valid JSON") from err
        if not isinstance(value, list):
            raise BadRequest("targets must be a list")
        return [str(item) for item in value if item]
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_volume(raw: str | None, default: float | None) -> float | None:
    """Return the volume as 0..1, None to keep the speaker's volume."""
    if raw is None or raw == "":
        return default
    if raw == "keep":
        return None
    try:
        value = float(raw)
    except ValueError as err:
        raise BadRequest("volume must be a number or keep") from err
    if not 0 <= value <= 100:
        raise BadRequest("volume must be between 0 and 100")
    return value / 100


def _error(message: str, status: HTTPStatus, code: str) -> web.Response:
    """Every error is JSON with a code the card can translate."""
    return web.json_response({"code": code, "message": message}, status=status)


class AnnounceUploadView(HomeAssistantView):
    """Receive a recording from the card or the panel and play it."""

    url = API_ANNOUNCE
    name = "api:hannounce:announce"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        """Handle the multipart upload."""
        if (runtime := _runtime(request)) is None:
            return _error("HA-nnounce is not set up", HTTPStatus.SERVICE_UNAVAILABLE, "not_set_up")
        if not request.content_type.startswith("multipart/"):
            return _error("Send multipart/form-data", HTTPStatus.BAD_REQUEST, "bad_request")
        hass = request.app[KEY_HASS]
        announcer = runtime.announcer
        settings = runtime.settings
        user = request.get("hass_user")

        fields: dict[str, str] = {}
        recording = bytearray()
        suffix = None
        reader = await request.multipart()
        while (part := await reader.next()) is not None:
            if not isinstance(part, BodyPartReader):
                continue
            if part.name == "audio":
                content_type = (part.headers.get("Content-Type") or "").split(";")[0]
                suffix = AUDIO_SUFFIXES.get(content_type.strip().lower(), "")
                if not suffix and part.filename and "." in part.filename:
                    suffix = "." + part.filename.rsplit(".", 1)[1][:5].lower()
                while chunk := await part.read_chunk(256 * 1024):
                    recording += chunk
                    if len(recording) > MAX_UPLOAD_BYTES:
                        return _error(
                            "The recording is too large",
                            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                            "too_large",
                        )
            else:
                fields[part.name or ""] = (await part.text())[:4096]

        # Check every field before anything is written or encoded
        if suffix is None or not recording:
            return _error("No audio received", HTTPStatus.BAD_REQUEST, "no_audio")
        try:
            targets = _parse_targets(fields.get("targets", ""))
            volume = _parse_volume(fields.get("volume"), settings.volume_level)
        except BadRequest as err:
            return _error(str(err), HTTPStatus.BAD_REQUEST, "bad_request")
        chime = fields.get("chime") or None
        if chime is not None and chime not in CHIMES:
            return _error("Unknown chime", HTTPStatus.BAD_REQUEST, "bad_request")
        if not targets:
            return _error("Choose at least one speaker", HTTPStatus.BAD_REQUEST, "no_targets")
        try:
            announcer.check_targets(targets)
        except HomeAssistantError as err:
            return _error(str(err), HTTPStatus.BAD_REQUEST, "no_targets")

        source = announcer.folder / f"in_{announcer.new_id()}{suffix}"
        await hass.async_add_executor_job(source.write_bytes, bytes(recording))
        del recording
        try:
            announcement = await announcer.async_create(
                source,
                settings,
                source_kind="upload",
                user_id=user.id if user else None,
                chime=chime,
            )
        except NoVoiceError:
            return _error("No voice in the recording", HTTPStatus.UNPROCESSABLE_ENTITY, "no_voice")
        except AudioError as err:
            _LOGGER.error("Could not process the recording: %s", err)
            return _error(
                f"Could not process the recording: {err}",
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "audio_error",
            )
        finally:
            await hass.async_add_executor_job(source.unlink, True)

        try:
            used = runtime.play(announcement, targets, volume)
        except HomeAssistantError as err:
            return _error(str(err), HTTPStatus.BAD_REQUEST, "play_failed")
        return web.json_response({**announcement.as_dict(), "targets": used})


class AnnounceAudioView(HomeAssistantView):
    """Serve an encoded announcement.

    Speakers open it through a signed URL, so no login is needed but the
    link only works for a while.
    """

    url = API_AUDIO + "/{announcement_id}"
    name = "api:hannounce:audio"
    requires_auth = True

    async def get(self, request: web.Request, announcement_id: str) -> web.StreamResponse:
        """Return the MP3 file."""
        if (runtime := _runtime(request)) is None:
            raise web.HTTPNotFound
        announcement = runtime.announcer.get(announcement_id.removesuffix(".mp3"))
        if announcement is None:
            raise web.HTTPNotFound
        return web.FileResponse(
            announcement.path,
            headers={
                "Content-Type": "audio/mpeg",
                "Cache-Control": "private, max-age=3600",
            },
        )

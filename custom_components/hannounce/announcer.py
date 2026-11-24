"""Store announcements and play them on the speakers."""

from __future__ import annotations

import asyncio
import contextlib
import html
import logging
import secrets
import shutil
import tempfile
import time
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    SERVICE_MEDIA_SEEK,
    SERVICE_PLAY_MEDIA,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.components.notify import (
    ATTR_MESSAGE as NOTIFY_ATTR_MESSAGE,
)
from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
)
from homeassistant.components.notify import (
    SERVICE_SEND_MESSAGE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_BUFFERING,
    STATE_OFF,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util import dt as dt_util

from . import audio
from .const import (
    ALEXA_AUDIO_SUFFIX,
    ALEXA_MAX_DURATION,
    ALEXA_PLATFORMS,
    ALEXA_PLAYBACK_BUFFER,
    ANNOUNCE_VOLUME_EXTRA,
    ANNOUNCEMENT_TTL,
    API_AUDIO,
    CHIME_CUSTOM,
    DOMAIN,
    EVENT_ANNOUNCED,
    MAX_ANNOUNCEMENTS,
    MEDIA_SOURCE_PLATFORMS,
    PLAYBACK_END_GRACE,
    PLAYBACK_START_TIMEOUT,
)
from .media_source import media_source_id
from .settings import AnnounceSettings, async_check_allowed_file

_LOGGER = logging.getLogger(__name__)

PLAYING_STATES = {STATE_PLAYING, STATE_BUFFERING}
RESUMABLE_PREFIXES = ("http://", "https://", "media-source://")
ALEXA_DEVICE_NOTIFY_PLATFORM = "alexa_devices"
ALEXA_MEDIA_PLATFORM = "alexa_media"


def _unlink_announcements(items: list[Announcement]) -> None:
    """Delete announcement audio files from disk (blocking I/O)."""
    for item in items:
        item.path.unlink(missing_ok=True)
        if item.alexa_path is not None:
            item.alexa_path.unlink(missing_ok=True)


class QuietHoursError(HomeAssistantError):
    """Raised when quiet hours skip every selected speaker."""

    def __init__(self) -> None:
        """Initialize with translation key."""
        super().__init__(translation_domain=DOMAIN, translation_key="quiet_hours")


@dataclass
class Announcement:
    """One recorded message, encoded and ready to play."""

    id: str
    path: Path
    duration: float
    created: float
    source: str
    user_id: str | None = None
    targets: list[str] = field(default_factory=list)
    alexa_path: Path | None = None

    @property
    def url_path(self) -> str:
        """Return the path the speakers download the audio from."""
        return f"{API_AUDIO}/{self.id}.mp3"

    @property
    def alexa_url_path(self) -> str:
        """Return the path Alexa speakers download the 48 kbps audio from."""
        return f"{API_AUDIO}/{self.id}{ALEXA_AUDIO_SUFFIX}"

    def as_dict(self) -> dict[str, Any]:
        """Return a summary for the frontend."""
        return {
            "id": self.id,
            "duration": round(self.duration, 2),
            "created": self.created,
            "source": self.source,
            "targets": self.targets,
        }


@dataclass(frozen=True)
class _PlaybackSnapshot:
    """Resumable media playing on a non-announce speaker before an announcement."""

    content_id: str
    content_type: str
    position: float | None = None
    can_seek: bool = False


@dataclass
class PlayOptions:
    """How to play one announcement."""

    volume: float | None  # 0..1, None keeps the speaker's volume
    title: str = "Announcement"
    # Players with an announcement volume of their own get the volume there,
    # so the volume of the music is never touched
    announce_volume: bool = True
    resume_playback: bool = False
    alexa_support: bool = False


class Announcer:
    """Encode recordings and play them on media players."""

    def __init__(self, hass: HomeAssistant, ffmpeg_binary: str) -> None:
        """Initialize."""
        self.hass = hass
        self.ffmpeg_binary = ffmpeg_binary
        self._dir: Path | None = None
        self._items: OrderedDict[str, Announcement] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}
        self._alexa_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()
        self.last: Announcement | None = None

    async def async_start(self) -> None:
        """Create the folder that holds the audio files."""
        self._dir = Path(
            await self.hass.async_add_executor_job(
                lambda: tempfile.mkdtemp(prefix="hannounce_")
            )
        )

    async def async_stop(self) -> None:
        """Cancel playback waiters and remove the files."""
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._items.clear()
        if self._dir is not None:
            await self.hass.async_add_executor_job(
                shutil.rmtree, self._dir, True
            )
            self._dir = None

    @property
    def folder(self) -> Path:
        """Return the working folder."""
        if self._dir is None:
            raise HomeAssistantError("Announcer is not started")
        return self._dir

    def new_id(self) -> str:
        """Return a new random id, also used as unguessable file name."""
        return secrets.token_urlsafe(16)

    # Encoding

    async def async_create(
        self,
        source: Path,
        settings: AnnounceSettings,
        *,
        source_kind: str,
        user_id: str | None = None,
        raw_pcm_rate: int | None = None,
        chime: str | None = None,
        min_voice_seconds: float = audio.MIN_VOICE_SECONDS,
    ) -> Announcement:
        """Encode a recording into an announcement and keep it for a while."""
        chosen_chime = chime if chime is not None else settings.chime
        custom_chime_path: Path | None = None
        if chosen_chime == CHIME_CUSTOM:
            if not settings.custom_chime:
                raise audio.AudioError("Custom chime is not configured")
            path_error = await async_check_allowed_file(
                self.hass, settings.custom_chime
            )
            if path_error == "path_not_allowed":
                raise audio.AudioError("Custom chime path is not allowed")
            if path_error == "file_not_found":
                raise audio.AudioError("Custom chime file not found")
            custom_chime_path = Path(settings.custom_chime)
        announcement_id = self.new_id()
        target = self.folder / f"{announcement_id}.mp3"
        rendered = await audio.async_render(
            self.hass.async_add_executor_job,
            self.ffmpeg_binary,
            source,
            target,
            chime=chosen_chime,
            normalize=settings.normalize,
            max_duration=settings.max_duration,
            voice_enhancement=settings.voice_enhancement,
            raw_pcm_rate=raw_pcm_rate,
            custom_chime=custom_chime_path,
            min_voice_seconds=min_voice_seconds,
        )
        announcement = Announcement(
            id=announcement_id,
            path=rendered.path,
            duration=rendered.duration,
            created=time.time(),
            source=source_kind,
            user_id=user_id,
        )
        self._items[announcement_id] = announcement
        await self._async_prune()
        return announcement

    def get(self, announcement_id: str) -> Announcement | None:
        """Return an announcement that is still kept."""
        announcement = self._items.get(announcement_id)
        if announcement and time.time() - announcement.created > ANNOUNCEMENT_TTL:
            return None
        return announcement

    async def _async_prune(self) -> None:
        """Drop announcements that are too old or too many."""
        now = time.time()
        drop = [
            item
            for item in self._items.values()
            if now - item.created > ANNOUNCEMENT_TTL
        ]
        overflow = len(self._items) - len(drop) - MAX_ANNOUNCEMENTS
        if overflow > 0:
            drop += [item for item in self._items.values() if item not in drop][
                :overflow
            ]
        for item in drop:
            self._items.pop(item.id, None)
            if self.last is item:
                self.last = None
        if drop:
            await self.hass.async_add_executor_job(_unlink_announcements, drop)

    # Playback

    def check_url(self) -> str:
        """Return the URL of Home Assistant the speakers download from, or raise."""
        try:
            return get_url(self.hass)
        except NoURLAvailableError as err:
            raise HomeAssistantError(
                "Home Assistant has no URL the speakers can reach. "
                "Set a local URL in Settings > System > Network."
            ) from err

    def check_external_https_url(self) -> str:
        """Return the external HTTPS URL required by Amazon Alexa, or raise."""
        try:
            return get_url(
                self.hass, allow_internal=False, allow_ip=False, require_ssl=True
            )
        except NoURLAvailableError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="external_https_required",
            ) from err

    def signed_url(self, announcement: Announcement) -> str:
        """Return an absolute URL the speakers can open without a login."""
        path = async_sign_path(
            self.hass,
            announcement.url_path,
            timedelta(seconds=ANNOUNCEMENT_TTL),
            use_content_user=True,
        )
        return f"{self.check_url()}{path}"

    def alexa_signed_url(self, announcement: Announcement) -> str:
        """Return an external HTTPS signed URL for Amazon Alexa SSML playback."""
        path = async_sign_path(
            self.hass,
            announcement.alexa_url_path,
            timedelta(seconds=ANNOUNCEMENT_TTL),
            use_content_user=True,
        )
        return f"{self.check_external_https_url()}{path}"

    def check_delivery(self, targets: list[str], *, alexa_support: bool) -> None:
        """Ensure URLs and options allow delivering the message to every target."""
        has_alexa = False
        has_standard = False
        for entity_id in targets:
            if self._platform(entity_id) in ALEXA_PLATFORMS:
                has_alexa = True
            else:
                has_standard = True
        if has_alexa:
            if not alexa_support:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="alexa_disabled"
                )
            self.check_external_https_url()
        if has_standard:
            self.check_url()

    def recent(self) -> list[Announcement]:
        """Return the messages still kept, newest first."""
        return [
            item
            for item in reversed(self._items.values())
            if self.get(item.id) is not None
        ]

    def check_targets(self, targets: list[str]) -> list[str]:
        """Return the targets that exist, raise if none."""
        valid = [
            entity_id
            for entity_id in dict.fromkeys(targets)
            if entity_id.startswith(f"{MEDIA_PLAYER_DOMAIN}.")
            and (state := self.hass.states.get(entity_id)) is not None
            and state.state != STATE_UNAVAILABLE
        ]
        if not valid:
            raise HomeAssistantError("None of the chosen speakers is available")
        return valid

    @callback
    def async_play(
        self,
        announcement: Announcement,
        targets: list[str],
        options: PlayOptions,
        *,
        speaker_volumes: dict[str, float | None] | None = None,
    ) -> list[str]:
        """Start playing on every target, return the targets used."""
        targets = self.check_targets(targets)
        self.check_delivery(targets, alexa_support=options.alexa_support)
        announcement.targets = targets
        self.last = announcement
        for entity_id in targets:
            play_options = options
            if speaker_volumes is not None and entity_id in speaker_volumes:
                play_options = replace(options, volume=speaker_volumes[entity_id])
            task = self.hass.async_create_background_task(
                self._async_play_on(entity_id, announcement, play_options),
                f"hannounce play {entity_id}",
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        self.hass.bus.async_fire(
            EVENT_ANNOUNCED,
            {
                "id": announcement.id,
                "targets": targets,
                "duration": round(announcement.duration, 2),
                "source": announcement.source,
                "user_id": announcement.user_id,
            },
        )
        return targets

    def _platform(self, entity_id: str) -> str | None:
        """Return the integration of a media player."""
        registry_entry = er.async_get(self.hass).async_get(entity_id)
        return registry_entry.platform if registry_entry else None

    def _announce_volume_extra(
        self, entity_id: str, options: PlayOptions
    ) -> dict[str, Any] | None:
        """Return the extra data that sets the announcement volume, if the player has one."""
        if options.volume is None or not options.announce_volume:
            return None
        spec = ANNOUNCE_VOLUME_EXTRA.get(self._platform(entity_id) or "")
        state = self.hass.states.get(entity_id)
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0) if state else 0
        if spec is None or not features & MediaPlayerEntityFeature.MEDIA_ANNOUNCE:
            return None
        key, scale = spec
        value = options.volume * scale
        return {key: round(value) if scale == 100 else round(value, 2)}

    def _media_args(
        self,
        entity_id: str,
        announcement: Announcement,
        title: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the play_media data that suits the speaker's integration.

        Integrations that know media sources get the message the way they get
        text-to-speech, and convert it for their device themselves. Others, such
        as custom integrations, get a signed URL.
        """
        platform = self._platform(entity_id)
        state = self.hass.states.get(entity_id)
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0) if state else 0
        if platform in MEDIA_SOURCE_PLATFORMS:
            media_id = media_source_id(announcement.id)
        else:
            media_id = self.signed_url(announcement)
        data: dict[str, Any] = {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_CONTENT_ID: media_id,
            ATTR_MEDIA_CONTENT_TYPE: "music",
        }
        extra = dict(extra or {})
        if platform == "cast":
            # The Cast default receiver shows this title, on a Nest Hub for one
            extra["metadata"] = {"metadataType": 0, "title": title}
        if extra:
            data[ATTR_MEDIA_EXTRA] = extra
        if features & MediaPlayerEntityFeature.MEDIA_ANNOUNCE:
            # Played over the music, which then resumes (Sonos, ESPHome, ...)
            data[ATTR_MEDIA_ANNOUNCE] = True
        return data

    async def _async_ensure_alexa_audio(self, announcement: Announcement) -> Path:
        """Transcode the announcement once into Alexa SSML CBR MP3 format."""
        async with self._alexa_lock:
            if announcement.alexa_path is not None:
                return announcement.alexa_path
            target = self.folder / f"{announcement.id}{ALEXA_AUDIO_SUFFIX}"
            try:
                await audio.async_render_alexa(
                    self.ffmpeg_binary, announcement.path, target
                )
            except audio.AudioError as err:
                raise HomeAssistantError(
                    f"Could not encode audio for Alexa: {err}"
                ) from err
            announcement.alexa_path = target
            return target

    def _alexa_notify_entity(self, entity_id: str) -> str | None:
        """Find the sibling notify entity (_speak preferred, fallback _announce) for alexa_devices."""
        registry = er.async_get(self.hass)
        entry = registry.async_get(entity_id)
        if entry is None or entry.device_id is None:
            return None
        candidates = [
            item
            for item in er.async_entries_for_device(registry, entry.device_id)
            if item.domain == NOTIFY_DOMAIN
            and item.platform == ALEXA_DEVICE_NOTIFY_PLATFORM
            and not item.disabled
        ]
        if not candidates:
            return None

        def rank(item: er.RegistryEntry) -> tuple[int, int]:
            state = self.hass.states.get(item.entity_id)
            unavailable = (
                1 if state is None or state.state == STATE_UNAVAILABLE else 0
            )
            if item.translation_key == "speak" or item.unique_id.endswith("-speak"):
                return (unavailable, 0)
            if item.translation_key == "announce" or item.unique_id.endswith(
                "-announce"
            ):
                return (unavailable, 1)
            return (unavailable, 2)

        candidates.sort(key=rank)
        return candidates[0].entity_id

    async def _async_play_alexa(
        self, entity_id: str, platform: str, announcement: Announcement
    ) -> None:
        """Deliver an announcement to an Alexa speaker via SSML <audio>."""
        await self._async_ensure_alexa_audio(announcement)
        url = self.alexa_signed_url(announcement)
        ssml = f'<audio src="{html.escape(url, quote=True)}"/>'
        if platform == ALEXA_DEVICE_NOTIFY_PLATFORM:
            notify_entity = self._alexa_notify_entity(entity_id)
            if notify_entity is None:
                raise HomeAssistantError(
                    f"No Alexa notify entity found for {entity_id}"
                )
            await self.hass.services.async_call(
                NOTIFY_DOMAIN,
                SERVICE_SEND_MESSAGE,
                {
                    ATTR_ENTITY_ID: notify_entity,
                    NOTIFY_ATTR_MESSAGE: ssml,
                },
                blocking=True,
            )
            return
        await self.hass.services.async_call(
            NOTIFY_DOMAIN,
            ALEXA_MEDIA_PLATFORM,
            {
                "target": [entity_id],
                NOTIFY_ATTR_MESSAGE: ssml,
                "data": {"type": "tts"},
            },
            blocking=True,
        )

    async def _async_wait_alexa(self, announcement: Announcement) -> None:
        """Wait for an Alexa SSML clip to finish before restoring volume."""
        wait_seconds = (
            min(announcement.duration, ALEXA_MAX_DURATION) + ALEXA_PLAYBACK_BUFFER
        )
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

    def _capture_resume_snapshot(
        self,
        state,
        features: int,
        platform: str | None,
        options: PlayOptions,
    ) -> _PlaybackSnapshot | None:
        """Capture resumable URL/media-source playback on non-announce speakers."""
        if (
            not options.resume_playback
            or platform in ALEXA_PLATFORMS
            or features & MediaPlayerEntityFeature.MEDIA_ANNOUNCE
            or not (features & MediaPlayerEntityFeature.PLAY_MEDIA)
            or state.state != STATE_PLAYING
        ):
            return None
        content_id = state.attributes.get(ATTR_MEDIA_CONTENT_ID)
        if (
            not isinstance(content_id, str)
            or not content_id.startswith(RESUMABLE_PREFIXES)
            or API_AUDIO in content_id
            or content_id.startswith(f"media-source://{DOMAIN}/")
        ):
            return None
        content_type = str(state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) or "music")
        raw_duration = state.attributes.get(ATTR_MEDIA_DURATION)
        duration = (
            float(raw_duration)
            if isinstance(raw_duration, (int, float)) and raw_duration > 0
            else None
        )
        position: float | None = None
        raw_position = state.attributes.get(ATTR_MEDIA_POSITION)
        if (
            duration is not None
            and isinstance(raw_position, (int, float))
            and raw_position >= 0
        ):
            estimated = float(raw_position)
            updated_at = state.attributes.get(ATTR_MEDIA_POSITION_UPDATED_AT)
            if isinstance(updated_at, datetime):
                elapsed = max(
                    0.0,
                    (dt_util.utcnow() - dt_util.as_utc(updated_at)).total_seconds(),
                )
                estimated += elapsed
            estimated = min(estimated, max(0.0, duration - 1.0))
            if estimated >= 1.0:
                position = round(estimated, 2)
        return _PlaybackSnapshot(
            content_id=content_id,
            content_type=content_type,
            position=position,
            can_seek=bool(features & MediaPlayerEntityFeature.SEEK),
        )

    async def _async_resume_playback(
        self,
        entity_id: str,
        announcement: Announcement,
        snapshot: _PlaybackSnapshot,
    ) -> None:
        """Best-effort resume of a URL/media-source track after volume is restored."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_OFF):
            return
        current_content = state.attributes.get(ATTR_MEDIA_CONTENT_ID)
        if (
            state.state in PLAYING_STATES
            and current_content
            and announcement.id not in str(current_content)
        ):
            _LOGGER.debug(
                "Media on %s changed during the message, skipping resume", entity_id
            )
            return
        try:
            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_PLAY_MEDIA,
                {
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_MEDIA_CONTENT_ID: snapshot.content_id,
                    ATTR_MEDIA_CONTENT_TYPE: snapshot.content_type,
                },
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Could not resume playback on %s: %s", entity_id, err)
            return
        if snapshot.position is not None and snapshot.can_seek:
            try:
                await self.hass.services.async_call(
                    MEDIA_PLAYER_DOMAIN,
                    SERVICE_MEDIA_SEEK,
                    {
                        ATTR_ENTITY_ID: entity_id,
                        ATTR_MEDIA_SEEK_POSITION: snapshot.position,
                    },
                    blocking=True,
                )
            except HomeAssistantError as err:
                _LOGGER.debug(
                    "Could not seek resumed playback on %s: %s", entity_id, err
                )

    async def _async_play_on(
        self,
        entity_id: str,
        announcement: Announcement,
        options: PlayOptions,
    ) -> None:
        """Play on one speaker, one message at a time, then restore volume and mute."""
        lock = self._locks.setdefault(entity_id, asyncio.Lock())
        async with lock:
            state = self.hass.states.get(entity_id)
            if state is None or state.state == STATE_UNAVAILABLE:
                _LOGGER.warning("%s is not available, message skipped", entity_id)
                return
            features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
            platform = self._platform(entity_id)
            is_alexa = platform in ALEXA_PLATFORMS
            previous_volume = state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL)
            previous_muted = state.attributes.get(ATTR_MEDIA_VOLUME_MUTED)
            changed_volume = False
            unmuted = False
            played = False
            extra = self._announce_volume_extra(entity_id, options)
            resume_snapshot = self._capture_resume_snapshot(
                state, features, platform, options
            )
            try:
                if (
                    extra is None
                    and options.volume is not None
                    and features & MediaPlayerEntityFeature.VOLUME_SET
                    and (
                        previous_volume is None
                        or abs(previous_volume - options.volume) > 0.005
                    )
                ):
                    await self.hass.services.async_call(
                        MEDIA_PLAYER_DOMAIN,
                        SERVICE_VOLUME_SET,
                        {
                            ATTR_ENTITY_ID: entity_id,
                            ATTR_MEDIA_VOLUME_LEVEL: options.volume,
                        },
                        blocking=True,
                    )
                    changed_volume = previous_volume is not None
                if (
                    extra is None
                    and previous_muted is True
                    and features & MediaPlayerEntityFeature.VOLUME_MUTE
                ):
                    await self.hass.services.async_call(
                        MEDIA_PLAYER_DOMAIN,
                        SERVICE_VOLUME_MUTE,
                        {
                            ATTR_ENTITY_ID: entity_id,
                            ATTR_MEDIA_VOLUME_MUTED: False,
                        },
                        blocking=True,
                    )
                    unmuted = True
                if is_alexa and platform is not None:
                    await self._async_play_alexa(entity_id, platform, announcement)
                    played = True
                    await self._async_wait_alexa(announcement)
                else:
                    await self.hass.services.async_call(
                        MEDIA_PLAYER_DOMAIN,
                        SERVICE_PLAY_MEDIA,
                        self._media_args(entity_id, announcement, options.title, extra),
                        blocking=True,
                    )
                    played = True
                    await self._async_wait_playback(entity_id, announcement)
            except HomeAssistantError as err:
                _LOGGER.error("Could not play the message on %s: %s", entity_id, err)
            finally:
                volume_overridden = False
                if changed_volume:
                    volume_overridden = not await self._async_restore_volume(
                        entity_id, previous_volume, options.volume
                    )
                if unmuted and not volume_overridden:
                    await self._async_restore_mute(entity_id)
                if played and resume_snapshot is not None:
                    await self._async_resume_playback(
                        entity_id, announcement, resume_snapshot
                    )

    async def _async_restore_volume(
        self, entity_id: str, volume: float, ours: float | None
    ) -> bool:
        """Put the volume back as it was before the message.

        If someone changed the volume during the message, theirs wins and False is returned.
        """
        state = self.hass.states.get(entity_id)
        current = state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) if state else None
        if current is not None and ours is not None and abs(current - ours) > 0.02:
            _LOGGER.debug(
                "Volume of %s changed during the message, not restored", entity_id
            )
            return False
        try:
            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_VOLUME_SET,
                {ATTR_ENTITY_ID: entity_id, ATTR_MEDIA_VOLUME_LEVEL: volume},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Could not restore the volume of %s: %s", entity_id, err)
        return True

    async def _async_restore_mute(self, entity_id: str) -> None:
        """Re-mute a speaker that was muted before the message."""
        state = self.hass.states.get(entity_id)
        if state and state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is True:
            return
        try:
            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_VOLUME_MUTE,
                {ATTR_ENTITY_ID: entity_id, ATTR_MEDIA_VOLUME_MUTED: True},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Could not restore mute state of %s: %s", entity_id, err)

    async def _async_wait_playback(
        self, entity_id: str, announcement: Announcement
    ) -> None:
        """Wait until the speaker has played the message, or gave up."""
        loop = asyncio.get_running_loop()
        started_at = loop.time()
        seen_playing = False
        finished = False
        changed = asyncio.Event()

        def is_ours(state) -> bool:
            content = state.attributes.get(ATTR_MEDIA_CONTENT_ID)
            # Players that don't report the content are trusted
            return not content or announcement.id in str(content)

        @callback
        def on_change(event: Event[EventStateChangedData]) -> None:
            nonlocal seen_playing, finished
            new_state = event.data["new_state"]
            if new_state is None:
                finished = True
            elif new_state.state in PLAYING_STATES and is_ours(new_state):
                seen_playing = True
            elif seen_playing:
                finished = True
            changed.set()

        unsub = async_track_state_change_event(self.hass, [entity_id], on_change)
        try:
            state = self.hass.states.get(entity_id)
            if state and state.state in PLAYING_STATES and is_ours(state):
                seen_playing = True
            while not finished:
                now = loop.time()
                if not seen_playing:
                    deadline = started_at + PLAYBACK_START_TIMEOUT
                    if now >= deadline:
                        # The player never said it played: wait for the length
                        remaining = started_at + announcement.duration + 1 - now
                        if remaining > 0:
                            await asyncio.sleep(remaining)
                        return
                else:
                    deadline = (
                        started_at
                        + PLAYBACK_START_TIMEOUT
                        + announcement.duration
                        + PLAYBACK_END_GRACE
                    )
                    if now >= deadline:
                        return
                changed.clear()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(changed.wait(), deadline - now)
        finally:
            unsub()

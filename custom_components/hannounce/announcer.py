"""Store announcements and play them on the speakers."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
import shutil
import tempfile
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    SERVICE_PLAY_MEDIA,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_BUFFERING,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.network import NoURLAvailableError, get_url

from . import audio
from .const import (
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

    @property
    def url_path(self) -> str:
        """Return the path the speakers download the audio from."""
        return f"{API_AUDIO}/{self.id}.mp3"

    def as_dict(self) -> dict[str, Any]:
        """Return a summary for the frontend."""
        return {
            "id": self.id,
            "duration": round(self.duration, 2),
            "created": self.created,
            "source": self.source,
            "targets": self.targets,
        }


@dataclass
class PlayOptions:
    """How to play one announcement."""

    volume: float | None  # 0..1, None keeps the speaker's volume
    title: str = "Announcement"
    # Players with an announcement volume of their own get the volume there,
    # so the volume of the music is never touched
    announce_volume: bool = True


class Announcer:
    """Encode recordings and play them on media players."""

    def __init__(self, hass: HomeAssistant, ffmpeg_binary: str) -> None:
        """Initialize."""
        self.hass = hass
        self.ffmpeg_binary = ffmpeg_binary
        self._dir: Path | None = None
        self._items: OrderedDict[str, Announcement] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}
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
            await self.hass.async_add_executor_job(
                lambda: [item.path.unlink(missing_ok=True) for item in drop]
            )

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

    def signed_url(self, announcement: Announcement) -> str:
        """Return an absolute URL the speakers can open without a login."""
        path = async_sign_path(
            self.hass,
            announcement.url_path,
            timedelta(seconds=ANNOUNCEMENT_TTL),
            use_content_user=True,
        )
        return f"{self.check_url()}{path}"

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
        announcement.targets = targets
        self.last = announcement
        self.check_url()
        for entity_id in targets:
            play_options = options
            if speaker_volumes is not None and entity_id in speaker_volumes:
                play_options = PlayOptions(
                    volume=speaker_volumes[entity_id],
                    title=options.title,
                    announce_volume=options.announce_volume,
                )
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
            previous_volume = state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL)
            previous_muted = state.attributes.get(ATTR_MEDIA_VOLUME_MUTED)
            changed_volume = False
            unmuted = False
            extra = self._announce_volume_extra(entity_id, options)
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
                await self.hass.services.async_call(
                    MEDIA_PLAYER_DOMAIN,
                    SERVICE_PLAY_MEDIA,
                    self._media_args(entity_id, announcement, options.title, extra),
                    blocking=True,
                )
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

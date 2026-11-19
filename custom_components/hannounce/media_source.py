"""Recent messages as a media source.

Speakers get media-source://hannounce/<id>.mp3, like text-to-speech gives them
media-source://tts/...: each media player integration resolves it and turns it
into what its device needs (a signed URL, a proxy, a MIME type). The messages
of the last hour also show in the Media panel.
"""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN

MIME_TYPE = "audio/mpeg"


async def async_get_media_source(hass: HomeAssistant) -> HannounceMediaSource:
    """Set up the media source."""
    return HannounceMediaSource(hass)


def media_source_id(announcement_id: str) -> str:
    """Return the media source id of a message."""
    return f"media-source://{DOMAIN}/{announcement_id}.mp3"


class HannounceMediaSource(MediaSource):
    """The messages kept by the integration."""

    name = "HA-nnounce"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        super().__init__(DOMAIN)
        self.hass = hass

    def _runtime(self):
        return self.hass.data.get(DOMAIN)

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Return the URL of a message."""
        runtime = self._runtime()
        announcement = (
            runtime.announcer.get(item.identifier.removesuffix(".mp3"))
            if runtime and item.identifier
            else None
        )
        if announcement is None:
            raise Unresolvable("This message is no longer available")
        return PlayMedia(announcement.url_path, MIME_TYPE)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """List the messages of the last hour, newest first."""
        if item.identifier:
            raise BrowseError("Only the list of messages can be browsed")
        runtime = self._runtime()
        children = []
        for announcement in runtime.announcer.recent() if runtime else []:
            when = dt_util.as_local(datetime.fromtimestamp(announcement.created, dt_util.UTC))
            names = ", ".join(runtime.speaker_name(entity_id) for entity_id in announcement.targets)
            title = f"{when:%H:%M} · {round(announcement.duration)} s"
            if names:
                title = f"{title} · {names}"
            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{announcement.id}.mp3",
                    media_class=MediaClass.MUSIC,
                    media_content_type=MIME_TYPE,
                    title=title,
                    can_play=True,
                    can_expand=False,
                )
            )
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=self.name,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.MUSIC,
            children=children,
        )

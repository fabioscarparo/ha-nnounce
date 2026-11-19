"""Constants for HA-nnounce."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "hannounce"

# Options
CONF_SPEAKERS: Final = "speakers"
CONF_SET_VOLUME: Final = "set_volume"
CONF_VOLUME: Final = "volume"
CONF_CHIME: Final = "chime"
CONF_NORMALIZE: Final = "normalize"
CONF_MAX_DURATION: Final = "max_duration"
CONF_SHOW_PANEL: Final = "show_panel"
CONF_INTERCOM: Final = "intercom"
CONF_ANNOUNCE_VOLUME: Final = "announce_volume"

DEFAULT_SET_VOLUME: Final = True
DEFAULT_VOLUME: Final = 60
DEFAULT_CHIME: Final = "ding_dong"
DEFAULT_NORMALIZE: Final = True
DEFAULT_MAX_DURATION: Final = 60
DEFAULT_SHOW_PANEL: Final = True
DEFAULT_INTERCOM: Final = False
DEFAULT_ANNOUNCE_VOLUME: Final = True

CHIME_NONE: Final = "none"
CHIMES: Final = ("none", "ding_dong", "soft", "three_tone")

MAX_UPLOAD_BYTES: Final = 15 * 1024 * 1024
MIN_DURATION: Final = 2  # lower bound of the max duration option, seconds
MAX_DURATION_LIMIT: Final = 300

# Kept in memory and on a temporary disk folder, then removed
ANNOUNCEMENT_TTL: Final = 3600
MAX_ANNOUNCEMENTS: Final = 20

# Waiting for the speaker while it plays
PLAYBACK_START_TIMEOUT: Final = 12
PLAYBACK_END_GRACE: Final = 6

# URLs
API_ANNOUNCE: Final = "/api/hannounce/announce"
API_AUDIO: Final = "/api/hannounce/audio"
STATIC_URL: Final = "/hannounce_static"
FRONTEND_FILE: Final = "hannounce.js"
PANEL_URL_PATH: Final = "hannounce"
PANEL_ELEMENT: Final = "hannounce-panel"

# Intercom (two-way audio camera, Home Assistant Labs)
INTERCOM_REQUIREMENT: Final = "aiortc==1.16.0"
INTERCOM_BROADCAST: Final = "broadcast"
ROUTE_TTL: Final = 120
INTERCOM_GAP: Final = 0.8  # seconds without audio that close one message

EVENT_ANNOUNCED: Final = f"{DOMAIN}_announced"

# Media player integrations of Home Assistant that play audio from a URL and
# resolve media sources (they call async_process_play_media_url). The group
# integration passes the message on to its members.
MEDIA_SOURCE_PLATFORMS: Final = frozenset(
    {
        "apple_tv",
        "bang_olufsen",
        "bluesound",
        "cast",
        "dlna_dmr",
        "dunehd",
        "esphome",
        "forked_daapd",
        "fully_kiosk",
        "group",
        "heos",
        "kodi",
        "linkplay",
        "mpd",
        "music_assistant",
        "openhome",
        "panasonic_viera",
        "roku",
        "slimproto",
        "sonos",
        "soundtouch",
        "squeezebox",
        "unifiprotect",
        "vlc_telnet",
        "wiim",
        "yamaha_musiccast",
    }
)

SERVICE_ANNOUNCE: Final = "announce"
SERVICE_REPLAY: Final = "replay"

ATTR_FILE: Final = "file"
ATTR_URL: Final = "url"

# Players whose announcement mode has a volume of its own: the key in the extra
# data of play_media, and the scale of the value (100 for 0..100, 1 for 0..1)
ANNOUNCE_VOLUME_EXTRA: Final[dict[str, tuple[str, int]]] = {
    "bang_olufsen": ("overlay_absolute_volume", 100),
    "music_assistant": ("announce_volume", 100),
    "sonos": ("volume", 100),
    "squeezebox": ("announce_volume", 1),
}

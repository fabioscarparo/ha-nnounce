"""Constants for HA-nnounce."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "hannounce"

# Options
CONF_SPEAKERS: Final = "speakers"
CONF_SET_VOLUME: Final = "set_volume"
CONF_VOLUME: Final = "volume"
CONF_CHIME: Final = "chime"
CONF_CUSTOM_CHIME: Final = "custom_chime"
CONF_NORMALIZE: Final = "normalize"
CONF_VOICE_ENHANCEMENT: Final = "voice_enhancement"
CONF_MAX_DURATION: Final = "max_duration"
CONF_SHOW_PANEL: Final = "show_panel"
CONF_INTERCOM: Final = "intercom"
CONF_ANNOUNCE_VOLUME: Final = "announce_volume"
CONF_TTS_ENTITY: Final = "tts_entity"
CONF_QUIET_HOURS: Final = "quiet_hours"
CONF_QUIET_START: Final = "quiet_start"
CONF_QUIET_END: Final = "quiet_end"
CONF_QUIET_MODE: Final = "quiet_mode"
CONF_QUIET_VOLUME: Final = "quiet_volume"
CONF_QUIET_SPEAKERS: Final = "quiet_speakers"
CONF_QUIET_ENTITY: Final = "quiet_entity"

DEFAULT_SET_VOLUME: Final = True
DEFAULT_VOLUME: Final = 60
DEFAULT_CHIME: Final = "ding_dong"
DEFAULT_CUSTOM_CHIME: Final = ""
DEFAULT_NORMALIZE: Final = True
DEFAULT_VOICE_ENHANCEMENT: Final = True
DEFAULT_MAX_DURATION: Final = 60
DEFAULT_SHOW_PANEL: Final = True
DEFAULT_INTERCOM: Final = False
DEFAULT_ANNOUNCE_VOLUME: Final = True
DEFAULT_TTS_ENTITY: Final = ""
DEFAULT_QUIET_HOURS: Final = False
DEFAULT_QUIET_START: Final = "22:00:00"
DEFAULT_QUIET_END: Final = "07:00:00"
DEFAULT_QUIET_MODE: Final = "cap_volume"
DEFAULT_QUIET_VOLUME: Final = 25

CHIME_NONE: Final = "none"
CHIME_CUSTOM: Final = "custom"
CHIMES: Final = ("none", "ding_dong", "soft", "three_tone")
ALL_CHIMES: Final = (*CHIMES, CHIME_CUSTOM)

QUIET_MODE_CAP: Final = "cap_volume"
QUIET_MODE_SKIP: Final = "skip"
QUIET_MODES: Final = (QUIET_MODE_CAP, QUIET_MODE_SKIP)

MAX_UPLOAD_BYTES: Final = 15 * 1024 * 1024
MAX_MESSAGE_LENGTH: Final = 1000
MAX_CUSTOM_CHIME_SECONDS: Final = 15.0
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
API_CHIME: Final = "/api/hannounce/chime"
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
ATTR_MESSAGE: Final = "message"
ATTR_TTS_ENTITY: Final = "tts_entity"
ATTR_LANGUAGE: Final = "language"
ATTR_FORCE: Final = "force"

# Players whose announcement mode has a volume of its own: the key in the extra
# data of play_media, and the scale of the value (100 for 0..100, 1 for 0..1)
ANNOUNCE_VOLUME_EXTRA: Final[dict[str, tuple[str, int]]] = {
    "bang_olufsen": ("overlay_absolute_volume", 100),
    "music_assistant": ("announce_volume", 100),
    "sonos": ("volume", 100),
    "squeezebox": ("announce_volume", 1),
}

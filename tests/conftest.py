"""Fixtures: speakers of several integrations, test audio and a set up integration."""

from __future__ import annotations

import asyncio
import math
import shutil
import struct
import wave
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_VOLUME_LEVEL,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry

from custom_components.hannounce.const import DOMAIN

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")

BASE_FEATURES = MediaPlayerEntityFeature.PLAY_MEDIA | MediaPlayerEntityFeature.VOLUME_SET
ANNOUNCE = MediaPlayerEntityFeature.MEDIA_ANNOUNCE

# entity_id: (integration, supported features, device class)
SPEAKERS: dict[str, tuple[str, int, str | None]] = {
    "media_player.kitchen": ("cast", BASE_FEATURES, None),
    "media_player.living_room": ("sonos", BASE_FEATURES | ANNOUNCE, "speaker"),
    "media_player.desk": ("esphome", BASE_FEATURES | ANNOUNCE, None),
    "media_player.garage": ("my_custom_player", BASE_FEATURES, None),
    "media_player.tv": ("cast", BASE_FEATURES, "tv"),
    "media_player.spotify": ("spotify", BASE_FEATURES, None),
}


@dataclass
class FakePlayers:
    """Media players that act like real ones: they play, then stop."""

    hass: HomeAssistant
    play_seconds: float = 0.1
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    timers: list[asyncio.TimerHandle] = field(default_factory=list)

    def calls_for(self, entity_id: str, service: str | None = None) -> list[dict[str, Any]]:
        """Return the service data sent to one player."""
        return [
            data
            for name, data in self.calls
            if data[ATTR_ENTITY_ID] == entity_id and (service is None or name == service)
        ]

    def set_volume(self, entity_id: str, volume: float) -> None:
        """Change the volume as a person would."""
        state = self.hass.states.get(entity_id)
        self.hass.states.async_set(
            entity_id, state.state, {**state.attributes, ATTR_MEDIA_VOLUME_LEVEL: volume}
        )


@pytest.fixture
async def players(hass: HomeAssistant) -> AsyncGenerator[FakePlayers]:
    """Create the speakers and answer the media player actions."""
    registry = er.async_get(hass)
    for entity_id, (platform, features, device_class) in SPEAKERS.items():
        object_id = entity_id.split(".", 1)[1]
        registry.async_get_or_create(
            MEDIA_PLAYER_DOMAIN,
            platform,
            f"unique_{object_id}",
            suggested_object_id=object_id,
            original_device_class=device_class,
            supported_features=features,
        )
        hass.states.async_set(
            entity_id,
            "idle",
            {
                ATTR_SUPPORTED_FEATURES: features,
                ATTR_MEDIA_VOLUME_LEVEL: 0.3,
                "friendly_name": object_id.replace("_", " ").title(),
            },
        )
    fake = FakePlayers(hass)

    async def volume_set(call: ServiceCall) -> None:
        for entity_id in _entity_ids(call):
            fake.calls.append(("volume_set", {**call.data, ATTR_ENTITY_ID: entity_id}))
            fake.set_volume(entity_id, call.data[ATTR_MEDIA_VOLUME_LEVEL])

    async def play_media(call: ServiceCall) -> None:
        for entity_id in _entity_ids(call):
            fake.calls.append(("play_media", {**call.data, ATTR_ENTITY_ID: entity_id}))
            state = hass.states.get(entity_id)
            attributes = {**state.attributes, ATTR_MEDIA_CONTENT_ID: call.data[ATTR_MEDIA_CONTENT_ID]}
            hass.states.async_set(entity_id, "playing", attributes)

            def stop(entity_id: str = entity_id) -> None:
                current = hass.states.get(entity_id)
                hass.states.async_set(entity_id, "idle", dict(current.attributes))

            fake.timers.append(hass.loop.call_later(fake.play_seconds, stop))

    # Set up media_player first, then answer its actions ourselves
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, MEDIA_PLAYER_DOMAIN, {})
    hass.services.async_register(MEDIA_PLAYER_DOMAIN, "volume_set", volume_set)
    hass.services.async_register(MEDIA_PLAYER_DOMAIN, "play_media", play_media)
    yield fake
    for timer in fake.timers:
        timer.cancel()


def _entity_ids(call: ServiceCall) -> list[str]:
    value = call.data[ATTR_ENTITY_ID]
    return [value] if isinstance(value, str) else list(value)


@pytest.fixture
def make_wav(tmp_path: Path) -> Callable[..., Path]:
    """Write a WAV file: a voice-like tone, or silence."""

    def make(name: str = "voice.wav", seconds: float = 1.5, silent: bool = False, rate: int = 16000) -> Path:
        path = tmp_path / name
        frames = bytearray()
        for i in range(int(seconds * rate)):
            t = i / rate
            # A tone that swells three times a second, like syllables
            value = 0 if silent else 0.5 * math.sin(2 * math.pi * 220 * t) * (0.6 + 0.4 * math.sin(2 * math.pi * 3 * t))
            frames += struct.pack("<h", int(value * 32767))
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(rate)
            handle.writeframes(bytes(frames))
        return path

    return make


DEFAULT_OPTIONS = {
    "speakers": [],
    "set_volume": True,
    "volume": 70,
    "announce_volume": True,
    "chime": "ding_dong",
    "normalize": True,
    "max_duration": 60,
    "show_panel": True,
    "intercom": False,
}


@pytest.fixture
def setup_integration(hass: HomeAssistant) -> Callable[..., Any]:
    """Set up the integration with some options."""

    async def setup(**options: Any) -> MockConfigEntry:
        hass.config.internal_url = "http://homeassistant.local:8123"
        entry = MockConfigEntry(domain=DOMAIN, title="HA-nnounce", data={}, options={**DEFAULT_OPTIONS, **options})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return setup


async def ws_call(client, message: dict[str, Any]) -> dict[str, Any]:
    """Send a command and return its result, skipping events of subscriptions."""
    await client.send_json_auto_id(message)
    while True:
        response = await client.receive_json()
        if response.get("id") == message["id"] and response["type"] == "result":
            return response

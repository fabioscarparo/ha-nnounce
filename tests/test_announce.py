"""Sending a recording and playing it on speakers of different integrations."""

import asyncio
import json
from pathlib import Path

import aiohttp
from homeassistant.core import HomeAssistant
from pytest_homeassistant.common import async_capture_events
from yarl import URL

from custom_components.hannounce.const import EVENT_ANNOUNCED

from .conftest import needs_ffmpeg

ALL = ["media_player.kitchen", "media_player.living_room", "media_player.desk", "media_player.garage"]


async def upload(client, wav: Path | None, **fields: str):
    data = aiohttp.FormData(default_to_multipart=True)
    if wav is not None:
        data.add_field("audio", wav.read_bytes(), filename=wav.name, content_type="audio/wav")  # noqa: ASYNC240
    for key, value in fields.items():
        data.add_field(key, value)
    response = await client.post("/api/hannounce/announce", data=data)
    if response.content_type != "application/json":
        return response.status, {}  # errors of Home Assistant itself, such as 401
    return response.status, await response.json()


@needs_ffmpeg
async def test_plays_on_every_kind_of_speaker(hass: HomeAssistant, players, setup_integration, hass_client, make_wav) -> None:
    await setup_integration()
    events = async_capture_events(hass, EVENT_ANNOUNCED)
    status, body = await upload(await hass_client(), make_wav(), targets=json.dumps(ALL))
    assert status == 200, body
    assert body["targets"] == ALL and body["source"] == "upload"
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(events) == 1 and events[0].data["id"] == body["id"]

    # Google Cast: media source, title for the Nest Hub, volume set and restored
    (play,) = players.calls_for("media_player.kitchen", "play_media")
    assert play["media_content_id"] == f"media-source://hannounce/{body['id']}.mp3"
    assert play["media_content_type"] == "music"
    assert play["extra"]["metadata"]["title"] == "Announcement"
    assert "announce" not in play
    assert [c["volume_level"] for c in players.calls_for("media_player.kitchen", "volume_set")] == [0.7, 0.3]

    # Sonos: announcement mode with its own volume, the music volume untouched
    (play,) = players.calls_for("media_player.living_room", "play_media")
    assert play["announce"] is True
    assert play["extra"] == {"volume": 70}
    assert players.calls_for("media_player.living_room", "volume_set") == []

    # ESPHome: announcement mode, no volume of its own, so set and restored
    (play,) = players.calls_for("media_player.desk", "play_media")
    assert play["announce"] is True and play["media_content_id"].startswith("media-source://hannounce/")
    assert [c["volume_level"] for c in players.calls_for("media_player.desk", "volume_set")] == [0.7, 0.3]

    # A custom integration gets a signed URL
    (play,) = players.calls_for("media_player.garage", "play_media")
    url = URL(play["media_content_id"])
    assert str(url.with_query(None)) == f"http://homeassistant.local:8123/api/hannounce/audio/{body['id']}.mp3"
    assert "authSig" in url.query


@needs_ffmpeg
async def test_announce_volume_option_off(hass: HomeAssistant, players, setup_integration, hass_client, make_wav) -> None:
    await setup_integration(announce_volume=False)
    status, _ = await upload(await hass_client(), make_wav(), targets="media_player.living_room")
    assert status == 200
    await hass.async_block_till_done(wait_background_tasks=True)
    (play,) = players.calls_for("media_player.living_room", "play_media")
    assert "extra" not in play
    assert [c["volume_level"] for c in players.calls_for("media_player.living_room", "volume_set")] == [0.7, 0.3]


@needs_ffmpeg
async def test_keep_volume(hass: HomeAssistant, players, setup_integration, hass_client, make_wav) -> None:
    await setup_integration()
    status, _ = await upload(await hass_client(), make_wav(), targets=json.dumps(ALL), volume="keep")
    assert status == 200
    await hass.async_block_till_done(wait_background_tasks=True)
    assert [name for name, _ in players.calls].count("volume_set") == 0
    (play,) = players.calls_for("media_player.living_room", "play_media")
    assert "extra" not in play


@needs_ffmpeg
async def test_volume_changed_during_message_is_kept(hass: HomeAssistant, players, setup_integration, hass_client, make_wav) -> None:
    await setup_integration()
    players.play_seconds = 0.6
    status, _ = await upload(await hass_client(), make_wav(), targets="media_player.garage", volume="50")
    assert status == 200
    await asyncio.sleep(0.3)
    players.set_volume("media_player.garage", 0.9)  # someone turns it up meanwhile
    await hass.async_block_till_done(wait_background_tasks=True)
    assert [c["volume_level"] for c in players.calls_for("media_player.garage", "volume_set")] == [0.5]
    assert hass.states.get("media_player.garage").attributes["volume_level"] == 0.9


@needs_ffmpeg
async def test_audio_needs_a_signature(hass: HomeAssistant, players, setup_integration, hass_client, hass_client_no_auth, make_wav) -> None:
    entry = await setup_integration()
    _, body = await upload(await hass_client(), make_wav(), targets="media_player.garage")
    announcement = entry.runtime_data.announcer.get(body["id"])
    signed = URL(entry.runtime_data.announcer.signed_url(announcement))

    anonymous = await hass_client_no_auth()
    response = await anonymous.get(signed.path_qs)
    assert response.status == 200
    assert response.headers["Content-Type"] == "audio/mpeg"
    assert len(await response.read()) == announcement.path.stat().st_size

    assert (await anonymous.get(f"/api/hannounce/audio/{body['id']}.mp3")).status == 401
    assert (await (await hass_client()).get("/api/hannounce/audio/unknown.mp3")).status == 404


@needs_ffmpeg
async def test_upload_errors(hass: HomeAssistant, players, setup_integration, hass_client, hass_client_no_auth, make_wav, tmp_path) -> None:
    await setup_integration()
    client = await hass_client()
    voice = make_wav()

    assert (await upload(client, None, targets="media_player.kitchen"))[1]["code"] == "no_audio"
    assert (await upload(client, voice, targets="[]"))[1]["code"] == "no_targets"
    assert (await upload(client, voice, targets="media_player.kitchen", chime="trumpet"))[0] == 400
    assert (await upload(client, voice, targets="media_player.kitchen", volume="loud"))[1]["code"] == "bad_request"
    assert (await upload(client, voice, targets="media_player.kitchen", volume="150"))[1]["code"] == "bad_request"
    assert (await upload(client, voice, targets="[not json"))[1]["code"] == "bad_request"
    assert (await upload(client, voice, targets='{"a": 1}'))[1]["code"] == "no_targets"

    status, body = await upload(client, make_wav("silence.wav", silent=True), targets="media_player.kitchen")
    assert (status, body["code"]) == (422, "no_voice")

    broken = tmp_path / "broken.webm"
    broken.write_bytes(b"not audio at all")
    status, body = await upload(client, broken, targets="media_player.kitchen")
    assert (status, body["code"]) == (422, "audio_error")

    hass.states.async_set("media_player.kitchen", "unavailable")
    status, body = await upload(client, voice, targets="media_player.kitchen")
    assert (status, body["code"]) == (400, "no_targets")

    anonymous = await hass_client_no_auth()
    assert (await upload(anonymous, voice, targets="media_player.desk"))[0] == 401
    assert players.calls == []


async def test_announce_volume_scales(hass: HomeAssistant, players, setup_integration) -> None:
    from homeassistant.helpers import entity_registry as er

    from custom_components.hannounce.announcer import PlayOptions

    from .conftest import ANNOUNCE, BASE_FEATURES

    entry = await setup_integration()
    registry = er.async_get(hass)
    for platform in ("squeezebox", "bang_olufsen", "music_assistant"):
        registry.async_get_or_create("media_player", platform, f"u_{platform}", suggested_object_id=platform)
        hass.states.async_set(f"media_player.{platform}", "idle", {"supported_features": BASE_FEATURES | ANNOUNCE})
    announcer = entry.runtime_data.announcer
    options = PlayOptions(volume=0.65)
    assert announcer._announce_volume_extra("media_player.squeezebox", options) == {"announce_volume": 0.65}
    assert announcer._announce_volume_extra("media_player.bang_olufsen", options) == {"overlay_absolute_volume": 65}
    assert announcer._announce_volume_extra("media_player.music_assistant", options) == {"announce_volume": 65}
    assert announcer._announce_volume_extra("media_player.kitchen", options) is None
    assert announcer._announce_volume_extra("media_player.squeezebox", PlayOptions(volume=None)) is None

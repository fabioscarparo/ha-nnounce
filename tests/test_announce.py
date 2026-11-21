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


@needs_ffmpeg
async def test_muted_speaker_is_unmuted_and_restored(
    hass: HomeAssistant, players, setup_integration, hass_client, make_wav
) -> None:
    await setup_integration()
    players.set_muted("media_player.kitchen", True)
    players.set_muted("media_player.living_room", True)

    status, _ = await upload(
        await hass_client(),
        make_wav(),
        targets=json.dumps(["media_player.kitchen", "media_player.living_room"]),
    )
    assert status == 200
    await hass.async_block_till_done(wait_background_tasks=True)

    # Cast: volume set, unmuted, played, volume restored, then re-muted last
    kitchen_seq = [
        (name, data)
        for name, data in players.calls
        if data["entity_id"] == "media_player.kitchen"
    ]
    assert [name for name, _ in kitchen_seq] == [
        "volume_set",
        "volume_mute",
        "play_media",
        "volume_set",
        "volume_mute",
    ]
    assert [c["is_volume_muted"] for c in players.calls_for("media_player.kitchen", "volume_mute")] == [
        False,
        True,
    ]
    assert hass.states.get("media_player.kitchen").attributes["is_volume_muted"] is True

    # Sonos with native announcement volume: mute state is left untouched
    assert players.calls_for("media_player.living_room", "volume_mute") == []


@needs_ffmpeg
async def test_muted_speaker_with_keep_volume_is_still_unmuted(
    hass: HomeAssistant, players, setup_integration, hass_client, make_wav
) -> None:
    await setup_integration()
    players.set_muted("media_player.desk", True)

    status, _ = await upload(
        await hass_client(), make_wav(), targets="media_player.desk", volume="keep"
    )
    assert status == 200
    await hass.async_block_till_done(wait_background_tasks=True)

    assert players.calls_for("media_player.desk", "volume_set") == []
    assert [c["is_volume_muted"] for c in players.calls_for("media_player.desk", "volume_mute")] == [
        False,
        True,
    ]
    assert hass.states.get("media_player.desk").attributes["is_volume_muted"] is True


@needs_ffmpeg
async def test_custom_chime_upload_and_preview(
    hass: HomeAssistant, players, setup_integration, hass_client, hass_client_no_auth, make_wav, tmp_path
) -> None:
    hass.config.allowlist_external_dirs = {str(tmp_path)}
    chime_file = make_wav("doorbell.wav", seconds=0.6)
    await setup_integration(custom_chime=str(chime_file))

    client = await hass_client()
    anonymous = await hass_client_no_auth()

    assert (await anonymous.get("/api/hannounce/chime")).status == 401
    preview = await client.get("/api/hannounce/chime")
    assert preview.status == 200
    assert await preview.read() == chime_file.read_bytes()

    status, body = await upload(client, make_wav("msg.wav"), targets="media_player.kitchen", chime="custom")
    assert status == 200, body
    assert body["targets"] == ["media_player.kitchen"]


@needs_ffmpeg
async def test_custom_chime_unconfigured_returns_404_and_400(
    hass: HomeAssistant, players, setup_integration, hass_client, make_wav
) -> None:
    await setup_integration()
    client = await hass_client()
    assert (await client.get("/api/hannounce/chime")).status == 404
    status, body = await upload(client, make_wav(), targets="media_player.kitchen", chime="custom")
    assert (status, body["code"]) == (400, "bad_request")


@needs_ffmpeg
async def test_quiet_hours_cap_volume(
    hass: HomeAssistant, players, setup_integration, hass_client, make_wav
) -> None:
    hass.states.async_set("input_boolean.sleep_mode", "on")
    await setup_integration(
        quiet_hours=True,
        quiet_start="00:00:00",
        quiet_end="00:00:00",
        quiet_mode="cap_volume",
        quiet_volume=25,
        quiet_speakers=["media_player.kitchen"],
        quiet_entity="input_boolean.sleep_mode",
    )
    players.set_volume("media_player.kitchen", 0.5)
    players.set_volume("media_player.desk", 0.3)

    status, _ = await upload(
        await hass_client(),
        make_wav(),
        targets=json.dumps(["media_player.kitchen", "media_player.desk"]),
        volume="70",
    )
    assert status == 200
    await hass.async_block_till_done(wait_background_tasks=True)

    # Kitchen is capped at 25% and restored to 50%; Desk plays at requested 70%
    assert [c["volume_level"] for c in players.calls_for("media_player.kitchen", "volume_set")] == [0.25, 0.5]
    assert [c["volume_level"] for c in players.calls_for("media_player.desk", "volume_set")] == [0.7, 0.3]

    # Even with volume="keep", a speaker above the cap is lowered to 25% and restored
    players.calls.clear()
    status, _ = await upload(
        await hass_client(),
        make_wav(),
        targets="media_player.kitchen",
        volume="keep",
    )
    assert status == 200
    await hass.async_block_till_done(wait_background_tasks=True)
    assert [c["volume_level"] for c in players.calls_for("media_player.kitchen", "volume_set")] == [0.25, 0.5]


@needs_ffmpeg
async def test_quiet_hours_skip_and_force(
    hass: HomeAssistant, players, setup_integration, hass_client, make_wav, tmp_path
) -> None:
    hass.config.allowlist_external_dirs = {str(tmp_path)}
    hass.states.async_set("input_boolean.sleep_mode", "on")
    await setup_integration(
        quiet_hours=True,
        quiet_start="00:00:00",
        quiet_end="00:00:00",
        quiet_mode="skip",
        quiet_speakers=["media_player.kitchen"],
        quiet_entity="input_boolean.sleep_mode",
    )
    client = await hass_client()

    # Partial skip: Kitchen is skipped, Desk plays
    status, body = await upload(
        client,
        make_wav(),
        targets=json.dumps(["media_player.kitchen", "media_player.desk"]),
    )
    assert status == 200
    assert body["targets"] == ["media_player.desk"]
    await hass.async_block_till_done(wait_background_tasks=True)
    assert players.calls_for("media_player.kitchen", "play_media") == []

    # Full skip: returns 422 quiet_hours
    status, body = await upload(client, make_wav(), targets="media_player.kitchen")
    assert (status, body["code"]) == (422, "quiet_hours")

    # Service call with force=True bypasses quiet hours
    response = await hass.services.async_call(
        "hannounce",
        "announce",
        {"entity_id": "media_player.kitchen", "file": str(make_wav()), "chime": "none", "force": True},
        blocking=True,
        return_response=True,
    )
    assert response["targets"] == ["media_player.kitchen"]


def test_quiet_time_window_logic() -> None:
    from datetime import time

    from custom_components.hannounce.settings import is_in_time_window

    # Overnight 22:00 -> 07:00
    assert is_in_time_window(time(22, 0), time(22, 0), time(7, 0)) is True
    assert is_in_time_window(time(23, 30), time(22, 0), time(7, 0)) is True
    assert is_in_time_window(time(6, 59), time(22, 0), time(7, 0)) is True
    assert is_in_time_window(time(7, 0), time(22, 0), time(7, 0)) is False
    assert is_in_time_window(time(15, 0), time(22, 0), time(7, 0)) is False

    # Same-day 13:00 -> 15:00
    assert is_in_time_window(time(14, 0), time(13, 0), time(15, 0)) is True
    assert is_in_time_window(time(12, 59), time(13, 0), time(15, 0)) is False
    assert is_in_time_window(time(15, 0), time(13, 0), time(15, 0)) is False

    # Equal bounds disable schedule
    assert is_in_time_window(time(0, 0), time(0, 0), time(0, 0)) is False

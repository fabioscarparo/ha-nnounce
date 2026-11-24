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


@needs_ffmpeg
async def test_resume_playback_stream_and_seek(
    hass: HomeAssistant, players, setup_integration, hass_client, make_wav
) -> None:
    from datetime import timedelta

    from homeassistant.components.media_player import MediaPlayerEntityFeature
    from homeassistant.util import dt as dt_util

    from .conftest import BASE_FEATURES

    await setup_integration(resume_playback=True)

    # Cast with SEEK playing a finite media-source track
    hass.states.async_set(
        "media_player.kitchen",
        "playing",
        {
            "supported_features": BASE_FEATURES | MediaPlayerEntityFeature.SEEK,
            "volume_level": 0.3,
            "media_content_id": "media-source://media_source/local/song.mp3",
            "media_content_type": "music",
            "media_duration": 180.0,
            "media_position": 42.0,
            "media_position_updated_at": dt_util.utcnow() - timedelta(seconds=3),
            "friendly_name": "Kitchen",
        },
    )
    # Custom player without SEEK playing a live radio stream (no duration)
    hass.states.async_set(
        "media_player.garage",
        "playing",
        {
            "supported_features": BASE_FEATURES,
            "volume_level": 0.3,
            "media_content_id": "https://radio.example.com/live.mp3",
            "media_content_type": "music",
            "friendly_name": "Garage",
        },
    )
    # Sonos with native MEDIA_ANNOUNCE playing a stream: must NOT manually resume
    sonos_state = hass.states.get("media_player.living_room")
    hass.states.async_set(
        "media_player.living_room",
        "playing",
        {
            **sonos_state.attributes,
            "media_content_id": "https://radio.example.com/jazz.mp3",
            "media_content_type": "music",
        },
    )

    status, _ = await upload(
        await hass_client(),
        make_wav(),
        targets=json.dumps(
            ["media_player.kitchen", "media_player.garage", "media_player.living_room"]
        ),
    )
    assert status == 200
    await hass.async_block_till_done(wait_background_tasks=True)

    # Kitchen: volume up -> announcement -> volume restored -> resume track -> seek
    kitchen_calls = [
        (name, data)
        for name, data in players.calls
        if data["entity_id"] == "media_player.kitchen"
    ]
    assert [name for name, _ in kitchen_calls] == [
        "volume_set",
        "play_media",
        "volume_set",
        "play_media",
        "media_seek",
    ]
    assert kitchen_calls[2][1]["volume_level"] == 0.3
    assert kitchen_calls[3][1]["media_content_id"] == "media-source://media_source/local/song.mp3"
    assert kitchen_calls[3][1]["media_content_type"] == "music"
    assert 44.0 <= kitchen_calls[4][1]["seek_position"] < 60.0

    # Garage: volume up -> announcement -> volume restored -> resume stream (no seek)
    garage_calls = [
        (name, data)
        for name, data in players.calls
        if data["entity_id"] == "media_player.garage"
    ]
    assert [name for name, _ in garage_calls] == [
        "volume_set",
        "play_media",
        "volume_set",
        "play_media",
    ]
    assert garage_calls[3][1]["media_content_id"] == "https://radio.example.com/live.mp3"

    # Sonos: native announce handles resume itself
    assert len(players.calls_for("media_player.living_room", "play_media")) == 1
    assert players.calls_for("media_player.living_room", "media_seek") == []


@needs_ffmpeg
async def test_resume_playback_skips_disabled_paused_and_non_url(
    hass: HomeAssistant, players, setup_integration, hass_client, make_wav
) -> None:
    from .conftest import BASE_FEATURES

    # Disabled by default: stream is not resumed
    entry = await setup_integration(resume_playback=False)
    hass.states.async_set(
        "media_player.kitchen",
        "playing",
        {
            "supported_features": BASE_FEATURES,
            "volume_level": 0.3,
            "media_content_id": "https://radio.example.com/live.mp3",
            "media_content_type": "music",
        },
    )
    client = await hass_client()
    status, _ = await upload(client, make_wav(), targets="media_player.kitchen")
    assert status == 200
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(players.calls_for("media_player.kitchen", "play_media")) == 1

    # Enable resume_playback: paused, opaque app IDs, and own hannounce URLs are skipped
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "resume_playback": True}
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    for state_name, content_id in (
        ("paused", "https://radio.example.com/live.mp3"),
        ("playing", "spotify:track:4cOdK2wGLETKBW3PvgPWqT"),
        ("playing", "http://homeassistant.local:8123/api/hannounce/audio/old.mp3"),
        ("playing", "media-source://hannounce/old.mp3"),
    ):
        players.calls.clear()
        hass.states.async_set(
            "media_player.kitchen",
            state_name,
            {
                "supported_features": BASE_FEATURES,
                "volume_level": 0.3,
                "media_content_id": content_id,
                "media_content_type": "music",
            },
        )
        status, _ = await upload(client, make_wav(), targets="media_player.kitchen")
        assert status == 200
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(players.calls_for("media_player.kitchen", "play_media")) == 1, (
            f"unexpected resume for {state_name} / {content_id}"
        )


def _register_alexa_speakers(hass: HomeAssistant, entry_id: str) -> None:
    """Register alexa_devices (single + WHA group) and alexa_media speakers."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    from .conftest import BASE_FEATURES

    devices = dr.async_get(hass)
    entities = er.async_get(hass)

    # 1. Official alexa_devices single Echo with sibling _speak and _announce notify entities
    echo_dev = devices.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={("alexa_devices", "ECHO123")},
        name="Echo Kitchen",
        model="Echo Dot",
    )
    entities.async_get_or_create(
        "media_player",
        "alexa_devices",
        "ECHO123-media",
        suggested_object_id="echo_kitchen",
        device_id=echo_dev.id,
        supported_features=BASE_FEATURES,
    )
    entities.async_get_or_create(
        "notify",
        "alexa_devices",
        "ECHO123-announce",
        suggested_object_id="echo_kitchen_announce",
        device_id=echo_dev.id,
        translation_key="announce",
    )
    entities.async_get_or_create(
        "notify",
        "alexa_devices",
        "ECHO123-speak",
        suggested_object_id="echo_kitchen_speak",
        device_id=echo_dev.id,
        translation_key="speak",
    )
    hass.states.async_set(
        "media_player.echo_kitchen",
        "standby",
        {
            "supported_features": BASE_FEATURES,
            "volume_level": 0.3,
            "friendly_name": "Echo Kitchen",
        },
    )
    hass.states.async_set("notify.echo_kitchen_speak", "unknown")
    hass.states.async_set("notify.echo_kitchen_announce", "unknown")

    # 2. Official alexa_devices WHA speaker group (only has _announce, no _speak)
    group_dev = devices.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={("alexa_devices", "GROUP123")},
        name="Everywhere",
        model="WHA",
    )
    entities.async_get_or_create(
        "media_player",
        "alexa_devices",
        "GROUP123-media",
        suggested_object_id="everywhere",
        device_id=group_dev.id,
        supported_features=BASE_FEATURES,
    )
    entities.async_get_or_create(
        "notify",
        "alexa_devices",
        "GROUP123-announce",
        suggested_object_id="everywhere_announce",
        device_id=group_dev.id,
        translation_key="announce",
    )
    hass.states.async_set(
        "media_player.everywhere",
        "standby",
        {
            "supported_features": BASE_FEATURES,
            "volume_level": 0.3,
            "friendly_name": "Everywhere",
        },
    )
    hass.states.async_set("notify.everywhere_announce", "unknown")

    # 3. HACS alexa_media speaker
    entities.async_get_or_create(
        "media_player",
        "alexa_media",
        "AM_OFFICE",
        suggested_object_id="echo_office",
        supported_features=BASE_FEATURES,
    )
    hass.states.async_set(
        "media_player.echo_office",
        "standby",
        {
            "supported_features": BASE_FEATURES,
            "volume_level": 0.3,
            "friendly_name": "Echo Office",
        },
    )


@needs_ffmpeg
async def test_alexa_disabled_by_default(
    hass: HomeAssistant, players, setup_integration, hass_client, make_wav, tmp_path
) -> None:
    import pytest
    from homeassistant.exceptions import HomeAssistantError
    from pytest_homeassistant.common import MockConfigEntry

    hass.config.allowlist_external_dirs = {str(tmp_path)}
    alexa_entry = MockConfigEntry(domain="alexa_devices")
    alexa_entry.add_to_hass(hass)
    _register_alexa_speakers(hass, alexa_entry.entry_id)

    entry = await setup_integration(alexa_support=False)
    runtime = entry.runtime_data

    # Not auto-discovered when opt-in is off
    discovered = runtime.speakers()
    assert "media_player.echo_kitchen" not in discovered
    assert "media_player.everywhere" not in discovered
    assert "media_player.echo_office" not in discovered

    # Direct service call raises alexa_disabled
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "hannounce",
            "announce",
            {"entity_id": "media_player.echo_kitchen", "file": str(make_wav()), "chime": "none"},
            blocking=True,
        )
    assert err.value.translation_key == "alexa_disabled"

    # Direct HTTP upload returns 400 alexa_disabled
    status, body = await upload(
        await hass_client(), make_wav(), targets="media_player.echo_office"
    )
    assert (status, body["code"]) == (400, "alexa_disabled")


@needs_ffmpeg
async def test_alexa_delivery_both_platforms_and_signed_endpoint(
    hass: HomeAssistant, players, setup_integration, hass_client, hass_client_no_auth, make_wav
) -> None:
    import re
    from unittest.mock import AsyncMock, patch

    from mutagen.mp3 import MP3
    from pytest_homeassistant.common import MockConfigEntry

    from custom_components.hannounce import audio
    from custom_components.hannounce.announcer import Announcer
    from custom_components.hannounce.settings import describe_speakers

    hass.config.external_url = "https://my-home.ui.nabu.casa"
    alexa_entry = MockConfigEntry(domain="alexa_devices")
    alexa_entry.add_to_hass(hass)
    _register_alexa_speakers(hass, alexa_entry.entry_id)

    notify_calls: list[tuple[str, dict]] = []

    async def fake_send_message(call) -> None:
        notify_calls.append(("send_message", dict(call.data)))

    async def fake_alexa_media(call) -> None:
        notify_calls.append(("alexa_media", dict(call.data)))

    hass.services.async_register("notify", "send_message", fake_send_message)
    hass.services.async_register("notify", "alexa_media", fake_alexa_media)

    entry = await setup_integration(alexa_support=True)
    runtime = entry.runtime_data

    # Discovered when opt-in is on, and WHA group is tagged as group=True
    discovered = runtime.speakers()
    assert "media_player.echo_kitchen" in discovered
    assert "media_player.everywhere" in discovered
    assert "media_player.echo_office" in discovered
    described = {s["entity_id"]: s for s in describe_speakers(hass, discovered)}
    assert described["media_player.echo_kitchen"]["group"] is False
    assert described["media_player.everywhere"]["group"] is True

    with (
        patch.object(Announcer, "_async_wait_alexa", new=AsyncMock()) as mocked_wait,
        patch.object(
            audio, "async_render_alexa", wraps=audio.async_render_alexa
        ) as mocked_render,
    ):
        status, body = await upload(
            await hass_client(),
            make_wav(),
            targets=json.dumps(
                [
                    "media_player.echo_kitchen",
                    "media_player.everywhere",
                    "media_player.echo_office",
                ]
            ),
            chime="none",
        )
        assert status == 200, body
        await hass.async_block_till_done(wait_background_tasks=True)

    # Shared single transcode across all 3 Alexa speakers
    assert mocked_render.call_count == 1
    assert mocked_wait.call_count == 3

    # Check alexa_devices notify calls (_speak for Echo, _announce fallback for WHA group)
    send_by_entity = {
        data["entity_id"]: data["message"]
        for service, data in notify_calls
        if service == "send_message"
    }
    assert set(send_by_entity) == {
        "notify.echo_kitchen_speak",
        "notify.everywhere_announce",
    }

    # Check HACS alexa_media notify call
    media_calls = [
        data for service, data in notify_calls if service == "alexa_media"
    ]
    assert len(media_calls) == 1
    assert media_calls[0]["target"] == ["media_player.echo_office"]
    assert media_calls[0]["data"] == {"type": "tts"}

    # Validate SSML payload and signed HTTPS -alexa.mp3 URL
    ssml = send_by_entity["notify.echo_kitchen_speak"]
    match = re.fullmatch(r'<audio src="(https://my-home\.ui\.nabu\.casa/api/hannounce/audio/[^"]+-alexa\.mp3\?authSig=[^"]+)"/>', ssml)
    assert match, f"unexpected SSML: {ssml}"
    signed_url = URL(match.group(1))
    assert signed_url.path == f"/api/hannounce/audio/{body['id']}-alexa.mp3"

    # Volume set and restored on Echo speakers
    assert [c["volume_level"] for c in players.calls_for("media_player.echo_kitchen", "volume_set")] == [0.7, 0.3]
    assert [c["volume_level"] for c in players.calls_for("media_player.echo_office", "volume_set")] == [0.7, 0.3]

    # Signed -alexa.mp3 endpoint serves valid 48 kbps / 24 kHz mono MP3 and requires auth
    anonymous = await hass_client_no_auth()
    resp = await anonymous.get(signed_url.path_qs)
    assert resp.status == 200
    assert resp.headers["Content-Type"] == "audio/mpeg"
    data = await resp.read()
    alexa_mp3 = runtime.announcer.folder / "downloaded_alexa.mp3"
    alexa_mp3.write_bytes(data)
    info = MP3(str(alexa_mp3)).info
    assert info.sample_rate == 24000
    assert info.bitrate == 48000
    assert info.channels == 1

    assert (await anonymous.get(signed_url.path)).status == 401

    # Non-Alexa announcement does NOT transcode an Alexa variant and returns 404 for -alexa.mp3
    status2, body2 = await upload(
        await hass_client(), make_wav(), targets="media_player.kitchen", chime="none"
    )
    assert status2 == 200
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (
        await (await hass_client()).get(f"/api/hannounce/audio/{body2['id']}-alexa.mp3")
    ).status == 404


@needs_ffmpeg
async def test_alexa_requires_external_https_at_runtime(
    hass: HomeAssistant, players, setup_integration, make_wav, tmp_path
) -> None:
    import pytest
    from homeassistant.exceptions import HomeAssistantError
    from pytest_homeassistant.common import MockConfigEntry

    hass.config.allowlist_external_dirs = {str(tmp_path)}
    alexa_entry = MockConfigEntry(domain="alexa_devices")
    alexa_entry.add_to_hass(hass)
    _register_alexa_speakers(hass, alexa_entry.entry_id)

    hass.config.external_url = "https://my-home.ui.nabu.casa"
    await setup_integration(alexa_support=True)

    # Simulate user later removing external HTTPS URL
    hass.config.external_url = None
    wav = str(make_wav())

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "hannounce",
            "announce",
            {"entity_id": "media_player.echo_kitchen", "file": wav, "chime": "none"},
            blocking=True,
        )
    assert err.value.translation_key == "external_https_required"

    # Standard local Cast speaker still works fine without external HTTPS
    response = await hass.services.async_call(
        "hannounce",
        "announce",
        {"entity_id": "media_player.kitchen", "file": wav, "chime": "none"},
        blocking=True,
        return_response=True,
    )
    assert response["targets"] == ["media_player.kitchen"]

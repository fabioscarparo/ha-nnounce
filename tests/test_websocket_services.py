"""WebSocket commands of the card and the service actions."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import label_registry as lr

from custom_components.hannounce.const import DOMAIN

from .conftest import needs_ffmpeg, ws_call


async def test_info_lists_supported_speakers(hass: HomeAssistant, players, setup_integration, hass_ws_client) -> None:
    await setup_integration()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/info"})
    result = (await client.receive_json())["result"]
    # Supported integrations only, no televisions, no Spotify, no custom players
    assert [s["entity_id"] for s in result["speakers"]] == [
        "media_player.desk",
        "media_player.kitchen",
        "media_player.living_room",
    ]
    assert result["defaults"] == {
        "set_volume": True,
        "volume": 70,
        "chime": "ding_dong",
        "max_duration": 60,
        "voice_enhancement": True,
    }
    assert result["intercom"]["enabled"] is False
    assert result["last"] is None


async def test_chosen_speakers_win(hass: HomeAssistant, players, setup_integration, hass_ws_client) -> None:
    await setup_integration(speakers=["media_player.garage", "media_player.tv"])
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/info"})
    speakers = (await client.receive_json())["result"]["speakers"]
    assert [s["entity_id"] for s in speakers] == ["media_player.garage", "media_player.tv"]
    assert speakers[0]["platform"] == "my_custom_player"


@needs_ffmpeg
async def test_replay_and_events(hass: HomeAssistant, players, setup_integration, hass_ws_client, make_wav, tmp_path) -> None:
    hass.config.allowlist_external_dirs = {str(tmp_path)}
    await setup_integration()
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": f"{DOMAIN}/replay"})
    assert (await client.receive_json())["error"]["code"] == "no_message"

    await client.send_json_auto_id({"type": f"{DOMAIN}/subscribe"})
    assert (await client.receive_json())["success"]

    response = await hass.services.async_call(
        DOMAIN, "announce", {"entity_id": ["media_player.kitchen"], "file": str(make_wav()), "chime": "none"},
        blocking=True, return_response=True,
    )
    assert response["targets"] == ["media_player.kitchen"] and response["source"] == "service"
    event = await client.receive_json()
    assert event["type"] == "event"
    assert event["event"]["id"] == response["id"]
    assert "user_id" not in event["event"]  # not sent to the browser

    result = (await ws_call(client, {"type": f"{DOMAIN}/replay", "targets": ["media_player.desk"], "volume": "keep"}))["result"]
    assert result["id"] == response["id"] and result["targets"] == ["media_player.desk"]
    await hass.async_block_till_done(wait_background_tasks=True)
    (play,) = players.calls_for("media_player.desk", "play_media")
    assert play["media_content_id"] == f"media-source://hannounce/{response['id']}.mp3"
    assert players.calls_for("media_player.desk", "volume_set") == []

    # Without speakers, the replay goes where the message went last
    replay = await hass.services.async_call(DOMAIN, "replay", {"volume": 20}, blocking=True, return_response=True)
    assert replay["targets"] == ["media_player.desk"]


async def test_route_needs_the_intercom(hass: HomeAssistant, players, setup_integration, hass_ws_client) -> None:
    await setup_integration()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/route", "targets": ["media_player.kitchen"]})
    assert (await client.receive_json())["error"]["code"] == "intercom_off"


async def test_announce_service_checks_files(hass: HomeAssistant, players, setup_integration, tmp_path) -> None:
    await setup_integration()
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, "announce", {"file": "/etc/hosts"}, blocking=True)
    assert err.value.translation_key == "path_not_allowed"

    hass.config.allowlist_external_dirs = {str(tmp_path)}
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, "announce", {"file": str(tmp_path / "missing.mp3")}, blocking=True)
    assert err.value.translation_key == "file_not_found"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "replay", {}, blocking=True)


@needs_ffmpeg
async def test_announce_service_downloads_url(hass: HomeAssistant, players, setup_integration, aioclient_mock, make_wav) -> None:
    await setup_integration()
    aioclient_mock.get("http://example.com/message.wav", content=make_wav().read_bytes())
    aioclient_mock.get("http://example.com/missing.wav", status=404)
    response = await hass.services.async_call(
        DOMAIN, "announce", {"entity_id": "media_player.living_room", "url": "http://example.com/message.wav", "volume": 30},
        blocking=True, return_response=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    (play,) = players.calls_for("media_player.living_room", "play_media")
    assert play["extra"] == {"volume": 30}
    assert response["targets"] == ["media_player.living_room"]

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(DOMAIN, "announce", {"url": "http://example.com/missing.wav"}, blocking=True)
    assert err.value.translation_key == "download_failed"


@needs_ffmpeg
async def test_service_supports_area_floor_and_label_targets(
    hass: HomeAssistant, players, setup_integration, make_wav, tmp_path
) -> None:
    hass.config.allowlist_external_dirs = {str(tmp_path)}
    await setup_integration()

    floors = fr.async_get(hass)
    areas = ar.async_get(hass)
    labels = lr.async_get(hass)
    entities = er.async_get(hass)

    ground = floors.async_create("Ground Floor")
    kitchen = areas.async_create("Kitchen", floor_id=ground.floor_id)
    living = areas.async_create("Living", floor_id=ground.floor_id)
    empty = areas.async_create("Attic")
    tag = labels.async_create("Voice")

    # TV is in the same area as kitchen speaker and must be skipped on area expansion
    entities.async_update_entity("media_player.kitchen", area_id=kitchen.id)
    entities.async_update_entity("media_player.tv", area_id=kitchen.id)
    entities.async_update_entity("media_player.living_room", area_id=living.id)
    entities.async_update_entity("media_player.desk", labels={tag.label_id})

    wav = str(make_wav())

    by_area = await hass.services.async_call(
        DOMAIN, "announce", {"file": wav, "chime": "none"}, target={"area_id": kitchen.id},
        blocking=True, return_response=True,
    )
    assert by_area["targets"] == ["media_player.kitchen"]

    by_floor = await hass.services.async_call(
        DOMAIN, "announce", {"file": wav, "chime": "none"}, target={"floor_id": ground.floor_id},
        blocking=True, return_response=True,
    )
    assert by_floor["targets"] == ["media_player.kitchen", "media_player.living_room"]

    by_label = await hass.services.async_call(
        DOMAIN, "replay", {}, target={"label_id": tag.label_id},
        blocking=True, return_response=True,
    )
    assert by_label["targets"] == ["media_player.desk"]

    # An area with no eligible speakers fails instead of falling back to all speakers
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "announce", {"file": wav, "chime": "none"}, target={"area_id": empty.id},
            blocking=True,
        )
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_info_exposes_areas_custom_chime_quiet_and_tts(
    hass: HomeAssistant, players, setup_integration, hass_ws_client, make_wav, tmp_path
) -> None:
    hass.config.allowlist_external_dirs = {str(tmp_path)}
    chime_file = make_wav("bell.wav", seconds=0.5)
    areas = ar.async_get(hass)
    entities = er.async_get(hass)
    living = areas.async_create("Living Zone", icon="mdi:sofa")
    entities.async_update_entity("media_player.kitchen", area_id=living.id)
    entities.async_update_entity("media_player.living_room", area_id=living.id)

    hass.states.async_set("input_boolean.sleep_mode", "on")
    await setup_integration(
        custom_chime=str(chime_file),
        quiet_hours=True,
        quiet_start="22:00:00",
        quiet_end="07:00:00",
        quiet_mode="cap_volume",
        quiet_volume=20,
        quiet_entity="input_boolean.sleep_mode",
    )

    client = await hass_ws_client(hass)
    result = (await ws_call(client, {"type": f"{DOMAIN}/info"}))["result"]
    assert "custom" in result["chimes"]
    assert result["quiet"]["enabled"] is True
    assert result["quiet"]["active"] is True
    assert result["quiet"]["volume"] == 20
    assert result["quiet"]["entity_id"] == "input_boolean.sleep_mode"
    assert result["tts"] == {"available": False, "engine": None}

    by_id = {s["entity_id"]: s for s in result["speakers"]}
    assert by_id["media_player.kitchen"]["area"] == "Living Zone"
    assert by_id["media_player.kitchen"]["area_id"] == living.id
    assert by_id["media_player.kitchen"]["area_icon"] == "mdi:sofa"


@needs_ffmpeg
async def test_tts_via_websocket_and_service(
    hass: HomeAssistant, players, setup_integration, hass_ws_client, make_wav
) -> None:
    hass.states.async_set("input_boolean.sleep_mode", "off")
    await setup_integration(
        quiet_hours=True,
        quiet_start="00:00:00",
        quiet_end="00:00:00",
        quiet_mode="skip",
        quiet_speakers=["media_player.kitchen"],
        quiet_entity="input_boolean.sleep_mode",
    )

    # Without TTS component loaded, service raises tts_unavailable
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "announce",
            {"entity_id": "media_player.kitchen", "message": "Hello"},
            blocking=True,
        )
    assert err.value.translation_key == "tts_unavailable"

    wav_bytes = make_wav("tts.wav", seconds=0.8).read_bytes()
    hass.config.components.add("tts")
    with (
        patch("homeassistant.components.tts.async_resolve_engine", return_value="tts.piper") as mock_resolve,
        patch(
            "homeassistant.components.tts.generate_media_source_id",
            return_value="media-source://tts/tts.piper?message=Dinner",
        ) as mock_gen,
        patch(
            "homeassistant.components.tts.async_get_media_source_audio",
            new=AsyncMock(return_value=("wav", wav_bytes)),
        ),
    ):
        client = await hass_ws_client(hass)
        info = (await ws_call(client, {"type": f"{DOMAIN}/info"}))["result"]
        assert info["tts"] == {"available": True, "engine": "tts.piper"}

        # WebSocket hannounce/say
        say = await ws_call(
            client,
            {
                "type": f"{DOMAIN}/say",
                "message": "Dinner is ready",
                "targets": ["media_player.kitchen"],
                "volume": 50,
                "chime": "none",
            },
        )
        assert say["success"] is True
        assert say["result"]["source"] == "tts"
        assert say["result"]["targets"] == ["media_player.kitchen"]
        await hass.async_block_till_done(wait_background_tasks=True)
        assert [c["volume_level"] for c in players.calls_for("media_player.kitchen", "volume_set")] == [0.5, 0.3]

        # Service call with message and language
        svc = await hass.services.async_call(
            DOMAIN,
            "announce",
            {
                "entity_id": "media_player.desk",
                "message": "Test message",
                "language": "it",
                "chime": "soft",
            },
            blocking=True,
            return_response=True,
        )
        assert svc["source"] == "service"
        assert svc["targets"] == ["media_player.desk"]
        mock_gen.assert_called_with(hass, "Test message", engine="tts.piper", language="it")
        assert mock_resolve.called

        # Quiet hours skip blocks ws hannounce/say unless force=True
        hass.states.async_set("input_boolean.sleep_mode", "on")
        blocked = await ws_call(
            client,
            {
                "type": f"{DOMAIN}/say",
                "message": "Shh",
                "targets": ["media_player.kitchen"],
                "chime": "none",
            },
        )
        assert blocked["success"] is False
        assert blocked["error"]["code"] == "quiet_hours"

        forced = await ws_call(
            client,
            {
                "type": f"{DOMAIN}/say",
                "message": "Emergency",
                "targets": ["media_player.kitchen"],
                "chime": "none",
                "force": True,
            },
        )
        assert forced["success"] is True
        assert forced["result"]["targets"] == ["media_player.kitchen"]

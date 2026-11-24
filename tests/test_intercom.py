"""Intercom cameras: Home Assistant's two-way audio sends the microphone over WebRTC."""

import asyncio
from unittest.mock import patch

import pytest

pytest.importorskip("aiortc")

from aiortc import RTCPeerConnection, RTCSessionDescription  # noqa: E402
from aiortc.contrib.media import MediaPlayer  # noqa: E402
from homeassistant.components.camera.helper import get_camera_from_entity_id  # noqa: E402
from homeassistant.components.labs import async_update_preview_feature  # noqa: E402
from homeassistant.core import HomeAssistant, callback  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from homeassistant.setup import async_setup_component  # noqa: E402

from custom_components.hannounce.const import DOMAIN, EVENT_ANNOUNCED  # noqa: E402

from .conftest import needs_ffmpeg, ws_call  # noqa: E402


def intercoms(hass: HomeAssistant) -> dict[str, str]:
    return {
        entry.unique_id.rsplit("_intercom_", 1)[1]: entry.entity_id
        for entry in er.async_get(hass).entities.values()
        if entry.platform == DOMAIN and entry.domain == "camera"
    }


async def test_one_intercom_per_speaker(hass: HomeAssistant, players, setup_integration) -> None:
    from custom_components.hannounce import intercom  # noqa: PLC0415

    assert await async_setup_component(hass, "labs", {})
    with (
        patch.object(intercom, "load_fonts", wraps=intercom.load_fonts) as mocked_load,
        patch.object(
            hass, "async_add_executor_job", wraps=hass.async_add_executor_job
        ) as executor,
    ):
        await setup_integration(intercom=True)
    # Fonts are loaded once via the executor and shared across all intercom cameras
    assert mocked_load.call_count == 1
    assert any(call.args and call.args[0] is mocked_load for call in executor.call_args_list)
    cameras = intercoms(hass)
    assert set(cameras) == {"broadcast", "media_player.desk", "media_player.kitchen", "media_player.living_room"}
    assert cameras["media_player.kitchen"] == "camera.intercom_kitchen"
    assert hass.states.get("camera.intercom_kitchen").attributes["speaker"] == "media_player.kitchen"

    camera = get_camera_from_entity_id(hass, "camera.intercom_kitchen")
    # The talk button needs the Labs preview feature
    assert camera.camera_capabilities.two_way_audio is False
    await async_update_preview_feature(hass, "camera", "two_way_audio", True)
    assert camera.camera_capabilities.two_way_audio is True


async def next_announcement(hass: HomeAssistant):
    """Wait for the next announcement event."""
    future = hass.loop.create_future()

    @callback
    def on_event(event) -> None:
        if not future.done():
            future.set_result(event)

    unsub = hass.bus.async_listen(EVENT_ANNOUNCED, on_event)
    try:
        async with asyncio.timeout(20):
            return await future
    finally:
        unsub()


async def answer_offer(client, pc: RTCPeerConnection, entity_id: str) -> int:
    """Send the offer like the frontend, apply the answer, return the subscription id."""
    await pc.setLocalDescription(await pc.createOffer())
    offer = {"type": "camera/webrtc/offer", "entity_id": entity_id, "offer": pc.localDescription.sdp}
    await client.send_json_auto_id(offer)
    while True:
        message = await asyncio.wait_for(client.receive_json(), 15)
        assert message.get("success", True), message
        if message.get("type") == "event" and message["event"]["type"] == "answer":
            await pc.setRemoteDescription(RTCSessionDescription(message["event"]["answer"], "answer"))
            return offer["id"]


@pytest.fixture
def loopback_ice():
    """The test harness fakes the network adapters: let WebRTC use the loopback."""
    with patch("aioice.ice.get_host_addresses", return_value=["127.0.0.1"]):
        yield


@needs_ffmpeg
@pytest.mark.usefixtures("loopback_ice")
async def test_talk_through_the_app(hass: HomeAssistant, players, setup_integration, hass_ws_client, socket_enabled, make_wav) -> None:
    """Like the iOS app: an audio-only session, the message goes when it closes."""
    assert await async_setup_component(hass, "labs", {})
    await setup_integration(intercom=True)
    client = await hass_ws_client(hass)

    # The card chooses where the broadcast intercom sends the next message
    route = (await ws_call(client, {"type": f"{DOMAIN}/route", "targets": ["media_player.desk"], "volume": "keep", "chime": "none"}))["result"]
    assert route["targets"] == ["media_player.desk"]

    pc = RTCPeerConnection()
    connected = asyncio.Event()

    @pc.on("connectionstatechange")
    def on_state() -> None:
        if pc.connectionState == "connected":
            connected.set()

    # A long message: the app, not a gap in the voice, ends it
    player = MediaPlayer(str(make_wav(seconds=6)))
    pc.addTransceiver(player.audio, direction="sendonly")
    offer_id = await answer_offer(client, pc, route["entity_id"])
    await asyncio.wait_for(connected.wait(), 10)
    await asyncio.sleep(1.5)  # the app streams the voice

    # The app stops: the subscription ends and Home Assistant closes the session
    waiting = asyncio.ensure_future(next_announcement(hass))
    await client.send_json_auto_id({"type": "unsubscribe_events", "subscription": offer_id})
    event = await waiting
    await pc.close()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert event.data["source"] == "intercom"
    assert event.data["targets"] == ["media_player.desk"]
    (play,) = players.calls_for("media_player.desk", "play_media")
    assert play["media_content_id"] == f"media-source://hannounce/{event.data['id']}.mp3"
    assert players.calls_for("media_player.desk", "volume_set") == []  # "keep"


@needs_ffmpeg
@pytest.mark.usefixtures("loopback_ice")
async def test_talk_from_the_camera_view(hass: HomeAssistant, players, setup_integration, hass_ws_client, socket_enabled, make_wav) -> None:
    """Like the Start talking button: video of the status, the message ends when the voice stops."""
    assert await async_setup_component(hass, "labs", {})
    await setup_integration(intercom=True)
    client = await hass_ws_client(hass)

    pc = RTCPeerConnection()
    player = MediaPlayer(str(make_wav(seconds=1.2)))
    pc.addTransceiver(player.audio, direction="sendrecv")
    pc.addTransceiver("video", direction="recvonly")
    frames: list = []
    readers: set[asyncio.Task] = set()

    @pc.on("track")
    def on_track(track) -> None:
        async def read() -> None:
            while True:
                try:
                    frames.append(await track.recv())
                except Exception:  # noqa: BLE001
                    return

        if track.kind == "video":
            readers.add(asyncio.ensure_future(read()))

    waiting = asyncio.ensure_future(next_announcement(hass))
    await answer_offer(client, pc, "camera.intercom_kitchen")
    # The file ends, the browser stops sending: the gap closes the message
    event = await waiting
    await pc.close()
    await asyncio.gather(*readers)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert event.data["targets"] == ["media_player.kitchen"]
    assert frames, "the status video never arrived"
    assert frames[0].width == 640 and frames[0].height == 360
    (play,) = players.calls_for("media_player.kitchen", "play_media")
    assert play["media_content_id"] == f"media-source://hannounce/{event.data['id']}.mp3"

    # The snapshot is the status screen
    camera = get_camera_from_entity_id(hass, "camera.intercom_kitchen")
    image = await camera.async_camera_image()
    assert image[:2] == b"\xff\xd8"  # JPEG


def test_intercom_screen_handles_unicode_and_ascii_fallback() -> None:
    """Romanian diacritics render cleanly with system fonts and degrade gracefully without them."""
    from custom_components.hannounce import intercom  # noqa: PLC0415

    assert intercom.strings("ro-RO")["recording"] == "Înregistrare"
    assert intercom._strip_diacritics("Înregistrare · Către eșuat…") == "Inregistrare · Catre esuat…"

    fonts = intercom.load_fonts()
    screen = intercom.Screen("Toate difuzoarele", "Bucătărie", "ro-RO", fonts)
    screen.set("recording")
    assert screen.jpeg()[:2] == b"\xff\xd8"

    with patch.object(intercom, "FONT_PATHS", ()):
        fallback_fonts = intercom.load_fonts()
        assert fallback_fonts.has_unicode is False
        fallback = intercom.Screen("Toate difuzoarele", "Bucătărie", "ro-RO", fallback_fonts)
        assert fallback._unicode_font is False
        fallback.set("error")
        assert fallback.jpeg()[:2] == b"\xff\xd8"

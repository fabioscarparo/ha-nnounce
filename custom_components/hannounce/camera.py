"""Intercom cameras: talk to a speaker with Home Assistant's two-way audio."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.camera import (
    Camera,
    CameraEntityCapabilities,
    CameraEntityFeature,
    WebRTCAnswer,
    WebRTCError,
    WebRTCSendMessage,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from webrtc_models import RTCIceCandidateInit

from .audio import NoVoiceError
from .const import DOMAIN, INTERCOM_BROADCAST

if TYPE_CHECKING:
    from . import HannounceData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add one intercom per speaker and one for all of them."""
    runtime: HannounceData = entry.runtime_data
    speakers = runtime.speakers()
    entities = [IntercomCamera(runtime, entity_id) for entity_id in speakers]
    entities.append(IntercomCamera(runtime, None))
    async_add_entities(entities)


class IntercomCamera(Camera):
    """A camera whose talk button plays the voice on a speaker."""

    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_should_poll = False

    def __init__(self, runtime: HannounceData, speaker: str | None) -> None:
        """Initialize."""
        super().__init__()
        from .intercom import Screen  # noqa: PLC0415

        self._runtime = runtime
        self._speaker = speaker
        self._sessions: dict[str, Any] = {}
        key = speaker or INTERCOM_BROADCAST
        self.route_key = key
        self._attr_unique_id = f"{runtime.entry.entry_id}_intercom_{key}"
        self._attr_camera_entity_capabilities = CameraEntityCapabilities(
            two_way_audio=True
        )
        # The device is named "Intercom": entities read "Intercom Kitchen"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry.entry_id)},
            translation_key="intercom",
            manufacturer="HA-nnounce",
            entry_type=DeviceEntryType.SERVICE,
        )
        if speaker is None:
            self._attr_translation_key = "intercom_all"
        else:
            self._attr_translation_key = "intercom"
            self._attr_translation_placeholders = {
                "speaker": runtime.speaker_name(speaker)
            }
        self._screen = Screen(
            title=runtime.speaker_name(speaker) if speaker else runtime.text("all"),
            targets=self._targets_label(),
            language=runtime.hass.config.language,
        )

    def _targets_label(self) -> str:
        targets = self._runtime.intercom_targets(self.route_key, self._speaker)
        names = [self._runtime.speaker_name(entity_id) for entity_id in targets]
        return ", ".join(names) if names else "-"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Tell which speaker this intercom plays on."""
        return {"speaker": self._speaker, "broadcast": self._speaker is None}

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the status screen as snapshot."""
        self._screen.state.targets = self._targets_label()
        return await self.hass.async_add_executor_job(self._screen.jpeg)

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Answer the frontend or the app with our own WebRTC peer."""
        from .intercom import IntercomSession  # noqa: PLC0415

        self._screen.state.targets = self._targets_label()
        session = IntercomSession(
            session_id=session_id,
            screen=self._screen,
            ice_servers=self._ice_servers(),
            on_message=self._async_on_message,
            max_seconds=self._runtime.settings.max_duration,
        )
        self._sessions[session_id] = session
        try:
            answer = await session.async_answer(offer_sdp)
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Intercom could not answer the WebRTC offer")
            self._sessions.pop(session_id, None)
            await session.async_close()
            send_message(WebRTCError("intercom_offer_failed", str(err)))
            return
        if session_id not in self._sessions:
            # Closed while answering
            await session.async_close()
            return
        send_message(WebRTCAnswer(answer))

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Pass a trickled candidate to the session."""
        if session := self._sessions.get(session_id):
            await session.async_add_candidate(
                candidate.candidate, candidate.sdp_mid, candidate.sdp_m_line_index
            )

    @callback
    def close_webrtc_session(self, session_id: str) -> None:
        """Close the session; what was said is still sent."""
        if session := self._sessions.pop(session_id, None):
            self.hass.async_create_background_task(
                session.async_close(), f"{DOMAIN} close {session_id}"
            )

    async def async_will_remove_from_hass(self) -> None:
        """Close every session."""
        sessions = list(self._sessions.values())
        self._sessions.clear()
        for session in sessions:
            await session.async_close()

    def _ice_servers(self) -> list:
        """Return the ICE servers Home Assistant gives the frontend, for aiortc."""
        from aiortc import RTCIceServer  # noqa: PLC0415

        servers = []
        config = self.async_get_webrtc_client_configuration().configuration
        for server in config.ice_servers:
            urls = [server.urls] if isinstance(server.urls, str) else list(server.urls)
            # aiortc only speaks stun and turn over UDP or TCP
            urls = [url for url in urls if url.split(":", 1)[0] in ("stun", "turn", "turns")]
            if urls:
                servers.append(
                    RTCIceServer(
                        urls=urls,
                        username=server.username,
                        credential=server.credential,
                    )
                )
        return servers

    async def _async_on_message(self, pcm: bytes) -> str:
        """Encode and play one message; return the names it went to."""
        try:
            targets = await self._runtime.async_play_pcm(
                pcm, self.route_key, self._speaker
            )
        except NoVoiceError as err:
            err.screen_status = "no_voice"  # type: ignore[attr-defined]
            raise
        return ", ".join(self._runtime.speaker_name(entity_id) for entity_id in targets)

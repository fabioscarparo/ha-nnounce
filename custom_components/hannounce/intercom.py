"""WebRTC sessions that receive the microphone of the frontend or of the apps.

Home Assistant's two-way audio (a Labs preview since 2026.11) sends the
microphone to a camera entity over WebRTC. Each intercom camera answers that
WebRTC offer itself with aiortc, collects the voice and, when the user stops
talking, hands the recording to the announcer. A small video stream shows
what is happening, which the frontend also needs to consider the stream live.

This module imports aiortc, PyAV and Pillow: it is only loaded once the
intercom option is on and aiortc is installed.
"""

from __future__ import annotations

import asyncio
import fractions
import io
import logging
import time
import unicodedata
from array import array
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import av
from aiortc import (
    MediaStreamTrack,
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.mediastreams import MediaStreamError
from aiortc.sdp import candidate_from_sdp
from PIL import Image, ImageDraw, ImageFont

from .const import INTERCOM_GAP

_LOGGER = logging.getLogger(__name__)

SAMPLE_RATE = 48000
WIDTH, HEIGHT = 640, 360
FPS = 8
RESULT_SECONDS = 8  # how long "sent" or an error stays on screen
VIDEO_CLOCK = 90000

BACKGROUND = (24, 28, 36)
SURFACE = (40, 46, 58)
TEXT = (236, 239, 244)
MUTED = (160, 168, 182)
ACCENT = (66, 133, 244)
RECORDING = (234, 67, 53)
SUCCESS = (52, 168, 83)

STRINGS = {
    "en": {
        "idle": "Ready to talk",
        "recording": "Recording",
        "sending": "Sending…",
        "sent": "Sent",
        "no_voice": "No voice heard",
        "error": "Could not send",
        "to": "To",
    },
    "it": {
        "idle": "Pronto per parlare",
        "recording": "Registrazione",
        "sending": "Invio…",
        "sent": "Inviato",
        "no_voice": "Nessuna voce rilevata",
        "error": "Invio non riuscito",
        "to": "A",
    },
    "ro": {
        "idle": "Gata de vorbit",
        "recording": "Înregistrare",
        "sending": "Se trimite…",
        "sent": "Trimis",
        "no_voice": "Nicio voce detectată",
        "error": "Trimiterea a eșuat",
        "to": "Către",
    },
}


SCREEN_FONT_SIZES = (22, 30)

FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)


@dataclass(frozen=True)
class FontSet:
    """Preloaded fonts shared by intercom status screens."""

    fonts: dict[int, ImageFont.ImageFont | ImageFont.FreeTypeFont]
    has_unicode: bool


def strings(language: str) -> dict[str, str]:
    """Return the screen strings for a language, English otherwise."""
    return STRINGS.get(language.split("-")[0], STRINGS["en"])


def _strip_diacritics(text: str) -> str:
    """Drop combining accents when falling back to Pillow's ASCII-only font."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _read_font_bytes() -> bytes | None:
    """Read the first usable Unicode TrueType font from disk once."""
    for path in FONT_PATHS:
        font_path = Path(path)
        if font_path.is_file():
            try:
                data = font_path.read_bytes()
                ImageFont.truetype(io.BytesIO(data), size=SCREEN_FONT_SIZES[0])
            except OSError:
                continue
            else:
                return data
    return None


def load_fonts() -> FontSet:
    """Load the intercom screen fonts once (blocking I/O: call in the executor)."""
    data = _read_font_bytes()
    if data is not None:
        return FontSet(
            fonts={
                size: ImageFont.truetype(io.BytesIO(data), size=size)
                for size in SCREEN_FONT_SIZES
            },
            has_unicode=True,
        )
    try:
        return FontSet(
            fonts={
                size: ImageFont.load_default(size=size) for size in SCREEN_FONT_SIZES
            },
            has_unicode=False,
        )
    except (TypeError, OSError):  # Pillow without FreeType
        default = ImageFont.load_default()
        return FontSet(
            fonts={size: default for size in SCREEN_FONT_SIZES},
            has_unicode=False,
        )


@dataclass
class ScreenState:
    """What the video shows."""

    title: str
    targets: str
    status: str = "idle"  # idle, recording, sending, sent, no_voice, error
    detail: str = ""
    level: float = 0.0
    started: float = 0.0
    changed: float = 0.0


class Screen:
    """Draw the status frames of an intercom."""

    def __init__(
        self, title: str, targets: str, language: str, fonts: FontSet
    ) -> None:
        """Initialize with fonts already loaded in the executor."""
        self.state = ScreenState(title=title, targets=targets)
        self._text = strings(language)
        self._fonts = fonts.fonts
        self._unicode_font = fonts.has_unicode
        self._cache_key: tuple | None = None
        self._cache: Image.Image | None = None

    def set(self, status: str, detail: str = "") -> None:
        """Change the status."""
        self.state.status = status
        self.state.detail = detail
        self.state.changed = time.monotonic()
        if status == "recording":
            self.state.started = time.monotonic()

    def render(self) -> Image.Image:
        """Return the current frame."""
        state = self.state
        if (
            state.status in ("sent", "no_voice", "error")
            and time.monotonic() - state.changed > RESULT_SECONDS
        ):
            state.status, state.detail = "idle", ""
        level_step = round(min(1.0, state.level) * 24)
        seconds = (
            int(time.monotonic() - state.started) if state.status == "recording" else 0
        )
        key = (state.status, state.detail, state.targets, level_step, seconds)
        if key == self._cache_key and self._cache is not None:
            return self._cache

        image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
        draw = ImageDraw.Draw(image)
        color = {
            "recording": RECORDING,
            "sent": SUCCESS,
            "error": RECORDING,
            "no_voice": MUTED,
        }.get(state.status, ACCENT)

        # Microphone badge
        cx, cy, radius = WIDTH // 2, 120, 54
        if state.status == "recording":
            halo = radius + 10 + level_step * 2
            draw.ellipse((cx - halo, cy - halo, cx + halo, cy + halo), fill=SURFACE)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color)
        draw.rounded_rectangle((cx - 13, cy - 30, cx + 13, cy + 10), radius=13, fill=TEXT)
        draw.arc((cx - 24, cy - 14, cx + 24, cy + 22), start=0, end=180, fill=TEXT, width=5)
        draw.line((cx, cy + 22, cx, cy + 34), fill=TEXT, width=5)
        draw.line((cx - 12, cy + 34, cx + 12, cy + 34), fill=TEXT, width=5)

        status = self._text.get(state.status, state.status)
        if state.status == "recording":
            status = f"{status}  {seconds // 60}:{seconds % 60:02d}"
        if state.detail:
            status = f"{status} · {state.detail}"
        self._centered(draw, 210, state.title, self._fonts[30], TEXT)
        self._centered(draw, 255, status, self._fonts[22], color if state.status != "idle" else MUTED)
        self._centered(draw, 300, f"{self._text['to']}: {state.targets}", self._fonts[22], MUTED)

        # Level bar
        if state.status == "recording":
            width = int((WIDTH - 160) * min(1.0, state.level))
            draw.rounded_rectangle((80, 336, WIDTH - 80, 344), radius=4, fill=SURFACE)
            if width > 0:
                draw.rounded_rectangle((80, 336, 80 + width, 344), radius=4, fill=RECORDING)

        self._cache_key = key
        self._cache = image
        return image

    def _centered(self, draw: ImageDraw.ImageDraw, y: int, text: str, font, fill) -> None:
        if not self._unicode_font:
            text = _strip_diacritics(text)
        if len(text) > 48:
            text = text[:47] + "…"
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(((WIDTH - (box[2] - box[0])) // 2, y), text, font=font, fill=fill)

    def jpeg(self) -> bytes:
        """Return the current frame as JPEG (for the camera snapshot)."""
        buffer = io.BytesIO()
        self.render().save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()


class ScreenTrack(MediaStreamTrack):
    """A slow video track that streams the screen."""

    kind = "video"

    def __init__(self, screen: Screen) -> None:
        """Initialize."""
        super().__init__()
        self._screen = screen
        self._start: float | None = None
        self._pts = 0

    async def recv(self) -> av.VideoFrame:
        """Return the next frame, paced at FPS."""
        if self.readyState != "live":
            raise MediaStreamError
        if self._start is None:
            self._start = time.monotonic()
        else:
            self._pts += VIDEO_CLOCK // FPS
            delay = self._start + self._pts / VIDEO_CLOCK - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
        frame = av.VideoFrame.from_image(self._screen.render())
        frame.pts = self._pts
        frame.time_base = fractions.Fraction(1, VIDEO_CLOCK)
        return frame


type MessageHandler = Callable[[bytes], Awaitable[str]]


class IntercomSession:
    """One WebRTC session of an intercom camera."""

    def __init__(
        self,
        *,
        session_id: str,
        screen: Screen,
        ice_servers: list[RTCIceServer],
        on_message: MessageHandler,
        max_seconds: float,
    ) -> None:
        """Initialize."""
        self.session_id = session_id
        self._screen = screen
        self._on_message = on_message
        self._max_bytes = int(max_seconds * SAMPLE_RATE * 2)
        self._pc = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers))
        self._video = ScreenTrack(screen)
        self._remote_set = False
        self._pending_candidates: list = []
        self._consumer: asyncio.Task | None = None
        self._jobs: set[asyncio.Task] = set()
        self._closed = False
        self._pc.on("track", self._on_track)
        self._pc.on("connectionstatechange", self._on_connection_state)

    async def async_answer(self, offer_sdp: str) -> str:
        """Accept the offer and return the answer, with our candidates in it."""
        await self._pc.setRemoteDescription(
            RTCSessionDescription(sdp=offer_sdp, type="offer")
        )
        self._remote_set = True
        if any(t.kind == "video" for t in self._pc.getTransceivers()):
            self._pc.addTrack(self._video)
        for candidate in self._pending_candidates:
            await self._pc.addIceCandidate(candidate)
        self._pending_candidates.clear()
        answer = await self._pc.createAnswer()
        await self._pc.setLocalDescription(answer)
        return self._pc.localDescription.sdp

    async def async_add_candidate(
        self, candidate: str, sdp_mid: str | None, sdp_m_line_index: int | None
    ) -> None:
        """Add a trickled candidate of the browser or app."""
        if not candidate:
            return  # end of candidates
        parsed = candidate_from_sdp(candidate.removeprefix("candidate:"))
        parsed.sdpMid = sdp_mid
        parsed.sdpMLineIndex = sdp_m_line_index
        if not self._remote_set:
            self._pending_candidates.append(parsed)
            return
        await self._pc.addIceCandidate(parsed)

    def _on_track(self, track: MediaStreamTrack) -> None:
        if track.kind == "audio" and self._consumer is None:
            _LOGGER.debug("Session %s: microphone track received", self.session_id)
            self._consumer = asyncio.create_task(self._consume(track))

    async def _on_connection_state(self) -> None:
        state = self._pc.connectionState
        _LOGGER.debug("Session %s: connection %s", self.session_id, state)
        if state in ("failed", "closed"):
            await self.async_close()

    async def _consume(self, track: MediaStreamTrack) -> None:
        """Collect the voice, one message per stretch of audio."""
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        pcm = bytearray()
        while True:
            try:
                frame = await asyncio.wait_for(track.recv(), INTERCOM_GAP)
            except TimeoutError:
                # The frontend stops sending when the user stops talking
                if pcm:
                    self._finish(bytes(pcm))
                    pcm = bytearray()
                continue
            except MediaStreamError:
                break
            if not pcm:
                self._screen.set("recording")
            for out in resampler.resample(frame):
                chunk = bytes(out.planes[0])[: out.samples * 2]
                pcm += chunk
                self._screen.state.level = _level(chunk)
            if len(pcm) >= self._max_bytes:
                self._finish(bytes(pcm))
                pcm = bytearray()
        if pcm:
            self._finish(bytes(pcm))

    def _finish(self, pcm: bytes) -> None:
        """Send one message in the background."""
        self._screen.state.level = 0.0
        self._screen.set("sending")
        job = asyncio.create_task(self._deliver(pcm))
        self._jobs.add(job)
        job.add_done_callback(self._jobs.discard)

    async def _deliver(self, pcm: bytes) -> None:
        try:
            detail = await self._on_message(pcm)
        except Exception as err:  # noqa: BLE001
            status = getattr(err, "screen_status", "error")
            _LOGGER.log(
                logging.DEBUG if status == "no_voice" else logging.ERROR,
                "Intercom message not sent: %s",
                err,
            )
            self._screen.set(status)
        else:
            self._screen.set("sent", detail)

    async def async_close(self) -> None:
        """Stop the session; a message being recorded is still sent."""
        if self._closed:
            return
        self._closed = True
        self._video.stop()
        await self._pc.close()
        if self._consumer is not None:
            # Closing ends the track, the consumer then sends what it holds
            try:
                await asyncio.wait_for(self._consumer, 2)
            except (TimeoutError, asyncio.CancelledError):
                self._consumer.cancel()
        if self._jobs:
            await asyncio.gather(*self._jobs, return_exceptions=True)


def _level(chunk: bytes) -> float:
    """Return a 0..1 loudness of a PCM chunk, for the meter."""
    samples = array("h", chunk)
    if not samples:
        return 0.0
    peak = max(abs(value) for value in samples[::8])
    # Speech peaks well below full scale: stretch the low end
    return min(1.0, (peak / 32768) ** 0.5 * 1.4)

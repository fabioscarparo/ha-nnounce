"""Audio processing with ffmpeg: clean up the voice, add a chime, encode to MP3."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from .const import CHIME_CUSTOM, CHIME_NONE, MAX_CUSTOM_CHIME_SECONDS

_LOGGER = logging.getLogger(__name__)

SAMPLE_RATE = 44100
BITRATE = 96_000
# Cast speakers often swallow the first fraction of a second
LEAD_IN_MS = 350
TAIL_SECONDS = 0.4
MIN_VOICE_SECONDS = 0.3
FFMPEG_TIMEOUT = 60


class AudioError(Exception):
    """Raised when the audio can't be processed."""


class NoVoiceError(AudioError):
    """Raised when the recording holds no audible voice."""


@dataclass(frozen=True)
class RenderedAudio:
    """An encoded announcement ready to be served."""

    path: Path
    duration: float


def _bell(freq: float, start: float, decay: float, gain: float) -> str:
    """Return an aevalsrc expression of a soft bell note starting at `start`."""
    t = f"(t-{start})"
    return (
        f"{gain}*gte(t,{start})*min(1,{t}*250)*exp(-{decay}*{t})*("
        f"sin(2*PI*{freq}*{t})"
        f"+0.28*sin(2*PI*{freq * 2}*{t})"
        f"+0.08*sin(2*PI*{freq * 2.76:.2f}*{t}))"
    )


# Chimes are synthesized, so no audio asset ships with the integration
CHIME_EXPRESSIONS: dict[str, tuple[str, float]] = {
    "ding_dong": (
        "+".join((_bell(659.25, 0, 3.6, 0.42), _bell(523.25, 0.45, 2.8, 0.42))),
        1.55,
    ),
    "soft": (
        "+".join((_bell(880.0, 0, 4.5, 0.3), _bell(1174.66, 0.16, 3.8, 0.26))),
        1.1,
    ),
    "three_tone": (
        "+".join(
            (
                _bell(523.25, 0, 4.0, 0.34),
                _bell(659.25, 0.22, 4.0, 0.34),
                _bell(783.99, 0.44, 3.0, 0.36),
            )
        ),
        1.6,
    ),
}


def build_ffmpeg_args(
    ffmpeg_binary: str,
    source: Path,
    target: Path,
    *,
    chime: str,
    normalize: bool,
    max_duration: float,
    trim_silence: bool = True,
    highpass: bool = True,
    raw_pcm_rate: int | None = None,
    custom_chime: Path | None = None,
) -> list[str]:
    """Build the ffmpeg command line for one announcement."""
    args = [ffmpeg_binary, "-hide_banner", "-nostdin", "-loglevel", "error", "-y"]

    has_chime = False
    use_custom = chime == CHIME_CUSTOM
    if use_custom:
        if custom_chime is None:
            raise AudioError("Custom chime is not configured")
        args += ["-t", f"{MAX_CUSTOM_CHIME_SECONDS:g}", "-i", str(custom_chime)]
        has_chime = True
    else:
        chime_spec = CHIME_EXPRESSIONS.get(chime) if chime != CHIME_NONE else None
        if chime_spec is not None:
            expression, length = chime_spec
            args += [
                "-f",
                "lavfi",
                "-i",
                f"aevalsrc=exprs='{expression}':s={SAMPLE_RATE}:d={length}",
            ]
            has_chime = True

    voice_index = 1 if has_chime else 0

    if raw_pcm_rate is not None:
        args += ["-f", "s16le", "-ar", str(raw_pcm_rate), "-ac", "1"]
    args += ["-t", f"{max_duration:g}", "-i", str(source)]

    fmt = f"aformat=sample_fmts=fltp:sample_rates={SAMPLE_RATE}:channel_layouts=mono"
    voice = [f"aresample={SAMPLE_RATE}", fmt]
    if highpass:
        voice.append("highpass=f=70")
    if trim_silence:
        cut = (
            "silenceremove=start_periods=1:start_duration=0.05:"
            "start_threshold=-48dB:detection=peak"
        )
        voice += [cut, "areverse", cut, "areverse"]
    if normalize:
        voice += ["loudnorm=I=-16:TP=-1.5:LRA=11", f"aresample={SAMPLE_RATE}", fmt]

    graph = [f"[{voice_index}:a]{','.join(voice)}[voice]"]
    if has_chime:
        chime_chain = f"aresample={SAMPLE_RATE},{fmt}" if use_custom else fmt
        graph.append(f"[0:a]{chime_chain}[chime]")
        graph.append("[chime][voice]concat=n=2:v=0:a=1[joined]")
        joined = "[joined]"
    else:
        joined = "[voice]"
    graph.append(
        f"{joined}adelay={LEAD_IN_MS}:all=1,apad=pad_dur={TAIL_SECONDS},{fmt}[out]"
    )

    args += [
        "-filter_complex",
        ";".join(graph),
        "-map",
        "[out]",
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-c:a",
        "libmp3lame",
        "-b:a",
        str(BITRATE),
        "-write_xing",
        "0",
        "-id3v2_version",
        "0",
        "-f",
        "mp3",
        str(target),
    ]
    return args


def chime_length(chime: str) -> float:
    """Return the length in seconds of a synthesized chime."""
    if spec := CHIME_EXPRESSIONS.get(chime):
        return spec[1]
    return 0.0


def audio_duration(path: Path) -> float:
    """Return the duration in seconds of an audio file, or 0.0 if unreadable."""
    try:
        import mutagen  # noqa: PLC0415

        parsed = mutagen.File(str(path))
        if parsed is not None and parsed.info is not None:
            return float(parsed.info.length)
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def mp3_duration(path: Path) -> float:
    """Return the duration of an MP3 file (blocking)."""
    try:
        from mutagen.mp3 import MP3  # noqa: PLC0415

        return float(MP3(str(path)).info.length)
    except Exception:  # noqa: BLE001
        # Constant bitrate without headers: the size gives the length
        return path.stat().st_size * 8 / BITRATE


async def _run(args: list[str]) -> None:
    """Run ffmpeg and raise AudioError when it fails."""
    _LOGGER.debug("Running %s", " ".join(args))
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as err:
        raise AudioError(f"ffmpeg not found: {args[0]}") from err
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), FFMPEG_TIMEOUT)
    except TimeoutError as err:
        process.kill()
        await process.wait()
        raise AudioError("ffmpeg took too long") from err
    if process.returncode != 0:
        message = stderr.decode(errors="replace").strip().splitlines()
        raise AudioError(message[-1] if message else f"ffmpeg exit {process.returncode}")


async def async_render(
    hass_executor,
    ffmpeg_binary: str,
    source: Path,
    target: Path,
    *,
    chime: str,
    normalize: bool,
    max_duration: float,
    voice_enhancement: bool = True,
    raw_pcm_rate: int | None = None,
    custom_chime: Path | None = None,
    min_voice_seconds: float = MIN_VOICE_SECONDS,
) -> RenderedAudio:
    """Encode a recording into an announcement MP3.

    `hass_executor` is `hass.async_add_executor_job`, used for blocking file reads.
    """
    await _run(
        build_ffmpeg_args(
            ffmpeg_binary,
            source,
            target,
            chime=chime,
            normalize=normalize,
            max_duration=max_duration,
            trim_silence=voice_enhancement,
            highpass=voice_enhancement,
            raw_pcm_rate=raw_pcm_rate,
            custom_chime=custom_chime,
        )
    )
    duration = await hass_executor(mp3_duration, target)
    if chime == CHIME_CUSTOM and custom_chime is not None:
        chime_seconds = min(
            MAX_CUSTOM_CHIME_SECONDS, await hass_executor(audio_duration, custom_chime)
        )
    else:
        chime_seconds = chime_length(chime)
    # Leading and trailing silence is cut when enhancement is on: verify audio remains
    required = min_voice_seconds if voice_enhancement else 0.05
    if duration - LEAD_IN_MS / 1000 - TAIL_SECONDS - chime_seconds < required:
        raise NoVoiceError("The recording is empty or silent")
    return RenderedAudio(target, duration)

"""Audio processing with the real ffmpeg."""

from pathlib import Path

import pytest

from custom_components.hannounce import audio

from .conftest import needs_ffmpeg


async def _executor(func, *args):
    return func(*args)


def test_command_with_chime() -> None:
    args = audio.build_ffmpeg_args("ffmpeg", Path("in.webm"), Path("out.mp3"), chime="ding_dong", normalize=True, max_duration=30)
    graph = args[args.index("-filter_complex") + 1]
    assert args[args.index("-f") + 1] == "lavfi"
    assert "[chime][voice]concat=n=2" in graph
    assert "loudnorm" in graph and "silenceremove" in graph
    assert args[args.index("-t") + 1] == "30"
    assert args[-1] == "out.mp3"


def test_command_without_chime_for_raw_pcm() -> None:
    args = audio.build_ffmpeg_args(
        "ffmpeg", Path("in.pcm"), Path("out.mp3"), chime="none", normalize=False, max_duration=10, raw_pcm_rate=48000
    )
    graph = args[args.index("-filter_complex") + 1]
    assert "lavfi" not in args
    assert args[args.index("-ar") + 1] == "48000"  # the input rate comes first
    assert "concat" not in graph and "loudnorm" not in graph
    assert graph.startswith("[0:a]")


def test_command_with_custom_chime() -> None:
    args = audio.build_ffmpeg_args(
        "ffmpeg",
        Path("in.webm"),
        Path("out.mp3"),
        chime="custom",
        normalize=True,
        max_duration=30,
        custom_chime=Path("/media/chime.wav"),
    )
    graph = args[args.index("-filter_complex") + 1]
    assert "lavfi" not in args
    assert "/media/chime.wav" in args
    assert "[0:a]aresample=44100" in graph
    assert "[chime][voice]concat=n=2" in graph

    with pytest.raises(audio.AudioError):
        audio.build_ffmpeg_args(
            "ffmpeg", Path("in.webm"), Path("out.mp3"), chime="custom", normalize=True, max_duration=30
        )


def test_command_without_voice_enhancement() -> None:
    args = audio.build_ffmpeg_args(
        "ffmpeg",
        Path("in.webm"),
        Path("out.mp3"),
        chime="none",
        normalize=False,
        max_duration=30,
        trim_silence=False,
        highpass=False,
    )
    graph = args[args.index("-filter_complex") + 1]
    assert "highpass" not in graph
    assert "silenceremove" not in graph
    assert "loudnorm" not in graph


@needs_ffmpeg
async def test_render_without_voice_enhancement_keeps_raw_audio(tmp_path: Path, make_wav) -> None:
    source = make_wav("quiet.wav", seconds=1.0, silent=True)
    result = await audio.async_render(
        _executor,
        "ffmpeg",
        source,
        tmp_path / "raw.mp3",
        chime="none",
        normalize=False,
        max_duration=60,
        voice_enhancement=False,
    )
    assert result.duration >= 1.0


@needs_ffmpeg
async def test_render_custom_chime(tmp_path: Path, make_wav) -> None:
    chime_file = make_wav("chime.wav", seconds=0.8)
    voice = make_wav("voice.wav", seconds=1.2)
    result = await audio.async_render(
        _executor,
        "ffmpeg",
        voice,
        tmp_path / "out.mp3",
        chime="custom",
        normalize=True,
        max_duration=60,
        custom_chime=chime_file,
    )
    expected = 1.2 + 0.8 + audio.LEAD_IN_MS / 1000 + audio.TAIL_SECONDS
    assert abs(result.duration - expected) < 0.3

    silent = make_wav("silent.wav", seconds=1.2, silent=True)
    with pytest.raises(audio.NoVoiceError):
        await audio.async_render(
            _executor,
            "ffmpeg",
            silent,
            tmp_path / "silent_out.mp3",
            chime="custom",
            normalize=True,
            max_duration=60,
            custom_chime=chime_file,
        )


@needs_ffmpeg
@pytest.mark.parametrize("chime", ["none", "ding_dong", "soft", "three_tone"])
async def test_render_voice(tmp_path: Path, make_wav, chime: str) -> None:
    source = make_wav(seconds=1.5)
    result = await audio.async_render(
        _executor, "ffmpeg", source, tmp_path / "out.mp3", chime=chime, normalize=True, max_duration=60
    )
    expected = 1.5 + audio.LEAD_IN_MS / 1000 + audio.TAIL_SECONDS + audio.chime_length(chime)
    assert result.path.read_bytes()[:2] in (b"\xff\xfb", b"\xff\xf3", b"ID")
    assert abs(result.duration - expected) < 0.25


@needs_ffmpeg
async def test_render_cuts_to_max_duration(tmp_path: Path, make_wav) -> None:
    source = make_wav(seconds=5)
    result = await audio.async_render(
        _executor, "ffmpeg", source, tmp_path / "out.mp3", chime="none", normalize=False, max_duration=2
    )
    assert result.duration < 2 + audio.LEAD_IN_MS / 1000 + audio.TAIL_SECONDS + 0.2


@needs_ffmpeg
async def test_silence_is_refused(tmp_path: Path, make_wav) -> None:
    source = make_wav(silent=True)
    with pytest.raises(audio.NoVoiceError):
        await audio.async_render(_executor, "ffmpeg", source, tmp_path / "out.mp3", chime="ding_dong", normalize=True, max_duration=60)


async def test_broken_file_is_an_audio_error(tmp_path: Path) -> None:
    source = tmp_path / "broken.webm"
    source.write_bytes(b"not audio")
    with pytest.raises(audio.AudioError):
        await audio.async_render(_executor, "ffmpeg", source, tmp_path / "out.mp3", chime="none", normalize=True, max_duration=60)


def test_command_for_alexa() -> None:
    args = audio.build_alexa_ffmpeg_args("ffmpeg", Path("in.mp3"), Path("out-alexa.mp3"))
    assert args[args.index("-t") + 1] == "240"
    assert args[args.index("-ac") + 1] == "1"
    assert args[args.index("-ar") + 1] == "24000"
    assert args[args.index("-b:a") + 1] == "48000"
    assert args[args.index("-write_xing") + 1] == "0"
    assert args[args.index("-id3v2_version") + 1] == "0"
    assert args[-1] == "out-alexa.mp3"


@needs_ffmpeg
async def test_render_alexa_mp3(tmp_path: Path, make_wav) -> None:
    from mutagen.mp3 import MP3

    source = make_wav(seconds=1.2)
    standard = await audio.async_render(
        _executor, "ffmpeg", source, tmp_path / "out.mp3", chime="soft", normalize=True, max_duration=60
    )
    alexa_path = await audio.async_render_alexa(
        "ffmpeg", standard.path, tmp_path / "out-alexa.mp3"
    )
    info = MP3(str(alexa_path)).info
    assert info.sample_rate == 24000
    assert info.bitrate == 48000
    assert info.channels == 1
    assert abs(info.length - standard.duration) < 0.25

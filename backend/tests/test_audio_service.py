import subprocess
from pathlib import Path

import pytest

from app.errors import AudioAssemblyError, FfmpegMissingError
from app.services.audio_service import assemble_audio, build_ffmpeg_command, ffmpeg_available
from tests.fakes import FakeTTSEngine

requires_ffmpeg = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not installed")


def test_build_ffmpeg_command_uses_settings() -> None:
    command = build_ffmpeg_command(Path("list.txt"), Path("out.mp3"), "96k", 2)

    assert command[0] == "ffmpeg"
    assert command[command.index("-b:a") + 1] == "96k"
    assert command[command.index("-ac") + 1] == "2"
    assert command[-1] == "out.mp3"


def test_assemble_audio_requires_chunks(tmp_path: Path) -> None:
    if not ffmpeg_available():
        pytest.skip("ffmpeg not installed")
    with pytest.raises(AudioAssemblyError):
        assemble_audio([], tmp_path / "out.mp3")


def test_missing_ffmpeg_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.audio_service.shutil.which", lambda _: None)

    with pytest.raises(FfmpegMissingError, match="brew install ffmpeg"):
        assemble_audio([tmp_path / "a.wav"], tmp_path / "out.mp3")


@requires_ffmpeg
def test_assemble_audio_concatenates_chunks_into_mp3(tmp_path: Path) -> None:
    engine = FakeTTSEngine(seconds_per_chunk=0.5)
    wavs = []
    for index in range(3):
        path = tmp_path / f"chunk_{index:03d}.wav"
        engine.synthesize_to_wav("x", path)
        wavs.append(path)

    output = assemble_audio(wavs, tmp_path / "out" / "final.mp3", "64k", 1)

    assert output.exists()
    assert not (tmp_path / "out" / "concat.txt").exists()
    duration = float(
        subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", output],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    assert 1.4 <= duration <= 1.7


@requires_ffmpeg
def test_assemble_audio_reports_encoding_failures(tmp_path: Path) -> None:
    broken = tmp_path / "broken.wav"
    broken.write_bytes(b"not a wav")

    with pytest.raises(AudioAssemblyError):
        assemble_audio([broken], tmp_path / "out.mp3")

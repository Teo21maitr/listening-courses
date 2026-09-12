"""Concatenate WAV chunks into the final MP3 with FFmpeg."""

import logging
import shutil
import subprocess
from pathlib import Path

from app.errors import AudioAssemblyError, FfmpegMissingError

logger = logging.getLogger(__name__)

CONCAT_LIST_FILENAME = "concat.txt"


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def check_ffmpeg() -> None:
    if not ffmpeg_available():
        raise FfmpegMissingError("FFmpeg is not installed. On macOS run: brew install ffmpeg")


def assemble_audio(
    wav_paths: list[Path], output_path: Path, bitrate: str = "128k", channels: int = 1
) -> Path:
    """Concatenate the WAV files in order and encode them as MP3 in one FFmpeg pass."""
    check_ffmpeg()
    if not wav_paths:
        raise AudioAssemblyError("No audio chunks to assemble.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    list_path = output_path.parent / CONCAT_LIST_FILENAME
    list_path.write_text(_concat_list(wav_paths), encoding="utf-8")

    command = build_ffmpeg_command(list_path, output_path, bitrate, channels)
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        logger.error("FFmpeg failed (%s): %s", error.returncode, error.stderr.strip())
        raise AudioAssemblyError("Audio assembly failed while encoding the MP3.") from error
    finally:
        list_path.unlink(missing_ok=True)
    return output_path


def build_ffmpeg_command(
    list_path: Path, output_path: Path, bitrate: str, channels: int
) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-codec:a", "libmp3lame",
        "-b:a", bitrate,
        "-ac", str(channels),
        str(output_path),
    ]


def _concat_list(wav_paths: list[Path]) -> str:
    return "".join(f"file '{_escape_path(path)}'\n" for path in wav_paths)


def _escape_path(path: Path) -> str:
    """Concat demuxer syntax: single quotes inside the path become '\\''."""
    return str(path.resolve()).replace("'", "'\\''")

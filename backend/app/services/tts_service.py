"""Text-to-speech with Piper.

`TTSEngine` is the seam used by tests (and by any future engine): the pipeline
only needs something that turns a text into a WAV file.
"""

import logging
import wave
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.config import Settings, get_settings
from app.errors import (
    AudioGenerationError,
    PiperNotInstalledError,
    UnknownLanguageError,
    VoiceModelMissingError,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]

CHUNK_FILENAME_FORMAT = "chunk_{index:03d}.wav"


class TTSEngine(Protocol):
    def synthesize_to_wav(self, text: str, output_path: Path) -> None: ...


class PiperEngine:
    def __init__(self, model_path: Path, config_path: Path) -> None:
        try:
            from piper import PiperVoice
        except ImportError as error:
            raise PiperNotInstalledError(
                "Piper TTS is not installed. Run: pip install piper-tts"
            ) from error
        self._voice = PiperVoice.load(model_path, config_path)

    def synthesize_to_wav(self, text: str, output_path: Path) -> None:
        with wave.open(str(output_path), "wb") as wav_file:
            self._voice.synthesize_wav(text, wav_file)


def resolve_voice_paths(language: str, settings: Settings) -> tuple[Path, Path]:
    """Return (model, config) for a language, or raise a clear error."""
    voices = settings.voice_models
    if language not in voices:
        raise UnknownLanguageError(
            f"Unknown language '{language}'. Supported: {', '.join(voices)}."
        )
    voice = voices[language]
    if not voice["model"].exists() or not voice["config"].exists():
        raise VoiceModelMissingError(
            f"Piper voice '{voice['voice']}' for language '{language}' is missing "
            f"in {voice['model'].parent}. Run: python scripts/download_voices.py {language}"
        )
    return voice["model"], voice["config"]


@lru_cache(maxsize=4)
def _load_piper_engine(model_path: Path, config_path: Path) -> PiperEngine:
    logger.info("Loading Piper voice %s", model_path.name)
    return PiperEngine(model_path, config_path)


def get_engine(language: str, settings: Settings | None = None) -> TTSEngine:
    """Piper engine for a language, loaded once per process."""
    model_path, config_path = resolve_voice_paths(language, settings or get_settings())
    return _load_piper_engine(model_path, config_path)


def generate_audio(
    text_chunks: list[str],
    language: str,
    output_dir: Path,
    on_progress: ProgressCallback | None = None,
    engine: TTSEngine | None = None,
) -> list[Path]:
    """Synthesize one WAV per chunk (chunk_001.wav, ...) and return them in order."""
    engine = engine or get_engine(language)
    output_dir.mkdir(parents=True, exist_ok=True)
    total = len(text_chunks)
    paths: list[Path] = []
    for index, chunk in enumerate(text_chunks, start=1):
        path = output_dir / CHUNK_FILENAME_FORMAT.format(index=index)
        try:
            engine.synthesize_to_wav(chunk, path)
        except Exception as error:
            logger.exception("Piper failed on chunk %d/%d", index, total)
            raise AudioGenerationError(
                f"Audio generation failed on chunk {index}/{total}."
            ) from error
        paths.append(path)
        if on_progress:
            on_progress(index, total)
    return paths

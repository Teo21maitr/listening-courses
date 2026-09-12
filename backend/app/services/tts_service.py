"""Text-to-speech engines (Piper, Kokoro) behind one small interface.

`TTSEngine` is the seam used by the pipeline and by tests: something that turns
a text into a WAV file. The engine is chosen per language in the settings.
Both engines synthesize paragraph by paragraph and insert explicit silences,
which is what makes the reading breathe.
"""

import logging
import wave
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from app.config import KOKORO_LANG_CODES, Settings, get_settings
from app.errors import (
    AudioGenerationError,
    TTSNotInstalledError,
    UnknownEngineError,
    UnknownLanguageError,
    VoiceModelMissingError,
)
from app.services.pdf_service import PARAGRAPH_SEPARATOR

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]

CHUNK_FILENAME_FORMAT = "chunk_{index:03d}.wav"
KOKORO_SAMPLE_RATE = 24000
SAMPLE_WIDTH_BYTES = 2  # 16-bit PCM
DOWNLOAD_HINT = "Run: python scripts/download_voices.py"


class TTSEngine(Protocol):
    def synthesize_to_wav(self, text: str, output_path: Path) -> None: ...


@dataclass(frozen=True)
class Prosody:
    """Speaking rate and silences shared by every engine (hashable: used as a cache key)."""

    speed: float = 1.0
    sentence_pause_ms: int = 250
    paragraph_pause_ms: int = 600

    @classmethod
    def from_settings(cls, settings: Settings) -> "Prosody":
        return cls(settings.tts_speed, settings.tts_sentence_pause_ms, settings.tts_paragraph_pause_ms)


class WavWriter:
    """Mono 16-bit WAV writer that can append silence."""

    def __init__(self, path: Path, sample_rate: int) -> None:
        self._wav = wave.open(str(path), "wb")
        self._wav.setnchannels(1)
        self._wav.setsampwidth(SAMPLE_WIDTH_BYTES)
        self._wav.setframerate(sample_rate)
        self._sample_rate = sample_rate

    def write(self, pcm16: bytes) -> None:
        self._wav.writeframes(pcm16)

    def write_silence(self, milliseconds: int) -> None:
        frames = self._sample_rate * milliseconds // 1000
        self._wav.writeframes(b"\x00" * (frames * SAMPLE_WIDTH_BYTES))

    def close(self) -> None:
        self._wav.close()

    def __enter__(self) -> "WavWriter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def split_paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in text.split(PARAGRAPH_SEPARATOR) if paragraph.strip()]


class PiperEngine:
    def __init__(self, model_path: Path, config_path: Path, prosody: Prosody) -> None:
        try:
            from piper import PiperVoice, SynthesisConfig
        except ImportError as error:
            raise TTSNotInstalledError("Piper TTS is not installed. Run: pip install piper-tts") from error
        self._voice = PiperVoice.load(model_path, config_path)
        # Piper's length_scale is the inverse of a speed factor.
        self._syn_config = SynthesisConfig(length_scale=1 / prosody.speed)
        self._prosody = prosody

    def synthesize_to_wav(self, text: str, output_path: Path) -> None:
        with WavWriter(output_path, self._voice.config.sample_rate) as wav:
            for paragraph in split_paragraphs(text):
                sentences = self._voice.synthesize(paragraph, syn_config=self._syn_config)
                _write_sentences(wav, (chunk.audio_int16_bytes for chunk in sentences), self._prosody)
                wav.write_silence(self._prosody.paragraph_pause_ms)


class KokoroEngine:
    def __init__(self, kokoro: Any, voice: str, lang: str, prosody: Prosody) -> None:
        self._kokoro = kokoro
        self._voice = voice
        self._lang = lang
        self._prosody = prosody

    def synthesize_to_wav(self, text: str, output_path: Path) -> None:
        with WavWriter(output_path, KOKORO_SAMPLE_RATE) as wav:
            for paragraph in split_paragraphs(text):
                samples, sample_rate = self._kokoro.create(
                    paragraph,
                    voice=self._voice,
                    speed=self._prosody.speed,
                    lang=self._lang,
                    sentence_pause=self._prosody.sentence_pause_ms / 1000,
                )
                if sample_rate != KOKORO_SAMPLE_RATE:
                    raise AudioGenerationError(f"Unexpected Kokoro sample rate {sample_rate}.")
                wav.write(_float_to_pcm16(samples))
                wav.write_silence(self._prosody.paragraph_pause_ms)


def _write_sentences(wav: WavWriter, sentences: Iterable[bytes], prosody: Prosody) -> None:
    for index, pcm in enumerate(sentences):
        if index > 0:
            wav.write_silence(prosody.sentence_pause_ms)
        wav.write(pcm)


def _float_to_pcm16(samples: Any) -> bytes:
    import numpy as np

    clipped = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
    return (clipped * 32767).astype(np.int16).tobytes()


# --- Engine resolution -------------------------------------------------------


def resolve_voice_paths(language: str, settings: Settings) -> tuple[Path, Path]:
    """Return Piper (model, config) for a language, or raise a clear error."""
    voices = settings.voice_models
    _check_language(language, settings)
    voice = voices[language]
    if not voice["model"].exists() or not voice["config"].exists():
        raise VoiceModelMissingError(
            f"Piper voice '{voice['voice']}' for language '{language}' is missing "
            f"in {voice['model'].parent}. {DOWNLOAD_HINT} {language}"
        )
    return voice["model"], voice["config"]


def resolve_kokoro_paths(settings: Settings) -> tuple[Path, Path]:
    model, voices = settings.kokoro_model_path, settings.kokoro_voices_path
    if not model.exists() or not voices.exists():
        raise VoiceModelMissingError(
            f"Kokoro model files are missing in {model.parent} "
            f"({model.name}, {voices.name}). {DOWNLOAD_HINT}"
        )
    return model, voices


def engine_ready(language: str, settings: Settings) -> bool:
    try:
        check_engine_ready(language, settings)
    except (VoiceModelMissingError, UnknownEngineError, UnknownLanguageError):
        return False
    return True


def check_engine_ready(language: str, settings: Settings) -> None:
    """Raise a clear error if the engine configured for a language cannot run."""
    engine = _engine_name(language, settings)
    if engine == "piper":
        resolve_voice_paths(language, settings)
    else:
        resolve_kokoro_paths(settings)


def get_engine(language: str, settings: Settings | None = None) -> TTSEngine:
    """Engine for a language, models loaded once per process."""
    settings = settings or get_settings()
    prosody = Prosody.from_settings(settings)
    if _engine_name(language, settings) == "piper":
        model_path, config_path = resolve_voice_paths(language, settings)
        return _load_piper_engine(model_path, config_path, prosody)
    model_path, voices_path = resolve_kokoro_paths(settings)
    kokoro = _load_kokoro(model_path, voices_path)
    return KokoroEngine(kokoro, settings.kokoro_voices[language], KOKORO_LANG_CODES[language], prosody)


def _engine_name(language: str, settings: Settings) -> str:
    _check_language(language, settings)
    engine = settings.engines[language]
    if engine not in ("piper", "kokoro"):
        raise UnknownEngineError(f"Unknown TTS engine '{engine}' for language '{language}' (use piper or kokoro).")
    return engine


def _check_language(language: str, settings: Settings) -> None:
    if language not in settings.engines:
        raise UnknownLanguageError(f"Unknown language '{language}'. Supported: {', '.join(settings.engines)}.")


@lru_cache(maxsize=4)
def _load_piper_engine(model_path: Path, config_path: Path, prosody: Prosody) -> PiperEngine:
    logger.info("Loading Piper voice %s", model_path.name)
    return PiperEngine(model_path, config_path, prosody)


@lru_cache(maxsize=1)
def _load_kokoro(model_path: Path, voices_path: Path) -> Any:
    try:
        from kokoro_onnx import Kokoro
    except ImportError as error:
        raise TTSNotInstalledError("Kokoro is not installed. Run: pip install kokoro-onnx") from error
    # phonemizer logs a harmless "words count mismatch" warning on almost every call
    logging.getLogger("phonemizer").setLevel(logging.ERROR)
    logger.info("Loading Kokoro model %s", model_path.name)
    return Kokoro(str(model_path), str(voices_path))


# --- Generation --------------------------------------------------------------


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
            logger.exception("TTS failed on chunk %d/%d", index, total)
            raise AudioGenerationError(f"Audio generation failed on chunk {index}/{total}.") from error
        paths.append(path)
        if on_progress:
            on_progress(index, total)
    return paths

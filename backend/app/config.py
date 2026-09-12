from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

SUPPORTED_LANGUAGES = ("fr", "en")
SUPPORTED_ENGINES = ("piper", "kokoro")

# espeak-ng language codes used by Kokoro
KOKORO_LANG_CODES = {"fr": "fr-fr", "en": "en-us"}


class VoiceModel(TypedDict):
    voice: str
    model: Path
    config: Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    max_pdf_size_mb: int = 100
    text_chunk_max_chars: int = 1500
    output_audio_bitrate: str = "128k"
    output_audio_channels: int = 1
    temp_dir: Path = Path("./tmp")
    piper_models_dir: Path = Path("./models/piper")
    piper_voice_fr: str = "fr_FR-siwis-medium"
    piper_voice_en: str = "en_US-lessac-medium"
    tts_engine_fr: str = "kokoro"
    tts_engine_en: str = "kokoro"
    kokoro_models_dir: Path = Path("./models/kokoro")
    kokoro_model_file: str = "kokoro-v1.0.onnx"
    kokoro_voices_file: str = "voices-v1.0.bin"
    kokoro_voice_fr: str = "ff_siwis"
    kokoro_voice_en: str = "af_heart"
    tts_speed: float = 1.0
    tts_sentence_pause_ms: int = 250
    tts_paragraph_pause_ms: int = 600
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_dist_dir: Path | None = None
    job_ttl_hours: float = 6
    max_concurrent_jobs: int = 1

    @property
    def max_pdf_size_bytes(self) -> int:
        return self.max_pdf_size_mb * 1024 * 1024

    @property
    def temp_path(self) -> Path:
        return _resolve(self.temp_dir)

    @property
    def jobs_path(self) -> Path:
        return self.temp_path / "jobs"

    @property
    def models_path(self) -> Path:
        return _resolve(self.piper_models_dir)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def engines(self) -> dict[str, str]:
        """Language code -> TTS engine name ("piper" or "kokoro")."""
        return {"fr": self.tts_engine_fr, "en": self.tts_engine_en}

    @property
    def kokoro_model_path(self) -> Path:
        return _resolve(self.kokoro_models_dir) / self.kokoro_model_file

    @property
    def kokoro_voices_path(self) -> Path:
        return _resolve(self.kokoro_models_dir) / self.kokoro_voices_file

    @property
    def kokoro_voices(self) -> dict[str, str]:
        return {"fr": self.kokoro_voice_fr, "en": self.kokoro_voice_en}

    @property
    def voice_models(self) -> dict[str, VoiceModel]:
        """Language code -> Piper voice files. Add a language here (and a PIPER_VOICE_* setting)."""
        voices = {"fr": self.piper_voice_fr, "en": self.piper_voice_en}
        return {
            language: {
                "voice": voice,
                "model": self.models_path / language / f"{voice}.onnx",
                "config": self.models_path / language / f"{voice}.onnx.json",
            }
            for language, voice in voices.items()
        }


def _resolve(path: Path) -> Path:
    """Relative paths are resolved against backend/, never against the process cwd."""
    return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()

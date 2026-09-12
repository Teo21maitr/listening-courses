from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

SUPPORTED_LANGUAGES = ("fr", "en")


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

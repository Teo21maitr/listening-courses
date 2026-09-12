from pathlib import Path

import pytest

from app.config import Settings
from app.errors import AudioGenerationError, UnknownLanguageError, VoiceModelMissingError
from app.services.tts_service import generate_audio, resolve_voice_paths
from tests.fakes import FailingTTSEngine, FakeTTSEngine


def test_generate_audio_writes_one_ordered_wav_per_chunk(tmp_path: Path) -> None:
    engine = FakeTTSEngine()
    progress: list[tuple[int, int]] = []

    paths = generate_audio(
        ["one", "two", "three"],
        "en",
        tmp_path / "chunks",
        lambda done, total: progress.append((done, total)),
        engine,
    )

    assert [path.name for path in paths] == ["chunk_001.wav", "chunk_002.wav", "chunk_003.wav"]
    assert all(path.exists() for path in paths)
    assert engine.texts == ["one", "two", "three"]
    assert progress == [(1, 3), (2, 3), (3, 3)]


def test_generate_audio_wraps_engine_failures(tmp_path: Path) -> None:
    with pytest.raises(AudioGenerationError, match="chunk 1/2"):
        generate_audio(["a", "b"], "en", tmp_path, engine=FailingTTSEngine())


def test_resolve_voice_paths_unknown_language(tmp_path: Path) -> None:
    settings = Settings(piper_models_dir=tmp_path)

    with pytest.raises(UnknownLanguageError, match="Supported: fr, en"):
        resolve_voice_paths("de", settings)


def test_resolve_voice_paths_missing_model(tmp_path: Path) -> None:
    settings = Settings(piper_models_dir=tmp_path)

    with pytest.raises(VoiceModelMissingError, match="download_voices.py fr"):
        resolve_voice_paths("fr", settings)


def test_resolve_voice_paths_finds_configured_files(tmp_path: Path) -> None:
    settings = Settings(piper_models_dir=tmp_path, piper_voice_en="en_US-test-low")
    (tmp_path / "en").mkdir()
    (tmp_path / "en" / "en_US-test-low.onnx").write_bytes(b"model")
    (tmp_path / "en" / "en_US-test-low.onnx.json").write_text("{}")

    model, config = resolve_voice_paths("en", settings)

    assert model.name == "en_US-test-low.onnx"
    assert config.name == "en_US-test-low.onnx.json"

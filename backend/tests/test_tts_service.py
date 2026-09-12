import wave
from pathlib import Path

import numpy as np
import pytest

from app.config import Settings
from app.errors import (
    AudioGenerationError,
    UnknownEngineError,
    UnknownLanguageError,
    VoiceModelMissingError,
)
from app.services.tts_service import (
    KOKORO_SAMPLE_RATE,
    KokoroEngine,
    PiperEngine,
    Prosody,
    WavWriter,
    check_engine_ready,
    engine_ready,
    generate_audio,
    get_engine,
    resolve_kokoro_paths,
    resolve_voice_paths,
)
from tests.fakes import FailingTTSEngine, FakeTTSEngine


def wav_duration_ms(path: Path) -> int:
    with wave.open(str(path)) as wav:
        return round(1000 * wav.getnframes() / wav.getframerate())


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


def test_wav_writer_silence_has_the_requested_duration(tmp_path: Path) -> None:
    path = tmp_path / "out.wav"
    with WavWriter(path, 16000) as wav:
        wav.write(b"\x00\x00" * 1600)  # 100 ms
        wav.write_silence(250)

    assert wav_duration_ms(path) == 350
    with wave.open(str(path)) as handle:
        assert (handle.getnchannels(), handle.getsampwidth(), handle.getframerate()) == (1, 2, 16000)


class StubPiperVoice:
    """Mimics piper.PiperVoice: one AudioChunk per sentence."""

    class Config:
        sample_rate = 22050

    class Chunk:
        def __init__(self, ms: int) -> None:
            self.audio_int16_bytes = b"\x01\x00" * (22050 * ms // 1000)

    config = Config()

    def __init__(self) -> None:
        self.calls: list[str] = []

    def synthesize(self, text: str, syn_config=None):
        self.calls.append(text)
        return [self.Chunk(100) for _ in text.split(". ") if _]


def test_piper_engine_inserts_sentence_and_paragraph_pauses(tmp_path: Path) -> None:
    engine = PiperEngine.__new__(PiperEngine)
    engine._voice = StubPiperVoice()
    engine._syn_config = None
    engine._prosody = Prosody(speed=1.0, sentence_pause_ms=200, paragraph_pause_ms=500)

    engine.synthesize_to_wav("Heading.\n\nOne. Two. Three.", tmp_path / "p.wav")

    assert engine._voice.calls == ["Heading.", "One. Two. Three."]
    # 4 sentences x 100 ms + 2 sentence pauses x 200 ms + 2 paragraph pauses x 500 ms
    assert wav_duration_ms(tmp_path / "p.wav") == 400 + 400 + 1000


class StubKokoro:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, text, voice, speed, lang, sentence_pause):
        self.calls.append({"text": text, "voice": voice, "speed": speed, "lang": lang, "pause": sentence_pause})
        return np.full(KOKORO_SAMPLE_RATE // 10, 0.5, dtype=np.float32), KOKORO_SAMPLE_RATE  # 100 ms


def test_kokoro_engine_converts_to_pcm16_and_pauses_between_paragraphs(tmp_path: Path) -> None:
    kokoro = StubKokoro()
    engine = KokoroEngine(kokoro, "af_heart", "en-us", Prosody(1.1, 250, 400))

    engine.synthesize_to_wav("First paragraph.\n\nSecond one.", tmp_path / "k.wav")

    assert [call["text"] for call in kokoro.calls] == ["First paragraph.", "Second one."]
    assert kokoro.calls[0] == {"text": "First paragraph.", "voice": "af_heart", "speed": 1.1, "lang": "en-us", "pause": 0.25}
    assert wav_duration_ms(tmp_path / "k.wav") == 2 * 100 + 2 * 400
    with wave.open(str(tmp_path / "k.wav")) as wav:
        first_sample = int.from_bytes(wav.readframes(1), "little", signed=True)
    assert first_sample == int(0.5 * 32767)


@pytest.fixture
def models(tmp_path: Path) -> Settings:
    piper_dir = tmp_path / "piper"
    (piper_dir / "en").mkdir(parents=True)
    (piper_dir / "en" / "en_US-lessac-medium.onnx").write_bytes(b"model")
    (piper_dir / "en" / "en_US-lessac-medium.onnx.json").write_text("{}")
    kokoro_dir = tmp_path / "kokoro"
    kokoro_dir.mkdir()
    (kokoro_dir / "kokoro-v1.0.onnx").write_bytes(b"model")
    (kokoro_dir / "voices-v1.0.bin").write_bytes(b"voices")
    return Settings(piper_models_dir=piper_dir, kokoro_models_dir=kokoro_dir, tts_engine_en="piper", tts_engine_fr="kokoro")


def test_resolve_voice_paths_unknown_language(models: Settings) -> None:
    with pytest.raises(UnknownLanguageError, match="Supported: fr, en"):
        resolve_voice_paths("de", models)


def test_resolve_voice_paths_missing_model(tmp_path: Path) -> None:
    with pytest.raises(VoiceModelMissingError, match="download_voices.py fr"):
        resolve_voice_paths("fr", Settings(piper_models_dir=tmp_path))


def test_resolve_kokoro_paths_missing_files(tmp_path: Path) -> None:
    with pytest.raises(VoiceModelMissingError, match="Kokoro model files are missing"):
        resolve_kokoro_paths(Settings(kokoro_models_dir=tmp_path))


def test_engine_readiness_follows_the_configured_engine(models: Settings) -> None:
    assert engine_ready("en", models)  # piper files present
    assert engine_ready("fr", models)  # kokoro files present
    assert not engine_ready("fr", Settings(piper_models_dir=models.piper_models_dir, kokoro_models_dir=models.piper_models_dir, tts_engine_fr="kokoro"))


def test_unknown_engine_name_is_reported(models: Settings) -> None:
    settings = Settings(piper_models_dir=models.piper_models_dir, tts_engine_en="espeak")

    with pytest.raises(UnknownEngineError, match="espeak"):
        check_engine_ready("en", settings)


def test_get_engine_builds_a_kokoro_engine_per_language(models: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubKokoro()
    monkeypatch.setattr("app.services.tts_service._load_kokoro", lambda model, voices: stub)

    engine = get_engine("fr", models)

    assert isinstance(engine, KokoroEngine)
    assert engine._voice == "ff_siwis" and engine._lang == "fr-fr"

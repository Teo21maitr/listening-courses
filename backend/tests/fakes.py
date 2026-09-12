"""Test doubles shared by several test modules."""

import wave
from pathlib import Path

SAMPLE_RATE = 22050


class FakeTTSEngine:
    """Writes a short silent WAV instead of running Piper."""

    def __init__(self, seconds_per_chunk: float = 0.1) -> None:
        self.seconds_per_chunk = seconds_per_chunk
        self.texts: list[str] = []

    def synthesize_to_wav(self, text: str, output_path: Path) -> None:
        self.texts.append(text)
        frames = int(SAMPLE_RATE * self.seconds_per_chunk)
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(b"\x00\x00" * frames)


class FailingTTSEngine:
    def synthesize_to_wav(self, text: str, output_path: Path) -> None:
        raise RuntimeError("boom")

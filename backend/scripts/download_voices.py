"""Download the TTS models configured in app.config.

Piper voices go to models/piper/<lang>/, Kokoro files to models/kokoro/.
Run explicitly (never at server start-up):

    python scripts/download_voices.py          # everything the configured engines need
    python scripts/download_voices.py fr       # one language only
"""

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings, get_settings  # noqa: E402

KOKORO_RELEASE_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"


def main(languages: list[str]) -> int:
    settings = get_settings()
    unknown = [language for language in languages if language not in settings.engines]
    if unknown:
        print(f"Unknown language(s): {', '.join(unknown)}. Available: {', '.join(settings.engines)}")
        return 1

    kokoro_needed = False
    for language in languages or list(settings.engines):
        if settings.engines[language] == "kokoro":
            kokoro_needed = True
        else:
            download_piper_voice(language, settings)
    if kokoro_needed:
        download_kokoro(settings)
    return 0


def download_piper_voice(language: str, settings: Settings) -> None:
    from piper.download_voices import download_voice

    voice = settings.voice_models[language]
    if voice["model"].exists() and voice["config"].exists():
        print(f"[{language}] Piper voice {voice['voice']} already present, skipping")
        return
    target_dir = voice["model"].parent
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{language}] downloading Piper voice {voice['voice']} into {target_dir} ...")
    download_voice(voice["voice"], target_dir)
    print(f"[{language}] done")


def download_kokoro(settings: Settings) -> None:
    for path in (settings.kokoro_model_path, settings.kokoro_voices_path):
        if path.exists():
            print(f"[kokoro] {path.name} already present, skipping")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        url = KOKORO_RELEASE_URL + path.name
        print(f"[kokoro] downloading {url} ...")
        _download(url, path)
        print(f"[kokoro] done ({path.stat().st_size // (1024 * 1024)} MB)")


def _download(url: str, destination: Path) -> None:
    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        urllib.request.urlretrieve(url, partial)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(destination)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

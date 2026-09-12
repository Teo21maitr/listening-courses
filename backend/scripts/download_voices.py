"""Download the Piper voices configured in app.config into models/piper/<lang>/.

Run explicitly (never at server start-up):

    python scripts/download_voices.py          # all configured languages
    python scripts/download_voices.py fr       # one language only
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from piper.download_voices import download_voice  # noqa: E402

from app.config import get_settings  # noqa: E402


def main(languages: list[str]) -> int:
    settings = get_settings()
    voices = settings.voice_models
    unknown = [language for language in languages if language not in voices]
    if unknown:
        print(f"Unknown language(s): {', '.join(unknown)}. Available: {', '.join(voices)}")
        return 1

    for language in languages or list(voices):
        voice = voices[language]
        if voice["model"].exists() and voice["config"].exists():
            print(f"[{language}] {voice['voice']} already present, skipping")
            continue
        target_dir = voice["model"].parent
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{language}] downloading {voice['voice']} into {target_dir} ...")
        download_voice(voice["voice"], target_dir)
        print(f"[{language}] done")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

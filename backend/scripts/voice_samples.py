"""Synthesize the same excerpt with several voices to compare them by ear.

    python scripts/voice_samples.py --lang en --out /tmp/samples \\
        piper:en_US-lessac-medium piper:en_US-hfc_female-medium kokoro:af_heart kokoro:bm_george

Piper voices missing from models/piper/<lang>/ are downloaded on the fly.
Kokoro needs its model files (python scripts/download_voices.py). Output: one
MP3 per voice named <engine>_<voice>.mp3, plus <engine>_<voice>.wav.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import KOKORO_LANG_CODES, get_settings  # noqa: E402
from app.services.audio_service import assemble_audio  # noqa: E402
from app.services.text_cleaner import clean_text  # noqa: E402
from app.services.tts_service import (  # noqa: E402
    KokoroEngine,
    PiperEngine,
    Prosody,
    TTSEngine,
    _load_kokoro,
    resolve_kokoro_paths,
)

EXCERPTS = {
    "en": (
        "1 Introduction\n\n"
        "The recent FBI reports show that individuals aged 60 and older filed over 100,000 fraud "
        "complaints a year and incurred the highest financial losses among all age groups. "
        "Researchers have investigated defense methods against SMS phishing, with a focus on the "
        "detection problem.\n\n"
        "They aim to detect phishing messages by analyzing textual features, or by verifying the "
        "sender identity. However, a warning alone rarely explains why a message is dangerous, "
        "which is exactly what older adults told us they needed."
    ),
    "fr": (
        "Deux grandes familles\n\n"
        "En cryptographie symétrique, la même clé sert à chiffrer et à déchiffrer : c'est rapide, "
        "mais la transmission des clés est difficile, puisqu'il faut une clé par couple de "
        "correspondants.\n\n"
        "En cryptographie asymétrique, la clé publique peut être diffusée librement tandis que la "
        "clé privée reste secrète. C'est l'analogie de la boîte aux lettres : tout le monde peut y "
        "déposer un message, seul le propriétaire peut l'ouvrir."
    ),
}


def build_engine(spec: str, language: str, prosody: Prosody) -> TTSEngine:
    engine_name, voice = spec.split(":", 1)
    settings = get_settings()
    if engine_name == "piper":
        model_dir = settings.models_path / language
        model, config = model_dir / f"{voice}.onnx", model_dir / f"{voice}.onnx.json"
        if not model.exists():
            from piper.download_voices import download_voice

            model_dir.mkdir(parents=True, exist_ok=True)
            print(f"  downloading Piper voice {voice} ...")
            download_voice(voice, model_dir)
        return PiperEngine(model, config, prosody)
    if engine_name == "kokoro":
        kokoro = _load_kokoro(*resolve_kokoro_paths(settings))
        return KokoroEngine(kokoro, voice, KOKORO_LANG_CODES[language], prosody)
    raise SystemExit(f"Unknown engine in '{spec}' (use piper:<voice> or kokoro:<voice>)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", choices=list(EXCERPTS), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--text", help="custom excerpt (default: built-in excerpt for the language)")
    parser.add_argument("voices", nargs="+", help="engine:voice, e.g. piper:en_US-lessac-medium kokoro:af_heart")
    args = parser.parse_args()

    settings = get_settings()
    prosody = Prosody.from_settings(settings)
    text = clean_text(args.text or EXCERPTS[args.lang])
    args.out.mkdir(parents=True, exist_ok=True)

    for spec in args.voices:
        print(f"[{args.lang}] {spec}")
        engine = build_engine(spec, args.lang, prosody)
        wav = args.out / f"{spec.replace(':', '_')}.wav"
        engine.synthesize_to_wav(text, wav)
        mp3 = assemble_audio([wav], wav.with_suffix(".mp3"), settings.output_audio_bitrate, settings.output_audio_channels)
        print(f"  -> {mp3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# PDF to Audio

Transforme un PDF en livre audio MP3 avec une synthèse vocale **100 % locale et gratuite** (Kokoro ou Piper).
Aucune API payante, aucun service cloud : le PDF est lu, nettoyé, découpé, synthétisé et assemblé sur la machine qui héberge le backend.

```
React (Vite) ──▶ FastAPI ──▶ PyMuPDF ──▶ nettoyage ──▶ chunks ──▶ Kokoro / Piper ──▶ FFmpeg ──▶ MP3
```

- Import d'un PDF (drag & drop), choix de la langue du document (🇫🇷 / 🇬🇧).
- Extraction du texte page par page, nettoyage pensé pour l'écoute (césures, numéros de page, headers/footers répétés, citations, URLs, ponctuation des titres…) et pauses entre phrases et paragraphes.
- Deux moteurs de synthèse au choix par langue : **Kokoro** (naturel, plus lent) ou **Piper** (rapide, plus synthétique).
- Génération asynchrone avec progression réelle (`Generating audio 12/48`).
- Lecteur audio intégré + téléchargement du MP3 (`mon_document_audio_fr.mp3`).

## Stack

| Couche | Technologies |
|---|---|
| Frontend | React 19, TypeScript strict, Vite, CSS pur (mobile-first) |
| Backend | Python 3.13, FastAPI, Uvicorn, pydantic-settings |
| PDF | PyMuPDF (`pymupdf`) |
| TTS | [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) via [`kokoro-onnx`](https://github.com/thewh1teagle/kokoro-onnx) et [Piper](https://github.com/OHF-Voice/piper1-gpl) via `piper-tts` (ONNX, CPU) |
| Audio | FFmpeg (concaténation + encodage MP3 128 kbps mono) |
| Déploiement | Docker (image unique), Railway |

## Démarrage rapide

```bash
./start.sh
```

Le script vérifie les prérequis, crée le venv et installe les dépendances si besoin, propose de télécharger les modèles de voix manquants, lance le backend et le frontend, puis affiche l'URL à ouvrir (http://localhost:5173). `Ctrl+C` arrête tout.

- `./start.sh --prod` : build du frontend et un seul serveur sur http://localhost:8000 (comme en production).
- `./start.sh --yes` : télécharge les modèles manquants sans demander.
- `BACKEND_PORT=8010 FRONTEND_PORT=3000 ./start.sh` : autres ports.

Les sections suivantes détaillent chaque étape pour un lancement manuel.

## Prérequis

- macOS (testé sur Apple Silicon) ou Linux
- Python 3.11+ (3.13 recommandé, `backend/.python-version`)
- Node.js 20+ et npm
- FFmpeg
- ~350 Mo d'espace disque pour le modèle Kokoro (ou ~130 Mo pour deux voix Piper)

### Installer FFmpeg (macOS)

```bash
brew install ffmpeg
```

Vérifier : `ffmpeg -version`.

### Installer les moteurs TTS

Kokoro (`kokoro-onnx`) et Piper (`piper-tts`) sont des dépendances Python de `backend/requirements.txt`.
Les deux embarquent espeak-ng et fournissent des wheels pour macOS arm64/x86_64 et Linux : aucune installation système supplémentaire.

### Récupérer les modèles de voix

Un script télécharge ce dont les moteurs configurés ont besoin (à lancer explicitement, jamais au démarrage du serveur) :

```bash
cd backend
source .venv/bin/activate
python scripts/download_voices.py        # fr + en
python scripts/download_voices.py fr     # une seule langue
```

Configuration par défaut (`backend/.env.example`) :

| Langue | Moteur | Voix | Fichiers |
|---|---|---|---|
| `fr` | Kokoro | `ff_siwis` | `backend/models/kokoro/kokoro-v1.0.onnx` (310 Mo) + `voices-v1.0.bin` (27 Mo), communs à toutes les langues |
| `en` | Kokoro | `af_heart` | idem |

- **Kokoro** : modèle [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (Apache 2.0), fichiers ONNX distribués par [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx/releases). Voix disponibles : voir [VOICES.md](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md) (`af_*`/`am_*` anglais US, `bf_*`/`bm_*` anglais UK, `ff_siwis` français). Une version quantifiée plus légère existe : `KOKORO_MODEL_FILE=kokoro-v1.0.int8.onnx` (~80 Mo, un peu plus rapide, qualité légèrement moindre).
- **Piper** : voix du dépôt [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices), un dossier par langue (`backend/models/piper/fr/`, `.../en/`), chaque voix = `.onnx` + `.onnx.json` (~63 Mo). Pour l'utiliser : `TTS_ENGINE_EN=piper` et `PIPER_VOICE_EN=en_US-lessac-medium` (par exemple), puis relance le script.

Ordres de grandeur sur un MacBook M4 : Piper synthétise ~50× plus vite que le temps réel, Kokoro ~4-5× (un document d'une heure d'écoute prend ~13 min). Les modèles ne sont pas commités (`.gitignore`).

Pour comparer des voix à l'oreille sur un même extrait :

```bash
python scripts/voice_samples.py --lang en --out /tmp/samples kokoro:af_heart kokoro:bm_george piper:en_US-ryan-high
```

## Lancer le backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt     # requirements.txt + pytest/httpx
cp .env.example .env                    # optionnel : ajuster la config
python scripts/download_voices.py
uvicorn app.main:app --reload
```

API sur http://localhost:8000 (documentation interactive : http://localhost:8000/docs).

`GET /api/health` indique si FFmpeg et les voix sont disponibles :

```json
{"status": "ok", "ffmpeg": true, "engines": {"fr": "kokoro", "en": "kokoro"}, "voices": {"fr": true, "en": true}, "max_pdf_size_mb": 100}
```

## Lancer le frontend

```bash
cd frontend
npm install
npm run dev
```

Interface sur http://localhost:5173 (le fichier `frontend/.env.development` pointe vers le backend sur le port 8000 ; CORS est configuré côté backend via `CORS_ORIGINS`).

## Tester

Tests backend (les moteurs TTS sont mockés ; les tests qui assemblent un MP3 sont ignorés si FFmpeg est absent) :

```bash
cd backend && source .venv/bin/activate
pytest
```

Frontend :

```bash
cd frontend
npm run lint && npm run build
```

Test manuel de bout en bout avec `curl` :

```bash
curl -F "file=@mon_document.pdf" -F language=fr http://localhost:8000/api/jobs
# → {"id":"<uuid>","status":"queued"}
curl http://localhost:8000/api/jobs/<uuid>
# → {"status":"generating_audio","progress":42,"message":"Generating audio 2/5",...}
curl -OJ http://localhost:8000/api/jobs/<uuid>/audio
```

## API

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/jobs` | multipart `file` (PDF) + `language` (`fr` / `en`) → `{id, status}` |
| `GET` | `/api/jobs/{id}` | état du job : `status`, `progress` (0-100), `message`, `audio_url`, `error` |
| `GET` | `/api/jobs/{id}/audio` | le MP3 (`Content-Disposition` avec un nom dérivé du PDF) |
| `GET` | `/api/health` | disponibilité de FFmpeg et des voix |

Statuts : `queued → extracting → cleaning → generating_audio → assembling → completed` (ou `failed`).

## Configuration

Variables lues depuis `backend/.env` (voir `backend/.env.example`) :

| Variable | Défaut | Rôle |
|---|---|---|
| `MAX_PDF_SIZE_MB` | `100` | taille maximale d'un PDF |
| `TEXT_CHUNK_MAX_CHARS` | `1500` | taille des morceaux envoyés à Piper |
| `OUTPUT_AUDIO_BITRATE` / `OUTPUT_AUDIO_CHANNELS` | `128k` / `1` | encodage du MP3 |
| `TEMP_DIR` | `./tmp` | dossier de travail (uploads, chunks, MP3) |
| `TTS_ENGINE_FR` / `TTS_ENGINE_EN` | `kokoro` / `kokoro` | moteur par langue (`kokoro` ou `piper`) |
| `KOKORO_MODELS_DIR`, `KOKORO_MODEL_FILE`, `KOKORO_VOICES_FILE` | `./models/kokoro`, `kokoro-v1.0.onnx`, `voices-v1.0.bin` | fichiers Kokoro |
| `KOKORO_VOICE_FR` / `KOKORO_VOICE_EN` | `ff_siwis` / `af_heart` | voix Kokoro par langue |
| `PIPER_MODELS_DIR` | `./models/piper` | dossier des voix Piper |
| `PIPER_VOICE_FR` / `PIPER_VOICE_EN` | `fr_FR-siwis-medium` / `en_US-lessac-medium` | voix Piper par langue |
| `TTS_SPEED` | `1.0` | débit (>1 plus rapide, <1 plus lent) |
| `TTS_SENTENCE_PAUSE_MS` / `TTS_PARAGRAPH_PAUSE_MS` | `250` / `600` | silences insérés entre phrases et entre paragraphes |
| `CORS_ORIGINS` | `http://localhost:5173,...` | origines autorisées en dev |
| `FRONTEND_DIST_DIR` | *(vide)* | si défini, FastAPI sert le frontend buildé sur `/` |
| `JOB_TTL_HOURS` | `6` | purge des jobs terminés (MP3 compris) |
| `MAX_CONCURRENT_JOBS` | `1` | jobs traités en parallèle (Piper est CPU-bound) |

Le frontend a sa propre constante `MAX_PDF_SIZE_MB` dans `frontend/src/config.ts` (validation avant upload ; la limite réelle est celle du backend).

## Docker

Une seule image : le frontend est buildé puis servi par FastAPI, FFmpeg et les voix sont installés dans l'image.

```bash
docker compose up --build
```

Application complète sur http://localhost:8000. Le moteur et les voix sont fixés au build (les modèles sont téléchargés dans l'image) :

```bash
docker build --build-arg KOKORO_VOICE_EN=bm_george -t pdf-to-audio .          # autre voix Kokoro
docker build --build-arg KOKORO_MODEL_FILE=kokoro-v1.0.int8.onnx -t pdf-to-audio .  # modèle léger
docker build --build-arg TTS_ENGINE_FR=piper --build-arg TTS_ENGINE_EN=piper -t pdf-to-audio .  # Piper partout
```

## Déploiement sur Railway

La branche `main` est celle déployée. `railway.toml` indique à Railway d'utiliser le `Dockerfile` et le healthcheck `/api/health`.

1. Créer un projet Railway et le lier au dépôt GitHub (branche `main`), ou depuis le terminal :
   ```bash
   railway login
   railway init          # ou railway link pour un projet existant
   railway up
   ```
2. Aucune variable obligatoire : `PORT` est fourni par Railway, le frontend est servi par le backend.
   Variables utiles : `MAX_PDF_SIZE_MB`, `JOB_TTL_HOURS`, `TEXT_CHUNK_MAX_CHARS`.
3. Le premier build télécharge le modèle Kokoro (~340 Mo) ; les suivants profitent du cache Docker.

À savoir : le disque Railway est éphémère (les MP3 disparaissent au redéploiement, ce qui est voulu), l'état des jobs est en mémoire (un seul worker) et la synthèse tourne sur CPU. Kokoro demande ~700 Mo de RAM et un CPU partagé est nettement plus lent qu'un M4 : compter de l'ordre de la durée d'écoute pour générer un document (un livre de 2 h peut prendre 1 à 2 h). Pour un petit plan, préférer `KOKORO_MODEL_FILE=kokoro-v1.0.int8.onnx` ou Piper (`TTS_ENGINE_*=piper`, ~20× plus rapide).

## Architecture

```
backend/
├── app/
│   ├── main.py              # création de l'app, CORS, handlers d'erreurs, frontend statique
│   ├── config.py            # Settings (.env) + VOICE_MODELS par langue
│   ├── errors.py            # erreurs métier avec message propre pour le frontend
│   ├── api/jobs.py          # routes REST + validation des uploads
│   ├── models/job.py        # Job, JobStatus, schémas de réponse
│   ├── services/
│   │   ├── pdf_service.py   # extraction PyMuPDF (point d'entrée futur pour l'OCR)
│   │   ├── text_cleaner.py  # fonctions de nettoyage unitaires
│   │   ├── text_chunker.py  # découpage paragraphes > phrases > mots
│   │   ├── tts_service.py   # TTSEngine + KokoroEngine / PiperEngine, pauses, choix par langue
│   │   └── audio_service.py # assemblage FFmpeg
│   └── jobs/
│       ├── pipeline.py      # PDF → MP3 avec callback de progression
│       └── manager.py       # store en mémoire + exécution en arrière-plan
├── models/piper/{fr,en}/    # voix (non commitées)
├── scripts/download_voices.py   # télécharge les modèles des moteurs configurés
├── scripts/voice_samples.py     # compare des voix sur un même extrait
└── tests/
frontend/src/
├── components/              # PdfUploader, LanguageSelector, Progress, AudioPlayer
├── api/jobs.ts              # client HTTP
├── hooks/useJobPolling.ts   # polling toutes les 1,5 s
├── types/job.ts
└── App.tsx
```

Une étape de traduction pourra s'insérer entre `clean_pages` et `chunk_text` dans `jobs/pipeline.py` sans toucher au reste.

## Limitations actuelles

```text
Current limitations:
- No translation
- No OCR for scanned PDFs
- French and English only
- Local processing only
```

Et aussi :

- pas d'authentification : ne pas exposer publiquement sans protection (Railway : restreindre l'accès ou ajouter une auth) ;
- état des jobs en mémoire : un redémarrage du serveur perd les jobs en cours ;
- un seul job à la fois par défaut (`MAX_CONCURRENT_JOBS`) ;
- Kokoro est lent sur CPU (~4-5× le temps réel sur M4, moins sur un serveur partagé) ; Piper reste disponible pour aller vite ;
- la voix française de Kokoro (`ff_siwis`) commet parfois des erreurs de prononciation ;
- les tableaux, formules et schémas d'un PDF donnent un texte peu lisible à l'oral.

# PDF to Audio

Transforme un PDF en livre audio MP3 avec une synthèse vocale **100 % locale et gratuite** (Piper TTS).
Aucune API payante, aucun service cloud : le PDF est lu, nettoyé, découpé, synthétisé et assemblé sur la machine qui héberge le backend.

```
React (Vite) ──▶ FastAPI ──▶ PyMuPDF ──▶ nettoyage ──▶ chunks ──▶ Piper TTS ──▶ FFmpeg ──▶ MP3
```

- Import d'un PDF (drag & drop), choix de la langue du document (🇫🇷 / 🇬🇧).
- Extraction du texte page par page, nettoyage pensé pour l'écoute (césures, numéros de page, headers/footers répétés, citations, URLs…).
- Génération asynchrone avec progression réelle (`Generating audio 12/48`).
- Lecteur audio intégré + téléchargement du MP3 (`mon_document_audio_fr.mp3`).

## Stack

| Couche | Technologies |
|---|---|
| Frontend | React 19, TypeScript strict, Vite, CSS pur (mobile-first) |
| Backend | Python 3.13, FastAPI, Uvicorn, pydantic-settings |
| PDF | PyMuPDF (`pymupdf`) |
| TTS | [Piper](https://github.com/OHF-Voice/piper1-gpl) via le package `piper-tts` (ONNX, CPU) |
| Audio | FFmpeg (concaténation + encodage MP3 128 kbps mono) |
| Déploiement | Docker (image unique), Railway |

## Prérequis

- macOS (testé sur Apple Silicon) ou Linux
- Python 3.11+ (3.13 recommandé, `backend/.python-version`)
- Node.js 20+ et npm
- FFmpeg
- ~130 Mo d'espace disque pour les deux voix Piper

### Installer FFmpeg (macOS)

```bash
brew install ffmpeg
```

Vérifier : `ffmpeg -version`.

### Installer Piper

Piper est installé comme dépendance Python (`piper-tts` dans `backend/requirements.txt`).
Le package embarque espeak-ng et fournit des wheels pour macOS arm64/x86_64 et Linux : aucune installation système supplémentaire.

### Récupérer les voix

Les voix viennent du dépôt HuggingFace [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices).
Un script les télécharge dans le bon dossier (à lancer explicitement, jamais au démarrage du serveur) :

```bash
cd backend
source .venv/bin/activate
python scripts/download_voices.py        # fr + en
python scripts/download_voices.py fr     # une seule langue
```

Voix par défaut (configurables dans `.env`) :

| Langue | Voix | Emplacement |
|---|---|---|
| `fr` | `fr_FR-siwis-medium` | `backend/models/piper/fr/` |
| `en` | `en_US-lessac-medium` | `backend/models/piper/en/` |

Chaque voix = un fichier `.onnx` + un fichier `.onnx.json` (~63 Mo). Pour changer de voix, modifie `PIPER_VOICE_FR` / `PIPER_VOICE_EN` dans `backend/.env` puis relance le script. Les modèles ne sont pas commités (`.gitignore`).

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
{"status": "ok", "ffmpeg": true, "voices": {"fr": true, "en": true}, "max_pdf_size_mb": 100}
```

## Lancer le frontend

```bash
cd frontend
npm install
npm run dev
```

Interface sur http://localhost:5173 (le fichier `frontend/.env.development` pointe vers le backend sur le port 8000 ; CORS est configuré côté backend via `CORS_ORIGINS`).

## Tester

Tests backend (Piper est mocké ; les tests qui assemblent un MP3 sont ignorés si FFmpeg est absent) :

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
| `PIPER_MODELS_DIR` | `./models/piper` | dossier des voix |
| `PIPER_VOICE_FR` / `PIPER_VOICE_EN` | `fr_FR-siwis-medium` / `en_US-lessac-medium` | voix par langue |
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

Application complète sur http://localhost:8000. Pour changer de voix au build :

```bash
docker build --build-arg PIPER_VOICE_EN=en_GB-alan-medium -t pdf-to-audio .
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
3. Le premier build télécharge les deux voix (~130 Mo) ; les suivants profitent du cache Docker.

À savoir : le disque Railway est éphémère (les MP3 disparaissent au redéploiement, ce qui est voulu), l'état des jobs est en mémoire (un seul worker) et la synthèse tourne sur CPU — un document de 20 pages prend environ une minute sur un petit plan.

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
│   │   ├── tts_service.py   # abstraction TTSEngine + PiperEngine
│   │   └── audio_service.py # assemblage FFmpeg
│   └── jobs/
│       ├── pipeline.py      # PDF → MP3 avec callback de progression
│       └── manager.py       # store en mémoire + exécution en arrière-plan
├── models/piper/{fr,en}/    # voix (non commitées)
├── scripts/download_voices.py
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
- les tableaux, formules et schémas d'un PDF donnent un texte peu lisible à l'oral.

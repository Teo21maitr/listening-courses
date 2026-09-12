# ---- Stage 1: build the React frontend -------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend + FFmpeg + Piper voices ------------------------
FROM python:3.13-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./

# Voices are fetched explicitly at build time (never at server start-up).
# Override the voices with --build-arg if you change PIPER_VOICE_* in config.
ARG PIPER_VOICE_FR=fr_FR-siwis-medium
ARG PIPER_VOICE_EN=en_US-lessac-medium
ENV PIPER_VOICE_FR=${PIPER_VOICE_FR} \
    PIPER_VOICE_EN=${PIPER_VOICE_EN}
RUN python scripts/download_voices.py

COPY --from=frontend /frontend/dist /app/frontend/dist

ENV FRONTEND_DIST_DIR=/app/frontend/dist \
    TEMP_DIR=/tmp/pdf-to-audio \
    PORT=8000

EXPOSE 8000

# Single worker: job state lives in memory (see app/jobs/manager.py).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

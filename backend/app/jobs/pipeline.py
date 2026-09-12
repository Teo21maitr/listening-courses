"""PDF -> text -> chunks -> WAV chunks -> MP3.

The pipeline knows nothing about HTTP or job storage: it reports progress
through a callback and returns the final MP3 path.
"""

import logging
import shutil
from collections.abc import Callable
from pathlib import Path

from app.config import Settings
from app.errors import ScannedPdfError
from app.models.job import JobStatus
from app.services.audio_service import assemble_audio, check_ffmpeg
from app.services.pdf_service import extract_pages
from app.services.text_chunker import chunk_text
from app.services.text_cleaner import clean_pages
from app.services.tts_service import TTSEngine, generate_audio, get_engine

logger = logging.getLogger(__name__)

StatusReporter = Callable[[JobStatus, int, str], None]

CHUNKS_DIRNAME = "chunks"
OUTPUT_FILENAME = "output.mp3"

# Progress budget of each stage (see SPECS §9)
PROGRESS_EXTRACTING = 0
PROGRESS_CLEANING = 5
PROGRESS_GENERATING_START = 10
PROGRESS_GENERATING_END = 90
PROGRESS_ASSEMBLING = 90
PROGRESS_ASSEMBLED = 99


def run_pipeline(
    pdf_path: Path,
    language: str,
    work_dir: Path,
    report: StatusReporter,
    settings: Settings,
    engine: TTSEngine | None = None,
) -> Path:
    # Fail fast on missing tools before spending minutes on synthesis.
    check_ffmpeg()
    engine = engine or get_engine(language, settings)

    report(JobStatus.EXTRACTING, PROGRESS_EXTRACTING, "Extracting PDF...")
    pages = extract_pages(pdf_path)

    report(JobStatus.CLEANING, PROGRESS_CLEANING, "Cleaning text...")
    chunks = chunk_text(clean_pages(pages), settings.text_chunk_max_chars)
    if not chunks:
        raise ScannedPdfError("No readable text left after cleaning the PDF.")
    logger.info("%d chunk(s) to synthesize for %s", len(chunks), pdf_path.name)

    total = len(chunks)
    report(JobStatus.GENERATING_AUDIO, PROGRESS_GENERATING_START, f"Generating audio 0/{total}")
    chunks_dir = work_dir / CHUNKS_DIRNAME
    wav_paths = generate_audio(
        chunks,
        language,
        chunks_dir,
        on_progress=lambda done, total: report(
            JobStatus.GENERATING_AUDIO,
            _generation_progress(done, total),
            f"Generating audio {done}/{total}",
        ),
        engine=engine,
    )

    report(JobStatus.ASSEMBLING, PROGRESS_ASSEMBLING, "Assembling audio...")
    output_path = assemble_audio(
        wav_paths,
        work_dir / OUTPUT_FILENAME,
        settings.output_audio_bitrate,
        settings.output_audio_channels,
    )
    shutil.rmtree(chunks_dir, ignore_errors=True)
    report(JobStatus.ASSEMBLING, PROGRESS_ASSEMBLED, "Finalizing...")
    return output_path


def _generation_progress(done: int, total: int) -> int:
    span = PROGRESS_GENERATING_END - PROGRESS_GENERATING_START
    return PROGRESS_GENERATING_START + span * done // total

from pathlib import Path

import pytest

from app.config import Settings
from app.errors import ScannedPdfError
from app.jobs.pipeline import run_pipeline
from app.models.job import JobStatus
from app.services.audio_service import ffmpeg_available
from tests.conftest import PdfFactory
from tests.fakes import FakeTTSEngine

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not installed")


def test_pipeline_produces_mp3_and_reports_each_stage(
    make_pdf: PdfFactory, tmp_path: Path
) -> None:
    pdf = make_pdf(["First page of the document. " * 3, "Second page with more text. " * 3])
    settings = Settings(text_chunk_max_chars=60)
    engine = FakeTTSEngine()
    reports: list[tuple[JobStatus, int, str]] = []

    output = run_pipeline(
        pdf, "en", tmp_path / "work", lambda *args: reports.append(args), settings, engine
    )

    assert output == tmp_path / "work" / "output.mp3"
    assert output.stat().st_size > 0
    assert not (tmp_path / "work" / "chunks").exists()
    statuses = [status for status, _, _ in reports]
    assert statuses[0] == JobStatus.EXTRACTING
    assert JobStatus.CLEANING in statuses
    assert JobStatus.GENERATING_AUDIO in statuses
    assert statuses[-1] == JobStatus.ASSEMBLING
    progresses = [progress for _, progress, _ in reports]
    assert progresses == sorted(progresses) and progresses[-1] == 99
    assert any(message == f"Generating audio {len(engine.texts)}/{len(engine.texts)}" for _, _, message in reports)


def test_pipeline_rejects_pdf_without_text(tmp_path: Path) -> None:
    import pymupdf

    document = pymupdf.open()
    document.new_page()
    pdf = tmp_path / "blank.pdf"
    document.save(pdf)
    document.close()

    with pytest.raises(ScannedPdfError):
        run_pipeline(pdf, "en", tmp_path / "work", lambda *_: None, Settings(), FakeTTSEngine())

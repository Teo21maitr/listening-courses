import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.config import Settings
from app.errors import AudioNotReadyError, JobNotFoundError
from app.jobs.manager import UNEXPECTED_ERROR_MESSAGE, JobManager
from app.models.job import JobStatus


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(temp_dir=tmp_path)


def test_create_and_get(settings: Settings) -> None:
    manager = JobManager(settings)

    job = manager.create("doc.pdf", "en")

    assert manager.get(job.id) is job
    assert job.status == JobStatus.QUEUED
    assert job.progress == 0
    assert job.work_dir.is_dir()
    assert job.work_dir.parent == settings.jobs_path


def test_get_unknown_job(settings: Settings) -> None:
    with pytest.raises(JobNotFoundError):
        JobManager(settings).get("missing")


def test_audio_path_requires_completion(settings: Settings) -> None:
    manager = JobManager(settings)
    job = manager.create("doc.pdf", "en")

    with pytest.raises(AudioNotReadyError):
        manager.audio_path(job.id)


def test_run_success_updates_job(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_pipeline(pdf_path, language, work_dir, report, settings, engine):
        report(JobStatus.EXTRACTING, 0, "Extracting PDF...")
        report(JobStatus.GENERATING_AUDIO, 50, "Generating audio 1/2")
        (work_dir / "output.mp3").write_bytes(b"mp3")
        return work_dir / "output.mp3"

    monkeypatch.setattr("app.jobs.manager.run_pipeline", fake_pipeline)
    manager = JobManager(settings)
    job = manager.create("doc.pdf", "en")
    pdf = job.work_dir / "input.pdf"
    pdf.write_bytes(b"%PDF-")

    manager.start(job.id, pdf)
    _wait(job)

    assert job.status == JobStatus.COMPLETED
    assert job.progress == 100
    assert job.audio_url == f"/api/jobs/{job.id}/audio"
    assert manager.audio_path(job.id).exists()
    assert not pdf.exists()


def test_run_crash_marks_job_failed_without_stack_trace(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    def crashing_pipeline(pdf_path, language, work_dir, report, settings, engine):
        (work_dir / "chunks").mkdir()
        (work_dir / "chunks" / "chunk_001.wav").write_bytes(b"wav")
        raise RuntimeError("secret internal details")

    monkeypatch.setattr("app.jobs.manager.run_pipeline", crashing_pipeline)
    manager = JobManager(settings)
    job = manager.create("doc.pdf", "en")

    manager.start(job.id, job.work_dir / "input.pdf")
    _wait(job)

    assert job.status == JobStatus.FAILED
    assert job.error == UNEXPECTED_ERROR_MESSAGE
    assert "secret" not in (job.error or "")
    assert not (job.work_dir / "chunks").exists()


def test_cleanup_expired_removes_finished_jobs_only(settings: Settings) -> None:
    manager = JobManager(settings)
    old_done = manager.create("a.pdf", "en")
    old_done.status = JobStatus.COMPLETED
    old_done.created_at = datetime.now(UTC) - timedelta(hours=2)
    old_running = manager.create("b.pdf", "en")
    old_running.status = JobStatus.GENERATING_AUDIO
    old_running.created_at = datetime.now(UTC) - timedelta(hours=2)
    fresh_done = manager.create("c.pdf", "en")
    fresh_done.status = JobStatus.FAILED

    removed = manager.cleanup_expired(timedelta(hours=1))

    assert removed == 1
    assert not old_done.work_dir.exists()
    assert old_running.work_dir.exists() and fresh_done.work_dir.exists()
    with pytest.raises(JobNotFoundError):
        manager.get(old_done.id)


def test_cleanup_orphans_removes_unknown_folders(settings: Settings) -> None:
    manager = JobManager(settings)
    known = manager.create("a.pdf", "en")
    orphan = settings.jobs_path / "leftover-from-previous-run"
    orphan.mkdir()

    assert manager.cleanup_orphans() == 1
    assert not orphan.exists()
    assert known.work_dir.exists()


def _wait(job, timeout: float = 5) -> None:
    deadline = time.time() + timeout
    while not job.is_finished and time.time() < deadline:
        time.sleep(0.01)

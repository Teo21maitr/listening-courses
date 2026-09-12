"""In-memory job store + background execution.

State lives in the process (no database in V1), so the API must run as a single
worker. Jobs run on a small thread pool because Piper is CPU-bound and blocking.
"""

import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.config import Settings
from app.errors import AppError, AudioNotReadyError, JobNotFoundError
from app.jobs.pipeline import OUTPUT_FILENAME, run_pipeline
from app.models.job import Job, JobStatus
from app.services.tts_service import TTSEngine

logger = logging.getLogger(__name__)

UNEXPECTED_ERROR_MESSAGE = "Unexpected error during generation. Check the server logs."


class JobManager:
    def __init__(self, settings: Settings, engine: TTSEngine | None = None) -> None:
        self._settings = settings
        self._engine = engine
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_concurrent_jobs, thread_name_prefix="job"
        )
        settings.jobs_path.mkdir(parents=True, exist_ok=True)

    def create(self, filename: str, language: str) -> Job:
        job_id = str(uuid4())
        work_dir = self._settings.jobs_path / job_id
        work_dir.mkdir(parents=True)
        job = Job(id=job_id, filename=filename, language=language, work_dir=work_dir)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError("Job not found.")
        return job

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def start(self, job_id: str, pdf_path: Path) -> None:
        self._executor.submit(self._run, job_id, pdf_path)

    def audio_path(self, job_id: str) -> Path:
        job = self.get(job_id)
        if job.status != JobStatus.COMPLETED:
            raise AudioNotReadyError("The audio is not ready yet.")
        return job.work_dir / OUTPUT_FILENAME

    def delete(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is not None:
            shutil.rmtree(job.work_dir, ignore_errors=True)

    def cleanup_expired(self, ttl: timedelta) -> int:
        """Delete finished jobs (and their files) older than ttl."""
        cutoff = datetime.now(UTC) - ttl
        expired = [job.id for job in self.list_jobs() if job.is_finished and job.created_at < cutoff]
        for job_id in expired:
            self.delete(job_id)
        return len(expired)

    def cleanup_orphans(self) -> int:
        """Remove job folders left on disk by a previous run (their state is lost)."""
        known = {job.id for job in self.list_jobs()}
        orphans = [path for path in self._settings.jobs_path.iterdir() if path.is_dir() and path.name not in known]
        for path in orphans:
            shutil.rmtree(path, ignore_errors=True)
        return len(orphans)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, job_id: str, pdf_path: Path) -> None:
        job = self.get(job_id)
        try:
            run_pipeline(
                pdf_path, job.language, job.work_dir, self._reporter(job_id), self._settings, self._engine
            )
            self._set(job_id, JobStatus.COMPLETED, 100, "Done", audio_url=f"/api/jobs/{job_id}/audio")
            logger.info("Job %s completed", job_id)
        except AppError as error:
            logger.warning("Job %s failed: %s", job_id, error.message)
            self._set(job_id, JobStatus.FAILED, job.progress, "Failed", error=error.message)
        except Exception:
            logger.exception("Job %s crashed", job_id)
            self._set(job_id, JobStatus.FAILED, job.progress, "Failed", error=UNEXPECTED_ERROR_MESSAGE)
        finally:
            pdf_path.unlink(missing_ok=True)

    def _reporter(self, job_id: str):  # noqa: ANN202 - returns a StatusReporter
        return lambda status, progress, message: self._set(job_id, status, progress, message)

    def _set(
        self,
        job_id: str,
        status: JobStatus,
        progress: int,
        message: str,
        audio_url: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:  # deleted while running
                return
            job.status = status
            job.progress = progress
            job.message = message
            if audio_url is not None:
                job.audio_url = audio_url
            if error is not None:
                job.error = error

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel


class JobStatus(StrEnum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    CLEANING = "cleaning"
    GENERATING_AUDIO = "generating_audio"
    ASSEMBLING = "assembling"
    COMPLETED = "completed"
    FAILED = "failed"


FINAL_STATUSES = frozenset({JobStatus.COMPLETED, JobStatus.FAILED})


@dataclass
class Job:
    id: str
    filename: str
    language: str
    work_dir: Path
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0
    message: str = "Queued"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    audio_url: str | None = None
    error: str | None = None

    @property
    def is_finished(self) -> bool:
        return self.status in FINAL_STATUSES


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    progress: int
    message: str
    filename: str
    language: str
    created_at: datetime
    audio_url: str | None
    error: str | None

    @classmethod
    def from_job(cls, job: Job) -> "JobResponse":
        return cls(
            id=job.id,
            status=job.status,
            progress=job.progress,
            message=job.message,
            filename=job.filename,
            language=job.language,
            created_at=job.created_at,
            audio_url=job.audio_url,
            error=job.error,
        )


class JobCreatedResponse(BaseModel):
    id: str
    status: JobStatus

import re
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.errors import FileTooLargeError, InvalidFileError, JobNotFoundError, UnknownLanguageError
from app.jobs.manager import JobManager
from app.models.job import JobCreatedResponse, JobResponse
from app.services.audio_service import check_ffmpeg, ffmpeg_available
from app.services.tts_service import check_engine_ready, engine_ready

router = APIRouter(prefix="/api", tags=["jobs"])

UPLOAD_FILENAME = "input.pdf"
PDF_SIGNATURE = b"%PDF-"
PDF_SIGNATURE_WINDOW = 1024  # the header may be preceded by a few junk bytes
ACCEPTED_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream", "", None}
COPY_CHUNK_SIZE = 1024 * 1024


def get_job_manager(request: Request) -> JobManager:
    return request.app.state.job_manager


SettingsDep = Annotated[Settings, Depends(get_settings)]
ManagerDep = Annotated[JobManager, Depends(get_job_manager)]


@router.get("/health")
def health(settings: SettingsDep) -> dict[str, object]:
    return {
        "status": "ok",
        "ffmpeg": ffmpeg_available(),
        "engines": settings.engines,
        "voices": {language: engine_ready(language, settings) for language in settings.engines},
        "max_pdf_size_mb": settings.max_pdf_size_mb,
    }


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(
    request: Request,
    settings: SettingsDep,
    manager: ManagerDep,
    file: Annotated[UploadFile, File()],
    language: Annotated[str, Form()],
) -> JobCreatedResponse:
    language = language.strip().lower()
    _validate_language(language, settings)
    _validate_upload_metadata(file)
    _validate_content_length(request, settings)
    # Fail fast on missing tools instead of accepting a job doomed to fail.
    check_ffmpeg()
    check_engine_ready(language, settings)

    job = manager.create(filename=file.filename or "document.pdf", language=language)
    pdf_path = job.work_dir / UPLOAD_FILENAME
    try:
        await _save_upload(file, pdf_path, settings.max_pdf_size_bytes)
        _validate_pdf_signature(pdf_path)
    except Exception:
        manager.delete(job.id)
        raise
    manager.start(job.id, pdf_path)
    return JobCreatedResponse(id=job.id, status=job.status)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, manager: ManagerDep) -> JobResponse:
    return JobResponse.from_job(manager.get(_validate_job_id(job_id)))


@router.get("/jobs/{job_id}/audio")
def get_job_audio(job_id: str, manager: ManagerDep) -> FileResponse:
    job = manager.get(_validate_job_id(job_id))
    return FileResponse(
        manager.audio_path(job.id),
        media_type="audio/mpeg",
        filename=audio_download_name(job.filename, job.language),
    )


def audio_download_name(original_filename: str, language: str) -> str:
    """"agile_project_management.pdf" -> "agile_project_management_audio_en.mp3"."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original_filename).stem).strip("._-")
    return f"{stem or 'document'}_audio_{language}.mp3"


def _validate_job_id(job_id: str) -> str:
    try:
        return str(uuid.UUID(job_id))
    except ValueError as error:
        raise JobNotFoundError("Job not found.") from error


def _validate_language(language: str, settings: Settings) -> None:
    if language not in settings.engines:
        raise UnknownLanguageError(
            f"Unknown language '{language}'. Supported: {', '.join(settings.engines)}."
        )


def _validate_upload_metadata(file: UploadFile) -> None:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise InvalidFileError("Only .pdf files are accepted.")
    if file.content_type not in ACCEPTED_CONTENT_TYPES:
        raise InvalidFileError("The uploaded file is not a PDF.")


def _validate_content_length(request: Request, settings: Settings) -> None:
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > settings.max_pdf_size_bytes + 64 * 1024:
        raise FileTooLargeError(f"The file exceeds the {settings.max_pdf_size_mb} MB limit.")


async def _save_upload(file: UploadFile, destination: Path, max_bytes: int) -> None:
    """Copy the upload to disk without ever using the client filename as a path."""
    written = 0
    with destination.open("wb") as target:
        while chunk := await file.read(COPY_CHUNK_SIZE):
            written += len(chunk)
            if written > max_bytes:
                raise FileTooLargeError(f"The file exceeds the {max_bytes // (1024 * 1024)} MB limit.")
            target.write(chunk)
    if written == 0:
        raise InvalidFileError("The uploaded file is empty.")


def _validate_pdf_signature(path: Path) -> None:
    with path.open("rb") as handle:
        header = handle.read(PDF_SIGNATURE_WINDOW)
    if PDF_SIGNATURE not in header:
        raise InvalidFileError("The uploaded file is not a valid PDF.")

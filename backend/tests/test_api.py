import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.jobs import audio_download_name
from app.config import Settings
from app.main import create_app
from app.services.audio_service import ffmpeg_available
from tests.conftest import PdfFactory
from tests.fakes import FakeTTSEngine


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    models_dir = tmp_path / "models"
    for language, voice in (("fr", "fr_FR-siwis-medium"), ("en", "en_US-lessac-medium")):
        (models_dir / language).mkdir(parents=True)
        (models_dir / language / f"{voice}.onnx").write_bytes(b"fake")
        (models_dir / language / f"{voice}.onnx.json").write_text("{}")
    return Settings(
        temp_dir=tmp_path / "tmp",
        piper_models_dir=models_dir,
        max_pdf_size_mb=1,
        text_chunk_max_chars=80,
    )


@pytest.fixture
def engine() -> FakeTTSEngine:
    return FakeTTSEngine()


@pytest.fixture
def client(settings: Settings, engine: FakeTTSEngine) -> Iterator[TestClient]:
    with TestClient(create_app(settings, engine)) as client:
        yield client


def wait_for_completion(client: TestClient, job_id: str, timeout: float = 10) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = client.get(f"/api/jobs/{job_id}").json()
        if payload["status"] in ("completed", "failed"):
            return payload
        time.sleep(0.05)
    raise AssertionError("job did not finish in time")


def upload(client: TestClient, path: Path, language: str = "en", **overrides):
    files = {"file": (overrides.get("filename", path.name), path.read_bytes(), overrides.get("content_type", "application/pdf"))}
    return client.post("/api/jobs", files=files, data={"language": language})


def test_health(client: TestClient) -> None:
    payload = client.get("/api/health").json()

    assert payload["status"] == "ok"
    assert payload["voices"] == {"fr": True, "en": True}
    assert payload["max_pdf_size_mb"] == 1


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not installed")
def test_full_job_lifecycle(client: TestClient, make_pdf: PdfFactory, engine: FakeTTSEngine, settings: Settings) -> None:
    pdf = make_pdf(["Hello audio world. " * 10, "Second page here. " * 10], name="My Book (v2).pdf")

    response = upload(client, pdf, "fr")

    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    assert response.json()["status"] == "queued"

    job = wait_for_completion(client, job_id)
    assert job["status"] == "completed", job
    assert job["progress"] == 100
    assert job["audio_url"] == f"/api/jobs/{job_id}/audio"
    assert job["filename"] == "My Book (v2).pdf"
    assert job["language"] == "fr"
    assert job["error"] is None
    assert len(engine.texts) > 1

    audio = client.get(job["audio_url"])
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/mpeg"
    assert 'filename="My_Book_v2_audio_fr.mp3"' in audio.headers["content-disposition"]
    assert len(audio.content) > 0

    work_dir = settings.jobs_path / job_id
    assert not (work_dir / "input.pdf").exists()
    assert not (work_dir / "chunks").exists()
    assert (work_dir / "output.mp3").exists()


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not installed")
def test_scanned_pdf_job_fails_with_clear_message(client: TestClient, tmp_path: Path) -> None:
    import pymupdf

    document = pymupdf.open()
    document.new_page()
    pdf = tmp_path / "blank.pdf"
    document.save(pdf)
    document.close()

    job_id = upload(client, pdf).json()["id"]

    job = wait_for_completion(client, job_id)
    assert job["status"] == "failed"
    assert "scanned" in job["error"]
    assert client.get(f"/api/jobs/{job_id}/audio").status_code == 409


def test_rejects_non_pdf_extension(client: TestClient, make_pdf: PdfFactory) -> None:
    response = upload(client, make_pdf(["text"]), filename="notes.txt")

    assert response.status_code == 400
    assert response.json()["detail"] == "Only .pdf files are accepted."


def test_rejects_wrong_content_type(client: TestClient, make_pdf: PdfFactory) -> None:
    response = upload(client, make_pdf(["text"]), content_type="image/png")

    assert response.status_code == 400
    assert "not a PDF" in response.json()["detail"]


def test_rejects_file_without_pdf_signature(client: TestClient, tmp_path: Path, settings: Settings) -> None:
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"hello, I am not a pdf at all")

    response = upload(client, fake)

    assert response.status_code == 400
    assert "not a valid PDF" in response.json()["detail"]
    assert list(settings.jobs_path.iterdir()) == []  # work dir cleaned up


def test_rejects_too_large_file(client: TestClient, tmp_path: Path) -> None:
    big = tmp_path / "big.pdf"
    big.write_bytes(b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 1))

    response = upload(client, big)

    assert response.status_code == 413
    assert "1 MB" in response.json()["detail"]


def test_rejects_unknown_language(client: TestClient, make_pdf: PdfFactory) -> None:
    response = upload(client, make_pdf(["text"]), language="de")

    assert response.status_code == 400
    assert "Unknown language 'de'" in response.json()["detail"]


def test_missing_voice_model_is_reported(client: TestClient, make_pdf: PdfFactory, settings: Settings) -> None:
    (settings.models_path / "en" / "en_US-lessac-medium.onnx").unlink()

    response = upload(client, make_pdf(["text"]), language="en")

    assert response.status_code == 500
    assert "download_voices.py en" in response.json()["detail"]


def test_missing_ffmpeg_is_reported(client: TestClient, make_pdf: PdfFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.audio_service.shutil.which", lambda _: None)

    response = upload(client, make_pdf(["text"]))

    assert response.status_code == 500
    assert "FFmpeg is not installed" in response.json()["detail"]


def test_unknown_job_returns_404(client: TestClient) -> None:
    assert client.get("/api/jobs/not-a-uuid").status_code == 404
    assert client.get("/api/jobs/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/api/jobs/../../etc/passwd/audio").status_code == 404


def test_audio_download_name() -> None:
    assert audio_download_name("agile_project_management.pdf", "en") == "agile_project_management_audio_en.mp3"
    assert audio_download_name("../../étrange nom?.pdf", "fr") == "trange_nom_audio_fr.mp3"
    assert audio_download_name("....pdf", "fr") == "document_audio_fr.mp3"

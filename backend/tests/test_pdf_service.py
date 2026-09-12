from pathlib import Path

import pymupdf
import pytest

from app.errors import EmptyPdfError, ScannedPdfError, UnreadablePdfError
from app.services.pdf_service import extract_pages, extract_text_from_pdf
from tests.conftest import PdfFactory


def test_extract_pages_keeps_page_order(make_pdf: PdfFactory) -> None:
    pdf = make_pdf(["First page content here.", "Second page content here.", "Third page."])

    pages = extract_pages(pdf)

    assert [page.page for page in pages] == [1, 2, 3]
    assert "First page" in pages[0].text
    assert "Second page" in pages[1].text
    assert "Third page" in pages[2].text


def test_extract_text_concatenates_pages(make_pdf: PdfFactory) -> None:
    pdf = make_pdf(["Hello from page one.", "Hello from page two."])

    text = extract_text_from_pdf(pdf)

    assert text.index("page one") < text.index("page two")


def test_extract_pages_separates_blocks_with_blank_line(make_pdf: PdfFactory) -> None:
    pdf = make_pdf(["A paragraph on two\nconsecutive lines."])

    page_text = extract_pages(pdf)[0].text

    # Lines of the same block stay joined by a single newline, no blank line inside.
    assert "two\nconsecutive" in page_text
    assert "\n\n" not in page_text.strip()


def test_pdf_without_text_is_reported_as_scanned(tmp_path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.draw_rect(pymupdf.Rect(10, 10, 100, 100), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / "image_only.pdf"
    document.save(path)
    document.close()

    with pytest.raises(ScannedPdfError, match="scanned"):
        extract_pages(path)


ZERO_PAGE_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
)


def test_pdf_without_pages_is_reported_as_empty(tmp_path: Path) -> None:
    path = tmp_path / "empty.pdf"
    path.write_bytes(ZERO_PAGE_PDF)

    with pytest.raises(EmptyPdfError):
        extract_pages(path)


def test_password_protected_pdf_is_unreadable(make_pdf: PdfFactory, tmp_path: Path) -> None:
    source = pymupdf.open(make_pdf(["Secret content of the document."]))
    protected = tmp_path / "protected.pdf"
    source.save(
        protected,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner",
        user_pw="user",
    )
    source.close()

    with pytest.raises(UnreadablePdfError, match="password"):
        extract_pages(protected)


def test_non_pdf_file_is_unreadable(tmp_path: Path) -> None:
    path = tmp_path / "not_a_pdf.pdf"
    path.write_bytes(b"this is definitely not a pdf")

    with pytest.raises(UnreadablePdfError):
        extract_pages(path)

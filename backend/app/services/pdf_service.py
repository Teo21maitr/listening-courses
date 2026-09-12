"""PDF text extraction with PyMuPDF.

Text-only extraction for now. An OCR fallback (e.g. Tesseract) can later hook
into `extract_pages` when a page yields no text.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from app.errors import EmptyPdfError, ScannedPdfError, UnreadablePdfError

logger = logging.getLogger(__name__)

# Below this many letters/digits in the whole document, we assume the PDF has no
# usable text layer (scanned images, vector drawings...).
MIN_MEANINGFUL_CHARS = 20

PARAGRAPH_SEPARATOR = "\n\n"


@dataclass(frozen=True)
class PageText:
    page: int  # 1-based
    text: str


def extract_pages(file_path: Path) -> list[PageText]:
    """Extract the text of every page, in page order.

    Text blocks of a page are separated by a blank line so that natural
    paragraphs survive until the cleaning step.
    """
    document = _open_document(file_path)
    try:
        if document.page_count == 0:
            raise EmptyPdfError("The PDF has no pages.")
        pages = [
            PageText(page=index + 1, text=_extract_page_text(page))
            for index, page in enumerate(document)
        ]
    finally:
        document.close()

    if not _has_meaningful_text(pages):
        raise ScannedPdfError(
            "No readable text found in this PDF. It is probably a scanned document "
            "(OCR is not supported yet)."
        )
    return pages


def extract_text_from_pdf(file_path: Path) -> str:
    return PARAGRAPH_SEPARATOR.join(page.text for page in extract_pages(file_path) if page.text)


def _open_document(file_path: Path) -> pymupdf.Document:
    try:
        document = pymupdf.open(file_path)
    except (pymupdf.FileDataError, RuntimeError, ValueError) as error:
        logger.warning("Cannot open PDF %s: %s", file_path, error)
        raise UnreadablePdfError("The file could not be read as a PDF.") from error

    if document.needs_pass:
        document.close()
        raise UnreadablePdfError("The PDF is password protected.")
    if not document.is_pdf:
        document.close()
        raise UnreadablePdfError("The file is not a PDF document.")
    return document


def _extract_page_text(page: pymupdf.Page) -> str:
    """Return the page text with blocks separated by blank lines, in reading order."""
    blocks = page.get_text("blocks", sort=True)
    texts = [block[4].strip() for block in blocks if block[6] == 0]  # 0 = text block
    return PARAGRAPH_SEPARATOR.join(text for text in texts if text)


def _has_meaningful_text(pages: list[PageText]) -> bool:
    count = sum(1 for page in pages for char in page.text if char.isalnum())
    return count >= MIN_MEANINGFUL_CHARS

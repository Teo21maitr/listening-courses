from collections.abc import Callable
from pathlib import Path

import pymupdf
import pytest

PdfFactory = Callable[[list[str]], Path]


@pytest.fixture
def make_pdf(tmp_path: Path) -> PdfFactory:
    """Build a PDF with one page per text item (lines separated by "\\n")."""

    def _make(pages: list[str], name: str = "test.pdf") -> Path:
        document = pymupdf.open()
        for content in pages:
            page = document.new_page()
            y = 72
            for line in content.split("\n"):
                page.insert_text((72, y), line, fontsize=11)
                y += 16
        path = tmp_path / name
        document.save(path)
        document.close()
        return path

    return _make

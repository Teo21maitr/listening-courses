"""Make raw PDF text pleasant to listen to.

Every step is a small pure function; `clean_pages` chains them. Page-aware
steps (headers/footers, page numbers) run first, then `clean_text` handles the
text-only steps and can be reused on any text (e.g. after a translation step).
"""

import re
import unicodedata
from collections import Counter

from app.services.pdf_service import PARAGRAPH_SEPARATOR, PageText

# Lines made only of a page number: "12", "- 12 -", "| 2", "Page 3", "3 / 20", "3 of 20"
_PAGE_NUMBER_LINE_RE = re.compile(
    r"^\s*[|\-–—]?\s*(?:page\s*)?\d{1,4}\s*(?:(?:/|of|de|sur)\s*\d{1,4})?\s*[|\-–—]?\s*$",
    re.IGNORECASE,
)
_ROMAN_NUMERAL_LINE_RE = re.compile(
    r"^\s*(?=[ivxlc])m{0,3}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})\s*$",
    re.IGNORECASE,
)
_BULLET_CHARS = "•◦▪▫●○■□➢►▶✓✔–—*·"
_BULLET_ONLY_LINE_RE = re.compile(rf"^\s*[{re.escape(_BULLET_CHARS)}\-]+\s*$")
_LEADING_BULLET_RE = re.compile(rf"^[ \t]*[{re.escape(_BULLET_CHARS)}]+[ \t]*", re.MULTILINE)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200d\ufeff\u00ad]")
_HYPHEN_LOWER_RE = re.compile(r"(\w)-\n([a-zà-öø-ÿ])")
_HYPHEN_OTHER_RE = re.compile(r"(\w)-\n(\w)")
_SOFT_LINE_BREAK_RE = re.compile(r"(?<!\n)\n(?!\n)")
_LONG_URL_RE = re.compile(r"(?:https?://|www\.)\S{20,}", re.IGNORECASE)
_BRACKET_CITATION_RE = re.compile(r"\s?\[\d{1,3}(?:\s*[,–-]\s*\d{1,3})*\]")
_SENTENCE_END_CHARS = '.!?:;…"»)'

# Header/footer detection: a line must appear on at least this share of pages
# (and on at least MIN_REPEATED_PAGES pages) to be considered repeated.
HEADER_FOOTER_MIN_RATIO = 0.5
MIN_REPEATED_PAGES = 3
EDGE_LINES = 2  # lines inspected at the top and bottom of each page


def clean_pages(pages: list[PageText]) -> str:
    texts = [normalize_artifacts(page.text) for page in pages]
    texts = remove_repeated_headers_footers(texts)
    texts = [remove_page_number_lines(text) for text in texts]
    return clean_text(join_pages(texts))


def clean_text(text: str) -> str:
    """Text-only cleaning steps, in order."""
    text = normalize_artifacts(text)
    text = fix_hyphenation(text)
    text = merge_soft_line_breaks(text)
    text = remove_long_urls(text)
    text = remove_bracket_citations(text)
    return collapse_whitespace(text)


def normalize_artifacts(text: str) -> str:
    """Ligatures, non-breaking spaces, control characters, tabs and bullets.

    Bullets are turned into paragraph breaks so each list item gets its own pause.
    """
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL_CHARS_RE.sub("", text)
    text = text.replace("\t", " ")
    lines = ["" if _BULLET_ONLY_LINE_RE.match(line) else line for line in text.split("\n")]
    return _LEADING_BULLET_RE.sub("\n", "\n".join(lines))


def remove_page_number_lines(text: str) -> str:
    lines = text.split("\n")
    kept = [line for line in lines if not _PAGE_NUMBER_LINE_RE.match(line)]
    return "\n".join(_strip_edge_roman_numerals(kept))


def remove_repeated_headers_footers(pages: list[str]) -> list[str]:
    """Drop lines that repeat at the top or bottom of most pages."""
    if len(pages) < MIN_REPEATED_PAGES:
        return pages
    counts = Counter(key for page in pages for key in _edge_line_keys(page))
    threshold = max(MIN_REPEATED_PAGES, int(len(pages) * HEADER_FOOTER_MIN_RATIO))
    repeated = {key for key, count in counts.items() if count >= threshold}
    if not repeated:
        return pages
    return [_strip_repeated_edge_lines(page, repeated) for page in pages]


def join_pages(pages: list[str]) -> str:
    """Join pages, continuing a sentence that was cut by the page break."""
    joined = ""
    for page in pages:
        page = page.strip()
        if not page:
            continue
        if not joined:
            joined = page
        elif _continues_sentence(joined, page):
            joined = f"{joined} {page}"
        else:
            joined = f"{joined}{PARAGRAPH_SEPARATOR}{page}"
    return joined


def fix_hyphenation(text: str) -> str:
    """"impor-\\ntant" -> "important"; "Jean-\\nPierre" keeps its hyphen."""
    text = _HYPHEN_LOWER_RE.sub(r"\1\2", text)
    return _HYPHEN_OTHER_RE.sub(r"\1-\2", text)


def merge_soft_line_breaks(text: str) -> str:
    """Single newlines are visual wraps; blank lines separate paragraphs."""
    return _SOFT_LINE_BREAK_RE.sub(" ", text)


def remove_long_urls(text: str) -> str:
    return _LONG_URL_RE.sub("", text)


def remove_bracket_citations(text: str) -> str:
    """Drop numeric references like [12] or [7, 33-35] that are noise when read aloud."""
    return _BRACKET_CITATION_RE.sub("", text)


def collapse_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", PARAGRAPH_SEPARATOR, text)
    return text.strip()


def _strip_edge_roman_numerals(lines: list[str]) -> list[str]:
    """Roman numerals are only treated as page numbers at the very top/bottom."""
    non_empty = [index for index, line in enumerate(lines) if line.strip()]
    edges = set(non_empty[:1] + non_empty[-1:])
    return [
        line
        for index, line in enumerate(lines)
        if not (index in edges and _ROMAN_NUMERAL_LINE_RE.match(line))
    ]


def _edge_line_keys(page: str) -> set[str]:
    lines = [line for line in page.split("\n") if line.strip()]
    edge_lines = lines[:EDGE_LINES] + lines[-EDGE_LINES:]
    return {key for key in map(_line_key, edge_lines) if key}


def _line_key(line: str) -> str:
    """Normalise a line so "Chapter 1 - page 12" and "Chapter 1 - page 13" match."""
    return re.sub(r"[\d\s]+", " ", line).strip().lower()


def _strip_repeated_edge_lines(page: str, repeated: set[str]) -> str:
    lines = page.split("\n")
    non_empty = [index for index, line in enumerate(lines) if line.strip()]
    edges = set(non_empty[:EDGE_LINES] + non_empty[-EDGE_LINES:])
    kept = [
        line
        for index, line in enumerate(lines)
        if not (index in edges and _line_key(line) in repeated)
    ]
    return "\n".join(kept)


def _continues_sentence(previous: str, following: str) -> bool:
    last, first = previous.rstrip()[-1], following.lstrip()[0]
    return last not in _SENTENCE_END_CHARS and first.islower()

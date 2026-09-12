"""Split cleaned text into chunks small enough for Piper.

Cut priority: paragraphs, then sentence ends, then spaces, then raw slicing.
"""

import re
from collections.abc import Callable

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")

Splitter = Callable[[str, int], list[str]]


def chunk_text(text: str, max_chars: int) -> list[str]:
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    paragraphs = _PARAGRAPH_SPLIT_RE.split(text)
    return _pack(paragraphs, max_chars, "\n\n", _split_paragraph)


def _split_paragraph(paragraph: str, max_chars: int) -> list[str]:
    sentences = _SENTENCE_SPLIT_RE.split(paragraph)
    return _pack(sentences, max_chars, " ", _split_sentence)


def _split_sentence(sentence: str, max_chars: int) -> list[str]:
    return _pack(sentence.split(" "), max_chars, " ", _split_word)


def _split_word(word: str, max_chars: int) -> list[str]:
    return [word[i : i + max_chars] for i in range(0, len(word), max_chars)]


def _pack(pieces: list[str], max_chars: int, separator: str, split_oversized: Splitter) -> list[str]:
    """Greedily join pieces up to max_chars; oversized pieces are split further."""
    chunks: list[str] = []
    current = ""
    for piece in (piece.strip() for piece in pieces):
        if not piece:
            continue
        if len(piece) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(split_oversized(piece, max_chars))
        elif not current:
            current = piece
        elif len(current) + len(separator) + len(piece) <= max_chars:
            current = f"{current}{separator}{piece}"
        else:
            chunks.append(current)
            current = piece
    if current:
        chunks.append(current)
    return chunks

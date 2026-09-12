import pytest

from app.services.text_chunker import chunk_text


def test_short_text_is_a_single_chunk() -> None:
    assert chunk_text("Hello world.", 100) == ["Hello world."]


def test_paragraphs_are_grouped_up_to_max_chars() -> None:
    text = "Para one.\n\nPara two.\n\nPara three."

    assert chunk_text(text, 22) == ["Para one.\n\nPara two.", "Para three."]


def test_long_paragraph_is_split_on_sentences() -> None:
    text = "First sentence here. Second sentence here. Third one!"

    assert chunk_text(text, 45) == ["First sentence here. Second sentence here.", "Third one!"]


def test_long_sentence_is_split_on_spaces() -> None:
    text = "one two three four five six"

    assert chunk_text(text, 13) == ["one two three", "four five six"]


def test_huge_word_is_split_raw() -> None:
    assert chunk_text("a" * 10, 4) == ["aaaa", "aaaa", "aa"]


def test_chunks_never_exceed_max_chars_and_keep_content() -> None:
    sentences = [f"Sentence number {index} is here." for index in range(60)]
    text = "\n\n".join(" ".join(sentences[i : i + 6]) for i in range(0, 60, 6))

    chunks = chunk_text(text, 120)

    assert all(0 < len(chunk) <= 120 for chunk in chunks)
    assert " ".join(chunks).split() == text.split()


def test_empty_text_gives_no_chunks() -> None:
    assert chunk_text("  \n\n  ", 100) == []


def test_invalid_max_chars() -> None:
    with pytest.raises(ValueError):
        chunk_text("text", 0)

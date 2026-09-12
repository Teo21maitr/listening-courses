from app.services.pdf_service import PageText
from app.services.text_cleaner import (
    clean_pages,
    clean_text,
    collapse_whitespace,
    ensure_sentence_endings,
    fix_hyphenation,
    join_pages,
    merge_soft_line_breaks,
    normalize_artifacts,
    remove_bracket_citations,
    remove_long_urls,
    remove_page_number_lines,
    remove_repeated_headers_footers,
)


def test_fix_hyphenation_joins_words_cut_at_line_end() -> None:
    assert fix_hyphenation("This is an impor-\ntant concept.") == "This is an important concept."


def test_fix_hyphenation_keeps_hyphen_before_capital() -> None:
    assert fix_hyphenation("Jean-\nPierre") == "Jean-Pierre"


def test_merge_soft_line_breaks_keeps_paragraphs() -> None:
    text = "First line\nsecond line.\n\nNew paragraph\nstill new."

    assert merge_soft_line_breaks(text) == "First line second line.\n\nNew paragraph still new."


def test_remove_page_number_lines() -> None:
    text = "12\nSome text.\nPage 3\n- 4 -\n| 2\n3 / 20\n3 of 20\nMore text 42 here."

    assert remove_page_number_lines(text) == "Some text.\nMore text 42 here."


def test_roman_numeral_removed_only_at_page_edges() -> None:
    text = "iv\nChapter I\nSome text.\nxii"

    assert remove_page_number_lines(text) == "Chapter I\nSome text."


def test_remove_repeated_headers_footers() -> None:
    words = ["alpha", "bravo", "charlie", "delta", "echo"]
    bodies = [f"Content {word}.\nMore {word} content.\nEnd of {word}." for word in words]
    pages = [
        f"My Great Book\n{body}\nCopyright 2024 - page {index}" for index, body in enumerate(bodies)
    ]

    assert remove_repeated_headers_footers(pages) == bodies


def test_headers_not_removed_on_short_documents() -> None:
    pages = ["Title\nText.", "Title\nOther."]

    assert remove_repeated_headers_footers(pages) == pages


def test_normalize_artifacts_handles_ligatures_bullets_and_control_chars() -> None:
    text = "ﬁnal\x0c\u00a0test\n•\n• item one\n\u200bend"

    assert normalize_artifacts(text) == "final test\n\n\nitem one\nend"


def test_bullets_become_paragraph_breaks_after_cleaning() -> None:
    assert clean_text("Title\n• first item\n• second item") == (
        "Title.\n\nfirst item.\n\nsecond item."
    )


def test_remove_long_urls_keeps_short_ones() -> None:
    text = "See https://example.com/a/very/long/path/that/nobody/wants/to/hear and https://a.io ok"

    assert remove_long_urls(text) == "See  and https://a.io ok"


def test_remove_bracket_citations() -> None:
    assert remove_bracket_citations("Reports [13,14] show [7, 33-35] results [x].") == (
        "Reports show results [x]."
    )


def test_collapse_whitespace() -> None:
    assert collapse_whitespace("  a   b \n\n\n\n c  \n d ") == "a b\n\nc\nd"


def test_join_pages_continues_cut_sentences() -> None:
    pages = ["The sentence continues on the next", "page and ends here.", "New paragraph."]

    assert join_pages(pages) == (
        "The sentence continues on the next page and ends here.\n\nNew paragraph."
    )


def test_clean_text_example_from_spec() -> None:
    assert clean_text("This is an impor-\ntant concept.") == "This is an important concept."


def test_clean_pages_end_to_end() -> None:
    pages = [
        PageText(1, "Header Line\n\nThis is an impor-\ntant concept\nabout audio.\n\n1"),
        PageText(2, "Header Line\n\nSecond page text.\n\n2"),
        PageText(3, "Header Line\n\nThird page text.\n\n3"),
    ]

    assert clean_pages(pages) == (
        "This is an important concept about audio.\n\nSecond page text.\n\nThird page text."
    )


def test_ensure_sentence_endings_adds_periods_to_unpunctuated_paragraphs() -> None:
    text = "Abstract\n\nThe text is fine.\n\nTitle:\n\nA question?\n\nTrailing comma,\n\nQuoted \"end\"\n\nDone (really)."

    assert ensure_sentence_endings(text) == (
        "Abstract.\n\nThe text is fine.\n\nTitle:\n\nA question?\n\nTrailing comma."
        "\n\nQuoted \"end.\"\n\nDone (really)."
    )


def test_clean_text_ends_headings_with_a_period() -> None:
    assert clean_text("1 Introduction\n\nSMS phishing is a problem.") == (
        "1 Introduction.\n\nSMS phishing is a problem."
    )

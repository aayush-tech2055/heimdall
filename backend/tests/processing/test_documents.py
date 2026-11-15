"""Guideline parsing: PDF pages and pasted text (task 4.1)."""

from pathlib import Path

import pymupdf
import pytest

from app.processing.documents import DocumentError, clean_text, parse_pdf, split_text

TEST_DATA = Path(__file__).resolve().parents[3] / "test-data" / "brands"


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 545, 790), text, fontsize=11)
    return doc.tobytes()


def test_pdf_gives_one_page_per_page_with_numbers():
    pages = parse_pdf(make_pdf(["Tone rules here.", "", "Legal rules here."]))
    assert [(p.page, p.text) for p in pages] == [(1, "Tone rules here."), (3, "Legal rules here.")]


def test_test_brand_guides_parse_to_five_pages_with_rules_intact():
    for brand in ("acmelearn", "brewbird"):
        pages = parse_pdf((TEST_DATA / brand / "guidelines.pdf").read_bytes())
        assert [p.page for p in pages] == [1, 2, 3, 4, 5]
        joined = " ".join(p.text for p in pages)
        assert "ﬀ" not in joined
    acme = parse_pdf((TEST_DATA / "acmelearn" / "guidelines.pdf").read_bytes())
    assert 'Never write "Acme Learn" or "Acme-Learn".' in acme[1].text
    assert acme[1].text.startswith("2. Terminology")


def test_clean_text_expands_ligatures_and_joins_hyphenated_lines():
    raw = "Use the coﬀee palette and the Acme-\nLearn name\nacross lines.\n\nNew para."
    assert (
        clean_text(raw)
        == "Use the coffee palette and the Acme-Learn name across lines.\n\nNew para."
    )


def test_clean_text_keeps_bullets_on_their_own_lines():
    raw = "Terminology\n• Never say cheap.\n• Never say hack\nor dummies.\n1. First item"
    assert clean_text(raw) == (
        "Terminology\n• Never say cheap.\n• Never say hack or dummies.\n1. First item"
    )


def test_bad_pdfs_raise_clear_errors():
    with pytest.raises(DocumentError, match="not a readable PDF"):
        parse_pdf(b"not a pdf")
    with pytest.raises(DocumentError, match="no extractable text"):
        parse_pdf(make_pdf(["", ""]))


def test_split_text_on_paragraphs_without_cutting_them():
    paras = [f"Paragraph {i} " + "x" * 90 for i in range(10)]
    parts = split_text("\n\n".join(paras), max_chars=250)
    assert [p.page for p in parts] == list(range(1, len(parts) + 1))
    assert all(len(p.text) <= 250 for p in parts)
    assert "\n\n".join(p.text for p in parts) == "\n\n".join(paras)


def test_split_text_keeps_an_oversized_paragraph_whole_and_rejects_empty():
    parts = split_text("short\n\n" + "y" * 500, max_chars=100)
    assert [p.text for p in parts] == ["short", "y" * 500]
    with pytest.raises(DocumentError):
        split_text(" \n\n ")

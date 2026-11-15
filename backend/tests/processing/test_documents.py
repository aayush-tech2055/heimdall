"""Guideline parsing: PDF pages, other guideline files and pasted text (task 4.1)."""

import io
import zipfile
from pathlib import Path

import pymupdf
import pytest

from app.processing.documents import (
    DocumentError,
    UnsupportedFileError,
    clean_text,
    parse_guideline_file,
    parse_pdf,
    split_text,
)

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


# --- Any guideline file: PDF, Word, PowerPoint, text, Markdown, CSV --------------------------

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'


def make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in files.items():
            z.writestr(name, body)
    return buf.getvalue()


def make_docx() -> bytes:
    body = (
        f"<w:document {W}><w:body>"
        "<w:p><w:r><w:t>Tone of voice</w:t></w:r></w:p>"
        '<w:p><w:pPr><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr>'
        "<w:r><w:t>Use a warm </w:t></w:r><w:r><w:t>tone.</w:t></w:r></w:p>"
        "<w:p></w:p>"
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Never say cheap.</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
        "</w:body></w:document>"
    )
    return make_zip({"word/document.xml": body, "[Content_Types].xml": "<Types/>"})


def make_pptx() -> bytes:
    def slide(*paras: str) -> str:
        ps = "".join(f"<a:p><a:r><a:t>{p}</a:t></a:r></a:p>" for p in paras)
        return f'<p:sld {A} xmlns:p="x"><a:txBody>{ps}</a:txBody></p:sld>'

    return make_zip({
        "ppt/slides/slide1.xml": slide("Tone", "Be warm."),
        "ppt/slides/slide2.xml": slide(),
        "ppt/slides/slide10.xml": slide("Legal", "End with T&amp;Cs apply."),
    })  # fmt: skip


def test_guideline_file_pdf_is_read_by_page():
    pages = parse_guideline_file("brand.pdf", make_pdf(["Tone rules here.", "Legal rules here."]))
    assert [p.page for p in pages] == [1, 2]


def test_guideline_file_docx_keeps_paragraphs_bullets_and_table_cells():
    [page] = parse_guideline_file("brand.docx", make_docx())
    assert page.text == "Tone of voice\n\n- Use a warm tone.\n\nNever say cheap."


def test_guideline_file_pptx_uses_slide_numbers_and_skips_empty_slides():
    pages = parse_guideline_file("deck.pptx", make_pptx())
    assert [(p.page, p.text) for p in pages] == [
        (1, "Tone\n\nBe warm."),
        (3, "Legal\n\nEnd with T&Cs apply."),
    ]


def test_guideline_file_text_and_markdown_in_common_encodings():
    md = "# Tone\n\n- Be warm.\n\n- Never shout."
    assert parse_guideline_file("brand.md", md.encode())[0].text == md
    assert parse_guideline_file("brand.txt", "﻿Café rules".encode())[0].text == "Café rules"
    assert parse_guideline_file("brand.txt", "Café rules".encode("cp1252"))[0].text == "Café rules"
    assert parse_guideline_file("brand.txt", "Be warm.".encode("utf-16"))[0].text == "Be warm."


def test_guideline_file_csv_labels_cells_with_their_header():
    data = b'Category,Rule,Example\ntone,Be warm.,\nterminology,"Never say ""cheap"", ever.",cheap course\n\n'
    [page] = parse_guideline_file("rules.csv", data)
    assert page.text == (
        "Category: tone; Rule: Be warm.\n\n"
        'Category: terminology; Rule: Never say "cheap", ever.; Example: cheap course'
    )


def test_guideline_file_single_column_csv_and_tsv():
    assert (
        parse_guideline_file("r.csv", b"Be warm.\nNo slang.")[0].text == "- Be warm.\n\n- No slang."
    )
    assert (
        parse_guideline_file("r.tsv", b"Category\tRule\ntone\tBe warm.")[0].text
        == "Category: tone; Rule: Be warm."
    )


def test_guideline_file_refuses_binary_and_unknown_office_files():
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 32
    with pytest.raises(UnsupportedFileError, match="Word"):
        parse_guideline_file("logo.png", png)
    with pytest.raises(UnsupportedFileError):
        parse_guideline_file("book.xlsx", make_zip({"xl/workbook.xml": "<x/>"}))
    with pytest.raises(DocumentError):
        parse_guideline_file("broken.docx", b"PK\x03\x04 broken")
    with pytest.raises(DocumentError):
        parse_guideline_file("empty.csv", b"\n , \n")

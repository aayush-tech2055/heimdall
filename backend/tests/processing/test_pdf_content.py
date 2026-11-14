"""PDF content units with page, bbox and evidence boxes; embedded images (task 8.1)."""

import pymupdf
import pytest

from app.processing.documents import DocumentError
from app.processing.pdf_content import parse_pdf_content


def make_pdf(with_image: bool = False) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Our cheap course is great.", fontsize=12)
    page.insert_text((72, 300), "Second block on page one.", fontsize=12, color=(0.8, 0.8, 0.8))
    page2 = doc.new_page()
    page2.insert_text((72, 120), "Page two says T&Cs apply.", fontsize=12)
    if with_image:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 120, 80), False)
        pix.set_rect(pix.irect, (59, 47, 143))
        page2.insert_image(pymupdf.Rect(72, 200, 252, 320), pixmap=pix)
    return doc.tobytes()


def test_units_keep_page_and_bbox_and_evidence_maps_to_word_boxes():
    pdf = parse_pdf_content(make_pdf())
    assert [(u.unit_id, u.location["page"], u.text) for u in pdf.units] == [
        ("u1", 1, "Our cheap course is great."),
        ("u2", 1, "Second block on page one."),
        ("u3", 2, "Page two says T&Cs apply."),
    ]
    x0, y0, x1, y1 = pdf.units[0].location["bbox"]
    assert x0 >= 70 and y1 <= 105 and x1 > x0
    start = pdf.units[0].text.index("cheap")
    ex0, ey0, ex1, ey1 = pdf.evidence_bbox("u1", start, start + 5)
    assert x0 < ex0 < ex1 < x1  # a tight box inside the block
    assert pdf.evidence_bbox("u1", 100, 110) is None
    assert pdf.page_sizes[0] == (595.0, 842.0)


def test_text_colours_are_kept_for_the_contrast_check():
    pdf = parse_pdf_content(make_pdf())
    grey = [s for s in pdf.styles if s.unit_id == "u2"]
    assert grey and grey[0].color == (204, 204, 204)


def test_embedded_images_are_extracted_with_their_page_box():
    pdf = parse_pdf_content(make_pdf(with_image=True))
    (img,) = pdf.images
    assert img.image_id.startswith("p2-") and img.page == 2
    assert img.data.startswith(b"\x89PNG") and (img.width, img.height) == (120, 80)
    assert img.bbox[0] == pytest.approx(72)


def test_scanned_or_broken_pdfs_are_refused():
    with pytest.raises(DocumentError):
        parse_pdf_content(b"nope")
    with pytest.raises(DocumentError, match="no extractable text"):
        parse_pdf_content(pymupdf.open().tobytes() if False else _blank())


def _blank() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    return doc.tobytes()

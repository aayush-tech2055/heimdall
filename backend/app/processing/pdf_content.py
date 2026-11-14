"""PDF content into review units (task 8.1).

One unit per text block. Unit text is built from PyMuPDF's words (ligatures expanded), and
each word keeps its box, so any evidence span inside a unit maps to a tight bounding box on
the page (`evidence_bbox`). Long blocks are split at sentence ends like text content.
Embedded images are extracted for the visual layer.
"""

import unicodedata
from dataclasses import dataclass, field

import pymupdf

from app.processing.documents import DocumentError
from app.review.segment import MAX_UNIT_CHARS, Unit

MIN_IMAGE_SIDE = 64  # px; smaller images are icons or rules, not content
MAX_IMAGES = 12

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class WordBox:
    start: int
    end: int
    bbox: BBox


@dataclass
class PdfImage:
    image_id: str  # "p2-i1"
    page: int
    bbox: BBox
    data: bytes  # PNG
    width: int
    height: int


@dataclass
class TextStyle:
    """A run of text with its colour, for the contrast check (task 8.3)."""

    unit_id: str
    text: str
    color: tuple[int, int, int]
    size: float


@dataclass
class PdfContent:
    units: list[Unit]
    boxes: dict[str, list[WordBox]] = field(default_factory=dict)
    images: list[PdfImage] = field(default_factory=list)
    styles: list[TextStyle] = field(default_factory=list)
    page_sizes: list[tuple[float, float]] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(u.text for u in self.units)

    def evidence_bbox(self, unit_id: str, start: int, end: int) -> BBox | None:
        """Union of the boxes of the words overlapping [start, end) in the unit text."""
        hit = [w.bbox for w in self.boxes.get(unit_id, []) if w.start < end and w.end > start]
        if not hit:
            return None
        return (min(b[0] for b in hit), min(b[1] for b in hit),
                max(b[2] for b in hit), max(b[3] for b in hit))  # fmt: skip


def _rgb(color: int) -> tuple[int, int, int]:
    return (color >> 16) & 255, (color >> 8) & 255, color & 255


def parse_pdf_content(data: bytes, max_chars: int = MAX_UNIT_CHARS) -> PdfContent:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        raise DocumentError("the file is not a readable PDF") from exc
    out = PdfContent(units=[])
    with doc:
        if doc.needs_pass:
            raise DocumentError("the PDF is password-protected")
        for page_index, page in enumerate(doc):
            page_no = page_index + 1
            out.page_sizes.append((page.rect.width, page.rect.height))
            words = page.get_text("words", sort=True)  # x0 y0 x1 y1 word block line wordno
            by_block: dict[int, list[tuple]] = {}
            for w in words:
                by_block.setdefault(w[5], []).append(w)
            for block_no in sorted(by_block, key=lambda b: (by_block[b][0][1], by_block[b][0][0])):
                _add_block(out, page_no, by_block[block_no], max_chars)
            _add_styles(out, page, page_no)
            _add_images(out, doc, page, page_no)
    if not out.units:
        raise DocumentError("the PDF has no extractable text (is it a scan?)")
    return out


def _add_block(out: PdfContent, page_no: int, words: list[tuple], max_chars: int) -> None:
    """One block -> one or more units (split at sentence ends when long)."""
    pieces: list[list[tuple]] = [[]]
    length = 0
    for w in words:
        token = unicodedata.normalize("NFKC", w[4])
        if (
            pieces[-1]
            and length + len(token) > max_chars
            and pieces[-1][-1][4].endswith((".", "!", "?"))
        ):
            pieces.append([])
            length = 0
        pieces[-1].append((*w[:4], token))
        length += len(token) + 1
    for piece in pieces:
        if not piece:
            continue
        text_parts: list[str] = []
        boxes: list[WordBox] = []
        cursor = 0
        for x0, y0, x1, y1, token in piece:
            if text_parts:
                cursor += 1
            boxes.append(WordBox(cursor, cursor + len(token), (x0, y0, x1, y1)))
            text_parts.append(token)
            cursor += len(token)
        n = len(out.units)
        unit_id = f"u{n + 1}"
        bbox = (min(b.bbox[0] for b in boxes), min(b.bbox[1] for b in boxes),
                max(b.bbox[2] for b in boxes), max(b.bbox[3] for b in boxes))  # fmt: skip
        location = {"page": page_no, "bbox": [round(v, 2) for v in bbox]}
        out.units.append(
            Unit(unit_id=unit_id, position=n, text=" ".join(text_parts), location=location)
        )
        out.boxes[unit_id] = boxes


def _inside(x: float, y: float, bbox: list[float], pad: float = 1.0) -> bool:
    return bbox[0] - pad <= x <= bbox[2] + pad and bbox[1] - pad <= y <= bbox[3] + pad


def _add_styles(out: PdfContent, page: pymupdf.Page, page_no: int) -> None:
    units = [u for u in out.units if u.location["page"] == page_no]
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue
                x0, y0, x1, y1 = span["bbox"]
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                unit = next((u for u in units if _inside(cx, cy, u.location["bbox"])), None)
                if unit:
                    out.styles.append(
                        TextStyle(unit.unit_id, text, _rgb(span["color"]), span["size"])
                    )


def _add_images(out: PdfContent, doc: pymupdf.Document, page: pymupdf.Page, page_no: int) -> None:
    for i, info in enumerate(page.get_images(full=True), start=1):
        if len(out.images) >= MAX_IMAGES:
            return
        xref = info[0]
        try:
            pix = pymupdf.Pixmap(doc, xref)
            if pix.n - pix.alpha >= 4:  # CMYK -> RGB
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        except Exception:  # noqa: BLE001 - unusual image encodings are skipped
            continue
        if min(pix.width, pix.height) < MIN_IMAGE_SIDE:
            continue
        rects = page.get_image_rects(xref)
        bbox = tuple(rects[0]) if rects else (0.0, 0.0, page.rect.width, page.rect.height)
        out.images.append(PdfImage(f"p{page_no}-i{i}", page_no, bbox, pix.tobytes("png"),
                                   pix.width, pix.height))  # fmt: skip

"""Turn guideline uploads into pages of clean text (task 4.1).

* PDF: one `PageText` per page, via PyMuPDF. Ligatures are expanded (NFKC: "ﬀ" -> "ff"), a line
  ending in "-" is joined to the next without a space ("Acme-" + "Learn" -> "Acme-Learn"), and
  other line breaks inside a paragraph become spaces.
* Pasted text: split on blank lines into page-sized parts, so each part fits one extraction
  call; paragraphs are never cut, and part numbers stand in for page numbers.
"""

import re
import unicodedata
from dataclasses import dataclass

import pymupdf

PAGE_CHARS = 3500  # about one printed page


class DocumentError(ValueError):
    """The upload could not be read."""


@dataclass(frozen=True)
class PageText:
    page: int  # 1-based
    text: str


def clean_text(raw: str) -> str:
    """Normalise extracted text: NFKC, de-hyphenate line ends, unwrap lines, keep paragraphs."""
    text = unicodedata.normalize("NFKC", raw).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("­", "")  # soft hyphens
    paragraphs = re.split(r"\n\s*\n", text)
    cleaned: list[str] = []
    for para in paragraphs:
        lines = [ln.strip() for ln in para.split("\n") if ln.strip()]
        if not lines:
            continue
        merged = lines[0]
        for line in lines[1:]:
            if merged.endswith("-") and not merged.endswith(" -"):
                merged += line
            elif _starts_new_item(line):
                merged += "\n" + line
            else:
                merged += " " + line
        cleaned.append(re.sub(r"[ \t]+", " ", merged))
    return "\n\n".join(cleaned)


def _starts_new_item(line: str) -> bool:
    """Bullets and numbered items start a new line instead of being unwrapped."""
    return bool(re.match(r"^([•▪◦\-*]|\d+[.)])\s", line))


def parse_pdf(data: bytes) -> list[PageText]:
    """One `PageText` per PDF page; empty pages are skipped."""
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - PyMuPDF raises several types
        raise DocumentError("the file is not a readable PDF") from exc
    with doc:
        if doc.needs_pass:
            raise DocumentError("the PDF is password-protected")
        pages = [
            PageText(i + 1, clean_text(page.get_text("text", sort=True)))
            for i, page in enumerate(doc)
        ]
    pages = [p for p in pages if p.text]
    if not pages:
        raise DocumentError("the PDF has no extractable text (is it a scan?)")
    return pages


def split_text(text: str, max_chars: int = PAGE_CHARS) -> list[PageText]:
    """Split pasted text into parts of at most ~max_chars, on paragraph boundaries."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.replace("\r\n", "\n")) if p.strip()]
    if not paragraphs:
        raise DocumentError("the text is empty")
    parts: list[str] = []
    current: list[str] = []
    size = 0
    for para in paragraphs:
        if current and size + len(para) > max_chars:
            parts.append("\n\n".join(current))
            current, size = [], 0
        current.append(para)
        size += len(para) + 2
    parts.append("\n\n".join(current))
    return [PageText(i + 1, unicodedata.normalize("NFKC", p)) for i, p in enumerate(parts)]

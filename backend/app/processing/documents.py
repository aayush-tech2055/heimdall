"""Turn guideline uploads into pages of clean text (task 4.1).

* PDF: one `PageText` per page, via PyMuPDF. Ligatures are expanded (NFKC: "ﬀ" -> "ff"), a line
  ending in "-" is joined to the next without a space ("Acme-" + "Learn" -> "Acme-Learn"), and
  other line breaks inside a paragraph become spaces.
* PowerPoint (.pptx): one `PageText` per slide, so a rule cites its slide number.
* Word (.docx), plain text and Markdown: paragraphs (Word list items become "- " bullets).
* CSV/TSV: one paragraph per row; with several columns each cell is labelled with its header
  ("Category: tone; Rule: Be warm.").
* Pasted text and everything without real pages: split on blank lines into page-sized parts,
  so each part fits one extraction call; paragraphs are never cut, and part numbers stand in
  for page numbers.

`parse_guideline_file` picks the parser from the file's signature (PDF, Office zip), falling
back to the extension only to tell CSV from plain text.
"""

import csv
import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import PurePath
from xml.etree import ElementTree

import pymupdf

PAGE_CHARS = 3500  # about one printed page


class DocumentError(ValueError):
    """The upload could not be read."""


class UnsupportedFileError(DocumentError):
    """The upload is not a kind of file guidelines can be read from."""


SUPPORTED_GUIDELINE_FILES = "PDF, Word (.docx), PowerPoint (.pptx), text (.txt, .md) or CSV"
TABLE_EXTENSIONS = {".csv": ",", ".tsv": "\t"}


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


def parse_guideline_file(filename: str, data: bytes) -> list[PageText]:
    """Read a guideline upload of any supported kind into pages of text."""
    if data.startswith(b"%PDF"):
        return parse_pdf(data)
    if data.startswith(b"PK\x03\x04"):
        return _parse_office(data)
    text = decode_text(data)
    delimiter = TABLE_EXTENSIONS.get(PurePath(filename or "").suffix.lower())
    if delimiter is not None:
        text = table_to_text(text, delimiter)
    return split_text(text)


def decode_text(data: bytes) -> str:
    """Decode a text file (UTF-8 with or without BOM, UTF-16 with BOM, else Windows-1252).

    Binary files (images, executables, old .doc/.xls) are refused.
    """
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError as exc:
            raise UnsupportedFileError(_unsupported()) from exc
    if b"\x00" in data[:4096]:
        raise UnsupportedFileError(_unsupported())
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    if text.count("\ufffd") > max(5, len(text) // 100):
        raise UnsupportedFileError(_unsupported())
    return text


def table_to_text(text: str, delimiter: str = ",") -> str:
    """One paragraph per CSV row. With 2+ columns the first row is the header and each cell is
    written as "Header: value"; with one column each row is a bullet."""
    rows = [
        [cell.strip() for cell in row]
        for row in csv.reader(io.StringIO(text), delimiter=delimiter)
        if any(cell.strip() for cell in row)
    ]
    if not rows:
        raise DocumentError("the CSV file is empty")
    if max(len(r) for r in rows) == 1:
        return "\n\n".join(f"- {r[0]}" for r in rows)
    if len(rows) == 1:
        return "; ".join(cell for cell in rows[0] if cell)
    header = rows[0]
    paragraphs = []
    for row in rows[1:]:
        cells = [
            f"{header[i]}: {cell}" if i < len(header) and header[i] else cell
            for i, cell in enumerate(row)
            if cell
        ]
        paragraphs.append("; ".join(cells))
    return "\n\n".join(paragraphs)


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _parse_office(data: bytes) -> list[PageText]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise DocumentError("the file is not a readable Word or PowerPoint file") from exc
    with archive:
        names = set(archive.namelist())
        try:
            if "word/document.xml" in names:
                return split_text(_docx_text(archive.read("word/document.xml")))
            slides = sorted(
                (n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                key=lambda n: int(re.findall(r"\d+", n)[-1]),
            )
            if slides:
                return _pptx_pages([archive.read(n) for n in slides])
        except ElementTree.ParseError as exc:
            raise DocumentError("the file is not a readable Word or PowerPoint file") from exc
    raise UnsupportedFileError(_unsupported())


def _docx_text(xml: bytes) -> str:
    """Paragraph text of a Word document, list items as bullets, tables cell by cell."""
    paragraphs = []
    for para in ElementTree.fromstring(xml).iter(f"{_W}p"):
        parts = []
        for node in para.iter():
            if node.tag == f"{_W}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{_W}tab":
                parts.append(" ")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                parts.append("\n")
        text = re.sub(r"[ \t]+", " ", "".join(parts)).strip()
        if not text:
            continue
        if para.find(f"{_W}pPr/{_W}numPr") is not None:
            text = f"- {text}"
        paragraphs.append(text)
    if not paragraphs:
        raise DocumentError("the Word file has no text")
    return "\n\n".join(paragraphs)


def _pptx_pages(slides: list[bytes]) -> list[PageText]:
    """One page per slide (slide numbers are the page numbers); empty slides are skipped."""
    pages = []
    for number, xml in enumerate(slides, start=1):
        paragraphs = []
        for para in ElementTree.fromstring(xml).iter(f"{_A}p"):
            text = "".join(t.text or "" for t in para.iter(f"{_A}t")).strip()
            if text:
                paragraphs.append(text)
        if paragraphs:
            pages.append(PageText(number, unicodedata.normalize("NFKC", "\n\n".join(paragraphs))))
    if not pages:
        raise DocumentError("the PowerPoint file has no text")
    return pages


def _unsupported() -> str:
    return f"Upload a {SUPPORTED_GUIDELINE_FILES} file"

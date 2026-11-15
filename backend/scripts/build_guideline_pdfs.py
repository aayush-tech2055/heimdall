"""Build test-data/brands/<brand>/guidelines.pdf from guidelines.md (task 1.1).

    cd backend && .venv/bin/python -m scripts.build_guideline_pdfs

Each `<!-- page -->` marker in the Markdown starts a new PDF page, so a rule's page in the PDF
is known in advance. Supports the small Markdown subset the guidelines use: `#`/`##`
headings, `- ` bullets, `*italic*` lines and plain paragraphs.
"""

import html
import re
from pathlib import Path

import pymupdf

BRANDS_DIR = Path(__file__).resolve().parents[2] / "test-data" / "brands"
PAGE_MARKER = "<!-- page -->"
CSS = """
* { font-family: sans-serif; }
h1 { font-size: 20px; color: #222; margin-bottom: 4px; }
h2 { font-size: 15px; color: #333; margin-top: 14px; }
p, li { font-size: 11px; line-height: 1.45; color: #111; }
p.meta { font-size: 9px; color: #555; }
"""


def markdown_to_html(md: str) -> str:
    out: list[str] = []
    in_list = False
    for raw in md.strip().splitlines():
        line = raw.strip()
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{html.escape(line[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if not line:
            continue
        if line.startswith("## "):
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif re.fullmatch(r"\*[^*]+\*", line):
            out.append(f'<p class="meta"><i>{html.escape(line[1:-1])}</i></p>')
        else:
            out.append(f"<p>{html.escape(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def build_pdf(md_path: Path, pdf_path: Path) -> int:
    """Render one PDF page per Markdown page; return the page count."""
    pages = md_path.read_text(encoding="utf-8").split(PAGE_MARKER)
    writer = pymupdf.DocumentWriter(str(pdf_path))
    rect = pymupdf.paper_rect("a4")
    where = rect + (54, 54, -54, -54)
    for page_md in pages:
        story = pymupdf.Story(html=markdown_to_html(page_md), user_css=CSS)
        more = True
        while more:  # a long page would overflow onto extra PDF pages; ours fit on one
            device = writer.begin_page(rect)
            more, _ = story.place(where)
            story.draw(device)
            writer.end_page()
    writer.close()
    with pymupdf.open(pdf_path) as doc:
        return doc.page_count


def main() -> None:
    for md_path in sorted(BRANDS_DIR.glob("*/guidelines.md")):
        pdf_path = md_path.with_suffix(".pdf")
        n_pages = build_pdf(md_path, pdf_path)
        expected = md_path.read_text(encoding="utf-8").count(PAGE_MARKER) + 1
        if n_pages != expected:
            raise SystemExit(f"{pdf_path}: {n_pages} pages, expected {expected}")
        print(f"{pdf_path.relative_to(BRANDS_DIR.parent)}: {n_pages} pages")


if __name__ == "__main__":
    main()

"""Website facts (tasks 12.1, 12.2): fetch pages, clean their text, extract facts, and diff
them in code against the approved facts.

* 12.1 Pages are fetched with httpx (or Playwright when installed and asked for, for pages
  that need JavaScript) and cleaned with BeautifulSoup: scripts, styles, navigation, headers
  and footers are dropped and the main text is kept.
* 12.2 Facts are extracted per page by the LLM, then compared with approved facts by
  (entity, attribute) using normalised values: `new`, `changed` (old value -> new value) or
  unchanged. The comparison is plain code.
"""

import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID

import httpx
from bs4 import BeautifulSoup

from app.llm import prompts
from app.llm.client import LLMClient
from app.models.facts import Fact
from app.models.llm import ExtractedFact

MAX_PAGE_CHARS = 12_000
MAX_URLS = 10


class WebsiteError(ValueError):
    pass


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    text: str


@dataclass
class FactChange:
    kind: str  # new | changed
    entity: str
    attribute: str
    new_value: str
    unit: str | None
    statement: str
    source_url: str
    fact_code: str | None = None  # the approved fact that changed
    old_value: str | None = None


def clean_html(html: str) -> tuple[str, str]:
    """(title, main text) of an HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "form", "svg"]):
        tag.decompose()
    root = soup.find("main") or soup.body or soup
    blocks = []
    for el in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th"]):
        text = " ".join(el.get_text(" ", strip=True).split())
        if text and (not blocks or blocks[-1] != text):
            blocks.append(text)
    if not blocks:
        blocks = [" ".join(root.get_text(" ", strip=True).split())]
    return title, unicodedata.normalize("NFKC", "\n".join(blocks))[:MAX_PAGE_CHARS]


def fetch_pages(
    urls: list[str], *, client: httpx.Client | None = None, render_js: bool = False
) -> list[Page]:
    if not urls:
        raise WebsiteError("give at least one URL")
    if len(urls) > MAX_URLS:
        raise WebsiteError(f"at most {MAX_URLS} URLs per check")
    for url in urls:
        if not re.match(r"^https?://", url):
            raise WebsiteError(f"not a web address: {url}")
    if render_js:
        rendered = _playwright(urls)
        if rendered is not None:
            return rendered
    client = client or httpx.Client(timeout=20, follow_redirects=True,
                                    headers={"User-Agent": "Heimdall-fact-check/1.0"})  # fmt: skip
    pages = []
    for url in urls:
        try:
            resp = client.get(url)
        except httpx.HTTPError as exc:
            raise WebsiteError(f"could not fetch {url}: {exc.__class__.__name__}") from exc
        if resp.is_error:
            raise WebsiteError(f"could not fetch {url}: HTTP {resp.status_code}")
        title, text = clean_html(resp.text)
        pages.append(Page(url, title, text))
    return pages


def _playwright(urls: list[str]) -> list[Page] | None:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except ImportError:
        return None
    pages = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for url in urls:
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=30_000)
                title, text = clean_html(page.content())
                pages.append(Page(url, title, text))
        finally:
            browser.close()
    return pages


def extract_page_facts(
    pages: list[Page], client: LLMClient, brand_id: UUID | None = None
) -> list[tuple[Page, ExtractedFact]]:
    found = []
    for page in pages:
        p = prompts.fact_extraction(page.text, url=page.url)
        out = client.json(p.schema, p.system, p.prompt, purpose=p.purpose, brand_id=brand_id)
        found += [(page, f) for f in out.facts]
    return found


def _key(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())


_SYNONYMS = {"fee": "price", "cost": "price", "costs": "price", "pricing": "price",
             "stars": "rating", "star": "rating", "score": "rating", "year": "", "count": "",
             "number": "", "total": "", "monthly": "", "of": "", "the": "",
             "per": "", "a": "", "in": "", "on": ""}  # fmt: skip


def attribute_words(attribute: str) -> set[str]:
    """Significant words of an attribute, with synonyms folded ("one-time fee" -> price)."""
    words = set()
    for w in _key(attribute).split():
        w = _SYNONYMS.get(w, w)
        if w:
            words.add(w[:-1] if w.endswith("s") and len(w) > 3 else w)
    return words


def attribute_key(attribute: str) -> str:
    return " ".join(sorted(attribute_words(attribute)))


def _best_match(entity: str, attribute: str, approved: list[Fact]) -> Fact | None:
    """The approved fact about the same entity whose attribute shares the most words."""
    words = attribute_words(attribute)
    best, best_score = None, 0.0
    for f in approved:
        if _key(f.entity) != _key(entity):
            continue
        other = attribute_words(f.attribute)
        shared = len(words & other)
        if shared == 0:
            continue
        score = shared / len(words | other)
        if score > best_score:
            best, best_score = f, score
    return best


def normalise_value(value: str) -> str:
    """'₹4,999' == '4999' == 'Rs 4999'; '2 million' == '2000000'; case and spaces ignored."""
    v = value.casefold().replace(",", "")
    v = re.sub(r"₹|\brs\.?(?=\s*\d)|\binr\b", " ", v)  # currency
    v = re.sub(r"\b(per month|a month|month|stars?|percent)\b|/month|%", " ", v)  # units
    scale = {"thousand": 1e3, "lakh": 1e5, "million": 1e6, "crore": 1e7}
    m = re.fullmatch(r"\s*([\d.]+)\s*(thousand|lakh|million|crore)?\s*\+?\s*", v)
    if m:
        number = float(m.group(1)) * scale.get(m.group(2) or "", 1)
        return f"{number:g}"
    return " ".join(v.split())


_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*(thousand|lakh|million|crore)?")


def same_value(a: str, b: str) -> bool:
    """Equal after normalisation; if both contain a number, the numbers decide
    ("7 days" == "7", "₹4,999" == "4999", "2 lakh" == "200000")."""
    na, nb = normalise_value(a), normalise_value(b)
    if na == nb:
        return True
    scale = {"thousand": 1e3, "lakh": 1e5, "million": 1e6, "crore": 1e7}
    ma = _NUMBER.search(a.casefold().replace(",", ""))
    mb = _NUMBER.search(b.casefold().replace(",", ""))
    if ma and mb:
        va = float(ma.group(1)) * scale.get(ma.group(2) or "", 1)
        vb = float(mb.group(1)) * scale.get(mb.group(2) or "", 1)
        return va == vb
    return False


def diff_facts(
    extracted: list[tuple[Page, ExtractedFact]], approved: list[Fact]
) -> list[FactChange]:
    """New facts and changed facts versus the approved ones: same entity, and the attribute
    that shares the most significant words; values compared after normalisation."""
    changes: list[FactChange] = []
    seen: set[tuple[str, str]] = set()
    for page, ef in extracted:
        current = _best_match(ef.entity, ef.attribute, approved)
        key = (_key(ef.entity), current.fact_code if current else attribute_key(ef.attribute))
        if key in seen:
            continue
        seen.add(key)
        if current is None:
            changes.append(FactChange("new", ef.entity, ef.attribute, ef.value, ef.unit,
                                      ef.statement, page.url))  # fmt: skip
        elif not same_value(current.value, ef.value):
            changes.append(FactChange(
                "changed", current.entity, current.attribute, ef.value, ef.unit or current.unit,
                ef.statement, page.url, fact_code=current.fact_code, old_value=current.value,
            ))  # fmt: skip
    return changes

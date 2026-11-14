"""Website facts: cleaning, value normalisation and the diff in code (tasks 12.1, 12.2)."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.models.facts import Fact
from app.models.llm import ExtractedFact
from app.rag.website import (
    Page,
    WebsiteError,
    clean_html,
    diff_facts,
    fetch_pages,
    normalise_value,
)

SITE = Path(__file__).resolve().parents[3] / "test-data" / "website" / "acmelearn"


def fact(code, entity, attribute, value):
    return Fact(fact_code=code, entity=entity, attribute=attribute, value=value, unit=None,
                statement="s", source=None, valid_until=None, status="approved", expiry="no_expiry",
                updated_at=datetime.now(UTC))  # fmt: skip


def test_clean_html_keeps_main_text_and_drops_scripts_nav_and_footer():
    title, text = clean_html((SITE / "pricing.html").read_text())
    assert title == "AcmeLearn pricing (fictional)"
    assert "AcmeLearn Pro now costs ₹649 a month" in text
    assert "tracking" not in text and "Home" not in text and "©" not in text


@pytest.mark.parametrize(
    ("a", "b"),
    [("₹4,999", "4999"), ("Rs 599", "599"), ("2 million", "2000000"), ("4.6 stars", "4.6"),
     ("68%", "68"), ("EdTech Startup of the Year 2025", "edtech startup of the year  2025")],
)  # fmt: skip
def test_values_compare_after_normalisation(a, b):
    assert normalise_value(a) == normalise_value(b)


def test_diff_reports_new_and_changed_facts_and_skips_unchanged():
    approved = [fact("F-002", "AcmeLearn Pro", "monthly price", "599"),
                fact("F-003", "AcmeLearn", "registered learners", "2000000")]  # fmt: skip
    page = Page("https://acmelearn.example/pricing", "Pricing", "")
    extracted = [
        (page, ExtractedFact(entity="AcmeLearn Pro", attribute="price", value="₹649", unit="INR",
                             statement="AcmeLearn Pro costs ₹649 a month.")),
        (page, ExtractedFact(entity="AcmeLearn", attribute="Registered learners", value="2 million",
                             statement="More than 2 million learners.")),
        (page, ExtractedFact(entity="AcmeLearn", attribute="mentors", value="1,200",
                             statement="AcmeLearn has 1,200 mentors.")),
        (page, ExtractedFact(entity="acmelearn", attribute="MENTORS", value="1200", statement="dup")),
    ]  # fmt: skip
    changes = diff_facts(extracted, approved)
    assert [(c.kind, c.fact_code, c.old_value, c.new_value) for c in changes] == [
        ("changed", "F-002", "599", "₹649"),
        ("new", None, None, "1,200"),
    ]
    assert changes[0].source_url == "https://acmelearn.example/pricing"


def test_fetch_pages_uses_http_and_rejects_bad_input():
    html = (SITE / "about.html").read_text()
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=html)))
    (page,) = fetch_pages(["https://acmelearn.example/about"], client=client)
    assert "420 courses" in page.text
    with pytest.raises(WebsiteError, match="not a web address"):
        fetch_pages(["file:///etc/passwd"])
    with pytest.raises(WebsiteError):
        fetch_pages([])
    failing = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    with pytest.raises(WebsiteError, match="HTTP 404"):
        fetch_pages(["https://acmelearn.example/x"], client=failing)


def test_attributes_match_on_shared_words_and_synonyms():
    approved = [fact("F-006", "AcmeLearn Pro", "free trial", "7"),
                fact("F-011", "Python Bootcamp", "price", "4999"),
                fact("F-009", "AcmeLearn", "course languages", "6"),
                fact("F-008", "AcmeLearn", "founded", "2019")]  # fmt: skip
    page = Page("https://x", "", "")
    extracted = [(page, ExtractedFact(entity=e, attribute=a, value=v, statement="s")) for e, a, v in [
        ("AcmeLearn Pro", "free trial duration", "7 days"),
        ("Python Bootcamp", "one-time fee", "₹4,999"),
        ("AcmeLearn", "Indian languages", "8"),
        ("AcmeLearn", "founded year", "2019"),
        ("AcmeLearn", "mentors", "1,200"),
    ]]  # fmt: skip
    changes = diff_facts(extracted, approved)
    assert [(c.kind, c.fact_code, c.new_value) for c in changes] == [
        ("changed", "F-009", "8"),  # 6 -> 8 languages; "7 days" and "₹4,999" are unchanged
        ("new", None, "1,200"),
    ]

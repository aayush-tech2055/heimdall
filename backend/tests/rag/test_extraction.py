"""Rule extraction: codes, pages and status set in code; decision 7 downgrade (task 4.2)."""

import json

from app.llm.cache import SQLiteCache
from app.llm.call_log import MemoryCallLogger
from app.llm.client import LLMClient
from app.models.llm import ExtractedRule
from app.processing.documents import PageText
from app.rag.extraction import extract_rules, normalise_rule


class PageAwareProvider:
    """Answers each extraction call with the rules scripted for the page in the prompt."""

    name, model = "fake", "fake-1"

    def __init__(self, by_page: dict[int, list[dict]]) -> None:
        self.by_page = by_page

    def complete(self, system: str, prompt: str) -> str:
        page = int(prompt.split("page ")[1].split(".")[0])
        return json.dumps({"rules": self.by_page[page]})


def run(by_page, pages, **kw):
    client = LLMClient([PageAwareProvider(by_page)], SQLiteCache(":memory:"), MemoryCallLogger())
    return extract_rules(pages, source_doc="guide.pdf", client=client, **kw)


def rule(text, category="tone", **kw):
    return {"category": category, "text": text, **kw}


def test_codes_pages_and_status_are_set_in_code():
    by_page = {
        1: [rule("Be warm.", rule_code="X-9", source_page=99, status="approved"), rule("Use you.")],
        2: [],
        3: [rule("Never say cheap.", "terminology", check_type="deterministic",
                 det_kind="banned_terms", terms=["cheap", " Cheap ", ""])],
    }  # fmt: skip
    pages = [PageText(1, "p1"), PageText(2, "p2"), PageText(3, "p3")]
    drafts = run(by_page, pages, first_number=12)
    assert [(d.rule_code, d.source_page, d.status) for d in drafts] == [
        ("R-012", 1, "pending"),
        ("R-013", 1, "pending"),
        ("R-014", 3, "pending"),
    ]
    assert all(d.source_doc == "guide.pdf" for d in drafts)
    assert drafts[2].terms == ["cheap"]
    assert drafts[2].check_type == "deterministic" and drafts[2].det_kind == "banned_terms"


def test_repeated_rule_is_stored_once():
    by_page = {1: [rule("Be warm.")], 2: [rule("Be  warm.")]}
    drafts = run(by_page, [PageText(1, "a"), PageText(2, "b")])
    assert [(d.text, d.source_page) for d in drafts] == [("Be warm.", 1)]


def test_deterministic_rule_without_terms_is_downgraded():
    for kw in ({"det_kind": "banned_terms", "terms": []}, {"det_kind": None, "terms": ["x"]}):
        out = normalise_rule(
            ExtractedRule(category="legal", text="t", check_type="deterministic", **kw)
        )
        assert (out["check_type"], out["det_kind"], out["terms"]) == ("semantic", None, [])


def test_semantic_rule_drops_stray_kind_and_terms():
    out = normalise_rule(
        ExtractedRule(category="tone", text=" Be   warm. ", det_kind="banned_terms", terms=["a"])
    )
    assert out == {
        "category": "tone", "text": "Be warm.", "check_type": "semantic", "det_kind": None,
        "terms": [], "examples_bad": [], "examples_good": [], "always_on": False,
    }  # fmt: skip


def test_quotes_are_stripped_from_terms():
    out = normalise_rule(
        ExtractedRule(category="legal", text="t", check_type="deterministic",
                      det_kind="required_phrase", terms=['"T&Cs apply."', "“T&Cs apply.”"])
    )  # fmt: skip
    assert out["terms"] == ["T&Cs apply."]

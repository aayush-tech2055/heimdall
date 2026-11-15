"""Rule extraction from guideline pages (task 4.2, decisions 5–8).

One LLM call per page (pages run in parallel). The model only proposes rule content; codes,
source document, page and `pending` status are set here, in code.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from uuid import UUID

from app.llm import prompts
from app.llm.client import LLMClient
from app.models.llm import ExtractedRule, RuleExtraction
from app.processing.documents import PageText


@dataclass
class RuleDraft:
    """A rule ready to store: everything the `rules` table needs except the embedding."""

    rule_code: str
    category: str
    text: str
    source_doc: str
    source_page: int
    check_type: str = "semantic"
    det_kind: str | None = None
    terms: list[str] = field(default_factory=list)
    examples_bad: list[str] = field(default_factory=list)
    examples_good: list[str] = field(default_factory=list)
    always_on: bool = False
    status: str = "pending"


def _clean_list(items: list[str]) -> list[str]:
    """Strip, drop empties and case-insensitive duplicates, keep order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        value = " ".join(item.split()).strip("\"'“”‘’ ")
        if value and value.lower() not in seen:
            seen.add(value.lower())
            out.append(value)
    return out


def normalise_rule(rule: ExtractedRule) -> dict:
    """Apply decision 7 and tidy the model's fields."""
    terms = _clean_list(rule.terms)
    check_type, det_kind = rule.check_type, rule.det_kind
    if check_type == "deterministic" and (det_kind is None or not terms):
        check_type, det_kind = "semantic", None  # no exact terms: cannot run in code
    if check_type == "semantic":
        det_kind, terms = None, []
    return {
        "category": rule.category,
        "text": " ".join(rule.text.split()),
        "check_type": check_type,
        "det_kind": det_kind,
        "terms": terms,
        "examples_bad": _clean_list(rule.examples_bad),
        "examples_good": _clean_list(rule.examples_good),
        "always_on": rule.always_on,
    }


def extract_rules(
    pages: list[PageText],
    *,
    source_doc: str,
    client: LLMClient,
    first_number: int = 1,
    brand_id: UUID | None = None,
    max_workers: int = 4,
) -> list[RuleDraft]:
    """Extract rules from every page, then number them R-NNN in page order."""

    def ask(page: PageText) -> RuleExtraction:
        p = prompts.rule_extraction(page.text, page=page.page, source_doc=source_doc)
        return client.json(p.schema, p.system, p.prompt, purpose=p.purpose, brand_id=brand_id)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(ask, pages))

    drafts: list[RuleDraft] = []
    seen_texts: set[str] = set()
    number = first_number
    for page, result in zip(pages, results, strict=True):
        for extracted in result.rules:
            fields = normalise_rule(extracted)
            key = fields["text"].lower()
            if not fields["text"] or key in seen_texts:
                continue  # the same rule repeated (e.g. across a page break) is stored once
            seen_texts.add(key)
            drafts.append(
                RuleDraft(
                    rule_code=f"R-{number:03d}",
                    source_doc=source_doc,
                    source_page=page.page,
                    **fields,
                )
            )
            number += 1
    return drafts

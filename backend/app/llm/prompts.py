"""Every prompt Heimdall sends to a model, in one place (task 3.3).

Each builder returns a `Prompt`: the purpose (logged to `ai_calls`), the output schema, the
system prompt and the user prompt. Call it with:

    p = prompts.judge(units, rules)
    result = client.json(p.schema, p.system, p.prompt, purpose=p.purpose, ...)

Rules:
* Untrusted text (content, guideline pages, web pages, quoted claims) is wrapped in <content>
  tags with `wrap_content`; `LLMClient` adds the guard saying it is data (decision 26).
* Prompts are deterministic for the same inputs, so the cache works (decision 24).
* The model never sets rule codes, pages, statuses or expiry (decisions 8 and 10).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import NamedTuple

from pydantic import BaseModel

from app.llm.safety import wrap_content
from app.models.llm import (
    ClaimExtraction,
    ClaimVerification,
    FactExtraction,
    JudgeOutput,
    PairVerdict,
    RuleExtraction,
    VaguenessCheck,
)

CATEGORY_GUIDE = """Categories:
- tone: voice, formality, emotion, attitude
- terminology: words and names to use or avoid, spelling, capitalisation
- messaging: what to say or emphasise about the brand and its products
- claims: factual, numeric, comparative or promotional statements and how to support them
- visuals: logos, colours, imagery, layout, typography
- accessibility: alt text, contrast, readability, inclusive language
- legal: disclaimers, regulated statements, trademarks, privacy
- other: anything that fits none of the above"""


class Prompt(NamedTuple):
    purpose: str
    schema: type[BaseModel]
    system: str
    prompt: str


@dataclass(frozen=True)
class RuleRef:
    code: str
    category: str
    text: str
    examples_bad: Sequence[str] = field(default_factory=tuple)
    examples_good: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class UnitRef:
    unit_id: str
    text: str


@dataclass(frozen=True)
class ClaimRef:
    claim_id: str
    unit_id: str
    claim: str
    entity: str
    attribute: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class FactRef:
    fact_code: str
    entity: str
    attribute: str
    value: str
    unit: str | None
    statement: str


def _rule_block(rule: RuleRef) -> str:
    lines = [f"[{rule.code}] ({rule.category}) {rule.text}"]
    lines += [f"  Bad example: {e}" for e in rule.examples_bad]
    lines += [f"  Good example: {e}" for e in rule.examples_good]
    return "\n".join(lines)


def _rules_section(rules: Sequence[RuleRef]) -> str:
    return "<rules>\n" + "\n".join(_rule_block(r) for r in rules) + "\n</rules>"


def _units_section(units: Sequence[UnitRef]) -> str:
    return "\n\n".join(wrap_content(u.text, unit_id=u.unit_id) for u in units)


# --- Guideline ingestion and verification (tasks 4.2, 4.4) ---------------------------------

RULE_EXTRACTION_SYSTEM = f"""You turn one page of a brand guideline into a list of rules.

A rule is one instruction that a reviewer could check a piece of marketing content against.
- Usually one bullet point or sentence of the guideline is one rule. Split it only when it
  mixes an exact word list with other instructions (the word list becomes its own rule) or
  covers two different categories.
- Keep each rule close to the guideline's own wording; do not add requirements.
- Skip text that is not an instruction: titles, introductions, tables of contents, history.
- Do not number the rules or invent rule codes; the system assigns codes and pages.

{CATEGORY_GUIDE}

check_type:
- "deterministic" with det_kind "banned_terms" only when the guideline lists exact words,
  phrases or spellings that must never appear (for example "Never use these words: ..." or
  "Never write X or Y"). Put each banned word or spelling in "terms", exactly as written.
- "deterministic" with det_kind "required_phrase" only when the guideline gives exact text
  that every piece of content must contain (for example "must end with the line ...").
  Put that exact text in "terms".
- Never put the brand's own correct name or product names in "terms".
- "semantic" for everything else, including rules whose quoted words are only examples of a
  broader idea (for example "never make health claims such as 'cures headaches'"): det_kind
  null, terms empty.

examples_bad / examples_good: copy examples only if the guideline gives them; never invent.
always_on: true only for rules that apply to every piece of content whatever its topic
(for example the overall tone of voice, or a disclaimer every post must carry).
If the page has no rules, return an empty list."""


def rule_extraction(page_text: str, *, page: int, source_doc: str) -> Prompt:
    prompt = (
        f"Guideline document: {source_doc}, page {page}.\n"
        "Extract every rule on this page.\n\n" + wrap_content(page_text, page=str(page))
    )
    return Prompt("rule_extraction", RuleExtraction, RULE_EXTRACTION_SYSTEM, prompt)


PAIR_CHECK_SYSTEM = """You compare two rules from the same brand guideline.

Label the pair:
- "duplicate": both rules require the same thing (one may be worded differently or be a
  subset that adds nothing).
- "contradiction": content cannot satisfy both rules at the same time.
- "compatible": anything else, including rules that are related but can both be followed.

Explain your label in one or two plain sentences that name both rule codes."""


def pair_check(rule_a: RuleRef, rule_b: RuleRef) -> Prompt:
    prompt = "Compare these two rules.\n\n" + _rules_section([rule_a, rule_b])
    return Prompt("pair_check", PairVerdict, PAIR_CHECK_SYSTEM, prompt)


VAGUENESS_SYSTEM = """You review brand guideline rules for testability.

A rule is vague when two careful reviewers could disagree about whether the same piece of
content breaks it, because it names no observable property (for example "be engaging" or
"keep it on-brand"). A rule is clear when a reviewer can point to the words or visual
elements that break it.

Return one result per rule, using the rule's code. For a vague rule, give the reason and a
testable rewrite that keeps the guideline's intent. For a clear rule, set vague to false,
give a short reason and set suggested_rewrite to null."""


def vagueness_check(rules: Sequence[RuleRef]) -> Prompt:
    prompt = "Check each rule for vagueness.\n\n" + _rules_section(rules)
    return Prompt("vagueness_check", VaguenessCheck, VAGUENESS_SYSTEM, prompt)


# --- Review: judge (task 6.4) --------------------------------------------------------------

JUDGE_SYSTEM = """You are a brand-compliance reviewer. You check marketing content against
the brand rules you are given, and nothing else.

- Flag a unit only when it clearly breaks one of the supplied rules, and cite that rule's
  code exactly as written. Never cite a rule that is not in the list, and never flag
  general writing quality, facts or opinions that no supplied rule covers.
- evidence: the shortest span of the unit that breaks the rule, copied
  character for character (same spelling, punctuation and capitalisation) from that unit.
- suggested_fix: replacement text for the evidence that keeps the creator's meaning and
  intent while following the rule; null if no rewrite can fix it.
- severity: "high" for legal, factual or reputational risk; "medium" for a clear breach;
  "low" for minor wording.
- confidence: how sure you are that this is a real breach, from 0 to 1.
- One flag per breach. If the same rule is broken twice, flag each span separately.
- If nothing breaks a rule, return an empty list."""


def judge(units: Sequence[UnitRef], rules: Sequence[RuleRef]) -> Prompt:
    prompt = (
        "Brand rules (the only rules you may cite):\n"
        + _rules_section(rules)
        + "\n\nContent units to review:\n\n"
        + _units_section(units)
    )
    return Prompt("judge", JudgeOutput, JUDGE_SYSTEM, prompt)


# --- Review: claims (task 6.5) -------------------------------------------------------------

CLAIM_EXTRACTION_SYSTEM = """You find the checkable claims in marketing content.

A claim is a statement that could be true or false about the brand, its products or the
world: prices, numbers and statistics, dates, rankings and superlatives ("No. 1", "best",
"fastest"), awards, guarantees, comparisons with competitors, and features or results.
Opinions and calls to action with nothing checkable ("Join us today!") are not claims.

For each claim:
- unit_id: the unit it is in.
- claim: the shortest exact quote from that unit that contains the whole claim, copied
  character for character.
- entity: what the claim is about (a product, plan, company or person name).
- attribute and value: the property and value claimed (for example "price" and "Rs 499
  a month"), or null when the claim has none (for example a superlative).
If there are no claims, return an empty list."""


def claim_extraction(units: Sequence[UnitRef]) -> Prompt:
    prompt = "Find every claim in these units.\n\n" + _units_section(units)
    return Prompt("claim_extraction", ClaimExtraction, CLAIM_EXTRACTION_SYSTEM, prompt)


CLAIM_VERIFICATION_SYSTEM = """You check claims from marketing content against the brand's
approved facts. The facts you are given are the only source of truth.

For each claim, return one verdict with its claim_id:
- "supported": a supplied fact states the same thing. Cite its fact_code.
- "contradicted": a supplied fact about the same entity and attribute states something
  different. Cite its fact_code and say what the fact says.
- "unsupported": no supplied fact covers the claim. fact_code must be null.
fact_code must be one of the supplied codes, copied exactly, or null.
suggested_fix: for a contradicted claim, the claim rewritten to match the fact; for an
unsupported claim, a softer version that makes no unverifiable promise; null otherwise.
Do not judge whether facts are current; that is checked separately."""


def claim_verification(claims: Sequence[ClaimRef], facts: Sequence[FactRef]) -> Prompt:
    fact_lines = [
        f"[{f.fact_code}] {f.entity} | {f.attribute} = {f.value}"
        + (f" {f.unit}" if f.unit else "")
        + f" | {f.statement}"
        for f in facts
    ]
    claim_lines = [
        f"claim_id={c.claim_id} unit_id={c.unit_id} entity={c.entity}"
        + (f" attribute={c.attribute}" if c.attribute else "")
        + (f" value={c.value}" if c.value else "")
        + f"\nquote: {c.claim}"
        for c in claims
    ]
    prompt = (
        "Approved facts:\n<facts>\n"
        + ("\n".join(fact_lines) if fact_lines else "(none)")
        + "\n</facts>\n\nClaims to check:\n"
        + wrap_content("\n\n".join(claim_lines))
    )
    return Prompt("claim_verification", ClaimVerification, CLAIM_VERIFICATION_SYSTEM, prompt)


# --- Website facts (task 12.2) -------------------------------------------------------------

FACT_EXTRACTION_SYSTEM = """You extract facts about a company and its products from one of
its web pages, for a fact sheet that marketing claims are checked against.

- Extract only facts the page states explicitly: prices, plans, numbers, dates, features,
  awards, locations. Never infer or calculate.
- entity: the product, plan or company the fact is about, named as on the page.
- attribute: the property (for example "monthly price", "learners", "founded").
- value: the value as stated, without the unit; unit: the unit or currency, or null.
- statement: one plain sentence stating the fact.
If the page states no facts, return an empty list."""


def fact_extraction(page_text: str, *, url: str) -> Prompt:
    prompt = f"Page URL: {url}\nExtract the facts on this page.\n\n" + wrap_content(page_text)
    return Prompt("fact_extraction", FactExtraction, FACT_EXTRACTION_SYSTEM, prompt)

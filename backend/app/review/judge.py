"""Layer (b): hybrid retrieval + the batched LLM judge (task 6.4, decisions 13, 18, 19).

Each unit's redacted text is embedded (RETRIEVAL_QUERY) and gets its top 6 approved semantic
rules from hybrid search, plus every always-on rule. Units go to the judge ~4 per call with
the union of their rules. The judge may only cite the rules it was given; that is enforced
later by citation validation, using the `supplied` set recorded on each candidate.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from uuid import UUID

from app.llm import prompts
from app.llm.client import LLMClient
from app.llm.prompts import RuleRef, UnitRef
from app.models.llm import JudgeOutput
from app.models.rules import Rule
from app.processing.redaction import Redacted
from app.rag.embeddings import Embedder
from app.review.candidates import Candidate
from app.review.segment import Unit

UNITS_PER_CALL = 4
RULES_PER_UNIT = 6

RuleSearch = Callable[[str, list[float], int], list[str]]


@dataclass
class JudgeResult:
    candidates: list[Candidate] = field(default_factory=list)
    retrieved: dict[str, list[str]] = field(default_factory=dict)  # unit_id -> rule codes


def _ref(rule: Rule) -> RuleRef:
    return RuleRef(rule.rule_code, rule.category, rule.text, rule.examples_bad, rule.examples_good)


def run_judge(
    units: list[Unit],
    redacted: dict[str, Redacted],
    rules: list[Rule],
    *,
    search: RuleSearch,
    embedder: Embedder,
    client: LLMClient,
    brand_id: UUID | None = None,
    content_version_id: UUID | None = None,
    max_workers: int = 2,
) -> JudgeResult:
    semantic = {
        r.rule_code: r for r in rules if r.status == "approved" and r.check_type == "semantic"
    }
    result = JudgeResult()
    if not semantic or not units:
        return result
    always_on = [code for code, r in semantic.items() if r.always_on]

    texts = [redacted[u.unit_id].text for u in units]
    vectors = embedder.embed_queries(
        texts, purpose="unit_embedding", brand_id=brand_id, content_version_id=content_version_id
    )
    for unit, text, vector in zip(units, texts, vectors, strict=True):
        found = [c for c in search(text, vector, RULES_PER_UNIT) if c in semantic]
        result.retrieved[unit.unit_id] = list(dict.fromkeys([*found, *always_on]))

    batches = [units[i : i + UNITS_PER_CALL] for i in range(0, len(units), UNITS_PER_CALL)]

    def judge_batch(batch: list[Unit]) -> tuple[frozenset[str], JudgeOutput]:
        codes = list(dict.fromkeys(c for u in batch for c in result.retrieved[u.unit_id]))
        p = prompts.judge(
            [UnitRef(u.unit_id, redacted[u.unit_id].text) for u in batch],
            [_ref(semantic[c]) for c in sorted(codes)],
        )
        out = client.json(
            p.schema, p.system, p.prompt, purpose=p.purpose, brand_id=brand_id,
            content_version_id=content_version_id,
        )  # fmt: skip
        return frozenset(codes), out

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        outputs = list(pool.map(judge_batch, batches))

    for supplied, out in outputs:
        for f in out.flags:
            rule = semantic.get(f.rule_code)
            result.candidates.append(
                Candidate(
                    unit_id=f.unit_id, source_type="rule", source_id=f.rule_code,
                    category=rule.category if rule else "other", severity=f.severity,
                    evidence=f.evidence, explanation=f.explanation,
                    suggested_fix=f.suggested_fix, confidence=f.confidence,
                    layer="guidelines", supplied=supplied,
                )
            )  # fmt: skip
    return result

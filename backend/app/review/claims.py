"""Layer (c): claims against approved facts (task 6.5, decisions 10, 11, 14).

1. Claim extraction on redacted units; only claims that are real quotes from their unit are kept.
2. Fact lookup per claim: exact entity match first, then hybrid search, top 3.
3. Claim verification, a batch of claims per call with the union of their facts.
4. Verdicts become candidates:
   * supported by an expired fact -> flagged as outdated, citing the fact (expiry is code);
   * contradicted, citing a supplied fact -> flagged, citing the fact;
   * contradicted without a real supplied fact -> dropped ("no_fact_cited");
   * unsupported -> flagged citing SYS-CLAIM-001, if the brand has the claim policy on.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from uuid import UUID

from app.llm import prompts
from app.llm.client import LLMClient
from app.llm.prompts import ClaimRef, FactRef, UnitRef
from app.models.facts import Fact
from app.models.llm import ClaimExtraction, ClaimVerification, ExtractedClaim
from app.processing.redaction import Redacted
from app.rag.embeddings import Embedder
from app.review.candidates import Candidate
from app.review.segment import Unit
from app.review.text import find_normalised

CLAIM_POLICY_ID = "SYS-CLAIM-001"
CLAIM_POLICY_TEXT = "Every factual or promotional claim must match an approved fact."
UNITS_PER_EXTRACTION = 6
CLAIMS_PER_VERIFICATION = 8

FactLookup = Callable[[ExtractedClaim, list[float]], list[Fact]]


@dataclass
class ClaimsResult:
    candidates: list[Candidate] = field(default_factory=list)
    dropped: list[tuple[dict, str]] = field(default_factory=list)
    claims: list[ExtractedClaim] = field(default_factory=list)
    facts_by_claim: dict[str, list[str]] = field(default_factory=dict)


def _fact_ref(f: Fact) -> FactRef:
    return FactRef(f.fact_code, f.entity, f.attribute, f.value, f.unit, f.statement)


def run_claims(
    units: list[Unit],
    redacted: dict[str, Redacted],
    *,
    lookup: FactLookup,
    embedder: Embedder,
    client: LLMClient,
    claim_policy_enabled: bool = True,
    brand_id: UUID | None = None,
    content_version_id: UUID | None = None,
    max_workers: int = 2,
) -> ClaimsResult:
    result = ClaimsResult()
    if not units:
        return result
    ctx = {"brand_id": brand_id, "content_version_id": content_version_id}
    unit_text = {u.unit_id: redacted[u.unit_id].text for u in units}

    def extract(batch: list[Unit]) -> ClaimExtraction:
        p = prompts.claim_extraction([UnitRef(u.unit_id, unit_text[u.unit_id]) for u in batch])
        return client.json(p.schema, p.system, p.prompt, purpose=p.purpose, **ctx)

    batches = [
        units[i : i + UNITS_PER_EXTRACTION] for i in range(0, len(units), UNITS_PER_EXTRACTION)
    ]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        extracted = [c for out in pool.map(extract, batches) for c in out.claims]

    seen: set[tuple[str, str]] = set()
    for claim in extracted:
        text = unit_text.get(claim.unit_id)
        if text is None or find_normalised(text, claim.claim) is None:
            result.dropped.append((claim.model_dump() | {"layer": "claims"}, "claim_not_quoted"))
            continue
        key = (claim.unit_id, claim.claim.strip().lower())
        if key not in seen:
            seen.add(key)
            result.claims.append(claim)
    if not result.claims:
        return result

    vectors = embedder.embed_queries(
        [c.claim for c in result.claims], purpose="claim_embedding", **ctx
    )
    facts: dict[str, Fact] = {}
    claim_ids = [f"c{i + 1}" for i in range(len(result.claims))]
    for cid, claim, vector in zip(claim_ids, result.claims, vectors, strict=True):
        found = lookup(claim, vector)
        facts.update({f.fact_code: f for f in found})
        result.facts_by_claim[cid] = [f.fact_code for f in found]

    by_id = dict(zip(claim_ids, result.claims, strict=True))
    groups = [claim_ids[i : i + CLAIMS_PER_VERIFICATION]
              for i in range(0, len(claim_ids), CLAIMS_PER_VERIFICATION)]  # fmt: skip

    def verify(group: list[str]) -> tuple[list[str], frozenset[str], ClaimVerification]:
        codes = list(dict.fromkeys(c for cid in group for c in result.facts_by_claim[cid]))
        p = prompts.claim_verification(
            [ClaimRef(cid, by_id[cid].unit_id, by_id[cid].claim, by_id[cid].entity,
                      by_id[cid].attribute, by_id[cid].value) for cid in group],
            [_fact_ref(facts[c]) for c in codes],
        )  # fmt: skip
        out = client.json(p.schema, p.system, p.prompt, purpose=p.purpose, **ctx)
        return group, frozenset(codes), out

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        verified = list(pool.map(verify, groups))

    for group, supplied, out in verified:
        for v in out.verdicts:
            if v.claim_id not in group:
                continue  # the model invented a claim id
            claim = by_id[v.claim_id]
            fact = facts.get(v.fact_code) if v.fact_code in supplied else None
            base = {
                "unit_id": claim.unit_id, "category": "claims", "evidence": claim.claim,
                "confidence": v.confidence, "layer": "claims",
                "supplied": supplied | {CLAIM_POLICY_ID},
            }  # fmt: skip
            if v.verdict == "supported":
                if fact is not None and fact.expiry == "expired":
                    result.candidates.append(Candidate(
                        source_type="fact", source_id=fact.fact_code, severity="high",
                        explanation=(f"This relies on {fact.fact_code} ({fact.statement}), which "
                                     f"expired on {fact.valid_until}. Check the current value."),
                        suggested_fix=v.suggested_fix, **base,
                    ))  # fmt: skip
            elif v.verdict == "contradicted":
                if fact is None:
                    result.dropped.append((
                        {**{k: base[k] for k in ("unit_id", "evidence")},
                         "source_id": v.fact_code, "explanation": v.explanation,
                         "layer": "claims"}, "no_fact_cited",
                    ))  # fmt: skip
                    continue
                result.candidates.append(Candidate(
                    source_type="fact", source_id=fact.fact_code, severity="high",
                    explanation=v.explanation, suggested_fix=v.suggested_fix, **base,
                ))  # fmt: skip
            elif claim_policy_enabled:
                result.candidates.append(Candidate(
                    source_type="policy", source_id=CLAIM_POLICY_ID, severity="medium",
                    explanation=v.explanation or "No approved fact supports this claim.",
                    suggested_fix=v.suggested_fix, **base,
                ))  # fmt: skip
    return result

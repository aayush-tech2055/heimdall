"""Layer (d): visual checks with a vision model (task 8.2).

Each image (from a PDF, or an uploaded image) goes to a vision-capable model with the brand's
approved visual rules and the asset library's descriptions (logo versions, palette). The model
returns flags whose evidence is a description of the image region; the source must be one of
the visual rules it was given (checked by citation validation).
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from uuid import UUID

from app.llm import prompts
from app.llm.client import LLMClient
from app.llm.prompts import RuleRef
from app.models.rules import Rule
from app.review.candidates import Candidate

IMAGE_WORDS = ("image", "photo", "picture", "logo", "colour", "color", "alt text", "visual",
               "contrast", "graphic", "palette")  # fmt: skip


@dataclass
class ImageInput:
    image_id: str
    data: bytes
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    alt_text: str | None = None
    start: float | None = None  # video frames: the 2-second window they stand for
    end: float | None = None


def visual_rules(rules: list[Rule]) -> list[Rule]:
    """Approved semantic rules a vision model can check: every visuals rule, and
    accessibility rules about images, colour or contrast."""
    return [
        r for r in rules
        if r.status == "approved" and r.check_type == "semantic"
        and (r.category == "visuals"
             or (r.category == "accessibility" and any(w in r.text.lower() for w in IMAGE_WORDS)))
    ]  # fmt: skip


def run_visuals(
    images: list[ImageInput],
    rules: list[Rule],
    *,
    client: LLMClient,
    assets: list[str] = (),
    brand_id: UUID | None = None,
    content_version_id: UUID | None = None,
    max_workers: int = 2,
) -> list[Candidate]:
    checkable = visual_rules(rules)
    if not images or not checkable:
        return []
    refs = [
        RuleRef(r.rule_code, r.category, r.text, r.examples_bad, r.examples_good) for r in checkable
    ]
    by_code = {r.rule_code: r for r in checkable}
    supplied = frozenset(by_code)

    def check(image: ImageInput) -> list[Candidate]:
        p = prompts.visual_check(image.image_id, refs, list(assets), alt_text=image.alt_text)
        out = client.json(p.schema, p.system, p.prompt, purpose=p.purpose, brand_id=brand_id,
                          content_version_id=content_version_id, images=[image.data])  # fmt: skip
        found = []
        for f in out.flags:
            rule = by_code.get(f.rule_code)
            found.append(Candidate(
                unit_id=image.image_id, source_type="rule", source_id=f.rule_code,
                category=rule.category if rule else "visuals", severity=f.severity,
                evidence=f.evidence, explanation=f.explanation, suggested_fix=f.suggested_fix,
                confidence=f.confidence, layer="visuals", supplied=supplied,
                extra={"region": f.region},
            ))  # fmt: skip
        return found

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return [c for batch in pool.map(check, images) for c in batch]

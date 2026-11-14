"""Accessibility checks in code (task 8.3).

* Contrast: WCAG 2 contrast ratio of PDF text colours against the (white) page; below 4.5:1
  (3:1 for large text) is flagged.
* Alt text: uploaded images without alt text are flagged.
* Readability: Flesch reading ease per unit against the brand's target; the hardest sentence
  is quoted as evidence. Computed here (vowel-group syllable count) instead of with textstat,
  whose current release downloads a dictionary at run time.

Every check cites the brand's own approved accessibility rule that it enforces (found by its
wording). If the brand has no such rule the check does not run: no source, no flag.
"""

import re

from app.models.rules import Rule
from app.processing.pdf_content import TextStyle
from app.review.candidates import Candidate
from app.review.segment import Unit

WHITE = (255, 255, 255)
LARGE_TEXT_PT = 18.0
MIN_WORDS_FOR_READABILITY = 20

_RULE_WORDS = {
    "contrast": ("contrast",),
    "alt": ("alt text", "alt-text", "alternative text"),
    # Video captions, not "social media captions": needs a word about video, speech or sound.
    "captions": ("subtitle", "closed caption"),
    "readability": ("reading level", "readab", "year-old", "plain language", "sentences under",
                    "easy to read", "everyday words"),
}  # fmt: skip


def count_syllables(word: str) -> int:
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    groups = len(re.findall(r"[aeiouy]+", word))
    if word.endswith("e") and not word.endswith(("le", "ee", "ye")) and groups > 1:
        groups -= 1
    return max(1, groups)


def reading_ease(text: str) -> float:
    """Flesch reading ease: 206.835 - 1.015 (words / sentence) - 84.6 (syllables / word)."""
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", text)
    if not words:
        return 100.0
    sentences = max(1, len(re.findall(r"[.!?]+(?:\s|$)", text)))
    syllables = sum(count_syllables(w) for w in words)
    return 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))


def find_rule(rules: list[Rule], kind: str) -> Rule | None:
    """The brand's approved rule that a code check enforces, by its wording."""
    words = _RULE_WORDS[kind]
    for r in rules:
        text = r.text.lower()
        if r.status != "approved":
            continue
        if any(w in text for w in words):
            return r
        if (
            kind == "captions"
            and "caption" in text
            and any(w in text for w in ("video", "speech", "spoken", "said", "audio", "sound"))
        ):
            return r
    return None


def _luminance(rgb: tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        v = c / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int] = WHITE) -> float:
    lighter, darker = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def check_contrast(styles: list[TextStyle], rules: list[Rule]) -> list[Candidate]:
    rule = find_rule(rules, "contrast")
    if rule is None:
        return []
    out: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    for s in styles:
        needed = 3.0 if s.size >= LARGE_TEXT_PT else 4.5
        ratio = contrast_ratio(s.color)
        if ratio >= needed or (s.unit_id, s.text) in seen:
            continue
        seen.add((s.unit_id, s.text))
        out.append(Candidate(
            unit_id=s.unit_id, source_type="rule", source_id=rule.rule_code,
            category="accessibility", severity="medium", evidence=s.text,
            explanation=(f"Text colour #{s.color[0]:02X}{s.color[1]:02X}{s.color[2]:02X} has a "
                         f"contrast ratio of {ratio:.1f}:1 on white; "
                         f"at least {needed:g}:1 is needed."),
            suggested_fix=None, confidence=1.0, layer="rules",
        ))  # fmt: skip
    return out


def check_alt_text(image_id: str, alt_text: str | None, rules: list[Rule]) -> list[Candidate]:
    rule = find_rule(rules, "alt")
    if rule is None or (alt_text and alt_text.strip()):
        return []
    return [Candidate(
        unit_id=image_id, source_type="rule", source_id=rule.rule_code, category="accessibility",
        severity="medium", evidence="Image has no alt text",
        explanation="This image has no alt text, so screen-reader users miss what it shows.",
        suggested_fix="Add alt text that describes the image.", confidence=1.0, layer="visuals",
        supplied=frozenset({rule.rule_code}),
    )]  # fmt: skip


def check_readability(
    units: list[Unit], rules: list[Rule], target: float | None
) -> list[Candidate]:
    rule = find_rule(rules, "readability")
    if rule is None or target is None:
        return []
    out: list[Candidate] = []
    for u in units:
        if len(u.text.split()) < MIN_WORDS_FOR_READABILITY:
            continue
        score = reading_ease(u.text)
        if score >= target:
            continue
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", u.text) if s.strip()]
        hardest = min(sentences, key=reading_ease) if sentences else u.text
        out.append(Candidate(
            unit_id=u.unit_id, source_type="rule", source_id=rule.rule_code,
            category="accessibility", severity="low", evidence=hardest,
            explanation=(f"Reading ease is {score:.0f}; the brand's target is {target:g} or more. "
                         "Use shorter sentences and everyday words."),
            suggested_fix=None, confidence=0.9, layer="rules",
        ))  # fmt: skip
    return out


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", text.lower()))


def check_captions(
    speech: list[Unit], cues: list[tuple[float, float, str]] | None, rules: list[Rule]
) -> list[Candidate]:
    """Task 11.5: captions exist (`cues` is None when no captions file was given) and match
    the speech: in each transcript unit's time window, at least 60% of the spoken words must
    appear in the captions."""
    rule = find_rule(rules, "captions")
    if rule is None or not speech:
        return []
    if cues is None:
        first = speech[0]
        return [Candidate(
            unit_id=first.unit_id, source_type="rule", source_id=rule.rule_code,
            category="accessibility", severity="medium", evidence="",
            explanation="This video has speech but no captions file.",
            suggested_fix="Upload captions (SRT or WebVTT) that match what is said.",
            confidence=1.0, layer="rules", allow_empty_evidence=True, span=(0, 0),
        )]  # fmt: skip
    out: list[Candidate] = []
    for u in speech:
        start, end = u.location["start"], u.location["end"]
        shown = " ".join(t for s, e, t in cues if s < end and e > start)
        spoken = _words(u.text)
        if len(spoken) < 4:
            continue
        coverage = len(spoken & _words(shown)) / len(spoken)
        if coverage < 0.6:
            out.append(Candidate(
                unit_id=u.unit_id, source_type="rule", source_id=rule.rule_code,
                category="accessibility", severity="medium", evidence=u.text,
                explanation=(f"The captions here cover only {coverage:.0%} of what is said"
                             + (f" (captions: “{shown[:120]}”)." if shown else " (no captions).")),
                suggested_fix=None, confidence=0.9, layer="rules", span=(0, len(u.text)),
            ))  # fmt: skip
    return out

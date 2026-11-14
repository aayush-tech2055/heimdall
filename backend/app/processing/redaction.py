"""Redaction before any AI call (task 6.2, decision 16).

Sensitive spans are replaced with placeholders like `[EMAIL]`. Detectors: regex for email,
phone, PAN, Aadhaar and card numbers (Luhn-checked), the brand's confidential terms, and
Presidio PERSON / LOCATION when Presidio is installed. Everything sent to a model is the
redacted text; `Redacted.to_original` maps a span in the redacted text back to the original,
so flags can still point at the creator's real words.
"""

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache

log = logging.getLogger(__name__)

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("CARD", re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")),
    ("AADHAAR", re.compile(r"(?<!\d)(?<!\d[ -])[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?![ -]?\d)")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("PHONE", re.compile(r"(?<![\w+])(?<!\d[ -])(?:\+?91[ -]?)?[6-9]\d{4}[ -]?\d{5}(?![ -]?\d)")),
    ("PHONE", re.compile(r"(?<![\w+])\+\d{1,3}[ -]?\(?\d{2,4}\)?[ -]?\d{3,4}[ -]?\d{3,4}(?!\d)")),
]


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


@dataclass(frozen=True)
class Replacement:
    orig_start: int
    orig_end: int
    red_start: int
    red_end: int
    label: str


@dataclass
class Redacted:
    original: str
    text: str
    replacements: list[Replacement] = field(default_factory=list)

    @property
    def labels(self) -> list[str]:
        return [r.label for r in self.replacements]

    def to_original(self, start: int, end: int) -> tuple[int, int]:
        """Map [start, end) in the redacted text to the original text.

        A boundary inside a placeholder expands to cover the whole original value.
        """
        return self._map(start, is_end=False), self._map(end, is_end=True)

    def _map(self, pos: int, *, is_end: bool) -> int:
        delta = 0
        for r in self.replacements:
            if pos <= r.red_start:  # before this placeholder (or exactly at its start)
                break
            if pos < r.red_end:  # strictly inside the placeholder
                return r.orig_end if is_end else r.orig_start
            delta = r.orig_end - r.red_end  # at or after its end
        return pos + delta


@lru_cache(maxsize=1)
def _presidio():  # noqa: ANN202 - optional dependency
    """Presidio's analyzer with a small spaCy model, or None when it is not installed."""
    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore[import-not-found]
        from presidio_analyzer.nlp_engine import NlpEngineProvider  # type: ignore[import-not-found]
    except ImportError:
        return None
    from app.config import get_settings

    model = get_settings().presidio_spacy_model
    try:
        nlp = NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": model}],
        }).create_engine()  # fmt: skip
        return AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])
    except Exception:  # noqa: BLE001 - missing spaCy model etc.
        log.warning("Presidio is installed but spaCy model %r is missing; skipping names", model)
        return None


def presidio_available() -> bool:
    return _presidio() is not None


def _detect(
    text: str, confidential_terms: list[str], use_presidio: bool
) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for label, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            if label == "CARD" and not _luhn_ok(re.sub(r"\D", "", m.group())):
                continue
            spans.append((m.start(), m.end(), label))
    for term in confidential_terms:
        term = term.strip()
        if not term:
            continue
        body = r"\s+".join(re.escape(w) for w in term.split())
        for m in re.finditer(rf"(?<!\w){body}(?!\w)", text, re.IGNORECASE):
            spans.append((m.start(), m.end(), "CONFIDENTIAL"))
    engine = _presidio() if use_presidio else None
    if engine is not None:
        for res in engine.analyze(text=text, entities=["PERSON", "LOCATION"], language="en"):
            if res.score >= 0.6:
                spans.append((res.start, res.end, res.entity_type))
    # Longest first, then earliest: overlapping detections keep the widest span.
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    kept: list[tuple[int, int, str]] = []
    for span in spans:
        if kept and span[0] < kept[-1][1]:
            if span[1] > kept[-1][1]:
                kept[-1] = (kept[-1][0], span[1], kept[-1][2])
            continue
        kept.append(span)
    return kept


def redact(
    text: str,
    confidential_terms: list[str] | None = None,
    *,
    use_presidio: bool = True,
    exempt_terms: list[str] | None = None,
) -> Redacted:
    """Replace sensitive spans with `[LABEL]` placeholders.

    `exempt_terms` (for example the brand's own and product names) are never redacted by
    Presidio, which can mistake them for people or places.
    """
    spans = _detect(text, confidential_terms or [], use_presidio)
    exempt = {t.lower() for t in (exempt_terms or [])}
    out: list[str] = []
    replacements: list[Replacement] = []
    cursor = 0
    red_len = 0
    for start, end, label in spans:
        if label in {"PERSON", "LOCATION"} and text[start:end].lower() in exempt:
            continue
        out.append(text[cursor:start])
        red_len += start - cursor
        placeholder = f"[{label}]"
        replacements.append(Replacement(start, end, red_len, red_len + len(placeholder), label))
        out.append(placeholder)
        red_len += len(placeholder)
        cursor = end
    out.append(text[cursor:])
    return Redacted(original=text, text="".join(out), replacements=replacements)

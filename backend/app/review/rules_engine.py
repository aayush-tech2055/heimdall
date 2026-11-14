"""Layer (a): deterministic rules, checked in code and never sent to a model (task 6.3).

* banned_terms: whole word, case-insensitive; every occurrence is flagged with its span.
* required_phrase: checked across the whole document (case, whitespace and quote style
  ignored); if missing, one flag with empty evidence on the last unit.
"""

import re

from app.models.rules import Rule
from app.review.candidates import Candidate
from app.review.segment import Unit
from app.review.text import find_normalised


def _severity(rule: Rule) -> str:
    return "high" if rule.category == "legal" else "medium"


def term_pattern(term: str) -> re.Pattern[str]:
    """Whole-word, case-insensitive; any run of whitespace matches inside multi-word terms."""
    body = r"\s+".join(re.escape(word) for word in term.split())
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


def check_deterministic(units: list[Unit], rules: list[Rule]) -> list[Candidate]:
    candidates: list[Candidate] = []
    for rule in rules:
        if rule.check_type != "deterministic" or rule.status != "approved" or not rule.terms:
            continue
        if rule.det_kind == "banned_terms":
            for unit in units:
                for term in rule.terms:
                    for m in term_pattern(term).finditer(unit.text):
                        candidates.append(
                            Candidate(
                                unit_id=unit.unit_id, source_type="rule",
                                source_id=rule.rule_code, category=rule.category,
                                severity=_severity(rule), evidence=m.group(),
                                explanation=f"“{m.group()}” is not allowed. {rule.text}",
                                suggested_fix=None, confidence=1.0, layer="rules",
                                span=(m.start(), m.end()),
                            )
                        )  # fmt: skip
        elif rule.det_kind == "required_phrase" and units:
            document = "\n\n".join(u.text for u in units)
            for phrase in rule.terms:
                if find_normalised(document, phrase) is None:
                    last = units[-1]
                    candidates.append(
                        Candidate(
                            unit_id=last.unit_id, source_type="rule",
                            source_id=rule.rule_code, category=rule.category,
                            severity=_severity(rule), evidence="",
                            explanation=f"Required text is missing: “{phrase}”. {rule.text}",
                            suggested_fix=phrase, confidence=1.0, layer="rules",
                            allow_empty_evidence=True, span=(len(last.text), len(last.text)),
                        )
                    )  # fmt: skip
    candidates.sort(key=lambda c: (int(c.unit_id[1:]), c.span or (0, 0)))
    return candidates

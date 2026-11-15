"""Split text content into review units (task 6.1, decision 15).

Paragraphs are separated by blank lines. A paragraph longer than ~900 characters is split at
sentence ends. Every unit keeps its paragraph number (1-based) and its exact character span
in the original text, so `text[char_start:char_end] == unit.text` always holds.
"""

import re
from dataclasses import dataclass, field

MAX_UNIT_CHARS = 900

_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n\s*")
# A sentence ends at . ! or ? (optionally followed by closing quotes/brackets) plus whitespace.
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"'”’)\]]*\s+")


@dataclass(frozen=True)
class Unit:
    unit_id: str
    position: int  # 0-based reading order
    text: str
    location: dict = field(default_factory=dict)

    @property
    def char_start(self) -> int:
        return self.location["char_start"]

    @property
    def char_end(self) -> int:
        return self.location["char_end"]


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _PARAGRAPH_BREAK.finditer(text):
        spans.append((start, match.start()))
        start = match.end()
    spans.append((start, len(text)))
    return spans


def _strip_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _split_long(text: str, start: int, end: int, limit: int) -> list[tuple[int, int]]:
    """Split [start, end) at sentence ends into pieces of at most ~limit characters."""
    if end - start <= limit:
        return [(start, end)]
    cuts = [start + m.end() for m in _SENTENCE_END.finditer(text[start:end])]
    pieces: list[tuple[int, int]] = []
    piece_start = start
    last_cut = start
    for cut in [*cuts, end]:
        if cut - piece_start > limit and last_cut > piece_start:
            pieces.append((piece_start, last_cut))
            piece_start = last_cut
        last_cut = cut
    pieces.append((piece_start, end))
    # A single sentence longer than the limit stays whole (it is never cut mid-sentence).
    return [_strip_span(text, s, e) for s, e in pieces]


def segment_text(text: str, max_chars: int = MAX_UNIT_CHARS) -> list[Unit]:
    """Units with ids u1, u2, … in reading order."""
    units: list[Unit] = []
    paragraph = 0
    for p_start, p_end in _paragraph_spans(text):
        p_start, p_end = _strip_span(text, p_start, p_end)
        if p_start == p_end:
            continue
        paragraph += 1
        for s, e in _split_long(text, p_start, p_end, max_chars):
            if s == e:
                continue
            n = len(units)
            units.append(
                Unit(
                    unit_id=f"u{n + 1}",
                    position=n,
                    text=text[s:e],
                    location={"paragraph": paragraph, "char_start": s, "char_end": e},
                )
            )
    return units

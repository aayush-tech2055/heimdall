"""Lenient text matching for evidence (decision 20): ignore case, whitespace and
curly-versus-straight quotes, but report spans in the original text."""

_QUOTES = str.maketrans(
    {"‘": "'", "’": "'", "‛": "'", "′": "'", "“": '"', "”": '"', "„": '"', "″": '"'}
)


def _normalise_with_map(text: str) -> tuple[str, list[int]]:
    """Normalised text plus, for each normalised char, the index of its original char."""
    out: list[str] = []
    index: list[int] = []
    in_space = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if not in_space and out:
                out.append(" ")
                index.append(i)
            in_space = True
            continue
        in_space = False
        for c in ch.translate(_QUOTES).casefold():
            out.append(c)
            index.append(i)
    if out and out[-1] == " ":
        out.pop()
        index.pop()
    return "".join(out), index


def normalise(text: str) -> str:
    return _normalise_with_map(text)[0]


def find_normalised(haystack: str, needle: str, start_at: int = 0) -> tuple[int, int] | None:
    """Span of the first lenient match of `needle` in `haystack`, in original indices."""
    norm_needle = normalise(needle)
    if not norm_needle:
        return None
    norm_hay, index = _normalise_with_map(haystack)
    first = next((n for n, i in enumerate(index) if i >= start_at), len(index))
    pos = norm_hay.find(norm_needle, first)
    if pos == -1:
        return None
    return index[pos], index[pos + len(norm_needle) - 1] + 1


def overlaps(a: str, b: str) -> bool:
    """True if one normalised string contains the other (used for approved exceptions)."""
    na, nb = normalise(a), normalise(b)
    return bool(na and nb) and (na in nb or nb in na)

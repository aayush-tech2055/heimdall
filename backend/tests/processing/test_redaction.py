"""Redaction before AI calls (task 6.2, decision 16)."""

import pytest

from app.processing.redaction import redact

CASES = [
    ("Write to priya.s@example.com today", "Write to [EMAIL] today"),
    ("Call +91 98200 12345 or 9820012345.", "Call [PHONE] or [PHONE]."),
    ("PAN ABCDE1234F on file", "PAN [PAN] on file"),
    ("Aadhaar 2345 6789 0123 shared", "Aadhaar [AADHAAR] shared"),
    ("Card 4111 1111 1111 1111 charged", "Card [CARD] charged"),
]


@pytest.mark.parametrize(("text", "expected"), CASES)
def test_regex_detectors(text, expected):
    assert redact(text, use_presidio=False).text == expected


@pytest.mark.parametrize(
    "text",
    [
        "AcmeLearn Pro costs ₹599 a month and ₹4,999 one-time.",
        "More than 2 million learners since 2019; rated 4.6 stars.",
        "Order 1234 5678 9012 3456 is not a valid card number.",  # fails Luhn
    ],
)
def test_prices_counts_and_invalid_cards_are_left_alone(text):
    assert redact(text, use_presidio=False).text == text


def test_confidential_terms_whole_word_case_insensitive():
    r = redact("Project falcon launches soon; projectfalcon is unaffected.", ["Project Falcon"],
               use_presidio=False)  # fmt: skip
    assert r.text == "[CONFIDENTIAL] launches soon; projectfalcon is unaffected."


def test_offsets_map_back_to_the_original():
    text = "Hi, email a@b.co and call 9820012345 about Project Falcon now."
    r = redact(text, ["Project Falcon"], use_presidio=False)
    assert r.text == "Hi, email [EMAIL] and call [PHONE] about [CONFIDENTIAL] now."
    assert r.labels == ["EMAIL", "PHONE", "CONFIDENTIAL"]

    def back(sub: str) -> str:
        i = r.text.index(sub)
        s, e = r.to_original(i, i + len(sub))
        return text[s:e]

    assert back("and call") == "and call"
    assert back("now.") == "now."
    assert back("[EMAIL]") == "a@b.co"
    assert back("email [EMAIL] and") == "email a@b.co and"
    assert back("ONFIDENT") == "Project Falcon"  # inside a placeholder: the whole value


def test_no_detections_is_identity():
    r = redact("Plain text.", use_presidio=False)
    assert r.text == "Plain text." and r.to_original(0, 5) == (0, 5)

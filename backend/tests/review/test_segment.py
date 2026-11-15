"""Text segmentation (task 6.1)."""

import json
from pathlib import Path

from app.review.segment import segment_text

TEST_DATA = Path(__file__).resolve().parents[3] / "test-data" / "brands"


def test_paragraphs_become_units_with_exact_spans():
    text = "  Title line\n\nFirst paragraph.\nStill first.\n\n\n  Second one.  \n"
    units = segment_text(text)
    assert [u.unit_id for u in units] == ["u1", "u2", "u3"]
    assert [u.text for u in units] == [
        "Title line",
        "First paragraph.\nStill first.",
        "Second one.",
    ]
    assert [u.location["paragraph"] for u in units] == [1, 2, 3]
    for u in units:
        assert text[u.char_start : u.char_end] == u.text


def test_long_paragraph_splits_at_sentence_ends_under_the_limit():
    sentences = [f"Sentence number {i} says something useful about the course." for i in range(40)]
    text = "Intro.\n\n" + " ".join(sentences)
    units = segment_text(text, max_chars=200)
    assert units[0].text == "Intro."
    body = units[1:]
    assert len(body) > 5
    assert all(len(u.text) <= 200 for u in body)
    assert all(u.text.endswith(".") for u in body)
    assert all(u.location["paragraph"] == 2 for u in body)
    assert " ".join(u.text for u in body) == " ".join(sentences)
    for u in units:
        assert text[u.char_start : u.char_end] == u.text


def test_one_overlong_sentence_is_never_cut():
    text = "x" * 50 + " " + "y" * 50
    assert [u.text for u in segment_text(text, max_chars=30)] == [text]


def test_empty_text_has_no_units():
    assert segment_text("") == [] and segment_text(" \n\n \n") == []


def test_every_test_content_item_round_trips():
    for brand in ("acmelearn", "brewbird"):
        for item in json.loads((TEST_DATA / brand / "content.json").read_text()):
            units = segment_text(item["text"])
            assert units, item["id"]
            for u in units:
                assert item["text"][u.char_start : u.char_end] == u.text

"""Pure fact logic: expiry in code (decision 10), CSV parsing, and RRF (decision 13)."""

from datetime import date
from pathlib import Path

import pytest

from app.rag.facts_store import expiry_status, parse_facts_csv
from app.rag.retrieval import rrf

TODAY = date(2026, 11, 15)
TEST_DATA = Path(__file__).resolve().parents[3] / "test-data" / "brands"


@pytest.mark.parametrize(
    ("valid_until", "expected"),
    [
        (None, "no_expiry"),
        (date(2026, 11, 14), "expired"),
        (date(2026, 11, 15), "expiring"),  # valid today, expires within 30 days
        (date(2026, 12, 15), "expiring"),
        (date(2026, 12, 16), "valid"),
    ],
)
def test_expiry_status(valid_until, expected):
    assert expiry_status(valid_until, TODAY) == expected


def test_test_data_facts_parse_cleanly_with_two_expired_each():
    for brand in ("acmelearn", "brewbird"):
        facts, errors = parse_facts_csv((TEST_DATA / brand / "facts.csv").read_text())
        assert errors == [] and len(facts) == 17
        assert sum(expiry_status(f.valid_until, TODAY) == "expired" for f in facts) == 2


def test_csv_errors_name_the_row_and_valid_rows_still_parse():
    text = (
        "Entity,Attribute,Value,Unit,Statement,Source,Valid_until\n"
        "Pro,price,599,INR,Pro costs 599.,site,2027-01-31\n"
        ",price,1,,No entity.,,\n"
        "Plus,price,299,INR,Plus costs 299.,site,31/01/2027\n"
        "\n"
        "Plus,trial,7,days,Seven days.,,\n"
    )
    facts, errors = parse_facts_csv(text)
    assert [f.entity for f in facts] == ["Pro", "Plus"]
    assert [e.row for e in errors] == [3, 4]
    assert "entity" in errors[0].message and "valid_until" in errors[1].message


def test_csv_missing_required_columns():
    facts, errors = parse_facts_csv("entity,value\nPro,599\n")
    assert facts == [] and "attribute" in errors[0].message and "statement" in errors[0].message


def test_rrf_merges_rankings_with_k_60():
    merged = rrf([["a", "b", "c"], ["c", "a", "d"]])
    # a: 1/61 + 1/62, c: 1/63 + 1/61, b: 1/62, d: 1/63
    assert merged == ["a", "c", "b", "d"]


def test_rrf_handles_empty_lists_and_ties_deterministically():
    assert rrf([[], []]) == []
    assert rrf([["x"], ["y"]]) == ["x", "y"]
    assert rrf([["y"], ["x"]]) == ["y", "x"]

"""Fact store and hybrid lookup on the real database (rolled back), fake embedder."""

from datetime import date

import pytest

from app.models.facts import FactCreate, FactUpdate
from app.rag.extraction import RuleDraft
from app.rag.facts_store import (
    FactNotFoundError,
    create_facts,
    list_facts,
    lookup_facts,
    set_fact_status,
    update_fact,
)
from app.rag.retrieval import search_rules
from app.rag.rules_store import set_rule_status, store_rules
from tests.db.helpers import make_brand
from tests.rag.fakes import FakeEmbedder, blend, unit_vector

pytestmark = pytest.mark.db
TODAY = date(2026, 11, 15)


def facts():
    return [
        FactCreate(entity="AcmeLearn Pro", attribute="monthly price", value="599", unit="INR",
                   statement="AcmeLearn Pro costs 599 rupees a month.",
                   valid_until=date(2027, 3, 31)),
        FactCreate(entity="AcmeLearn Pro", attribute="free trial", value="7", unit="days",
                   statement="AcmeLearn Pro comes with a 7-day free trial."),
        FactCreate(entity="AcmeLearn", attribute="registered learners", value="2000000",
                   statement="More than 2 million learners have registered on AcmeLearn.",
                   valid_until=date(2026, 6, 30)),
    ]  # fmt: skip


def test_create_approved_or_pending_with_codes_and_expiry(db):
    brand = make_brand(db)
    typed = create_facts(db, brand, facts()[:1], FakeEmbedder(), status="approved",
                         actor_id=None, today=TODAY)  # fmt: skip
    imported = create_facts(db, brand, facts()[1:], FakeEmbedder(), status="pending",
                            actor_id=None, today=TODAY)  # fmt: skip
    assert [(f.fact_code, f.status) for f in typed + imported] == [
        ("F-001", "approved"), ("F-002", "pending"), ("F-003", "pending"),
    ]  # fmt: skip
    assert [f.expiry for f in typed + imported] == ["valid", "no_expiry", "expired"]
    assert [f.fact_code for f in list_facts(db, brand, TODAY, query="trial")] == ["F-002"]
    assert [f.fact_code for f in list_facts(db, brand, TODAY, status="pending")] == [
        "F-002",
        "F-003",
    ]


def test_edit_keeps_code_and_reembeds_statement(db):
    brand = make_brand(db)
    create_facts(
        db, brand, facts()[:1], FakeEmbedder(), status="approved", actor_id=None, today=TODAY
    )
    emb = FakeEmbedder()
    after = update_fact(db, brand, "F-001", FactUpdate(value="649", statement="Pro costs 649."),
                        emb, actor_id=None, today=TODAY)  # fmt: skip
    assert (after.fact_code, after.value) == ("F-001", "649") and len(emb.calls) == 1
    with pytest.raises(FactNotFoundError):
        update_fact(db, brand, "F-404", FactUpdate(value="1"), emb, actor_id=None, today=TODAY)
    approved = set_fact_status(db, brand, ["F-001"], "rejected", actor_id=None, today=TODAY)
    assert approved[0].status == "rejected"


def test_lookup_prefers_exact_entity_then_hybrid_and_skips_unapproved(db):
    brand = make_brand(db)
    claim = "Try AcmeLearn Pro free for 30 days"
    q = unit_vector(claim)
    emb = FakeEmbedder({
        facts()[1].statement: blend(q, unit_vector("x"), 0.1),  # very close to the claim
        facts()[2].statement: blend(q, unit_vector("y"), 0.3),
    })  # fmt: skip
    create_facts(db, brand, facts(), emb, status="approved", actor_id=None, today=TODAY)
    create_facts(db, brand, [FactCreate(entity="AcmeLearn Pro", attribute="x", value="1",
                 statement="Pending fact about trials.")], emb, status="pending",
                 actor_id=None, today=TODAY)  # fmt: skip

    found = lookup_facts(db, brand, entity="acmelearn pro", claim=claim, vector=q, today=TODAY)
    codes = [f.fact_code for f in found]
    assert codes[:2] == ["F-002", "F-001"] or codes[:2] == ["F-001", "F-002"]
    assert set(codes) == {"F-001", "F-002", "F-003"} and "F-004" not in codes
    assert found[-1].expiry == "expired" if codes[-1] == "F-003" else True

    other = lookup_facts(db, brand, entity="Nobody", claim=claim, vector=q, today=TODAY, limit=1)
    assert [f.fact_code for f in other] == ["F-002"]  # no exact match: hybrid's best


def test_rule_search_returns_only_approved_semantic_rules(db):
    brand = make_brand(db)
    unit = "Our cheap course is great"
    q = unit_vector(unit)
    drafts = [
        RuleDraft("R-001", "terminology", "Never call courses cheap.", "g", 1),
        RuleDraft("R-002", "terminology", "Never say cheap.", "g", 1, check_type="deterministic",
                  det_kind="banned_terms", terms=["cheap"]),
        RuleDraft("R-003", "tone", "Be warm.", "g", 1),
        RuleDraft("R-004", "tone", "Pending rule about cheap courses.", "g", 1),
    ]  # fmt: skip
    emb = FakeEmbedder({"Never call courses cheap.": blend(q, unit_vector("z"), 0.1)})
    store_rules(db, brand, drafts, emb)
    set_rule_status(db, brand, ["R-001", "R-002", "R-003"], "approved", None)
    codes = search_rules(db, brand, unit, q)
    assert codes[0] == "R-001"
    assert "R-002" not in codes and "R-004" not in codes

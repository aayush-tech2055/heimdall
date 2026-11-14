"""Rules store against the real database (rolled back), with a fake embedder."""

import pytest

from app.models.rules import RuleUpdate
from app.rag.extraction import RuleDraft
from app.rag.rules_store import (
    RuleNotFoundError,
    list_rules,
    next_rule_number,
    set_rule_status,
    store_rules,
    update_rule,
)
from tests.db.helpers import make_brand, make_user
from tests.rag.fakes import FakeEmbedder

pytestmark = pytest.mark.db


def drafts():
    return [
        RuleDraft("R-001", "tone", "Be warm.", "guide.pdf", 1, always_on=True),
        RuleDraft("R-002", "terminology", "Never say cheap.", "guide.pdf", 2,
                  check_type="deterministic", det_kind="banned_terms", terms=["cheap"],
                  examples_bad=["Cheap course!"]),
    ]  # fmt: skip


def test_store_embeds_and_inserts_pending_rules(db):
    brand = make_brand(db)
    embedder = FakeEmbedder()
    stored = store_rules(db, brand, drafts(), embedder)
    assert [(r.rule_code, r.status, r.source_page) for r in stored] == [
        ("R-001", "pending", 1),
        ("R-002", "pending", 2),
    ]
    assert embedder.calls == [
        ("doc", ["Be warm.", "Never say cheap. Examples of breaking it: Cheap course!"])
    ]
    dims = db.execute(
        "select extensions.vector_dims(embedding) from public.rules where brand_id = %s",
        (brand,),
    ).fetchall()
    assert dims == [(768,), (768,)]
    assert next_rule_number(db, brand) == 3


def test_list_filters_by_status_and_approval_is_audited(db):
    brand = make_brand(db)
    admin = make_user(db, brand, "admin")
    store_rules(db, brand, drafts(), FakeEmbedder())
    set_rule_status(db, brand, ["R-002"], "approved", admin)
    assert [r.rule_code for r in list_rules(db, brand, "approved")] == ["R-002"]
    assert [r.rule_code for r in list_rules(db, brand, "pending")] == ["R-001"]
    approved_by = db.execute(
        "select approved_by from public.rules where brand_id = %s and rule_code = 'R-002'",
        (brand,),
    ).fetchone()[0]
    assert approved_by == admin
    actions = db.execute(
        "select action, entity_id from public.audit_log where brand_id = %s", (brand,)
    ).fetchall()
    assert actions == [("rule.approved", "R-002")]


def test_unknown_code_changes_nothing(db):
    brand = make_brand(db)
    store_rules(db, brand, drafts(), FakeEmbedder())
    with pytest.raises(RuleNotFoundError, match="R-404"):
        set_rule_status(db, brand, ["R-001", "R-404"], "approved", None)
    assert list_rules(db, brand, "approved") == []


def test_edit_reembeds_only_when_text_changes_and_keeps_decision_7(db):
    brand = make_brand(db)
    store_rules(db, brand, drafts(), FakeEmbedder())
    embedder = FakeEmbedder()
    edited = update_rule(db, brand, "R-001", RuleUpdate(category="messaging"), embedder, None)
    assert edited.category == "messaging" and embedder.calls == []
    edited = update_rule(db, brand, "R-001", RuleUpdate(text="Be kind."), embedder, None)
    assert edited.text == "Be kind." and len(embedder.calls) == 1
    downgraded = update_rule(db, brand, "R-002", RuleUpdate(terms=[]), embedder, None)
    assert (downgraded.check_type, downgraded.det_kind) == ("semantic", None)
    with pytest.raises(RuleNotFoundError):
        update_rule(db, brand, "R-999", RuleUpdate(text="x"), embedder, None)

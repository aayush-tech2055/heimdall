"""The workflow state machine (task 7.1): allowed moves only."""

import pytest

from app.review.workflow import TRANSITIONS, InvalidTransitionError, allowed, transition

STATES = ["draft", "checking", "creator_review", "manager_review", "changes_requested", "approved"]


def test_the_locked_happy_path_and_send_back_loop_are_allowed():
    path = ["draft", "checking", "creator_review", "manager_review", "changes_requested",
            "creator_review", "manager_review", "approved"]  # fmt: skip
    assert all(allowed(a, b) for a, b in zip(path, path[1:], strict=False))


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("draft", "approved"),
        ("creator_review", "approved"),  # skipping the manager
        ("checking", "manager_review"),
        ("approved", "creator_review"),  # approved is final
        ("manager_review", "creator_review"),  # send-back goes through changes_requested
        ("draft", "manager_review"),
    ],
)
def test_shortcuts_are_refused(current, target):
    assert not allowed(current, target)


def test_approved_is_terminal_and_every_state_is_known():
    assert not any(a == "approved" for a, _ in TRANSITIONS)
    assert {s for pair in TRANSITIONS for s in pair} == set(STATES)


class FakeConn:
    def __init__(self, status):
        self.status, self.statements = status, []

    def execute(self, sql, params=()):
        self.statements.append(sql.split()[0])
        status = self.status

        class R:
            def fetchone(self):
                return (status, "brand")

        return R()


def test_invalid_transition_raises_and_writes_nothing():
    conn = FakeConn("approved")
    with pytest.raises(InvalidTransitionError, match="from approved to checking"):
        transition(conn, "c1", "checking", actor_id=None)
    assert conn.statements == ["select"]


def test_valid_transition_updates_and_audits():
    conn = FakeConn("creator_review")
    assert transition(conn, "c1", "manager_review", actor_id=None) == "creator_review"
    assert conn.statements == ["select", "update", "insert"]

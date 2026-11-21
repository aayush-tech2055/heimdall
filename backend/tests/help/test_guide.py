from app.help.guide import OVERVIEW, PAGES, ROLES, context_for, page_note


def test_longest_page_prefix_wins():
    assert page_note("/creator/content/abc") == PAGES["/creator/content"]
    assert page_note("/creator") == PAGES["/creator"]
    assert page_note("/creator/new") == PAGES["/creator/new"]
    assert page_note("/creatorx") is None
    assert page_note("/") is None


def test_context_has_overview_role_and_page_only():
    ctx = context_for("admin", "/admin/team")
    assert ctx.startswith(OVERVIEW)
    assert ROLES["admin"] in ctx and ROLES["creator"] not in ctx
    assert "The user is on /admin/team." in ctx and PAGES["/admin/team"] in ctx
    assert context_for(None, "/") == OVERVIEW


def test_every_role_has_a_section():
    assert set(ROLES) == {"admin", "manager", "creator"}

"""Per-user rate limits (task 14.4)."""

from app.api import ratelimit
from tests.api.conftest import sign_in_as


def test_sliding_window():
    ratelimit.reset()
    key = ("u1", "review")
    assert [ratelimit.check(key, 2, 60, now=t) for t in (0, 1)] == [0.0, 0.0]
    assert ratelimit.check(key, 2, 60, now=2) == 58.0  # third call waits for the first to expire
    assert ratelimit.check(key, 2, 60, now=60.5) == 0.0
    assert ratelimit.check(("u2", "review"), 2, 60, now=2) == 0.0  # per user


def test_upload_is_limited_with_retry_after(api):
    ratelimit.reset()
    sign_in_as("creator")
    user_hits = 0
    for _ in range(31):
        response = api.post(
            "/contents", data={"title": "x", "text": " "}
        )  # 422 after the limit check
        user_hits += 1
        if response.status_code == 429:
            break
    assert response.status_code == 429 and user_hits == 31
    assert "Retry-After" in response.headers
    ratelimit.reset()

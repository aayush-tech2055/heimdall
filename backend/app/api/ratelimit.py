"""Per-user rate limits on the endpoints that call AI models or process files (task 14.4).

A small in-memory sliding window, per user and action. One backend process is enough for
the demo; a multi-process deployment would move this to Redis or the database.
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.api.deps import CurrentUser, get_current_user

_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def check(key: tuple[str, str], limit: int, window: float, now: float | None = None) -> float:
    """Record a hit; return 0 if allowed, else the seconds until the next hit is allowed."""
    now = time.monotonic() if now is None else now
    with _lock:
        hits = _hits[key]
        while hits and hits[0] <= now - window:
            hits.popleft()
        if len(hits) >= limit:
            return hits[0] + window - now
        hits.append(now)
        return 0.0


def reset() -> None:
    with _lock:
        _hits.clear()


def limited(action: str, limit: int, window: float = 600.0) -> Callable[..., CurrentUser]:
    """A dependency: at most `limit` calls of `action` per user per `window` seconds."""

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:  # noqa: B008
        wait = check((str(user.id), action), limit, window)
        if wait > 0:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Too many {action} requests; try again in {int(wait) + 1} s",
                headers={"Retry-After": str(int(wait) + 1)},
            )
        return user

    return dependency

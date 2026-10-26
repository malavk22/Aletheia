"""Rate limits: how often one sign-in address or one user may do something.

Kept in memory, in this process: simple, and enough for one server. With
several server processes each would count on its own, and a restart forgets
the counts; a shared store (such as Redis) would fix both, when needed.
"""

import math
import time
from collections import deque
from threading import Lock

# Past this many keys, idle ones are forgotten before counting another.
MAX_KEYS = 10_000


class RateLimiter:
    """At most `limit` events per key in any `window` seconds (a sliding
    window: each event is forgotten `window` seconds after it happened)."""

    def __init__(self, limit: int, window: float, clock=time.monotonic):
        self.limit = limit
        self.window = window
        self.clock = clock
        self.events: dict[str, deque[float]] = {}
        # Sync routes run in a thread pool: two requests can count at once.
        self.lock = Lock()

    def retry_after(self, key: str) -> int | None:
        """Seconds until `key` may act again, or None if it may now."""
        with self.lock:
            events = self._recent(key)
            if len(events) < self.limit:
                if not events:
                    # Forget idle keys, so the dictionary doesn't grow forever.
                    del self.events[key]
                return None
            return max(1, math.ceil(events[0] + self.window - self.clock()))

    def record(self, key: str) -> None:
        with self.lock:
            self._recent(key).append(self.clock())

    def hit(self, key: str) -> int | None:
        """Counts an event for `key` if it is allowed; otherwise returns the
        seconds to wait and counts nothing."""
        with self.lock:
            events = self._recent(key)
            if len(events) >= self.limit:
                return max(1, math.ceil(events[0] + self.window - self.clock()))
            events.append(self.clock())
            return None

    def reset(self) -> None:
        with self.lock:
            self.events.clear()

    def _recent(self, key: str) -> deque[float]:
        """The key's events of the last `window` seconds, oldest first."""
        if len(self.events) > MAX_KEYS:
            self._forget_idle_keys()
        events = self.events.setdefault(key, deque())
        while events and events[0] <= self.clock() - self.window:
            events.popleft()
        return events

    def _forget_idle_keys(self) -> None:
        # Keys whose events are all older than the window. Without this,
        # requests from many different addresses would fill memory.
        cutoff = self.clock() - self.window
        for key in [key for key, events in self.events.items() if not events or events[-1] <= cutoff]:
            del self.events[key]


# Failed sign-ins per address: slows down password guessing.
failed_logins = RateLimiter(limit=5, window=15 * 60)
# New accounts per address: slows down mass sign-ups and checking which
# emails have an account.
registrations = RateLimiter(limit=10, window=60 * 60)
# AI requests (Ask, Key facts, Actions, Conflicts) per user: one person can't
# use up the shared Gemini quota.
ai_requests = RateLimiter(limit=10, window=60)

ALL = [failed_logins, registrations, ai_requests]

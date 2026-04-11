"""In-memory per-user rate limiting for the chat endpoint."""

import time
from uuid import UUID

from src.domain.exceptions import RateLimitExceededError


class InMemoryRateLimiter:
    """Fixed-window counter. Resets on server restart — acceptable for 2 users."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._counters: dict[UUID, tuple[float, int]] = {}

    def check(self, person_id: UUID) -> None:
        now = time.monotonic()
        entry = self._counters.get(person_id)
        if entry is None or now - entry[0] >= self._window:
            self._counters[person_id] = (now, 1)
            return
        window_start, count = entry
        if count >= self._max:
            raise RateLimitExceededError(
                f"Rate limit exceeded — max {self._max} requests per {self._window}s"
            )
        self._counters[person_id] = (window_start, count + 1)

    def reset(self) -> None:
        self._counters.clear()

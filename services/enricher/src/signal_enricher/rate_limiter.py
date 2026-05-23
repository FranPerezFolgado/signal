import threading
import time


class RateLimiter:
    """Token bucket with continuous refill at capacity/30 tokens per second."""

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._tokens = float(capacity)
        self._refill_rate = capacity / 30.0
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    def acquire(self) -> None:
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._refill_rate
            time.sleep(wait)

import threading
import time
from enum import Enum


class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    CLOSED  → failures >= threshold → OPEN
    OPEN    → timeout elapsed → HALF_OPEN
    HALF_OPEN → success → CLOSED; failure → OPEN
    """

    def __init__(self, failure_threshold: int, timeout_s: float) -> None:
        self._threshold = failure_threshold
        self._timeout = timeout_s
        self._state = State.CLOSED
        self._failure_count = 0
        self._opened_at: float = 0.0
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            if self._state == State.OPEN:
                if time.monotonic() - self._opened_at >= self._timeout:
                    self._state = State.HALF_OPEN
                    return False
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = State.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._state == State.HALF_OPEN or self._failure_count >= self._threshold:
                self._state = State.OPEN
                self._opened_at = time.monotonic()
                self._failure_count = 0

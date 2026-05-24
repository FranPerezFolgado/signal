import threading
import time
from enum import Enum

from signal_common.logger import get_logger


class CircuitOpenError(RuntimeError):
    """Raised when the circuit is open and the operation must not proceed."""
    pass

_log = get_logger(__name__)


class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    CLOSED    → failures >= threshold → OPEN
    OPEN      → timeout elapsed → HALF_OPEN (via should_allow)
    HALF_OPEN → success → CLOSED; failure → OPEN
    """

    def __init__(self, failure_threshold: int, timeout_s: float) -> None:
        self._threshold = failure_threshold
        self._timeout = timeout_s
        self._state = State.CLOSED
        self._failure_count = 0
        self._opened_at: float = 0.0
        self._lock = threading.Lock()

    def should_allow(self) -> bool:
        """Returns True if a request should proceed.
        Atomically transitions OPEN→HALF_OPEN when the timeout has elapsed."""
        with self._lock:
            if self._state == State.CLOSED:
                return True
            if self._state == State.HALF_OPEN:
                return True
            # OPEN — allow probe once timeout elapses
            if time.monotonic() - self._opened_at >= self._timeout:
                self._state = State.HALF_OPEN
                _log.info("circuit_half_open")
                return True
            return False

    @property
    def is_open(self) -> bool:
        """Pure read. True only when the circuit is actively blocking requests."""
        with self._lock:
            if self._state == State.OPEN:
                return time.monotonic() - self._opened_at < self._timeout
            return False

    def record_success(self) -> None:
        with self._lock:
            prev = self._state
            self._failure_count = 0
            self._state = State.CLOSED
            if prev != State.CLOSED:
                _log.info("circuit_closed")

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._state == State.HALF_OPEN or self._failure_count >= self._threshold:
                self._state = State.OPEN
                self._opened_at = time.monotonic()
                self._failure_count = 0
                _log.warning("circuit_open", threshold=self._threshold)

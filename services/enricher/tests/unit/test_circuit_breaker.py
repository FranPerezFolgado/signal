import time

from signal_enricher.circuit_breaker import CircuitBreaker, State


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(failure_threshold=3, timeout_s=60.0)
        assert not cb.is_open

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=3, timeout_s=60.0)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open

    def test_does_not_open_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, timeout_s=60.0)
        cb.record_failure()
        cb.record_failure()
        assert not cb.is_open

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3, timeout_s=60.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        assert not cb.is_open

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, timeout_s=0.01)
        cb.record_failure()
        assert cb.is_open
        time.sleep(0.02)
        assert not cb.is_open  # HALF_OPEN → returns False from is_open

    def test_success_in_half_open_closes(self):
        cb = CircuitBreaker(failure_threshold=1, timeout_s=0.01)
        cb.record_failure()
        time.sleep(0.02)
        _ = cb.is_open  # transitions to HALF_OPEN
        cb.record_success()
        assert cb._state == State.CLOSED

    def test_failure_in_half_open_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, timeout_s=0.01)
        cb.record_failure()
        time.sleep(0.02)
        _ = cb.is_open  # transitions to HALF_OPEN
        cb.record_failure()
        assert cb.is_open

import time
from unittest.mock import patch

from signal_enricher.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_acquire_consumes_token(self):
        rl = RateLimiter(capacity=10)
        before = rl._tokens
        rl.acquire()
        assert rl._tokens == before - 1.0

    def test_refill_adds_tokens_over_time(self):
        rl = RateLimiter(capacity=10)
        rl._tokens = 0.0
        rl._last_refill = time.monotonic() - 5.0  # 5s elapsed at 10/30 tok/s = ~1.67 tokens
        rl._refill()
        assert rl._tokens > 1.0

    def test_refill_does_not_exceed_capacity(self):
        rl = RateLimiter(capacity=10)
        rl._last_refill = time.monotonic() - 9999.0
        rl._refill()
        assert rl._tokens == 10

    def test_acquire_sleeps_when_empty(self):
        rl = RateLimiter(capacity=10)
        rl._tokens = 0.0
        slept = []
        original_sleep = time.sleep

        def fake_sleep(s):
            slept.append(s)
            rl._tokens = 1.0  # unblock on first sleep

        with patch("signal_enricher.rate_limiter.time.sleep", side_effect=fake_sleep):
            rl.acquire()

        assert len(slept) == 1
        assert slept[0] > 0

    def test_capacity_set_correctly(self):
        rl = RateLimiter(capacity=180)
        assert rl._capacity == 180
        assert rl._refill_rate == 6.0  # 180/30

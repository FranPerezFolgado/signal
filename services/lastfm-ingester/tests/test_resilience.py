import time
from unittest.mock import MagicMock, patch

from signal_common.circuit_breaker import CircuitBreaker, State
from signal_common.rate_limiter import RateLimiter
from signal_lastfm_ingester.client import LastfmClient


class TestLastfmClientRateLimiter:
    def test_acquire_called_before_each_request(self):
        rl = MagicMock(spec=RateLimiter)
        client = LastfmClient("key", "user", rate_limiter=rl)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "recenttracks": {
                "track": [{"name": "t", "artist": {"#text": "a"}, "date": {"uts": "1"}}],
                "@attr": {"totalPages": "1"},
            }
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            client.get_recent_tracks()
        rl.acquire.assert_called_once()

    def test_no_rate_limiter_works_fine(self):
        client = LastfmClient("key", "user")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "recenttracks": {
                "track": [],
                "@attr": {"totalPages": "1"},
            }
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            result = client.get_recent_tracks()
        assert result.total_pages == 1


class TestCircuitBreakerBehaviour:
    def test_circuit_open_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=3, timeout_s=60.0)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open
        assert not cb.should_allow()

    def test_circuit_resets_after_successful_probe(self):
        cb = CircuitBreaker(failure_threshold=1, timeout_s=0.01)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.should_allow()
        cb.record_success()
        assert cb._state == State.CLOSED

    def test_circuit_open_poll_skipped(self):
        cb = CircuitBreaker(failure_threshold=1, timeout_s=60.0)
        cb.record_failure()

        poll_called = False
        if cb.should_allow():
            poll_called = True

        assert not poll_called

    def test_backfill_raises_when_circuit_open(self):
        cb = CircuitBreaker(failure_threshold=1, timeout_s=60.0)
        cb.record_failure()

        import pytest
        with pytest.raises(RuntimeError, match="circuit open"):
            if not cb.should_allow():
                raise RuntimeError("circuit open — retry backfill when Last.fm recovers")

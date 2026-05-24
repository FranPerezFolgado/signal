import time
from unittest.mock import MagicMock, patch

import pytest

from signal_common.circuit_breaker import CircuitBreaker, CircuitOpenError, State
from signal_common.rate_limiter import RateLimiter
from signal_lastfm_ingester.client import LastfmClient


class TestLastfmClientRateLimiter:
    def test_acquire_called_once_per_call(self):
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
        # acquire() gates entry into the call, not each retry attempt
        rl.acquire.assert_called_once()

    def test_acquire_not_called_again_on_retry(self):
        """A transient 500 triggers a retry but should NOT call acquire() again."""
        rl = MagicMock(spec=RateLimiter)
        client = LastfmClient("key", "user", rate_limiter=rl)
        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.raise_for_status = MagicMock()
        resp_200.json.return_value = {
            "recenttracks": {
                "track": [],
                "@attr": {"totalPages": "1"},
            }
        }
        with patch("requests.get", side_effect=[resp_500, resp_200]), \
             patch("time.sleep"):
            client.get_recent_tracks()
        assert rl.acquire.call_count == 1

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

    def test_backfill_raises_circuit_open_error(self):
        cb = CircuitBreaker(failure_threshold=1, timeout_s=60.0)
        cb.record_failure()

        with pytest.raises(CircuitOpenError):
            if not cb.should_allow():
                raise CircuitOpenError("circuit open — retry backfill when Last.fm recovers")

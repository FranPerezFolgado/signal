from unittest.mock import MagicMock, patch

import pytest
from signal_common.rate_limiter import RateLimiter
from signal_common.spotify import SpotifyServiceError
from signal_normalizer.spotify_client import SpotifyClient


@pytest.fixture
def client():
    return SpotifyClient("client_id", "client_secret", "refresh_token", timeout=2.0)


@pytest.fixture
def client_with_limiter():
    rl = MagicMock(spec=RateLimiter)
    return SpotifyClient(
        "client_id", "client_secret", "refresh_token",
        timeout=2.0, rate_limiter=rl,
        retry_after_default=5.0, retry_after_max=60.0,
    ), rl


def _mock_token(client):
    client._access_token = "test_token"


class TestSearchTrack:
    def test_returns_uri_formatted_ids_on_success(self, client):
        _mock_token(client)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tracks": {
                "items": [
                    {
                        "id": "track123",
                        "artists": [{"id": "artist456", "name": "Actress"}],
                    }
                ]
            }
        }
        with patch("requests.get", return_value=mock_resp):
            artist_id, track_id = client.search_track("Actress", "Ascending")

        assert artist_id == "spotify:artist:artist456"
        assert track_id == "spotify:track:track123"

    def test_returns_none_none_on_empty_results(self, client):
        _mock_token(client)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"tracks": {"items": []}}
        with patch("requests.get", return_value=mock_resp):
            artist_id, track_id = client.search_track("Unknown", "Track")

        assert artist_id is None
        assert track_id is None

    def test_raises_on_timeout(self, client):
        import requests as req
        _mock_token(client)
        with (
            patch("requests.get", side_effect=req.Timeout),
            pytest.raises(SpotifyServiceError),
        ):
            client.search_track("Actress", "Ascending")

    def test_raises_on_non_200(self, client):
        _mock_token(client)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.headers = {}
        with (
            patch("requests.get", return_value=mock_resp),
            pytest.raises(SpotifyServiceError),
        ):
            client.search_track("Actress", "Ascending")

    def test_refreshes_token_on_401_then_retries(self, client):
        client._access_token = "expired_token"
        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "tracks": {"items": [{"id": "t1", "artists": [{"id": "a1", "name": "X"}]}]}
        }
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {"access_token": "new_token"}

        with patch("requests.get", side_effect=[resp_401, resp_200]), \
             patch("requests.post", return_value=token_resp):
            artist_id, track_id = client.search_track("X", "Y")

        assert artist_id == "spotify:artist:a1"
        assert track_id == "spotify:track:t1"

    def test_single_attempt_on_timeout(self, client):
        import requests as req
        _mock_token(client)
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise req.Timeout

        with (
            patch("requests.get", side_effect=side_effect),
            pytest.raises(SpotifyServiceError),
        ):
            client.search_track("Actress", "Ascending")

        assert call_count == 1


class TestRateLimiter:
    def test_acquire_called_before_request(self, client_with_limiter):
        client, rl = client_with_limiter
        _mock_token(client)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"tracks": {"items": []}}
        with patch("requests.get", return_value=mock_resp):
            client.search_track("X", "Y")
        rl.acquire.assert_called_once()


class TestRetryAfter:
    def test_429_with_header_sleeps_and_retries(self, client_with_limiter):
        client, rl = client_with_limiter
        _mock_token(client)
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "2"}
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "tracks": {"items": [{"id": "t1", "artists": [{"id": "a1", "name": "X"}]}]}
        }
        with patch("requests.get", side_effect=[resp_429, resp_200]), \
             patch("time.sleep") as mock_sleep:
            artist_id, track_id = client.search_track("X", "Y")
        mock_sleep.assert_called_once_with(2.0)
        assert artist_id == "spotify:artist:a1"
        # acquire() called: initial request + after-429 retry = 2
        assert rl.acquire.call_count == 2

    def test_429_without_header_uses_default(self, client_with_limiter):
        client, rl = client_with_limiter
        _mock_token(client)
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {}
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"tracks": {"items": []}}
        with patch("requests.get", side_effect=[resp_429, resp_200]), \
             patch("time.sleep") as mock_sleep:
            client.search_track("X", "Y")
        mock_sleep.assert_called_once_with(5.0)

    def test_429_header_capped_at_max(self, client_with_limiter):
        client, rl = client_with_limiter
        _mock_token(client)
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "9999"}
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"tracks": {"items": []}}
        with patch("requests.get", side_effect=[resp_429, resp_200]), \
             patch("time.sleep") as mock_sleep:
            client.search_track("X", "Y")
        mock_sleep.assert_called_once_with(60.0)

    def test_429_header_zero_does_not_sleep_negative(self, client_with_limiter):
        client, rl = client_with_limiter
        _mock_token(client)
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "0"}
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"tracks": {"items": []}}
        with patch("requests.get", side_effect=[resp_429, resp_200]), \
             patch("time.sleep") as mock_sleep:
            client.search_track("X", "Y")
        mock_sleep.assert_called_once_with(0.0)

    def test_429_non_numeric_header_uses_default(self, client_with_limiter):
        client, rl = client_with_limiter
        _mock_token(client)
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "invalid"}
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"tracks": {"items": []}}
        with patch("requests.get", side_effect=[resp_429, resp_200]), \
             patch("time.sleep") as mock_sleep:
            client.search_track("X", "Y")
        mock_sleep.assert_called_once_with(5.0)

    def test_429_retry_also_fails_raises(self, client_with_limiter):
        client, rl = client_with_limiter
        _mock_token(client)
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "1"}
        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_500.headers = {}
        with patch("requests.get", side_effect=[resp_429, resp_500]), \
             patch("time.sleep"), pytest.raises(SpotifyServiceError):
            client.search_track("X", "Y")

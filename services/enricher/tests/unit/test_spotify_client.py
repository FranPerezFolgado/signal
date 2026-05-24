from unittest.mock import MagicMock, patch

import pytest

from signal_common.rate_limiter import RateLimiter
from signal_common.spotify import SpotifyServiceError
from signal_enricher.spotify_client import EnricherSpotifyClient


@pytest.fixture
def client():
    return EnricherSpotifyClient("cid", "csecret", "rtoken", timeout=2.0)


@pytest.fixture
def client_with_limiter():
    rl = MagicMock(spec=RateLimiter)
    return EnricherSpotifyClient(
        "cid", "csecret", "rtoken",
        timeout=2.0, rate_limiter=rl,
        retry_after_default=5.0, retry_after_max=60.0,
    ), rl


def _mock_token(client):
    client._access_token = "test_token"


class TestGetArtistData:
    def test_returns_genres_and_popularity(self, client):
        _mock_token(client)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "genres": ["electronic", "ambient"],
            "popularity": 42,
            "followers": {"total": 12345},
        }
        with patch("requests.get", return_value=mock_resp):
            result = client.get_artist_data("spotify:artist:abc1234567890ABCDE")

        assert result["genres"] == ["electronic", "ambient"]
        assert result["artist_popularity"] == 42
        assert result["followers"] == 12345

    def test_strips_uri_prefix_before_api_call(self, client):
        _mock_token(client)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"genres": [], "popularity": 0, "followers": {"total": 0}}
        with patch("requests.get", return_value=mock_resp) as mock_get:
            client.get_artist_data("spotify:artist:abc1234567890ABCDE")

        called_url = mock_get.call_args[0][0]
        assert "abc1234567890ABCDE" in called_url
        assert "spotify:artist:" not in called_url

    def test_raises_on_non_200(self, client):
        _mock_token(client)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.headers = {}
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(SpotifyServiceError):
                client.get_artist_data("spotify:artist:abc1234567890ABCDE")

    def test_returns_none_for_none_uri(self, client):
        assert client.get_artist_data(None) is None

    def test_raises_on_timeout(self, client):
        import requests as req
        _mock_token(client)
        with patch("requests.get", side_effect=req.Timeout):
            with pytest.raises(SpotifyServiceError):
                client.get_artist_data("spotify:artist:abc1234567890ABCDE")


class TestGetTrackData:
    def test_returns_track_popularity(self, client):
        _mock_token(client)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"popularity": 55, "duration_ms": 300000}
        with patch("requests.get", return_value=mock_resp):
            result = client.get_track_data("spotify:track:track1234567890ABCDE")

        assert result["track_popularity"] == 55
        assert result["duration_ms"] == 300000

    def test_raises_on_timeout(self, client):
        import requests as req
        _mock_token(client)
        with patch("requests.get", side_effect=req.Timeout):
            with pytest.raises(SpotifyServiceError):
                client.get_track_data("spotify:track:track1234567890ABCDE")


class TestStripUriPrefix:
    def test_rejects_missing_prefix(self, client):
        assert client._strip_uri_prefix("abc123456789012345678901", "artist") is None

    def test_rejects_wrong_kind(self, client):
        assert client._strip_uri_prefix("spotify:track:abc123456789012345678901", "artist") is None

    def test_rejects_id_too_short(self, client):
        assert client._strip_uri_prefix("spotify:artist:short", "artist") is None

    def test_rejects_id_with_path_traversal(self, client):
        assert client._strip_uri_prefix("spotify:artist:../etc/passwd/AAAAAA", "artist") is None

    def test_accepts_valid_uri(self, client):
        raw = client._strip_uri_prefix("spotify:artist:abc1234567890ABCDE", "artist")
        assert raw == "abc1234567890ABCDE"


class TestRetryAfter:
    def test_429_with_header_sleeps_and_retries(self, client_with_limiter):
        client, rl = client_with_limiter
        _mock_token(client)
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "3"}
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"genres": [], "popularity": 0, "followers": {"total": 0}}
        with patch("requests.get", side_effect=[resp_429, resp_200]), \
             patch("time.sleep") as mock_sleep:
            client.get_artist_data("spotify:artist:abc1234567890ABCDE")
        mock_sleep.assert_called_once_with(3.0)
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
        resp_200.json.return_value = {"genres": [], "popularity": 0, "followers": {"total": 0}}
        with patch("requests.get", side_effect=[resp_429, resp_200]), \
             patch("time.sleep") as mock_sleep:
            client.get_artist_data("spotify:artist:abc1234567890ABCDE")
        mock_sleep.assert_called_once_with(5.0)

    def test_429_header_capped_at_max(self, client_with_limiter):
        client, rl = client_with_limiter
        _mock_token(client)
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "9999"}
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"genres": [], "popularity": 0, "followers": {"total": 0}}
        with patch("requests.get", side_effect=[resp_429, resp_200]), \
             patch("time.sleep") as mock_sleep:
            client.get_artist_data("spotify:artist:abc1234567890ABCDE")
        mock_sleep.assert_called_once_with(60.0)

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
             patch("time.sleep"):
            with pytest.raises(SpotifyServiceError):
                client.get_artist_data("spotify:artist:abc1234567890ABCDE")

    def test_rate_limiter_acquire_called_before_request(self, client_with_limiter):
        client, rl = client_with_limiter
        _mock_token(client)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"genres": [], "popularity": 0, "followers": {"total": 0}}
        with patch("requests.get", return_value=mock_resp):
            client.get_artist_data("spotify:artist:abc1234567890ABCDE")
        rl.acquire.assert_called_once()

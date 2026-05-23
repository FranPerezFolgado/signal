from unittest.mock import MagicMock, patch

import pytest

from signal_enricher.spotify_client import EnricherSpotifyClient, SpotifyAuthError


@pytest.fixture
def client():
    return EnricherSpotifyClient("cid", "csecret", "rtoken", timeout=2.0)


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
            result = client.get_artist_data("spotify:artist:abc123")

        assert result["genres"] == ["electronic", "ambient"]
        assert result["artist_popularity"] == 42
        assert result["followers"] == 12345

    def test_strips_uri_prefix_before_api_call(self, client):
        _mock_token(client)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"genres": [], "popularity": 0, "followers": {"total": 0}}
        with patch("requests.get", return_value=mock_resp) as mock_get:
            client.get_artist_data("spotify:artist:abc123")

        called_url = mock_get.call_args[0][0]
        assert "abc123" in called_url
        assert "spotify:artist:" not in called_url

    def test_returns_none_on_failure(self, client):
        _mock_token(client)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("requests.get", return_value=mock_resp):
            result = client.get_artist_data("spotify:artist:abc123")

        assert result is None

    def test_returns_none_for_none_uri(self, client):
        assert client.get_artist_data(None) is None


class TestGetTrackData:
    def test_returns_track_popularity(self, client):
        _mock_token(client)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"popularity": 55, "duration_ms": 300000}
        with patch("requests.get", return_value=mock_resp):
            result = client.get_track_data("spotify:track:t1")

        assert result["track_popularity"] == 55
        assert result["duration_ms"] == 300000

    def test_returns_none_on_timeout(self, client):
        import requests as req
        _mock_token(client)
        with patch("requests.get", side_effect=req.Timeout):
            result = client.get_track_data("spotify:track:t1")

        assert result is None

from unittest.mock import MagicMock, patch

import pytest

from signal_normalizer.spotify_client import (
    AudioFeatures,
    SpotifyAuthError,
    SpotifyClient,
    SpotifyTrack,
)


def _make_client(max_retries: int = 3, token: str = "token") -> SpotifyClient:
    """Build a SpotifyClient bypassing __init__ — token defaults to pre-populated."""
    client = SpotifyClient.__new__(SpotifyClient)
    client._client_id = "id"
    client._client_secret = "secret"
    client._refresh_token = "refresh"
    client._max_retries = max_retries
    client._access_token = token
    return client


def _mock_response(status: int, json_data: dict | None = None, headers: dict | None = None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or {}
    resp.headers = headers or {}
    return resp


class TestLazyTokenInit:
    def test_no_token_fetches_on_first_get(self) -> None:
        client = _make_client(token="")
        with patch("signal_normalizer.spotify_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response(200, {"access_token": "lazy_token"})
            with patch("signal_normalizer.spotify_client.requests.get") as mock_get:
                mock_get.return_value = _mock_response(200, {"ok": True})
                result = client._get("https://api.spotify.com/v1/test")
        mock_post.assert_called_once()
        assert result == {"ok": True}

    def test_no_token_auth_failure_returns_none(self) -> None:
        client = _make_client(token="")
        with patch("signal_normalizer.spotify_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response(500)
            result = client._get("https://api.spotify.com/v1/test")
        assert result is None

    def test_with_token_skips_refresh(self) -> None:
        client = _make_client(token="existing")
        with patch("signal_normalizer.spotify_client.requests.post") as mock_post:
            with patch("signal_normalizer.spotify_client.requests.get") as mock_get:
                mock_get.return_value = _mock_response(200, {"ok": True})
                client._get("https://api.spotify.com/v1/test")
        mock_post.assert_not_called()


class TestRefreshAccessToken:
    def test_success(self) -> None:
        client = _make_client()
        with patch("signal_normalizer.spotify_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response(200, {"access_token": "new_token"})
            client._refresh_access_token()
        assert client._access_token == "new_token"

    def test_failure_raises_auth_error(self) -> None:
        client = _make_client()
        with patch("signal_normalizer.spotify_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response(401)
            with pytest.raises(SpotifyAuthError) as exc_info:
                client._refresh_access_token()
        assert "401" in str(exc_info.value)
        assert "secret" not in str(exc_info.value)


class TestGet:
    def test_200_returns_json(self) -> None:
        client = _make_client()
        payload = {"foo": "bar"}
        with patch("signal_normalizer.spotify_client.requests.get") as mock_get:
            mock_get.return_value = _mock_response(200, payload)
            result = client._get("https://api.spotify.com/v1/test")
        assert result == payload

    def test_404_returns_none(self) -> None:
        client = _make_client()
        with patch("signal_normalizer.spotify_client.requests.get") as mock_get:
            mock_get.return_value = _mock_response(404)
            result = client._get("https://api.spotify.com/v1/test")
        assert result is None

    def test_429_retries_then_gives_up(self) -> None:
        client = _make_client(max_retries=2)
        with patch("signal_normalizer.spotify_client.requests.get") as mock_get:
            with patch("signal_normalizer.spotify_client.time.sleep"):
                mock_get.return_value = _mock_response(429, headers={"Retry-After": "1"})
                result = client._get("https://api.spotify.com/v1/test")
        assert result is None
        assert mock_get.call_count == 3  # initial + 2 retries

    def test_429_succeeds_after_retry(self) -> None:
        client = _make_client(max_retries=2)
        with patch("signal_normalizer.spotify_client.requests.get") as mock_get:
            with patch("signal_normalizer.spotify_client.time.sleep"):
                mock_get.side_effect = [
                    _mock_response(429, headers={"Retry-After": "1"}),
                    _mock_response(200, {"ok": True}),
                ]
                result = client._get("https://api.spotify.com/v1/test")
        assert result == {"ok": True}

    def test_429_retry_after_clamped(self) -> None:
        client = _make_client(max_retries=1)
        with patch("signal_normalizer.spotify_client.requests.get") as mock_get:
            with patch("signal_normalizer.spotify_client.time.sleep") as mock_sleep:
                mock_get.return_value = _mock_response(
                    429, headers={"Retry-After": "9999"}
                )
                client._get("https://api.spotify.com/v1/test")
        # Should be clamped to _MAX_RETRY_AFTER_SECONDS + small jitter, not 9999
        assert mock_sleep.call_count >= 1
        slept = mock_sleep.call_args_list[0][0][0]
        assert slept <= 61  # 60s clamp + tiny jitter

    def test_429_non_integer_retry_after(self) -> None:
        client = _make_client(max_retries=1)
        with patch("signal_normalizer.spotify_client.requests.get") as mock_get:
            with patch("signal_normalizer.spotify_client.time.sleep"):
                mock_get.return_value = _mock_response(
                    429, headers={"Retry-After": "not-a-number"}
                )
                result = client._get("https://api.spotify.com/v1/test")
        assert result is None  # should not raise, just fallback to default

    def test_500_retries_then_gives_up(self) -> None:
        client = _make_client(max_retries=2)
        with patch("signal_normalizer.spotify_client.requests.get") as mock_get:
            with patch("signal_normalizer.spotify_client.time.sleep"):
                mock_get.return_value = _mock_response(500)
                result = client._get("https://api.spotify.com/v1/test")
        assert result is None
        assert mock_get.call_count == 3

    def test_401_refreshes_token_once(self) -> None:
        client = _make_client()
        with patch("signal_normalizer.spotify_client.requests.get") as mock_get:
            with patch.object(client, "_refresh_access_token") as mock_refresh:
                mock_get.side_effect = [
                    _mock_response(401),
                    _mock_response(200, {"data": 1}),
                ]
                result = client._get("https://api.spotify.com/v1/test")
        mock_refresh.assert_called_once()
        assert result == {"data": 1}

    def test_double_401_returns_none(self) -> None:
        """After one token refresh, a second 401 returns None (not raises)."""
        client = _make_client()
        with patch("signal_normalizer.spotify_client.requests.get") as mock_get:
            with patch.object(client, "_refresh_access_token"):
                mock_get.return_value = _mock_response(401)
                result = client._get("https://api.spotify.com/v1/test")
        assert result is None

    def test_401_after_429_retries_refreshes_token(self) -> None:
        """401 on attempt > 0 (after 429 retries) must still refresh once."""
        client = _make_client(max_retries=3)
        with patch("signal_normalizer.spotify_client.requests.get") as mock_get:
            with patch("signal_normalizer.spotify_client.time.sleep"):
                with patch.object(client, "_refresh_access_token") as mock_refresh:
                    mock_get.side_effect = [
                        _mock_response(429, headers={"Retry-After": "0"}),
                        _mock_response(401),
                        _mock_response(200, {"data": 1}),
                    ]
                    result = client._get("https://api.spotify.com/v1/test")
        mock_refresh.assert_called_once()
        assert result == {"data": 1}


class TestSearchTrack:
    def _spotify_search_response(self) -> dict:
        return {
            "tracks": {
                "items": [
                    {
                        "id": "track123",
                        "popularity": 42,
                        "artists": [{"id": "artist456", "name": "Actress"}],
                    }
                ]
            }
        }

    def test_returns_track_on_success(self) -> None:
        client = _make_client()
        with patch.object(client, "_get") as mock_get:
            with patch.object(client, "_get_artist_genres", return_value=["electronic"]):
                mock_get.return_value = self._spotify_search_response()
                result = client.search_track("Actress", "Ascending")
        assert isinstance(result, SpotifyTrack)
        assert result.track_id == "track123"
        assert result.artist_id == "artist456"
        assert result.genres == ["electronic"]
        assert result.popularity == 42

    def test_returns_none_when_no_items(self) -> None:
        client = _make_client()
        with patch.object(client, "_get") as mock_get:
            mock_get.return_value = {"tracks": {"items": []}}
            result = client.search_track("Unknown", "Track")
        assert result is None

    def test_returns_none_when_get_fails(self) -> None:
        client = _make_client()
        with patch.object(client, "_get", return_value=None):
            result = client.search_track("Artist", "Title")
        assert result is None

    def test_returns_none_when_missing_artist_id(self) -> None:
        client = _make_client()
        with patch.object(client, "_get") as mock_get:
            mock_get.return_value = {
                "tracks": {"items": [{"id": "t1", "popularity": 10, "artists": [{"name": "X"}]}]}
            }
            result = client.search_track("X", "Y")
        assert result is None

    def test_returns_none_when_artists_array_empty(self) -> None:
        client = _make_client()
        with patch.object(client, "_get") as mock_get:
            mock_get.return_value = {
                "tracks": {"items": [{"id": "t1", "popularity": 10, "artists": []}]}
            }
            result = client.search_track("X", "Y")
        assert result is None


class TestGetArtistGenres:
    def test_returns_genres_on_success(self) -> None:
        client = _make_client()
        with patch.object(client, "_get", return_value={"genres": ["techno", "ambient"]}):
            result = client._get_artist_genres("artist123")
        assert result == ["techno", "ambient"]

    def test_returns_empty_on_missing_genres_key(self) -> None:
        client = _make_client()
        with patch.object(client, "_get", return_value={"name": "Actress"}):
            result = client._get_artist_genres("artist123")
        assert result == []

    def test_returns_empty_when_get_fails(self) -> None:
        client = _make_client()
        with patch.object(client, "_get", return_value=None):
            result = client._get_artist_genres("artist123")
        assert result == []


class TestGetAudioFeatures:
    def test_returns_features_on_success(self) -> None:
        client = _make_client()
        data = {
            "energy": 0.3, "valence": 0.2, "tempo": 95.0,
            "danceability": 0.4, "acousticness": 0.1, "instrumentalness": 0.8,
        }
        with patch.object(client, "_get", return_value=data):
            result = client.get_audio_features("track123")
        assert isinstance(result, AudioFeatures)
        assert result.energy == 0.3

    def test_returns_none_on_missing_key(self) -> None:
        client = _make_client()
        with patch.object(client, "_get", return_value={"energy": 0.3}):
            result = client.get_audio_features("track123")
        assert result is None

    def test_returns_none_when_get_fails(self) -> None:
        client = _make_client()
        with patch.object(client, "_get", return_value=None):
            result = client.get_audio_features("track123")
        assert result is None

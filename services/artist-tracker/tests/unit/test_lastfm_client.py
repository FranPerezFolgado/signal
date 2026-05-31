from unittest.mock import MagicMock, patch

import requests
from signal_artist_tracker.lastfm_client import LastfmSimilarClient, SimilarArtist


def _make_client():
    rate_limiter = MagicMock()
    return LastfmSimilarClient(api_key="test_key", rate_limiter=rate_limiter), rate_limiter


def _make_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


def _similar_payload(artists):
    return {"similarartists": {"artist": artists}}


class TestGetSimilar:
    def test_success_two_artists_one_with_mbid(self):
        client, _ = _make_client()
        payload = _similar_payload([
            {"name": "Burial", "mbid": "abc123", "match": "0.9"},
            {"name": "Actress", "mbid": "", "match": "0.7"},
        ])
        with patch("signal_artist_tracker.lastfm_client.requests.get") as mock_get:
            mock_get.return_value = _make_response(200, payload)
            result = client.get_similar("Burial", limit=10)

        assert len(result) == 2
        assert result[0] == SimilarArtist(name="Burial", mbid="abc123", match_score=0.9)
        assert result[1] == SimilarArtist(name="Actress", mbid=None, match_score=0.7)

    def test_empty_artist_array_returns_empty_list(self):
        client, _ = _make_client()
        payload = _similar_payload([])
        with patch("signal_artist_tracker.lastfm_client.requests.get") as mock_get:
            mock_get.return_value = _make_response(200, payload)
            result = client.get_similar("Unknown", limit=10)

        assert result == []

    def test_http_403_returns_empty_list(self):
        client, _ = _make_client()
        with patch("signal_artist_tracker.lastfm_client.requests.get") as mock_get:
            mock_get.return_value = _make_response(403, {})
            result = client.get_similar("Artist", limit=5)

        assert result == []

    def test_http_429_returns_empty_list(self):
        client, _ = _make_client()
        with patch("signal_artist_tracker.lastfm_client.requests.get") as mock_get:
            mock_get.return_value = _make_response(429, {})
            result = client.get_similar("Artist", limit=5)

        assert result == []

    def test_lastfm_error_code_returns_empty_list(self):
        client, _ = _make_client()
        payload = {"error": 6, "message": "Artist not found"}
        with patch("signal_artist_tracker.lastfm_client.requests.get") as mock_get:
            mock_get.return_value = _make_response(200, payload)
            result = client.get_similar("NoSuchArtist", limit=10)

        assert result == []

    def test_request_exception_returns_empty_list(self):
        client, _ = _make_client()
        with patch("signal_artist_tracker.lastfm_client.requests.get") as mock_get:
            mock_get.side_effect = requests.RequestException("timeout")
            result = client.get_similar("Artist", limit=10)

        assert result == []

    def test_empty_string_mbid_normalised_to_none(self):
        client, _ = _make_client()
        payload = _similar_payload([{"name": "Aphex Twin", "mbid": "", "match": "0.5"}])
        with patch("signal_artist_tracker.lastfm_client.requests.get") as mock_get:
            mock_get.return_value = _make_response(200, payload)
            result = client.get_similar("Squarepusher", limit=10)

        assert result[0].mbid is None

    def test_rate_limiter_acquire_called_before_request(self):
        client, rate_limiter = _make_client()
        call_order = []
        rate_limiter.acquire.side_effect = lambda: call_order.append("acquire")
        def _get_stub(*a, **kw):
            call_order.append("get")
            return _make_response(200, _similar_payload([]))

        with patch("signal_artist_tracker.lastfm_client.requests.get", side_effect=_get_stub):
            client.get_similar("Artist", limit=5)

        assert call_order == ["acquire", "get"]

    def test_artists_missing_name_field_are_filtered(self):
        client, _ = _make_client()
        payload = _similar_payload([
            {"name": "ValidArtist", "mbid": "xyz", "match": "0.8"},
            {"name": "", "mbid": "abc", "match": "0.5"},
        ])
        with patch("signal_artist_tracker.lastfm_client.requests.get") as mock_get:
            mock_get.return_value = _make_response(200, payload)
            result = client.get_similar("Source", limit=10)

        assert len(result) == 1
        assert result[0].name == "ValidArtist"

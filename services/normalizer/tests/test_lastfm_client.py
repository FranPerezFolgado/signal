from unittest.mock import MagicMock, patch

import pytest
import requests as req

from signal_normalizer.lastfm_client import LastfmFallbackClient, _MAX_TAGS


def _make_client() -> LastfmFallbackClient:
    return LastfmFallbackClient(api_key="test_key")


def _mock_response(status: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    return resp


def _tags_response(names: list[str]) -> dict:
    return {"track": {"toptags": {"tag": [{"name": n} for n in names]}}}


class TestGetTags:
    def test_returns_tags_on_success(self) -> None:
        client = _make_client()
        with patch("signal_normalizer.lastfm_client.requests.get") as mock_get:
            mock_get.return_value = _mock_response(200, _tags_response(["electronic", "ambient"]))
            result = client.get_tags("Actress", "Ascending")
        assert result == ["electronic", "ambient"]

    def test_respects_max_tags_limit(self) -> None:
        client = _make_client()
        names = [f"tag{i}" for i in range(_MAX_TAGS + 3)]
        with patch("signal_normalizer.lastfm_client.requests.get") as mock_get:
            mock_get.return_value = _mock_response(200, _tags_response(names))
            result = client.get_tags("Artist", "Track")
        assert len(result) == _MAX_TAGS

    def test_returns_empty_on_non_200(self) -> None:
        client = _make_client()
        with patch("signal_normalizer.lastfm_client.requests.get") as mock_get:
            mock_get.return_value = _mock_response(503, {})
            result = client.get_tags("Artist", "Track")
        assert result == []

    def test_returns_empty_when_track_not_found(self) -> None:
        client = _make_client()
        with patch("signal_normalizer.lastfm_client.requests.get") as mock_get:
            mock_get.return_value = _mock_response(200, {"error": 6, "message": "Track not found"})
            result = client.get_tags("Unknown", "Track")
        assert result == []

    def test_returns_empty_on_request_exception(self) -> None:
        client = _make_client()
        with patch("signal_normalizer.lastfm_client.requests.get") as mock_get:
            mock_get.side_effect = req.ConnectionError("network down")
            result = client.get_tags("Artist", "Track")
        assert result == []

    def test_returns_empty_on_timeout(self) -> None:
        client = _make_client()
        with patch("signal_normalizer.lastfm_client.requests.get") as mock_get:
            mock_get.side_effect = req.Timeout("timeout")
            result = client.get_tags("Artist", "Track")
        assert result == []

    def test_returns_empty_on_malformed_json(self) -> None:
        client = _make_client()
        with patch("signal_normalizer.lastfm_client.requests.get") as mock_get:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.side_effect = ValueError("not json")
            mock_get.return_value = resp
            result = client.get_tags("Artist", "Track")
        assert result == []

    def test_filters_empty_tag_names(self) -> None:
        client = _make_client()
        with patch("signal_normalizer.lastfm_client.requests.get") as mock_get:
            mock_get.return_value = _mock_response(
                200, {"track": {"toptags": {"tag": [{"name": "electronic"}, {"name": ""}]}}}
            )
            result = client.get_tags("Artist", "Track")
        assert result == ["electronic"]

from unittest.mock import MagicMock, patch

import pytest
from signal_enricher.lastfm_client import LastfmFallbackClient


@pytest.fixture
def client():
    return LastfmFallbackClient(api_key="test_key")


class TestGetTags:
    def test_returns_tags_on_success(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "track": {
                "toptags": {
                    "tag": [
                        {"name": "electronic"},
                        {"name": "ambient"},
                        {"name": "drone"},
                    ]
                }
            }
        }
        with patch("requests.get", return_value=mock_resp):
            result = client.get_tags("Actress", "Ascending")

        assert result == ["electronic", "ambient", "drone"]

    def test_caps_at_five_tags(self, client):
        tags = [{"name": f"tag{i}"} for i in range(10)]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"track": {"toptags": {"tag": tags}}}
        with patch("requests.get", return_value=mock_resp):
            result = client.get_tags("Artist", "Title")

        assert len(result) == 5

    def test_returns_empty_on_non_200(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch("requests.get", return_value=mock_resp):
            result = client.get_tags("Artist", "Title")

        assert result == []

    def test_returns_empty_on_lastfm_error_field(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"error": 6, "message": "Track not found"}
        with patch("requests.get", return_value=mock_resp):
            result = client.get_tags("Unknown", "Unknown")

        assert result == []

    def test_returns_empty_on_exception(self, client):
        with patch("requests.get", side_effect=OSError("network error")):
            result = client.get_tags("Artist", "Title")

        assert result == []

    def test_returns_empty_when_no_tags(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"track": {"toptags": {"tag": []}}}
        with patch("requests.get", return_value=mock_resp):
            result = client.get_tags("Artist", "Title")

        assert result == []


class TestGetArtistTags:
    def test_returns_tags_above_min_count(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "toptags": {
                "tag": [
                    {"name": "emo", "count": 100},
                    {"name": "pop punk", "count": 80},
                    {"name": "noise", "count": 5},  # below threshold — excluded
                ]
            }
        }
        with patch("requests.get", return_value=mock_resp):
            result = client.get_artist_tags("Hot Mulligan")

        assert result == ["emo", "pop punk"]

    def test_lowercases_tags(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "toptags": {"tag": [{"name": "Post-Hardcore", "count": 50}]}
        }
        with patch("requests.get", return_value=mock_resp):
            result = client.get_artist_tags("Silverstein")

        assert result == ["post-hardcore"]

    def test_caps_at_five_tags(self, client):
        tags = [{"name": f"tag{i}", "count": 50} for i in range(10)]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"toptags": {"tag": tags}}
        with patch("requests.get", return_value=mock_resp):
            result = client.get_artist_tags("Artist")

        assert len(result) == 5

    def test_returns_empty_on_non_200(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch("requests.get", return_value=mock_resp):
            result = client.get_artist_tags("Artist")

        assert result == []

    def test_returns_empty_on_lastfm_error(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"error": 6, "message": "Artist not found"}
        with patch("requests.get", return_value=mock_resp):
            result = client.get_artist_tags("Unknown")

        assert result == []

    def test_returns_empty_on_exception(self, client):
        with patch("requests.get", side_effect=OSError("network error")):
            result = client.get_artist_tags("Artist")

        assert result == []

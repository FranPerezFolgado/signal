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

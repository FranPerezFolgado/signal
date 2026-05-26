from unittest.mock import patch


def test_excluded_paths_not_logged(client):
    for path in ("/health", "/metrics"):
        with patch("signal_api.app._log") as mock_log:
            client.get(path)
            mock_log.info.assert_not_called()


def test_api_requests_log_request_complete(client):
    with patch("signal_api.routers.recommendations.ArtistRepository") as MockRepo:
        MockRepo.return_value.list_recommendations.return_value = ([], 0)
        with patch("signal_api.app._log") as mock_log:
            resp = client.get("/v1/recommendations")
            assert resp.status_code == 200
            mock_log.info.assert_called_once()
            call_args = mock_log.info.call_args
            assert call_args[0][0] == "request_complete"
            assert call_args[1]["method"] == "GET"
            assert call_args[1]["path"] == "/v1/recommendations"
            assert call_args[1]["status"] == 200
            assert isinstance(call_args[1]["duration_ms"], int)


def test_request_complete_log_not_emitted_for_health(client):
    with patch("signal_api.app._log") as mock_log:
        resp = client.get("/health")
        assert resp.status_code == 200
        mock_log.info.assert_not_called()

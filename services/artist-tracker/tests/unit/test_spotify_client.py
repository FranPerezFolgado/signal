from unittest.mock import patch

import pytest
from signal_artist_tracker.spotify_client import SpotifyClient
from signal_common.spotify import SpotifyServiceError


def _make_client():
    client = SpotifyClient.__new__(SpotifyClient)
    return client


def _make_track_payload(
    name="Ascending", track_id="5CXokd", artist_name="Actress", artist_id="3G3Gdm4"
):
    return {
        "name": name,
        "id": track_id,
        "artists": [{"name": artist_name, "id": artist_id}],
    }


class TestGetTopTracks:
    def test_successful_response_returns_track_dicts(self):
        client = _make_client()
        response = {
            "tracks": [_make_track_payload(), _make_track_payload(name="X", track_id="abc")]
        }

        with patch.object(client, "_get", return_value=response):
            tracks = client.get_top_tracks("spotify:artist:3G3Gdm4vNKHNf3jiRfPVzqt")

        assert len(tracks) == 2
        assert tracks[0]["name"] == "Ascending"
        assert tracks[0]["id"] == "5CXokd"
        assert tracks[0]["artist_name"] == "Actress"
        assert tracks[0]["artist_id"] == "3G3Gdm4"

    def test_empty_tracks_returns_empty_list(self):
        client = _make_client()
        with patch.object(client, "_get", return_value={"tracks": []}):
            tracks = client.get_top_tracks("spotify:artist:3G3Gdm4")

        assert tracks == []

    def test_missing_tracks_key_returns_empty_list(self):
        client = _make_client()
        with patch.object(client, "_get", return_value={}):
            tracks = client.get_top_tracks("spotify:artist:3G3Gdm4")

        assert tracks == []

    def test_spotify_uri_prefix_stripped_before_url_construction(self):
        client = _make_client()
        with patch.object(client, "_get", return_value={"tracks": []}) as mock_get:
            client.get_top_tracks("spotify:artist:ABC123")

        called_url = mock_get.call_args[0][0]
        assert "ABC123" in called_url
        assert "spotify:artist:" not in called_url

    def test_bare_id_also_works(self):
        client = _make_client()
        with patch.object(client, "_get", return_value={"tracks": []}) as mock_get:
            client.get_top_tracks("ABC123")

        called_url = mock_get.call_args[0][0]
        assert "ABC123" in called_url

    def test_spotify_service_error_propagates(self):
        client = _make_client()
        with (
            patch.object(client, "_get", side_effect=SpotifyServiceError("timeout")),
            pytest.raises(SpotifyServiceError),
        ):
            client.get_top_tracks("spotify:artist:3G3Gdm4")

    def test_track_without_artists_is_skipped(self):
        client = _make_client()
        track_no_artists = {"name": "X", "id": "y", "artists": []}
        with patch.object(
            client, "_get", return_value={"tracks": [track_no_artists, _make_track_payload()]}
        ):
            tracks = client.get_top_tracks("spotify:artist:3G3Gdm4")

        assert len(tracks) == 1
        assert tracks[0]["name"] == "Ascending"

    def test_market_param_included(self):
        client = _make_client()
        with patch.object(client, "_get", return_value={"tracks": []}) as mock_get:
            client.get_top_tracks("spotify:artist:3G3Gdm4")

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get("params") == {"market": "from_token"}

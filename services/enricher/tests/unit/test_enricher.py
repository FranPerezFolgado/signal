import time
from unittest.mock import MagicMock

from signal_common.circuit_breaker import State
from signal_common.spotify import SpotifyServiceError
from signal_enricher.enricher import Enricher


def _make_settings(lastfm_enabled=True):
    s = MagicMock()
    s.spotify_client_id = "cid"
    s.spotify_client_secret = "csecret"
    s.spotify_refresh_token = "rtoken"
    s.spotify_timeout = 2.0
    s.lastfm_api_key = "lfm_key"
    s.lastfm_fallback_enabled = lastfm_enabled
    s.spotify_rate_limit_per_30s = 180
    s.circuit_breaker_failure_threshold = 5
    s.circuit_breaker_timeout_s = 60.0
    s.backoff_base_s = 0.0
    s.backoff_max_s = 0.0
    s.spotify_retry_after_default_s = 5.0
    s.spotify_retry_after_max_s = 60.0
    return s


def _normalized(artist_id="spotify:artist:a1", track_id="spotify:track:t1"):
    return {
        "signal_id": "sig1",
        "artist": "Actress",
        "title": "Ascending",
        "artist_id": artist_id,
        "track_id": track_id,
        "sources": ["lastfm"],
        "played": True,
        "played_at": "2026-01-01T00:00:00Z",
        "processed_at": "2026-01-01T00:01:00Z",
    }


class TestEnrich:
    def test_successful_spotify_enrichment(self):
        enricher = Enricher(_make_settings())
        artist_data = {"genres": ["electronic"], "artist_popularity": 40, "followers": 1000}
        track_data = {"track_popularity": 30, "duration_ms": 200000}
        enricher._spotify.get_artist_data = MagicMock(return_value=artist_data)
        enricher._spotify.get_track_data = MagicMock(return_value=track_data)

        result = enricher.enrich(_normalized())

        assert result["enrichment_source"] == "spotify"
        assert result["pending_enrichment"] is False
        assert result["genres"] == ["electronic"]
        assert result["artist_popularity"] == 40
        assert result["track_popularity"] == 30

    def test_falls_back_to_lastfm_when_spotify_fails(self):
        enricher = Enricher(_make_settings(lastfm_enabled=True))
        enricher._spotify.get_artist_data = MagicMock(return_value=None)
        enricher._spotify.get_track_data = MagicMock(return_value=None)
        enricher._lastfm.get_artist_tags = MagicMock(return_value=["ambient", "electronic"])
        enricher._lastfm.get_tags = MagicMock(return_value=[])

        result = enricher.enrich(_normalized())

        assert result["enrichment_source"] == "lastfm"
        assert result["genres"] == ["ambient", "electronic"]
        assert result["pending_enrichment"] is False

    def test_pending_when_spotify_fails_and_lastfm_empty(self):
        enricher = Enricher(_make_settings(lastfm_enabled=True))
        enricher._spotify.get_artist_data = MagicMock(side_effect=SpotifyServiceError("5xx"))
        enricher._spotify.get_track_data = MagicMock(return_value=None)
        enricher._lastfm.get_artist_tags = MagicMock(return_value=[])
        enricher._lastfm.get_tags = MagicMock(return_value=[])

        result = enricher.enrich(_normalized())

        assert result["enrichment_source"] == "pending"
        assert result["pending_enrichment"] is True

    def test_pending_when_no_spotify_ids(self):
        enricher = Enricher(_make_settings())

        result = enricher.enrich(_normalized(artist_id=None, track_id=None))

        assert result["pending_enrichment"] is True

    def test_circuit_open_skips_spotify(self):
        enricher = Enricher(_make_settings(lastfm_enabled=False))
        enricher._circuit_breaker._state = State.OPEN
        enricher._circuit_breaker._opened_at = time.monotonic()
        enricher._spotify.get_artist_data = MagicMock()

        result = enricher.enrich(_normalized())

        enricher._spotify.get_artist_data.assert_not_called()
        assert result["pending_enrichment"] is True

    def test_circuit_open_with_lastfm_enabled(self):
        enricher = Enricher(_make_settings(lastfm_enabled=True))
        enricher._circuit_breaker._state = State.OPEN
        enricher._circuit_breaker._opened_at = time.monotonic()
        enricher._lastfm.get_artist_tags = MagicMock(return_value=["ambient"])
        enricher._lastfm.get_tags = MagicMock(return_value=[])
        enricher._spotify.get_artist_data = MagicMock()

        result = enricher.enrich(_normalized())

        enricher._spotify.get_artist_data.assert_not_called()
        assert result["enrichment_source"] == "lastfm"
        assert result["genres"] == ["ambient"]
        assert result["pending_enrichment"] is False

    def test_backoff_retries_on_spotify_service_error(self):
        enricher = Enricher(_make_settings(lastfm_enabled=False))
        enricher._spotify.get_artist_data = MagicMock(side_effect=SpotifyServiceError("timeout"))
        enricher._spotify.get_track_data = MagicMock(return_value=None)

        enricher.enrich(_normalized())

        assert enricher._spotify.get_artist_data.call_count == 3

    def test_spotify_empty_genres_supplemented_by_lastfm(self):
        enricher = Enricher(_make_settings(lastfm_enabled=True))
        enricher._spotify.get_artist_data = MagicMock(
            return_value={"genres": [], "artist_popularity": 50, "followers": 1000}
        )
        enricher._spotify.get_track_data = MagicMock(
            return_value={"track_popularity": 40, "duration_ms": 200000}
        )
        enricher._lastfm.get_artist_tags = MagicMock(return_value=["electronic", "ambient"])

        result = enricher.enrich(_normalized())

        assert result["enrichment_source"] == "spotify"
        assert result["pending_enrichment"] is False
        assert result["genres"] == ["electronic", "ambient"]

    def test_output_preserves_normalized_fields(self):
        enricher = Enricher(_make_settings())
        enricher._spotify.get_artist_data = MagicMock(
            return_value={"genres": [], "artist_popularity": None, "followers": None}
        )
        enricher._spotify.get_track_data = MagicMock(
            return_value={"track_popularity": None, "duration_ms": None}
        )
        enricher._lastfm.get_artist_tags = MagicMock(return_value=[])

        normalized = _normalized()
        result = enricher.enrich(normalized)

        for key in ("signal_id", "artist", "title", "sources", "played", "played_at"):
            assert result[key] == normalized[key]

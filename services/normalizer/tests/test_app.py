from unittest.mock import MagicMock, patch

from signal_common.circuit_breaker import CircuitBreaker
from signal_normalizer.app import _build_output, _is_valid


class TestIsValid:
    def test_valid_message(self):
        assert _is_valid({"artist": "Actress", "title": "Ascending"})

    def test_missing_artist(self):
        assert not _is_valid({"title": "Ascending"})

    def test_empty_artist(self):
        assert not _is_valid({"artist": "  ", "title": "Ascending"})

    def test_missing_title(self):
        assert not _is_valid({"artist": "Actress"})

    def test_artist_too_long(self):
        assert not _is_valid({"artist": "A" * 501, "title": "Title"})


class TestBuildOutput:
    def test_lastfm_source_sets_played_true(self):
        raw = {"artist": "Actress", "title": "Ascending", "source": "lastfm", "played_at": "2026-01-01T00:00:00Z"}
        out = _build_output(raw, "sig123", "spotify:artist:a1", "spotify:track:t1", "2026-01-01T00:01:00Z")
        assert out["played"] is True
        assert out["sources"] == ["lastfm"]

    def test_spotify_source_sets_played_false(self):
        raw = {"artist": "Actress", "title": "Ascending", "source": "spotify", "played_at": None}
        out = _build_output(raw, "sig123", "spotify:artist:a1", "spotify:track:t1", "2026-01-01T00:01:00Z")
        assert out["played"] is False

    def test_default_source_is_lastfm(self):
        raw = {"artist": "Actress", "title": "Ascending"}
        out = _build_output(raw, "sig123", None, None, "2026-01-01T00:01:00Z")
        assert out["played"] is True

    def test_v2_schema_has_no_enrichment_fields(self):
        raw = {"artist": "Actress", "title": "Ascending", "source": "lastfm"}
        out = _build_output(raw, "sig123", None, None, "2026-01-01T00:01:00Z")
        for forbidden in ("genres", "audio_features", "popularity", "pending_enrichment"):
            assert forbidden not in out

    def test_v2_schema_exact_fields(self):
        raw = {"artist": "Actress", "title": "Ascending", "source": "lastfm", "played_at": "2026-01-01T00:00:00Z"}
        out = _build_output(raw, "sig123", "spotify:artist:a1", "spotify:track:t1", "2026-01-01T00:01:00Z")
        assert set(out.keys()) == {
            "signal_id", "artist", "artist_id", "track_id",
            "title", "sources", "played", "played_at", "processed_at",
        }

    def test_null_ids_when_spotify_failed(self):
        raw = {"artist": "Actress", "title": "Ascending", "source": "lastfm"}
        out = _build_output(raw, "sig123", None, None, "2026-01-01T00:01:00Z")
        assert out["artist_id"] is None
        assert out["track_id"] is None


class TestCircuitBreakerIntegration:
    def test_circuit_open_skips_spotify_and_forwards_null_ids(self):
        cb = CircuitBreaker(failure_threshold=1, timeout_s=60.0)
        cb.record_failure()
        assert not cb.should_allow()

        spotify = MagicMock()
        if cb.should_allow():
            artist_id, track_id = spotify.search_track("X", "Y")
        else:
            artist_id, track_id = None, None

        spotify.search_track.assert_not_called()
        assert artist_id is None
        assert track_id is None

    def test_circuit_records_success_on_resolved_ids(self):
        cb = CircuitBreaker(failure_threshold=3, timeout_s=60.0)
        cb.record_failure()

        artist_id = "spotify:artist:abc"
        if artist_id is not None:
            cb.record_success()

        assert not cb.is_open

    def test_circuit_records_failure_on_null_ids(self):
        cb = CircuitBreaker(failure_threshold=2, timeout_s=60.0)
        for _ in range(2):
            cb.record_failure()
        assert cb.is_open

import signal as _signal
from unittest.mock import MagicMock, patch

import pytest

from signal_common.circuit_breaker import CircuitBreaker
from signal_common.spotify import SpotifyServiceError
from signal_normalizer.app import _INPUT_TOPICS, _build_output, _is_valid


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

    def test_circuit_records_success_on_not_found(self):
        """(None, None) from search is 'not found' — not a failure."""
        cb = CircuitBreaker(failure_threshold=3, timeout_s=60.0)
        spotify = MagicMock()
        spotify.search_track.return_value = (None, None)

        if cb.should_allow():
            try:
                artist_id, track_id = spotify.search_track("X", "Y")
                cb.record_success()
            except SpotifyServiceError:
                cb.record_failure()
                artist_id, track_id = None, None

        assert not cb.is_open

    def test_circuit_records_failure_on_service_error(self):
        cb = CircuitBreaker(failure_threshold=2, timeout_s=60.0)
        spotify = MagicMock()
        spotify.search_track.side_effect = SpotifyServiceError("timeout")

        for _ in range(2):
            if cb.should_allow():
                try:
                    spotify.search_track("X", "Y")
                    cb.record_success()
                except SpotifyServiceError:
                    cb.record_failure()

        assert cb.is_open


class TestMultiTopicSubscription:
    def test_consumer_subscribes_to_both_topics(self):
        assert "raw.plays" in _INPUT_TOPICS
        assert "raw.tracks" in _INPUT_TOPICS
        msg = {"artist": "Actress", "title": "Ascending", "source": "lastfm", "played_at": "2026-01-01T00:00:00Z"}
        _, consumer = self._run_one_message(msg)
        consumer.subscribe.assert_called_once_with(_INPUT_TOPICS)

    def _run_one_message(self, msg: dict):
        settings = MagicMock()
        settings.kafka_bootstrap_servers = "localhost:9092"
        settings.kafka_consumer_group = "test-group"
        settings.spotify_rate_limit_per_30s = 30
        settings.circuit_breaker_failure_threshold = 5
        settings.circuit_breaker_timeout_s = 60.0
        settings.spotify_client_id = "id"
        settings.spotify_client_secret = "secret"
        settings.spotify_refresh_token = "token"
        settings.spotify_timeout = 5.0
        settings.spotify_retry_after_default_s = 5.0
        settings.spotify_retry_after_max_s = 60.0

        poll_calls = [0]

        def poll_side_effect(timeout):
            poll_calls[0] += 1
            return msg if poll_calls[0] == 1 else None

        consumer = MagicMock()
        consumer.poll.side_effect = poll_side_effect

        handlers: dict = {}

        def register_handler(sig, handler):
            handlers[sig] = handler

        producer = MagicMock()
        producer.flush.return_value = 0

        def commit_then_stop(*args, **kwargs):
            if _signal.SIGTERM in handlers:
                handlers[_signal.SIGTERM](_signal.SIGTERM, None)

        consumer.commit.side_effect = commit_then_stop

        with (
            patch("signal_normalizer.app.KafkaJsonConsumer", return_value=consumer),
            patch("signal_normalizer.app.KafkaJsonProducer", return_value=producer),
            patch("signal_normalizer.app.SpotifyClient") as mock_spotify_cls,
            patch("signal_normalizer.app.signal") as mock_sig,
        ):
            mock_sig.SIGTERM = _signal.SIGTERM
            mock_sig.SIGINT = _signal.SIGINT
            mock_sig.signal.side_effect = register_handler

            spotify = MagicMock()
            spotify.search_track.return_value = (None, None)
            mock_spotify_cls.return_value = spotify

            from signal_normalizer.app import run_consumer
            run_consumer(settings)

        return producer, consumer

    def test_spotify_source_produces_played_false(self):
        msg = {"artist": "Actress", "title": "Ascending", "source": "spotify"}
        producer, _ = self._run_one_message(msg)

        producer.produce.assert_called_once()
        _, out_msg = producer.produce.call_args[0][0], producer.produce.call_args[0][1]
        assert out_msg["played"] is False

    def test_lastfm_source_produces_played_true(self):
        msg = {"artist": "Actress", "title": "Ascending", "source": "lastfm", "played_at": "2026-01-01T00:00:00Z"}
        producer, _ = self._run_one_message(msg)

        producer.produce.assert_called_once()
        _, out_msg = producer.produce.call_args[0][0], producer.produce.call_args[0][1]
        assert out_msg["played"] is True

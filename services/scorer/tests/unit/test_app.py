import signal as _signal
from unittest.mock import MagicMock, patch

import pytest
from signal_scorer.app import run_consumer


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_settings(**overrides):
    s = MagicMock()
    s.kafka_bootstrap_servers = "localhost:9092"
    s.kafka_consumer_group = "scorer-test"
    s.kafka_input_topic = "tracks.novel"
    s.kafka_dlq_topic = "scorer.dlq"
    s.database_url = "postgresql://signal:signal@localhost:5432/signal"
    s.w1 = 0.6
    s.w2 = 0.4
    s.hp_bonus = 1.2
    s.scorer_stats_interval = 100
    s.log_level = "INFO"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _valid_msg(**overrides) -> dict:
    base = {
        "signal_id": "sig-abc",
        "artist": "Actress",
        "artist_id": "spotify:artist:3G3Gdm4",
        "artist_popularity": 20,
        "novelty_signals": {"genre_novelty_ratio": 0.8},
    }
    base.update(overrides)
    return base


def _run_loop(
    msg: dict,
    *,
    artist_result=None,
    upsert_side_effect=None,
):
    """Run one message through the consumer loop, then stop via SIGTERM."""
    settings = _make_settings()

    with (
        patch("signal_scorer.app.KafkaJsonConsumer") as MockConsumer,
        patch("signal_scorer.app.KafkaJsonProducer") as MockProducer,
        patch("signal_scorer.app.DlqPublisher") as MockDlq,
        patch("signal_scorer.app.lookup_artist") as mock_lookup,
        patch("signal_scorer.app.upsert_recommendation") as mock_upsert,
        patch("signal_scorer.app.psycopg") as MockPsycopg,
        patch("signal_scorer.app.signal") as mock_sig_module,
    ):
        handlers: dict = {}
        mock_sig_module.SIGTERM = _signal.SIGTERM
        mock_sig_module.SIGINT = _signal.SIGINT
        mock_sig_module.signal.side_effect = lambda sig, h: handlers.update({sig: h})

        consumer = MockConsumer.return_value
        call_count = [0]

        def poll_side_effect(timeout=1.0):
            call_count[0] += 1
            if call_count[0] == 1:
                return msg
            handlers.get(_signal.SIGTERM, lambda *_: None)(_signal.SIGTERM, None)
            return None

        consumer.poll.side_effect = poll_side_effect

        mock_lookup.return_value = artist_result
        if upsert_side_effect is not None:
            mock_upsert.side_effect = upsert_side_effect

        conn = MagicMock()
        MockPsycopg.connect.return_value.__enter__ = MagicMock(return_value=conn)
        MockPsycopg.connect.return_value.__exit__ = MagicMock(return_value=False)

        dlq = MockDlq.return_value
        run_consumer(settings)
        return consumer, dlq, mock_upsert


# ─── DLQ paths ────────────────────────────────────────────────────────────────


class TestMalformedMessage:
    def test_goes_to_dlq(self):
        _, dlq, _ = _run_loop({"artist": "Actress"})  # missing signal_id + novelty_signals
        dlq.publish.assert_called_once()

    def test_dlq_reason_is_validation_failed(self):
        _, dlq, _ = _run_loop({"artist": "Actress"})
        assert dlq.publish.call_args[1]["error_reason"] == "validation_failed"

    def test_no_upsert_called(self):
        _, _, mock_upsert = _run_loop({"artist": "Actress"})
        mock_upsert.assert_not_called()

    def test_offset_committed(self):
        consumer, _, _ = _run_loop({"artist": "Actress"})
        consumer.commit.assert_called()

    def test_consumer_closed_on_shutdown(self):
        consumer, _, _ = _run_loop({"artist": "Actress"})
        consumer.close.assert_called_once()


class TestArtistNotFound:
    def test_goes_to_dlq(self):
        _, dlq, _ = _run_loop(_valid_msg(), artist_result=None)
        dlq.publish.assert_called_once()

    def test_dlq_reason_is_artist_not_found(self):
        _, dlq, _ = _run_loop(_valid_msg(), artist_result=None)
        assert dlq.publish.call_args[1]["error_reason"] == "artist_not_found"

    def test_no_upsert_called(self):
        _, _, mock_upsert = _run_loop(_valid_msg(), artist_result=None)
        mock_upsert.assert_not_called()

    def test_offset_committed(self):
        consumer, _, _ = _run_loop(_valid_msg(), artist_result=None)
        consumer.commit.assert_called()


class TestAfterDlqContinues:
    def test_consumer_keeps_running_after_dlq(self):
        """After a DLQ'd message the consumer must not crash; it closes cleanly on shutdown."""
        consumer, dlq, _ = _run_loop({"artist": "Actress"})
        dlq.publish.assert_called_once()
        consumer.close.assert_called_once()


# ─── Happy path ───────────────────────────────────────────────────────────────


class TestSuccessfulScoring:
    import uuid as _uuid
    _artist_uuid = _uuid.uuid4()

    def test_upsert_called(self):
        consumer, _, mock_upsert = _run_loop(
            _valid_msg(), artist_result=(self._artist_uuid, False)
        )
        mock_upsert.assert_called_once()

    def test_offset_committed_after_upsert(self):
        consumer, _, mock_upsert = _run_loop(
            _valid_msg(), artist_result=(self._artist_uuid, False)
        )
        consumer.commit.assert_called()

    def test_no_dlq_on_success(self):
        _, dlq, _ = _run_loop(_valid_msg(), artist_result=(self._artist_uuid, False))
        dlq.publish.assert_not_called()


# ─── Stats counter ────────────────────────────────────────────────────────────


class TestStatsCounters:
    import uuid as _uuid
    _artist_uuid = _uuid.uuid4()

    def test_stats_interval_of_1_logs_on_every_message(self):
        """With interval=1, stats must be logged after the single message."""
        import signal_scorer.app as app_module

        settings = _make_settings(scorer_stats_interval=1)
        logged_stats = []

        original_maybe = app_module._maybe_log_stats

        def capture_stats(consumed, upserted, dlq, errors, interval):
            logged_stats.append((consumed, upserted, dlq, errors))
            original_maybe(consumed, upserted, dlq, errors, interval)

        with (
            patch("signal_scorer.app.KafkaJsonConsumer") as MockConsumer,
            patch("signal_scorer.app.KafkaJsonProducer"),
            patch("signal_scorer.app.DlqPublisher"),
            patch("signal_scorer.app.lookup_artist") as mock_lookup,
            patch("signal_scorer.app.upsert_recommendation"),
            patch("signal_scorer.app.psycopg") as MockPsycopg,
            patch("signal_scorer.app.signal") as mock_sig_module,
            patch("signal_scorer.app._maybe_log_stats", side_effect=capture_stats),
        ):
            handlers: dict = {}
            mock_sig_module.SIGTERM = _signal.SIGTERM
            mock_sig_module.SIGINT = _signal.SIGINT
            mock_sig_module.signal.side_effect = lambda sig, h: handlers.update({sig: h})

            consumer = MockConsumer.return_value
            call_count = [0]

            def poll_side_effect(timeout=1.0):
                call_count[0] += 1
                if call_count[0] == 1:
                    return _valid_msg()
                handlers.get(_signal.SIGTERM, lambda *_: None)(_signal.SIGTERM, None)
                return None

            consumer.poll.side_effect = poll_side_effect
            mock_lookup.return_value = (self._artist_uuid, False)

            conn = MagicMock()
            MockPsycopg.connect.return_value.__enter__ = MagicMock(return_value=conn)
            MockPsycopg.connect.return_value.__exit__ = MagicMock(return_value=False)

            run_consumer(settings)

        assert len(logged_stats) == 1
        consumed, upserted, dlq, errors = logged_stats[0]
        assert consumed == 1
        assert upserted == 1
        assert dlq == 0
        assert errors == 0

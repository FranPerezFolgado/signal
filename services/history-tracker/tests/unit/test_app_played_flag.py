import signal as _signal
from unittest.mock import MagicMock, patch


def _make_settings():
    s = MagicMock()
    s.kafka_bootstrap_servers = "localhost:9092"
    s.kafka_consumer_group = "test-group"
    s.database_url = "postgresql://signal:signal@localhost:5432/signal"
    return s


def _make_msg(**kwargs):
    base = {
        "signal_id": "abc123def456" + "0" * 52,
        "artist": "Actress",
        "title": "Ascending",
        "artist_id": "spotify:artist:3G3Gdm4vNKHNf3jiRfPVzqt",
    }
    base.update(kwargs)
    return base


def _run_one_message(msg: dict):
    """Drive one message through the consumer loop then stop via SIGINT."""
    settings = _make_settings()

    history_repo = MagicMock()
    history_repo.upsert.return_value = True
    artist_repo = MagicMock()
    artist_repo.upsert.return_value = True
    producer = MagicMock()
    producer.flush.return_value = 0
    dlq = MagicMock()

    poll_calls = 0

    def poll_side_effect(timeout):
        nonlocal poll_calls
        poll_calls += 1
        return msg if poll_calls == 1 else None

    consumer = MagicMock()
    consumer.poll.side_effect = poll_side_effect

    handlers: dict = {}

    def register_handler(sig, handler):
        handlers[sig] = handler

    with (
        patch("signal_history_tracker.app.KafkaJsonConsumer", return_value=consumer),
        patch("signal_history_tracker.app.KafkaJsonProducer", return_value=producer),
        patch("signal_history_tracker.app.DlqPublisher", return_value=dlq),
        patch("signal_history_tracker.app.HistoryRepository", return_value=history_repo),
        patch("signal_history_tracker.app.ArtistRepository", return_value=artist_repo),
        patch("signal_history_tracker.app.psycopg") as mock_psycopg,
        patch("signal_history_tracker.app.signal") as mock_sig,
    ):
        mock_sig.SIGTERM = _signal.SIGTERM
        mock_sig.SIGINT = _signal.SIGINT
        mock_sig.signal.side_effect = register_handler

        mock_conn = MagicMock()
        mock_psycopg.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_psycopg.connect.return_value.__exit__ = MagicMock(return_value=False)

        # After processing the one message, fire SIGTERM to stop the loop
        def commit_then_stop(*args, **kwargs):
            if _signal.SIGTERM in handlers:
                handlers[_signal.SIGTERM](_signal.SIGTERM, None)

        consumer.commit.side_effect = commit_then_stop

        from signal_history_tracker.app import run_consumer
        run_consumer(settings)

    return history_repo, artist_repo, consumer, dlq


def test_played_false_skips_upsert():
    history_repo, artist_repo, consumer, _ = _run_one_message(_make_msg(played=False))
    history_repo.upsert.assert_not_called()
    artist_repo.upsert.assert_not_called()
    consumer.commit.assert_called()


def test_played_true_processes_normally():
    history_repo, artist_repo, consumer, _ = _run_one_message(_make_msg(played=True))
    history_repo.upsert.assert_called_once()


def test_played_absent_defaults_to_true():
    """Legacy messages without a 'played' field must be processed normally."""
    msg = _make_msg()
    assert "played" not in msg
    history_repo, artist_repo, consumer, _ = _run_one_message(msg)
    history_repo.upsert.assert_called_once()

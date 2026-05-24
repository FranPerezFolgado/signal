import signal as _signal
from unittest.mock import MagicMock, patch

import pytest

from signal_novelty_detector.app import _is_valid


# ─── _is_valid ────────────────────────────────────────────────────────────────

class TestIsValid:
    def test_valid_message(self):
        msg = {"signal_id": "abc", "artist": "Actress", "title": "Ascending", "pending_enrichment": False}
        assert _is_valid(msg) is True

    def test_pending_enrichment_true_still_valid(self):
        # _is_valid accepts it; the loop skips it separately
        msg = {"signal_id": "abc", "artist": "Actress", "title": "Ascending", "pending_enrichment": True}
        assert _is_valid(msg) is True

    def test_missing_signal_id(self):
        msg = {"artist": "Actress", "title": "Ascending", "pending_enrichment": False}
        assert _is_valid(msg) is False

    def test_signal_id_not_string(self):
        msg = {"signal_id": 123, "artist": "Actress", "title": "Ascending", "pending_enrichment": False}
        assert _is_valid(msg) is False

    def test_missing_artist(self):
        msg = {"signal_id": "abc", "title": "Ascending", "pending_enrichment": False}
        assert _is_valid(msg) is False

    def test_missing_title(self):
        msg = {"signal_id": "abc", "artist": "Actress", "pending_enrichment": False}
        assert _is_valid(msg) is False

    def test_missing_pending_enrichment(self):
        msg = {"signal_id": "abc", "artist": "Actress", "title": "Ascending"}
        assert _is_valid(msg) is False


# ─── Consumer loop helpers ─────────────────────────────────────────────────────

def _make_settings(auto_follow_plays=3):
    s = MagicMock()
    s.kafka_bootstrap_servers = "localhost:9092"
    s.kafka_consumer_group = "novelty-detector-test"
    s.database_url = "postgresql://signal:signal@localhost:5432/signal"
    s.auto_follow_plays = auto_follow_plays
    s.log_level = "INFO"
    return s


def _make_artist_row(status="TRACKED", scrobble_count=1):
    return {"id": "some-uuid", "status": status, "scrobble_count": scrobble_count}


def _build_msg(signal_id="sig-abc", artist="Actress", title="Ascending",
               pending=False, genres=None, artist_id=None):
    return {
        "signal_id": signal_id,
        "artist": artist,
        "title": title,
        "pending_enrichment": pending,
        "genres": genres if genres is not None else [],
        "artist_id": artist_id,
    }


def _run_loop(msg, *, artist_row=None, artist_is_new=True, new_genres=None,
              track_is_new=True, auto_follow_plays=3):
    """Run the consumer loop with a single message then stop via SIGTERM handler."""
    settings = _make_settings(auto_follow_plays)

    with (
        patch("signal_novelty_detector.app.KafkaJsonConsumer") as MockConsumer,
        patch("signal_novelty_detector.app.KafkaJsonProducer") as MockProducer,
        patch("signal_novelty_detector.app.DlqPublisher") as MockDlq,
        patch("signal_novelty_detector.app.NoveltyRepository") as MockNoveltyRepo,
        patch("signal_novelty_detector.app.ArtistRepository") as MockArtistRepo,
        patch("signal_novelty_detector.app.psycopg") as MockPsycopg,
        patch("signal_novelty_detector.app.signal") as mock_sig_module,
    ):
        # Capture the SIGTERM handler so we can call it to stop the loop
        handlers: dict = {}
        mock_sig_module.SIGTERM = _signal.SIGTERM
        mock_sig_module.SIGINT = _signal.SIGINT
        mock_sig_module.signal.side_effect = lambda sig, h: handlers.update({sig: h})

        consumer = MockConsumer.return_value

        # Return msg on first poll, then trigger stop on second
        call_count = [0]
        def poll_side_effect(timeout=1.0):
            call_count[0] += 1
            if call_count[0] == 1:
                return msg
            handlers.get(_signal.SIGTERM, lambda *_: None)(_signal.SIGTERM, None)
            return None
        consumer.poll.side_effect = poll_side_effect

        # Wire novelty repo
        novelty_repo = MockNoveltyRepo.return_value
        novelty_repo.is_artist_new.return_value = artist_is_new
        novelty_repo.get_new_genres.return_value = new_genres if new_genres is not None else []
        novelty_repo.is_track_new.return_value = track_is_new

        # Wire artist repo
        artist_repo = MockArtistRepo.return_value
        artist_repo.get.return_value = artist_row
        artist_repo.promote_to_following.return_value = False

        # Wire producers
        output_producer = MagicMock()
        output_producer.flush.return_value = 0
        dlq_producer = MagicMock()
        producers = [output_producer, dlq_producer]
        idx = [0]
        def make_producer(*a, **kw):
            p = producers[idx[0]] if idx[0] < len(producers) else MagicMock()
            idx[0] += 1
            return p
        MockProducer.side_effect = make_producer

        dlq = MockDlq.return_value

        # Wire psycopg context manager
        conn = MagicMock()
        MockPsycopg.connect.return_value.__enter__ = MagicMock(return_value=conn)
        MockPsycopg.connect.return_value.__exit__ = MagicMock(return_value=False)

        from signal_novelty_detector.app import run_consumer
        run_consumer(settings)

        return output_producer, dlq, artist_repo, novelty_repo, consumer


# ─── Consumer loop: skip and DLQ paths ────────────────────────────────────────

class TestPendingEnrichmentSkip:
    def test_no_event_emitted(self):
        output_producer, dlq, *_ = _run_loop(_build_msg(pending=True))
        output_producer.produce.assert_not_called()

    def test_no_dlq_entry(self):
        _, dlq, *_ = _run_loop(_build_msg(pending=True))
        dlq.publish.assert_not_called()

    def test_offset_committed(self):
        _, _, _, _, consumer = _run_loop(_build_msg(pending=True))
        consumer.commit.assert_called()


class TestMalformedMessage:
    def test_goes_to_dlq(self):
        _, dlq, *_ = _run_loop({"artist": "Actress"})  # missing fields
        dlq.publish.assert_called_once()

    def test_dlq_reason_is_malformed(self):
        _, dlq, *_ = _run_loop({"artist": "Actress"})
        assert dlq.publish.call_args[1]["error_reason"] == "malformed_message"

    def test_no_novelty_event_emitted(self):
        output_producer, *_ = _run_loop({"artist": "Actress"})
        output_producer.produce.assert_not_called()


class TestMissingArtistRecord:
    def test_goes_to_dlq(self):
        _, dlq, *_ = _run_loop(_build_msg(), artist_row=None)
        dlq.publish.assert_called_once()

    def test_dlq_reason_is_artist_missing(self):
        _, dlq, *_ = _run_loop(_build_msg(), artist_row=None)
        assert dlq.publish.call_args[1]["error_reason"] == "artist record missing"

    def test_no_novelty_event_emitted(self):
        output_producer, *_ = _run_loop(_build_msg(), artist_row=None)
        output_producer.produce.assert_not_called()


# ─── Consumer loop: novelty detection ─────────────────────────────────────────

class TestNoveltyDetection:
    def test_new_artist_emits_event(self):
        msg = _build_msg(genres=["footwork", "experimental"])
        output_producer, *_ = _run_loop(
            msg, artist_row=_make_artist_row(), artist_is_new=True,
            new_genres=["footwork", "experimental"]
        )
        output_producer.produce.assert_called_once()

    def test_new_artist_event_has_correct_signals(self):
        msg = _build_msg(genres=["footwork", "experimental"])
        output_producer, *_ = _run_loop(
            msg, artist_row=_make_artist_row(), artist_is_new=True,
            new_genres=["footwork", "experimental"]
        )
        produced = output_producer.produce.call_args[0][1]
        signals = produced["novelty_signals"]
        assert signals["artist_is_new"] is True
        assert signals["genre_novelty_ratio"] == 1.0
        assert signals["new_genres"] == ["footwork", "experimental"]
        assert signals["known_genres"] == []

    def test_known_artist_all_known_genres_no_event(self):
        msg = _build_msg(genres=["electronic"])
        output_producer, dlq, *_ = _run_loop(
            msg, artist_row=_make_artist_row(), artist_is_new=False, new_genres=[]
        )
        output_producer.produce.assert_not_called()
        dlq.publish.assert_not_called()

    def test_known_artist_one_new_genre_emits_event(self):
        msg = _build_msg(genres=["electronic", "footwork"])
        output_producer, *_ = _run_loop(
            msg, artist_row=_make_artist_row(), artist_is_new=False,
            new_genres=["footwork"]
        )
        output_producer.produce.assert_called_once()
        produced = output_producer.produce.call_args[0][1]
        signals = produced["novelty_signals"]
        assert signals["genre_novelty_ratio"] == 0.5
        assert signals["new_genres"] == ["footwork"]
        assert signals["known_genres"] == ["electronic"]

    def test_new_artist_empty_genres_emits_event_with_ratio_zero(self):
        msg = _build_msg(genres=[])
        output_producer, *_ = _run_loop(
            msg, artist_row=_make_artist_row(), artist_is_new=True, new_genres=[]
        )
        output_producer.produce.assert_called_once()
        produced = output_producer.produce.call_args[0][1]
        assert produced["novelty_signals"]["genre_novelty_ratio"] == 0.0

    def test_known_artist_empty_genres_no_event(self):
        msg = _build_msg(genres=[])
        output_producer, dlq, *_ = _run_loop(
            msg, artist_row=_make_artist_row(), artist_is_new=False, new_genres=[]
        )
        output_producer.produce.assert_not_called()
        dlq.publish.assert_not_called()


# ─── Consumer loop: auto-promotion ────────────────────────────────────────────

class TestAutoPromotion:
    def test_tracked_at_threshold_promotion_attempted(self):
        msg = _build_msg(genres=["electronic"])
        _, _, artist_repo, *_ = _run_loop(
            msg, artist_row=_make_artist_row(status="TRACKED", scrobble_count=3),
            artist_is_new=True, new_genres=["electronic"], auto_follow_plays=3
        )
        artist_repo.promote_to_following.assert_called_once()

    def test_following_artist_not_promoted(self):
        msg = _build_msg(genres=["electronic"])
        _, _, artist_repo, *_ = _run_loop(
            msg, artist_row=_make_artist_row(status="FOLLOWING", scrobble_count=10),
            artist_is_new=False, new_genres=["electronic"]
        )
        artist_repo.promote_to_following.assert_not_called()

    def test_artist_below_threshold_not_promoted(self):
        msg = _build_msg(genres=["electronic"])
        _, _, artist_repo, *_ = _run_loop(
            msg, artist_row=_make_artist_row(status="TRACKED", scrobble_count=2),
            artist_is_new=True, new_genres=["electronic"], auto_follow_plays=3
        )
        artist_repo.promote_to_following.assert_not_called()

    def test_promotion_db_failure_does_not_block_event(self):
        msg = _build_msg(genres=["electronic"])
        with (
            patch("signal_novelty_detector.app.KafkaJsonConsumer") as MockConsumer,
            patch("signal_novelty_detector.app.KafkaJsonProducer") as MockProducer,
            patch("signal_novelty_detector.app.DlqPublisher") as MockDlq,
            patch("signal_novelty_detector.app.NoveltyRepository") as MockNoveltyRepo,
            patch("signal_novelty_detector.app.ArtistRepository") as MockArtistRepo,
            patch("signal_novelty_detector.app.psycopg") as MockPsycopg,
            patch("signal_novelty_detector.app.signal") as mock_sig_module,
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

            novelty_repo = MockNoveltyRepo.return_value
            novelty_repo.is_artist_new.return_value = True
            novelty_repo.get_new_genres.return_value = ["electronic"]
            novelty_repo.is_track_new.return_value = True

            artist_repo = MockArtistRepo.return_value
            artist_repo.get.return_value = _make_artist_row(status="TRACKED", scrobble_count=5)
            artist_repo.promote_to_following.side_effect = Exception("db error")

            output_producer = MagicMock()
            output_producer.flush.return_value = 0
            producers = [output_producer, MagicMock()]
            idx = [0]
            def make_producer(*a, **kw):
                p = producers[idx[0]] if idx[0] < 2 else MagicMock()
                idx[0] += 1
                return p
            MockProducer.side_effect = make_producer

            conn = MagicMock()
            MockPsycopg.connect.return_value.__enter__ = MagicMock(return_value=conn)
            MockPsycopg.connect.return_value.__exit__ = MagicMock(return_value=False)

            from signal_novelty_detector.app import run_consumer
            run_consumer(_make_settings())

            output_producer.produce.assert_called_once()
            MockDlq.return_value.publish.assert_not_called()

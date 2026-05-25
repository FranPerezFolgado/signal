import signal

import psycopg
from psycopg import OperationalError as _PsycopgOperationalError
from signal_common.kafka_consumer import KafkaJsonConsumer
from signal_common.kafka_producer import KafkaJsonProducer
from signal_common.logger import get_logger
from signal_common.models import ArtistStatus

from signal_novelty_detector.artist_repository import ArtistRepository
from signal_novelty_detector.dlq_publisher import DlqPublisher
from signal_novelty_detector.novelty_repository import NoveltyRepository
from signal_novelty_detector.settings import Settings

_INPUT_TOPIC = "tracks.enriched"
_OUTPUT_TOPIC = "tracks.novel"
_DLQ_TOPIC = "novelty-detector.dlq"
_CLIENT_ID = "novelty-detector"

_log = get_logger(__name__)


def _is_valid(msg: dict) -> bool:
    return (
        isinstance(msg.get("signal_id"), str)
        and isinstance(msg.get("artist"), str)
        and isinstance(msg.get("title"), str)
        and "pending_enrichment" in msg
        and (msg.get("genres") is None or isinstance(msg.get("genres"), list))
    )


def run_consumer(settings: Settings) -> None:
    consumer = KafkaJsonConsumer(
        settings.kafka_bootstrap_servers,
        settings.kafka_consumer_group,
        _CLIENT_ID,
    )
    output_producer = KafkaJsonProducer(settings.kafka_bootstrap_servers, client_id=_CLIENT_ID)
    dlq_producer = KafkaJsonProducer(
        settings.kafka_bootstrap_servers, client_id=f"{_CLIENT_ID}-dlq"
    )

    novelty_repo = NoveltyRepository()
    artist_repo = ArtistRepository()
    dlq = DlqPublisher(dlq_producer, _DLQ_TOPIC)

    processed = 0
    skipped_pending = 0
    skipped_no_novelty = 0
    failed_dlq = 0

    stop = False

    def _handle_signal(sig: int, _frame: object) -> None:
        nonlocal stop
        _log.info("shutdown_requested", signal=sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    consumer.subscribe([_INPUT_TOPIC])
    _log.info("novelty_detector_started")

    try:
        with psycopg.connect(settings.database_url) as conn:
            while not stop:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue

                if not _is_valid(msg):
                    dlq.publish(
                        error_reason="malformed_message",
                        error_detail="invalid or missing required fields",
                        original_payload=msg,
                    )
                    failed_dlq += 1
                    consumer.commit()
                    continue

                if msg["pending_enrichment"]:
                    _log.debug("skipping_pending_enrichment", signal_id=str(msg["signal_id"])[:8])
                    skipped_pending += 1
                    consumer.commit()
                    continue

                signal_id: str = msg["signal_id"]
                artist: str = msg["artist"]
                genres: list[str] = [g for g in (msg.get("genres") or []) if isinstance(g, str)]

                try:
                    artist_row = artist_repo.get(conn, artist)
                    if artist_row is None:
                        dlq.publish(
                            error_reason="artist record missing",
                            error_detail="artist not found in artists table",
                            original_payload=msg,
                        )
                        failed_dlq += 1
                        consumer.commit()
                        continue

                    artist_is_new = novelty_repo.is_artist_new(conn, artist, signal_id)
                    new_genres = novelty_repo.get_new_genres(conn, genres, signal_id)
                    track_is_new = novelty_repo.is_track_new(conn, signal_id)
                    known_genres = [g for g in genres if g not in new_genres]
                    genre_novelty_ratio = len(new_genres) / len(genres) if genres else 0.0

                    # Auto-promotion: best-effort; DB failure logs a warning, never blocks the event
                    if (
                        artist_row["status"] == ArtistStatus.TRACKED
                        and artist_row["scrobble_count"] >= settings.auto_follow_plays
                    ):
                        try:
                            if artist_repo.promote_to_following(
                                conn, artist, settings.auto_follow_plays
                            ):
                                _log.info(
                                    "artist_promoted",
                                    artist=artist,
                                    scrobble_count=artist_row["scrobble_count"],
                                )
                            conn.commit()
                        except Exception as exc:
                            _log.warning("auto_promotion_failed", artist=artist, error=str(exc))
                            conn.rollback()

                    if not (artist_is_new or new_genres):
                        skipped_no_novelty += 1
                        consumer.commit()
                        continue

                    novel_event = {
                        "signal_id": signal_id,
                        "artist": artist,
                        "artist_id": msg.get("artist_id"),
                        "genres": genres,
                        "artist_popularity": msg.get("artist_popularity"),
                        "track_popularity": msg.get("track_popularity"),
                        "played_at": msg.get("played_at"),
                        "novelty_signals": {
                            "track_is_new": track_is_new,
                            "artist_is_new": artist_is_new,
                            "new_genres": new_genres,
                            "known_genres": known_genres,
                            "genre_novelty_ratio": genre_novelty_ratio,
                        },
                    }

                    output_producer.produce(_OUTPUT_TOPIC, novel_event, key=signal_id)
                    unflushed = output_producer.flush(timeout=10.0)
                    if unflushed > 0:
                        _log.error("kafka_flush_timeout", signal_id=signal_id[:8])
                        continue  # do not commit offset — message will be redelivered

                    processed += 1
                    consumer.commit()

                except _PsycopgOperationalError:
                    # Transient infrastructure failure — crash so Docker restarts cleanly
                    raise

                except Exception as exc:
                    _log.error("processing_error", signal_id=signal_id[:8], error=str(exc))
                    dlq.publish(
                        error_reason="processing_error",
                        error_detail="message processing failed",
                        original_payload=msg,
                    )
                    failed_dlq += 1
                    consumer.commit()

    finally:
        _log.info(
            "novelty_detector_stopped",
            processed=processed,
            skipped_pending=skipped_pending,
            skipped_no_novelty=skipped_no_novelty,
            failed_dlq=failed_dlq,
        )
        output_producer.flush(timeout=10.0)
        consumer.close()

import signal

import psycopg

from signal_common.kafka_consumer import KafkaJsonConsumer
from signal_common.kafka_producer import KafkaJsonProducer
from signal_common.logger import get_logger

from signal_history_tracker.artist_repository import ArtistRepository
from signal_history_tracker.dlq_publisher import DlqPublisher
from signal_history_tracker.history_repository import HistoryRepository
from signal_history_tracker.settings import Settings

_INPUT_TOPIC = "tracks.enriched"
_OUTPUT_TOPIC = "listening.history"
_DLQ_TOPIC = "history-tracker.dlq"
_CLIENT_ID = "history-tracker"

_log = get_logger(__name__)


def _is_valid(msg: dict) -> bool:
    return (
        isinstance(msg.get("signal_id"), str)
        and isinstance(msg.get("artist"), str)
        and isinstance(msg.get("title"), str)
    )


def run_consumer(settings: Settings) -> None:
    consumer = KafkaJsonConsumer(
        settings.kafka_bootstrap_servers,
        settings.kafka_consumer_group,
        _CLIENT_ID,
    )
    output_producer = KafkaJsonProducer(settings.kafka_bootstrap_servers, client_id=_CLIENT_ID)
    dlq_producer = KafkaJsonProducer(settings.kafka_bootstrap_servers, client_id=f"{_CLIENT_ID}-dlq")
    history_repo = HistoryRepository()
    artist_repo = ArtistRepository()
    dlq = DlqPublisher(dlq_producer, _DLQ_TOPIC)

    processed = 0
    failed_dlq = 0
    already_seen = 0

    stop = False

    def _handle_signal(sig: int, _frame: object) -> None:
        nonlocal stop
        _log.info("shutdown_requested", signal=sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    consumer.subscribe([_INPUT_TOPIC])
    _log.info("history_tracker_started")

    with psycopg.connect(settings.database_url) as conn:
        try:
            while not stop:
                raw = consumer.poll(timeout=1.0)
                if raw is None:
                    continue

                if raw.get("signal_id") is None:
                    dlq.publish("NULL_SIGNAL_ID", "signal_id missing or null", raw)
                    consumer.commit()
                    failed_dlq += 1
                    continue

                if not _is_valid(raw):
                    _log.warning("invalid_message_skipped", keys=list(raw.keys())[:20])
                    consumer.commit()
                    continue

                try:
                    inserted = history_repo.upsert(conn, raw)
                    artist_repo.upsert(conn, raw, new_track=inserted)
                except Exception as exc:
                    _log.error("db_error", signal_id=str(raw["signal_id"])[:8], exc_info=True)
                    conn.rollback()
                    dlq.publish("DB_FAILURE", "database error", raw)
                    consumer.commit()
                    failed_dlq += 1
                    continue

                try:
                    output_producer.produce(_OUTPUT_TOPIC, raw, key=raw["signal_id"])
                    unflushed = output_producer.flush(timeout=10.0)
                except Exception as exc:
                    _log.error("kafka_produce_error", signal_id=str(raw["signal_id"])[:8], error=str(exc))
                    conn.rollback()
                    dlq.publish("KAFKA_EMIT_FAILURE", "produce error", raw)
                    consumer.commit()
                    failed_dlq += 1
                    continue

                if unflushed > 0:
                    conn.rollback()
                    dlq.publish("KAFKA_EMIT_FAILURE", "flush timeout", raw)
                    consumer.commit()
                    failed_dlq += 1
                    continue

                conn.commit()
                consumer.commit()

                if inserted:
                    processed += 1
                    _log.info("processed", signal_id=str(raw["signal_id"])[:8])
                else:
                    already_seen += 1
        finally:
            consumer.close()

    _log.info(
        "history_tracker_stopped",
        processed=processed,
        failed_dlq=failed_dlq,
        already_seen=already_seen,
    )

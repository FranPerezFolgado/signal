import signal

import psycopg

from signal_common.kafka_consumer import KafkaJsonConsumer
from signal_common.kafka_producer import KafkaJsonProducer
from signal_common.logger import get_logger

from signal_history_tracker.artist_repository import ArtistRepository
from signal_history_tracker.dlq_publisher import DlqPublisher
from signal_history_tracker.history_repository import HistoryRepository
from signal_history_tracker.settings import Settings

_INPUT_TOPIC = "tracks.normalized"
_OUTPUT_TOPIC = "listening.history"
_CLIENT_ID = "history-tracker"

_log = get_logger(__name__)


def run_consumer(settings: Settings) -> None:
    consumer = KafkaJsonConsumer(
        settings.kafka_bootstrap_servers,
        settings.kafka_consumer_group,
        _CLIENT_ID,
    )
    producer = KafkaJsonProducer(settings.kafka_bootstrap_servers, client_id=_CLIENT_ID)
    history_repo = HistoryRepository()
    artist_repo = ArtistRepository()
    dlq = DlqPublisher(producer)

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

                try:
                    inserted = history_repo.upsert(conn, raw)
                    if inserted:
                        artist_repo.increment_play_count(conn, raw["artist"])
                except Exception as exc:
                    conn.rollback()
                    dlq.publish("DB_FAILURE", str(exc), raw)
                    consumer.commit()
                    failed_dlq += 1
                    continue

                producer.produce(_OUTPUT_TOPIC, raw, key=raw["signal_id"])
                unflushed = producer.flush(timeout=10.0)
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
                    _log.info("processed", signal_id=raw["signal_id"][:8])
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

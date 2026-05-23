import signal
from datetime import UTC, datetime

from signal_common.kafka_consumer import KafkaJsonConsumer
from signal_common.kafka_producer import KafkaJsonProducer
from signal_common.logger import get_logger

from signal_enricher.enricher import Enricher
from signal_enricher.settings import Settings

_INPUT_TOPIC = "tracks.normalized"
_OUTPUT_TOPIC = "tracks.enriched"
_CLIENT_ID = "enricher"

_log = get_logger(__name__)


def _is_valid(msg: dict) -> bool:
    return (
        isinstance(msg.get("signal_id"), str)
        and isinstance(msg.get("artist"), str)
        and isinstance(msg.get("title"), str)
    )


def run_consumer(settings: Settings) -> None:
    enricher = Enricher(settings)

    consumer = KafkaJsonConsumer(
        settings.kafka_bootstrap_servers,
        settings.kafka_consumer_group,
        _CLIENT_ID,
    )
    producer = KafkaJsonProducer(settings.kafka_bootstrap_servers, client_id=_CLIENT_ID)

    stop = False

    def _handle_signal(sig: int, _frame: object) -> None:
        nonlocal stop
        _log.info("shutdown_requested", signal=sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    consumer.subscribe([_INPUT_TOPIC])
    _log.info("enricher_started")

    try:
        while not stop:
            normalized = consumer.poll(timeout=1.0)
            if normalized is None:
                continue

            if not _is_valid(normalized):
                _log.warning("malformed_message_skipped", key_count=len(normalized))
                consumer.commit()
                continue

            signal_id = normalized.get("signal_id", "")
            artist = normalized.get("artist", "")
            processed_at = datetime.now(tz=UTC).isoformat()

            enriched = enricher.enrich(normalized)
            enriched["processed_at"] = processed_at

            producer.produce(_OUTPUT_TOPIC, enriched, key=signal_id)
            unflushed = producer.flush(timeout=10.0)
            if unflushed > 0:
                # Accept at-most-once for this message rather than risk
                # re-processing the same message in a tight loop.
                _log.error("kafka_flush_timeout", unflushed=unflushed, signal_id=signal_id[:8])
                consumer.commit()
                continue

            consumer.commit()
            _log.info(
                "enriched",
                signal_id=signal_id[:8],
                artist=artist,
                source=enriched.get("enrichment_source"),
                pending=enriched.get("pending_enrichment"),
            )
    finally:
        consumer.close()

    _log.info("enricher_stopped")

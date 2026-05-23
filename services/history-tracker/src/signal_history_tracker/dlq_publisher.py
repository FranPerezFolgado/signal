from datetime import UTC, datetime

from signal_common.kafka_producer import KafkaJsonProducer
from signal_common.logger import get_logger

_log = get_logger(__name__)


class DlqPublisher:
    def __init__(self, producer: KafkaJsonProducer, dlq_topic: str = "history-tracker.dlq") -> None:
        self._producer = producer
        self._dlq_topic = dlq_topic

    def publish(
        self,
        error_reason: str,
        error_detail: str,
        original_payload: dict | None,
    ) -> None:
        message = {
            "error_reason": error_reason,
            "error_detail": error_detail,
            "original_payload": original_payload,
            "failed_at": datetime.now(UTC).isoformat(),
        }
        try:
            self._producer.produce(self._dlq_topic, message)
            self._producer.flush(timeout=5.0)
        except Exception as exc:
            _log.error("dlq_emit_failed", error_reason=error_reason, error=str(exc))

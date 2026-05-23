from datetime import UTC, datetime

from signal_common.kafka_producer import KafkaJsonProducer
from signal_common.logger import get_logger

_log = get_logger(__name__)


class DlqPublisher:
    DLQ_TOPIC = "history-tracker.dlq"

    def __init__(self, producer: KafkaJsonProducer) -> None:
        self._producer = producer

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
            self._producer.produce(self.DLQ_TOPIC, message)
            self._producer.flush(timeout=5.0)
        except Exception as exc:
            _log.error("dlq_emit_failed", error_reason=error_reason, error=str(exc))

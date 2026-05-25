import json
from typing import Any

from confluent_kafka import Producer

from signal_common.logger import get_logger

_log = get_logger(__name__)


class KafkaJsonProducer:
    def __init__(self, bootstrap_servers: str, client_id: str) -> None:
        self._producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "client.id": client_id,
                "acks": "all",
            }
        )

    def produce(self, topic: str, value: dict[str, Any], key: str | None = None) -> None:
        self._producer.produce(
            topic=topic,
            value=json.dumps(value).encode(),
            key=key.encode() if key else None,
            on_delivery=self._on_delivery,
        )
        self._producer.poll(0)

    def flush(self, timeout: float = 10.0) -> int:
        return self._producer.flush(timeout)

    def _on_delivery(self, err: Any, msg: Any) -> None:
        if err:
            _log.error("kafka_delivery_failed", topic=msg.topic(), error=str(err))
        else:
            _log.debug("kafka_delivery_ok", topic=msg.topic(), partition=msg.partition())

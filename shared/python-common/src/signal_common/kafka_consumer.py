import json
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException

from signal_common.logger import get_logger

_log = get_logger(__name__)


class KafkaJsonConsumer:
    def __init__(self, bootstrap_servers: str, group_id: str, client_id: str) -> None:
        self._consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id,
                "client.id": client_id,
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
                "session.timeout.ms": 30000,
            }
        )

    def subscribe(self, topics: list[str]) -> None:
        self._consumer.subscribe(topics)
        _log.info("kafka_consumer_subscribed", topics=topics)

    def poll(self, timeout: float = 1.0) -> dict[str, Any] | None:
        msg = self._consumer.poll(timeout)
        if msg is None:
            return None
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                return None
            raise KafkaException(msg.error())
        return json.loads(msg.value().decode())

    def commit(self) -> None:
        self._consumer.commit(asynchronous=False)

    def close(self) -> None:
        self._consumer.close()
        _log.info("kafka_consumer_closed")

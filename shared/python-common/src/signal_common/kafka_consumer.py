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
        """Return the next deserialized JSON message, or None on timeout/EOF.

        Raises KafkaException on unrecoverable broker errors.
        Returns None (and logs a warning) if the message is not valid JSON —
        callers should commit and skip such messages rather than retrying forever.
        """
        msg = self._consumer.poll(timeout)
        if msg is None:
            return None
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                return None
            raise KafkaException(msg.error())
        try:
            return json.loads(msg.value().decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _log.warning(
                "kafka_message_decode_error",
                offset=msg.offset(),
                partition=msg.partition(),
                error=str(exc),
            )
            return None

    def commit(self) -> None:
        """Commit the latest polled offset synchronously.

        Only safe when called immediately after a single poll() — commits the
        most recently returned message's offset, not a specific message token.
        """
        self._consumer.commit(asynchronous=False)

    def close(self) -> None:
        self._consumer.close()
        _log.info("kafka_consumer_closed")

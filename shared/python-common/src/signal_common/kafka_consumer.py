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

        If the message cannot be decoded (malformed JSON/bytes), its offset is
        committed immediately so it is not re-delivered, then None is returned.
        Callers can therefore treat None as "nothing to process" in all cases.
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
            # Commit the bad message's offset so it is never re-delivered.
            # The message is permanently unprocessable — retrying would stall the pipeline.
            self._consumer.commit(message=msg, asynchronous=False)
            return None

    def commit(self) -> None:
        """Commit the latest successfully-processed message's offset synchronously.

        Call this only after both the DB write and Kafka emit for a message have
        succeeded. Committing on poll timeout would risk advancing past a message
        whose Kafka flush previously failed and was intentionally not committed.
        """
        self._consumer.commit(asynchronous=False)

    def close(self) -> None:
        self._consumer.close()
        _log.info("kafka_consumer_closed")

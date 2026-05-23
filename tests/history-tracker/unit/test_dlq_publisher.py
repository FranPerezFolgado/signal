from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from signal_history_tracker.dlq_publisher import DlqPublisher

_ERROR_REASONS = ["MALFORMED_JSON", "NULL_SIGNAL_ID", "DB_FAILURE", "KAFKA_EMIT_FAILURE"]


@pytest.fixture
def producer():
    return MagicMock()


@pytest.fixture
def publisher(producer):
    return DlqPublisher(producer)


@pytest.mark.parametrize("error_reason", _ERROR_REASONS)
def test_publish_message_shape(publisher, producer, error_reason):
    original = {"signal_id": "abc", "artist": "Radiohead"}
    publisher.publish(error_reason, "some detail", original)

    producer.produce.assert_called_once()
    topic, msg = producer.produce.call_args[0]
    assert topic == "history-tracker.dlq"
    assert msg["error_reason"] == error_reason
    assert msg["error_detail"] == "some detail"
    assert msg["original_payload"] == original
    assert "failed_at" in msg


def test_publish_with_none_original_payload(publisher, producer):
    publisher.publish("MALFORMED_JSON", "bad bytes", None)
    producer.produce.assert_called_once()
    _, msg = producer.produce.call_args[0]
    assert msg["original_payload"] is None


def test_publish_swallows_produce_exception(publisher, producer):
    producer.produce.side_effect = Exception("broker down")
    publisher.publish("DB_FAILURE", "oops", {"signal_id": "x"})


def test_publish_swallows_flush_exception(publisher, producer):
    producer.flush.side_effect = Exception("timeout")
    publisher.publish("DB_FAILURE", "oops", {"signal_id": "x"})


def test_failed_at_is_iso8601_utc(publisher, producer):
    publisher.publish("NULL_SIGNAL_ID", "missing", {})
    _, msg = producer.produce.call_args[0]
    failed_at = msg["failed_at"]
    parsed = datetime.fromisoformat(failed_at)
    assert parsed.tzinfo is not None

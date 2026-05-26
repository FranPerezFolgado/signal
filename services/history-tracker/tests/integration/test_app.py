"""Integration tests for history-tracker.

Requires live stack: `make up` (Kafka + PostgreSQL running).
Run with: uv run pytest services/history-tracker/tests/integration/ -v

These tests produce real Kafka messages and assert on PostgreSQL state.
"""
import json
import os
import time
import uuid

import psycopg
import pytest
from confluent_kafka import Consumer as KConsumer
from confluent_kafka import Producer

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://signal:signal@localhost:5432/signal")
INPUT_TOPIC = "tracks.enriched"
OUTPUT_TOPIC = "listening.history"
DLQ_TOPIC = "history-tracker.dlq"


def _make_signal_id() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex[:32]


def _produce(topic: str, value: dict, key: str | None = None) -> None:
    p = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})
    p.produce(topic, json.dumps(value).encode(), key=key.encode() if key else None)
    p.flush(timeout=10.0)


def _wait_for_row(conn: psycopg.Connection, signal_id: str, timeout: float = 10.0) -> dict | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("SELECT * FROM listening_history WHERE signal_id = %s", (signal_id,))
            row = cur.fetchone()
            if row:
                return row
        time.sleep(0.3)
    return None


def _get_play_count(conn: psycopg.Connection, artist_name: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute("SELECT play_count FROM artists WHERE LOWER(name) = LOWER(%s)", (artist_name,))
        row = cur.fetchone()
        return row[0] if row else None


def _get_scrobble_count(conn: psycopg.Connection, artist_name: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT scrobble_count FROM artists WHERE LOWER(name) = LOWER(%s)", (artist_name,)
        )
        row = cur.fetchone()
        return row[0] if row else None


def _make_consumer(group_suffix: str) -> KConsumer:
    return KConsumer({
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": f"test-{group_suffix}-{uuid.uuid4().hex[:8]}",
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
    })


def _wait_for_kafka_message(
    consumer: KConsumer, match_fn, timeout: float = 15.0
) -> dict | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        m = consumer.poll(1.0)
        if m and not m.error():
            payload = json.loads(m.value().decode())
            if match_fn(payload):
                return payload
    return None


@pytest.fixture(scope="module")
def db():
    with psycopg.connect(DATABASE_URL) as conn:
        yield conn


@pytest.mark.integration
def test_happy_path_persists_row_and_increments_play_count(db):
    signal_id = _make_signal_id()
    msg = {
        "signal_id": signal_id,
        "artist": "Radiohead",
        "artist_id": "spotify:artist:4Z8W4fKeB5YxbusRsdQVPb",
        "track_id": "spotify:track:t1",
        "title": "Karma Police",
        "genres": ["alternative rock"],
        "played_at": "2026-05-21T10:00:00+00:00",
        "sources": ["lastfm"],
        "artist_popularity": 75,
        "track_popularity": 60,
        "enrichment_source": "spotify",
        "pending_enrichment": False,
        "processed_at": "2026-05-21T10:00:01+00:00",
    }

    before_play = _get_play_count(db, "Radiohead") or 0
    before_scrobble = _get_scrobble_count(db, "Radiohead") or 0
    _produce(INPUT_TOPIC, msg, key=signal_id)

    row = _wait_for_row(db, signal_id)
    assert row is not None, "Row not found in listening_history after 10s"
    assert row["artist"] == "Radiohead"
    assert row["title"] == "Karma Police"
    assert row["signal_id"] == signal_id

    after_play = _get_play_count(db, "Radiohead") or 0
    after_scrobble = _get_scrobble_count(db, "Radiohead") or 0
    assert after_play == before_play + 1
    assert after_scrobble == before_scrobble + 1


@pytest.mark.integration
def test_repeat_play_increments_scrobble_not_play_count(db):
    signal_id = _make_signal_id()
    msg = {
        "signal_id": signal_id,
        "artist": "Radiohead",
        "artist_id": "spotify:artist:4Z8W4fKeB5YxbusRsdQVPb",
        "track_id": "spotify:track:t2",
        "title": "Creep",
        "genres": ["alternative rock"],
        "played_at": "2026-05-21T11:00:00+00:00",
        "sources": ["lastfm"],
        "artist_popularity": 80,
        "track_popularity": 70,
        "enrichment_source": "spotify",
        "pending_enrichment": False,
        "processed_at": "2026-05-21T11:00:01+00:00",
    }

    # First delivery: new track — both counts increment.
    _produce(INPUT_TOPIC, msg, key=signal_id)
    _wait_for_row(db, signal_id)
    before_play = _get_play_count(db, "Radiohead") or 0
    before_scrobble = _get_scrobble_count(db, "Radiohead") or 0

    # Second delivery: same signal_id — play_count must NOT increment, scrobble_count MUST.
    _produce(INPUT_TOPIC, msg, key=signal_id)

    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        if (_get_scrobble_count(db, "Radiohead") or 0) > before_scrobble:
            break
        time.sleep(0.3)

    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM listening_history WHERE signal_id = %s", (signal_id,))
        count = cur.fetchone()[0]
    assert count == 1, f"Expected 1 row in listening_history, got {count}"

    assert (
        (_get_play_count(db, "Radiohead") or 0) == before_play
    ), "play_count must not increment on repeat"
    assert (
        (_get_scrobble_count(db, "Radiohead") or 0) == before_scrobble + 1
    ), "scrobble_count must increment on repeat"


@pytest.mark.integration
def test_null_signal_id_goes_to_dlq(db):
    msg = {"artist": "Ghost", "title": "Some Track", "signal_id": None}

    c = _make_consumer("dlq-reader")
    c.subscribe([DLQ_TOPIC])
    c.poll(0.5)  # trigger partition assignment before produce

    _produce(INPUT_TOPIC, msg)

    dlq_msg = _wait_for_kafka_message(
        c, lambda p: p.get("error_reason") == "NULL_SIGNAL_ID"
    )
    c.close()

    assert dlq_msg is not None, "No NULL_SIGNAL_ID DLQ message received within 15s"
    assert dlq_msg["original_payload"]["artist"] == "Ghost"


@pytest.mark.integration
def test_pending_enrichment_message_persisted_and_forwarded(db):
    signal_id = _make_signal_id()
    msg = {
        "signal_id": signal_id,
        "artist": "Unknown Mortal Orchestra",
        "artist_id": None,
        "track_id": None,
        "title": "So Good At Being In Trouble",
        "genres": [],
        "played_at": "2026-05-21T12:00:00+00:00",
        "sources": ["lastfm"],
        "artist_popularity": None,
        "track_popularity": None,
        "enrichment_source": "pending",
        "pending_enrichment": True,
        "processed_at": "2026-05-21T12:00:01+00:00",
    }

    c = _make_consumer("output-reader")
    c.subscribe([OUTPUT_TOPIC])
    c.poll(0.5)  # trigger partition assignment before produce

    _produce(INPUT_TOPIC, msg, key=signal_id)

    row = _wait_for_row(db, signal_id)
    assert row is not None, "Pending-enrichment row not persisted within 10s"
    assert row["signal_id"] == signal_id

    forwarded = _wait_for_kafka_message(
        c, lambda p: p.get("signal_id") == signal_id
    )
    c.close()

    assert forwarded is not None, "Message not forwarded to listening.history within 15s"

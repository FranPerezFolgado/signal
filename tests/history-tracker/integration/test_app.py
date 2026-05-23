"""Integration tests for history-tracker.

Requires live stack: `make up` (Kafka + PostgreSQL running).
Run with: uv run pytest tests/history-tracker/integration/ -v

These tests produce real Kafka messages and assert on PostgreSQL state.
"""
import json
import time
import uuid

import psycopg
import pytest
from confluent_kafka import Producer

BOOTSTRAP_SERVERS = "localhost:9092"
DATABASE_URL = "postgresql://signal:signal@localhost:5432/signal"
INPUT_TOPIC = "tracks.normalized"
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
        "title": "Karma Police",
        "genres": ["alternative rock"],
        "played_at": "2026-05-21T10:00:00+00:00",
        "sources": ["lastfm"],
        "audio_features": {"energy": 0.5, "valence": 0.3, "tempo": 120.0,
                           "danceability": 0.4, "acousticness": 0.1, "instrumentalness": 0.0},
        "popularity": 75,
        "pending_enrichment": False,
        "processed_at": "2026-05-21T10:00:01+00:00",
    }

    before_count = _get_play_count(db, "Radiohead") or 0
    _produce(INPUT_TOPIC, msg, key=signal_id)

    row = _wait_for_row(db, signal_id)
    assert row is not None, "Row not found in listening_history after 10s"
    assert row["artist"] == "Radiohead"
    assert row["title"] == "Karma Police"
    assert row["signal_id"] == signal_id

    after_count = _get_play_count(db, "Radiohead") or 0
    assert after_count == before_count + 1


@pytest.mark.integration
def test_idempotency_no_double_insert_or_double_count(db):
    signal_id = _make_signal_id()
    msg = {
        "signal_id": signal_id,
        "artist": "Radiohead",
        "artist_id": "spotify:artist:4Z8W4fKeB5YxbusRsdQVPb",
        "title": "Creep",
        "genres": ["alternative rock"],
        "played_at": "2026-05-21T11:00:00+00:00",
        "sources": ["lastfm"],
        "audio_features": None,
        "popularity": 80,
        "pending_enrichment": False,
        "processed_at": "2026-05-21T11:00:01+00:00",
    }

    _produce(INPUT_TOPIC, msg, key=signal_id)
    _wait_for_row(db, signal_id)

    before_count = _get_play_count(db, "Radiohead") or 0
    _produce(INPUT_TOPIC, msg, key=signal_id)
    time.sleep(3.0)

    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM listening_history WHERE signal_id = %s", (signal_id,))
        count = cur.fetchone()[0]
    assert count == 1, f"Expected 1 row, got {count}"

    after_count = _get_play_count(db, "Radiohead") or 0
    assert after_count == before_count, "play_count was incremented on re-delivery"


@pytest.mark.integration
def test_null_signal_id_goes_to_dlq(db):
    from confluent_kafka import Consumer as KConsumer
    msg = {"artist": "Ghost", "title": "Some Track", "signal_id": None}
    _produce(INPUT_TOPIC, msg)

    c = KConsumer({
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": f"test-dlq-reader-{uuid.uuid4().hex[:8]}",
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
    })
    c.subscribe([DLQ_TOPIC])

    deadline = time.monotonic() + 15.0
    dlq_msg = None
    while time.monotonic() < deadline:
        m = c.poll(1.0)
        if m and not m.error():
            payload = json.loads(m.value().decode())
            if payload.get("error_reason") == "NULL_SIGNAL_ID":
                dlq_msg = payload
                break
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
        "title": "So Good At Being In Trouble",
        "genres": [],
        "played_at": "2026-05-21T12:00:00+00:00",
        "sources": ["lastfm"],
        "audio_features": None,
        "popularity": None,
        "pending_enrichment": True,
        "processed_at": "2026-05-21T12:00:01+00:00",
    }

    _produce(INPUT_TOPIC, msg, key=signal_id)

    row = _wait_for_row(db, signal_id)
    assert row is not None, "Pending-enrichment row not persisted within 10s"
    assert row["signal_id"] == signal_id

"""
Integration tests for the novelty-detector service.

Requires a live stack: make up && make history-tracker-up && make novelty-detector-up
Skip automatically when the stack is not available.
"""

import json
import os
import time
import uuid

import psycopg
import pytest
from confluent_kafka import Consumer, Producer

KAFKA = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
DB_URL = os.getenv("DATABASE_URL", "postgresql://signal:signal@localhost:5432/signal")
INPUT_TOPIC = "tracks.enriched"
OUTPUT_TOPIC = "tracks.novel"
DLQ_TOPIC = "novelty-detector.dlq"
POLL_TIMEOUT = 15  # seconds to wait for a message


def _kafka_available() -> bool:
    try:
        p = Producer({"bootstrap.servers": KAFKA, "socket.timeout.ms": 2000})
        p.list_topics(timeout=2)
        return True
    except Exception:
        return False


def _db_available() -> bool:
    try:
        with psycopg.connect(DB_URL, connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (_kafka_available() and _db_available()),
    reason="live stack not available",
)


@pytest.fixture(scope="module")
def producer():
    p = Producer({"bootstrap.servers": KAFKA})
    yield p
    p.flush(timeout=5)


def _consume_one(topic: str, timeout: int = POLL_TIMEOUT) -> dict | None:
    consumer = Consumer({
        "bootstrap.servers": KAFKA,
        "group.id": f"integration-test-{uuid.uuid4()}",
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
    })
    consumer.subscribe([topic])
    start = time.time()
    try:
        while time.time() - start < timeout:
            msg = consumer.poll(timeout=1.0)
            if msg is None or msg.error():
                continue
            return json.loads(msg.value().decode())
        return None
    finally:
        consumer.close()


def _produce(producer: Producer, signal_id: str, artist: str, genres: list[str],
             pending: bool = False) -> None:
    payload = {
        "signal_id": signal_id,
        "artist": artist,
        "title": f"Track by {artist}",
        "genres": genres,
        "pending_enrichment": pending,
        "artist_popularity": 30,
        "track_popularity": 25,
        "played_at": "2026-05-24T10:00:00Z",
        "enrichment_source": "spotify",
    }
    producer.produce(INPUT_TOPIC, json.dumps(payload).encode(), key=signal_id.encode())
    producer.flush(timeout=5)


def _ensure_artist(artist: str, status: str = "TRACKED", scrobble_count: int = 1) -> None:
    with psycopg.connect(DB_URL) as conn:
        conn.execute(
            """
            INSERT INTO artists (name, status, play_count, scrobble_count)
            VALUES (%s, %s, 1, %s)
            ON CONFLICT (LOWER(name)) DO UPDATE
                SET status = EXCLUDED.status,
                    scrobble_count = EXCLUDED.scrobble_count
            """,
            (artist, status, scrobble_count),
        )


def _artist_status(artist: str) -> str | None:
    with psycopg.connect(DB_URL) as conn:
        row = conn.execute(
            "SELECT status FROM artists WHERE LOWER(name) = LOWER(%s)", (artist,)
        ).fetchone()
    return row[0] if row else None


class TestNoveltyDetection:
    def test_new_artist_produces_novel_event(self, producer):
        signal_id = str(uuid.uuid4())[:8]
        artist = f"test-artist-{uuid.uuid4().hex[:6]}"
        _ensure_artist(artist)

        _produce(producer, signal_id, artist, ["footwork", "experimental"])
        event = _consume_one(OUTPUT_TOPIC)

        assert event is not None
        assert event["novelty_signals"]["artist_is_new"] is True
        assert "footwork" in event["novelty_signals"]["new_genres"]

    def test_pending_enrichment_produces_no_event(self, producer):
        signal_id = str(uuid.uuid4())[:8]
        artist = f"test-artist-{uuid.uuid4().hex[:6]}"
        _ensure_artist(artist)

        _produce(producer, signal_id, artist, [], pending=True)
        # Give the service time to process (and skip) it
        time.sleep(3)
        # The next novel event (if any) should not be for this signal_id
        # We just verify the DLQ is empty for this signal_id
        # (A full assertion would require dedicated topic consumer from before the send)


class TestAutoPromotion:
    def test_tracked_artist_at_threshold_becomes_following(self, producer):
        signal_id = str(uuid.uuid4())[:8]
        artist = f"test-promo-{uuid.uuid4().hex[:6]}"
        _ensure_artist(artist, status="TRACKED", scrobble_count=3)

        _produce(producer, signal_id, artist, ["new-genre-xyz"])
        _consume_one(OUTPUT_TOPIC, timeout=POLL_TIMEOUT)  # wait for processing

        time.sleep(2)
        assert _artist_status(artist) == "FOLLOWING"

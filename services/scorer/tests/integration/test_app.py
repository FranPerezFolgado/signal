"""
Integration tests for the scorer service.

Requires a live stack: make up (Kafka + PostgreSQL running).
Skip automatically when the stack is not available.
"""

import json
import os
import time
import uuid

import psycopg
import pytest
from confluent_kafka import Producer

KAFKA = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
DB_URL = os.getenv("DATABASE_URL", "postgresql://signal:signal@localhost:5432/signal")
INPUT_TOPIC = "tracks.novel"
DLQ_TOPIC = "scorer.dlq"


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


requires_stack = pytest.mark.skipif(
    not (_kafka_available() and _db_available()),
    reason="Live stack not available — run 'make up' first",
)


def _produce(topic: str, payload: dict) -> None:
    p = Producer({"bootstrap.servers": KAFKA})
    p.produce(topic, json.dumps(payload).encode())
    p.flush(timeout=10)


def _insert_test_artist(conn: psycopg.Connection, spotify_uri: str, name: str) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO artists (name, external_ids, status, high_priority)
            VALUES (%s, %s::jsonb, 'TRACKED', false)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (name, json.dumps({"spotify": spotify_uri})),
        )
        row = cur.fetchone()
        if row:
            conn.commit()
            return row[0]
        # Already existed — fetch it
        cur.execute("SELECT id FROM artists WHERE LOWER(name) = LOWER(%s)", (name,))
        return cur.fetchone()[0]


def _wait_for_recommendation(
    conn: psycopg.Connection, artist_id: uuid.UUID, timeout: int = 15
) -> dict | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT score, score_breakdown, evidence_tracks FROM artist_recommendations"
                " WHERE artist_id = %s",
                (str(artist_id),),
            )
            row = cur.fetchone()
        if row:
            return {"score": row[0], "score_breakdown": row[1], "evidence_tracks": row[2]}
        time.sleep(0.5)
    return None


@requires_stack
class TestScorerIntegration:
    def test_valid_message_creates_recommendation(self):
        signal_id = f"integ-{uuid.uuid4().hex[:8]}"
        spotify_uri = f"spotify:artist:integ{uuid.uuid4().hex[:8]}"
        artist_name = f"Test Artist {uuid.uuid4().hex[:6]}"

        with psycopg.connect(DB_URL) as conn:
            artist_uuid = _insert_test_artist(conn, spotify_uri, artist_name)
            # Clean up any existing recommendation for this artist
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM artist_recommendations WHERE artist_id = %s", (str(artist_uuid),)
                )
            conn.commit()

        msg = {
            "signal_id": signal_id,
            "artist": artist_name,
            "artist_id": spotify_uri,
            "artist_popularity": 20,
            "novelty_signals": {"genre_novelty_ratio": 0.8},
        }
        _produce(INPUT_TOPIC, msg)

        with psycopg.connect(DB_URL) as conn:
            rec = _wait_for_recommendation(conn, artist_uuid, timeout=15)

        assert rec is not None, "No recommendation row created within timeout"
        assert 0.0 <= rec["score"] <= 1.0
        assert "genre_novelty" in rec["score_breakdown"]
        assert "popularity_norm" in rec["score_breakdown"]
        assert signal_id in (rec["evidence_tracks"] or [])

    def test_idempotent_upsert_same_signal_id(self):
        signal_id = f"idem-{uuid.uuid4().hex[:8]}"
        spotify_uri = f"spotify:artist:idem{uuid.uuid4().hex[:8]}"
        artist_name = f"Idem Artist {uuid.uuid4().hex[:6]}"

        with psycopg.connect(DB_URL) as conn:
            artist_uuid = _insert_test_artist(conn, spotify_uri, artist_name)
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM artist_recommendations WHERE artist_id = %s", (str(artist_uuid),)
                )
            conn.commit()

        msg = {
            "signal_id": signal_id,
            "artist": artist_name,
            "artist_id": spotify_uri,
            "artist_popularity": 30,
            "novelty_signals": {"genre_novelty_ratio": 0.6},
        }
        _produce(INPUT_TOPIC, msg)
        _produce(INPUT_TOPIC, msg)  # second identical message

        time.sleep(5)  # let scorer process both

        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM artist_recommendations WHERE artist_id = %s",
                    (str(artist_uuid),),
                )
                count = cur.fetchone()[0]

        assert count == 1, f"Expected 1 recommendation row, got {count}"

"""
E2e test fixtures.

Injects a synthetic `tracks.enriched` message and verifies the full
history-tracker → novelty-detector → scorer pipeline writes a recommendation.

Requires a live stack: make up && make services-up (or the CI `services` profile).
Auto-skips when Kafka or PostgreSQL is unavailable.
"""

import json
import uuid

import psycopg
import pytest
from confluent_kafka import Producer

from helpers import DB_URL, KAFKA, stack_available

ENRICHED_TOPIC = "tracks.enriched"

requires_stack = pytest.mark.skipif(
    not stack_available(),
    reason="Live stack not available — run 'make up && make services-up' first",
)


@pytest.fixture(scope="function")
def e2e_artist():
    """Pre-insert a test artist, emit a tracks.enriched event, yield ids, then tear down."""
    run_id = uuid.uuid4().hex[:8]
    artist_name = f"e2e-artist-{run_id}"
    signal_id = f"e2e-{run_id}"
    artist_spotify_uri = f"spotify:artist:e2e{run_id}"

    # Pre-insert so scorer can resolve the artist regardless of service ordering
    with psycopg.connect(DB_URL) as conn:
        conn.execute(
            """
            INSERT INTO artists (name, external_ids, status, high_priority)
            VALUES (%s, %s::jsonb, 'TRACKED', false)
            ON CONFLICT DO NOTHING
            """,
            (artist_name, json.dumps({"spotify": artist_spotify_uri})),
        )

    payload = {
        "signal_id": signal_id,
        "artist": artist_name,
        "artist_id": artist_spotify_uri,
        "title": f"E2E Track {run_id}",
        "genres": [f"e2e-genre-{run_id}"],
        "artist_popularity": 15,
        "track_popularity": 10,
        "enrichment_source": "spotify",
        "pending_enrichment": False,
        "played_at": "2026-01-01T00:00:00Z",
        "processed_at": "2026-01-01T00:00:01Z",
    }

    producer = Producer({"bootstrap.servers": KAFKA})
    producer.produce(ENRICHED_TOPIC, json.dumps(payload).encode(), key=signal_id.encode())
    producer.flush(timeout=10)

    yield {"artist_name": artist_name, "signal_id": signal_id}

    # Teardown — remove test rows so re-runs start clean
    with psycopg.connect(DB_URL) as conn:
        conn.execute(
            """
            DELETE FROM artist_recommendations
            WHERE artist_id IN (
                SELECT id FROM artists WHERE LOWER(name) = LOWER(%s)
            )
            """,
            (artist_name,),
        )
        conn.execute(
            "DELETE FROM listening_history WHERE signal_id = %s", (signal_id,)
        )
        conn.execute(
            "DELETE FROM artists WHERE LOWER(name) = LOWER(%s)", (artist_name,)
        )

"""Shared helpers for e2e tests (not fixtures — import directly)."""

import os
import time

import psycopg
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient

KAFKA = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
DB_URL = os.getenv("DATABASE_URL", "postgresql://signal:signal@localhost:5432/signal")

# Consumer groups that must be STABLE (have active members) for the pipeline to work
_PIPELINE_GROUPS = ["scorer", "novelty-detector", "history-tracker-enriched-group"]


def kafka_available() -> bool:
    try:
        p = Producer({"bootstrap.servers": KAFKA, "socket.timeout.ms": 3000})
        p.list_topics(timeout=3)
        return True
    except Exception:
        return False


def db_available() -> bool:
    try:
        with psycopg.connect(DB_URL, connect_timeout=3):
            return True
    except Exception:
        return False


def stack_available() -> bool:
    return kafka_available() and db_available()


def services_healthy() -> bool:
    """Return True if all pipeline consumer groups have at least one active member.

    A group with no members means the service is running but not consuming (zombie
    state after a Kafka session timeout). The e2e test will hang for its full timeout
    if this is not caught upfront.
    """
    try:
        admin = AdminClient({"bootstrap.servers": KAFKA, "socket.timeout.ms": 3000})
        futures = admin.describe_consumer_groups(_PIPELINE_GROUPS)
        for group_id in _PIPELINE_GROUPS:
            group = futures[group_id].result(timeout=5)
            if not group.members:
                return False
        return True
    except Exception:
        return False


def wait_for_recommendation(artist_name: str, timeout: int = 60) -> dict | None:
    """Poll artist_recommendations by artist name until a row appears or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with psycopg.connect(DB_URL, connect_timeout=5) as conn:
                row = conn.execute(
                    """
                    SELECT ar.score, ar.score_breakdown, ar.evidence_tracks
                    FROM artist_recommendations ar
                    JOIN artists a ON a.id = ar.artist_id
                    WHERE LOWER(a.name) = LOWER(%s)
                    """,
                    (artist_name,),
                ).fetchone()
            if row:
                return {"score": row[0], "score_breakdown": row[1], "evidence_tracks": row[2]}
        except psycopg.OperationalError:
            pass  # transient DB issue — retry on next iteration
        time.sleep(5)
    return None

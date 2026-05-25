import signal
import time
from uuid import UUID

import psycopg
from psycopg import OperationalError as _PsycopgOperationalError
from signal_common.kafka_consumer import KafkaJsonConsumer
from signal_common.kafka_producer import KafkaJsonProducer
from signal_common.logger import get_logger

from signal_scorer.dlq_publisher import DlqPublisher
from signal_scorer.scoring import compute_score, validate_message
from signal_scorer.settings import Settings

_CLIENT_ID = "scorer"

_log = get_logger(__name__)


def lookup_artist(
    conn: psycopg.Connection,
    spotify_artist_id: str | None,
    artist_name: str,
) -> tuple[UUID, bool] | None:
    """Return (artist_uuid, high_priority) or None if not found via either lookup."""
    # Step 1: lookup by Spotify URI (skipped if artist_id is null/empty)
    if spotify_artist_id:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, high_priority FROM artists"
                " WHERE external_ids->>'spotify' = %s LIMIT 2",
                (spotify_artist_id,),
            )
            rows = cur.fetchall()
        if len(rows) > 1:
            _log.warning("artist_lookup_multiple_matches", spotify_id=spotify_artist_id[:16])
        if rows:
            return rows[0][0], rows[0][1]

    # Step 2: fallback by case-insensitive name
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, high_priority FROM artists WHERE LOWER(name) = LOWER(%s) LIMIT 2",
            (artist_name,),
        )
        rows = cur.fetchall()
    if len(rows) > 1:
        _log.warning("artist_name_lookup_multiple_matches", artist=artist_name)
    if rows:
        return rows[0][0], rows[0][1]

    return None


def upsert_recommendation(
    conn: psycopg.Connection,
    artist_uuid: UUID,
    score: float,
    breakdown: dict,
    signal_id: str,
) -> None:
    """Upsert artist_recommendations row. updated_at always refreshed; score/evidence only on improvement."""
    import json

    breakdown_json = json.dumps(breakdown)
    signal_id_json = json.dumps([signal_id])

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO artist_recommendations
                (artist_id, score, score_breakdown, evidence_tracks, updated_at)
            VALUES
                (%s, %s, %s::jsonb, %s::jsonb, now())
            ON CONFLICT (artist_id) DO UPDATE SET
                score = CASE
                    WHEN EXCLUDED.score > artist_recommendations.score THEN EXCLUDED.score
                    ELSE artist_recommendations.score
                END,
                score_breakdown = CASE
                    WHEN EXCLUDED.score > artist_recommendations.score THEN EXCLUDED.score_breakdown
                    ELSE artist_recommendations.score_breakdown
                END,
                evidence_tracks = CASE
                    WHEN EXCLUDED.score > artist_recommendations.score
                     AND NOT (artist_recommendations.evidence_tracks @> %s::jsonb)
                    THEN artist_recommendations.evidence_tracks || %s::jsonb
                    ELSE artist_recommendations.evidence_tracks
                END,
                updated_at = now()
            """,
            (str(artist_uuid), score, breakdown_json, signal_id_json, signal_id_json, signal_id_json),
        )
    conn.commit()


def run_consumer(settings: Settings) -> None:
    consumer = KafkaJsonConsumer(
        settings.kafka_bootstrap_servers,
        settings.kafka_consumer_group,
        _CLIENT_ID,
    )
    dlq_producer = KafkaJsonProducer(
        settings.kafka_bootstrap_servers, client_id=f"{_CLIENT_ID}-dlq"
    )
    dlq = DlqPublisher(dlq_producer, settings.kafka_dlq_topic)

    total_consumed = 0
    total_upserted = 0
    total_dlq = 0
    total_errors = 0

    stop = False

    def _handle_signal(sig: int, _frame: object) -> None:
        nonlocal stop
        _log.info("shutdown_requested", signal=sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    consumer.subscribe([settings.kafka_input_topic])
    _log.info("scorer_started", topic=settings.kafka_input_topic)

    try:
        with psycopg.connect(settings.database_url) as conn:
            while not stop:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue

                total_consumed += 1
                t_start = time.monotonic()

                try:
                    validate_message(msg)
                except ValueError as exc:
                    _log.warning("validation_failed", error=str(exc))
                    dlq.publish(
                        error_reason="validation_failed",
                        error_detail=str(exc),
                        original_payload=msg,
                    )
                    total_dlq += 1
                    consumer.commit()
                    _maybe_log_stats(
                        total_consumed, total_upserted, total_dlq, total_errors,
                        settings.scorer_stats_interval,
                    )
                    continue

                signal_id: str = msg["signal_id"]
                artist: str = msg["artist"]
                spotify_artist_id: str | None = msg.get("artist_id") or None
                artist_popularity: int | None = msg.get("artist_popularity")
                ratio: float = msg["novelty_signals"]["genre_novelty_ratio"]

                try:
                    result = lookup_artist(conn, spotify_artist_id, artist)
                    if result is None:
                        dlq.publish(
                            error_reason="artist_not_found",
                            error_detail="artist not resolvable by Spotify URI or name",
                            original_payload=msg,
                        )
                        total_dlq += 1
                        consumer.commit()
                        _maybe_log_stats(
                            total_consumed, total_upserted, total_dlq, total_errors,
                            settings.scorer_stats_interval,
                        )
                        continue

                    artist_uuid, high_priority = result
                    score, breakdown = compute_score(
                        ratio, artist_popularity, high_priority,
                        settings.w1, settings.w2, settings.hp_bonus,
                    )

                    upsert_recommendation(conn, artist_uuid, score, breakdown, signal_id)

                    duration_ms = round((time.monotonic() - t_start) * 1000, 1)
                    _log.info(
                        "scored",
                        artist=artist,
                        score=round(score, 4),
                        breakdown=breakdown,
                        duration_ms=duration_ms,
                    )

                    total_upserted += 1
                    consumer.commit()

                except _PsycopgOperationalError:
                    raise

                except Exception as exc:
                    _log.error("processing_error", signal_id=signal_id[:8], error=str(exc))
                    dlq.publish(
                        error_reason="processing_error",
                        error_detail="unexpected error during scoring",
                        original_payload=msg,
                    )
                    total_errors += 1
                    total_dlq += 1
                    consumer.commit()

                _maybe_log_stats(
                    total_consumed, total_upserted, total_dlq, total_errors,
                    settings.scorer_stats_interval,
                )

    finally:
        _log.info(
            "scorer_stopped",
            total_consumed=total_consumed,
            total_upserted=total_upserted,
            total_dlq=total_dlq,
            total_errors=total_errors,
        )
        consumer.close()


def _maybe_log_stats(
    consumed: int, upserted: int, dlq: int, errors: int, interval: int
) -> None:
    if consumed % interval == 0:
        _log.info(
            "stats",
            total_consumed=consumed,
            total_upserted=upserted,
            total_dlq=dlq,
            total_errors=errors,
        )

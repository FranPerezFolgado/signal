import signal
from datetime import UTC, datetime

import psycopg

from signal_common.kafka_consumer import KafkaJsonConsumer
from signal_common.kafka_producer import KafkaJsonProducer
from signal_common.logger import get_logger

from signal_normalizer.artist_repository import ArtistRepository
from signal_normalizer.enricher import Enricher
from signal_normalizer.lastfm_client import LastfmFallbackClient
from signal_normalizer.settings import Settings
from signal_normalizer.signal_id import compute_signal_id
from signal_normalizer.spotify_client import SpotifyClient

_INPUT_TOPIC = "raw.plays"
_OUTPUT_TOPIC = "tracks.normalized"
_CLIENT_ID = "normalizer"

_log = get_logger(__name__)


def _is_valid(msg: dict) -> bool:
    artist = msg.get("artist")
    title = msg.get("title")
    return (
        isinstance(artist, str)
        and bool(artist.strip())
        and len(artist) <= 500
        and isinstance(title, str)
        and bool(title.strip())
        and len(title) <= 500
    )


def _build_output(raw: dict, signal_id: str, result, processed_at: str) -> dict:
    audio = None
    if result.audio_features is not None:
        audio = {
            "energy": result.audio_features.energy,
            "valence": result.audio_features.valence,
            "tempo": result.audio_features.tempo,
            "danceability": result.audio_features.danceability,
            "acousticness": result.audio_features.acousticness,
            "instrumentalness": result.audio_features.instrumentalness,
        }
    return {
        "signal_id": signal_id,
        "artist": raw["artist"],
        "artist_id": result.artist_id,
        "title": raw["title"],
        "genres": result.genres,
        "sources": [raw.get("source", "lastfm")],
        "played_at": raw.get("played_at"),
        "audio_features": audio,
        "popularity": result.popularity,
        "pending_enrichment": result.pending_enrichment,
        "processed_at": processed_at,
    }


def run_consumer(settings: Settings) -> None:
    spotify = SpotifyClient(
        settings.spotify_client_id,
        settings.spotify_client_secret,
        settings.spotify_refresh_token,
        settings.spotify_max_retries,
    )
    lastfm = LastfmFallbackClient(settings.lastfm_api_key)
    enricher = Enricher(spotify, lastfm)

    consumer = KafkaJsonConsumer(
        settings.kafka_bootstrap_servers,
        settings.kafka_consumer_group,
        _CLIENT_ID,
    )
    producer = KafkaJsonProducer(settings.kafka_bootstrap_servers, client_id=_CLIENT_ID)
    repo = ArtistRepository()

    stop = False

    def _handle_signal(sig: int, _frame: object) -> None:
        nonlocal stop
        _log.info("shutdown_requested", signal=sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    consumer.subscribe([_INPUT_TOPIC])
    _log.info("normalizer_started")

    # Single DB connection for the lifetime of this consumer run.
    # psycopg.connect() as a context manager commits on clean exit / rolls back on error.
    with psycopg.connect(settings.database_url) as conn:
        try:
            while not stop:
                raw = consumer.poll(timeout=1.0)
                if raw is None:
                    # None from poll() means timeout, EOF, or a decode error (already logged).
                    # Commit the offset so a permanently-bad message is not redelivered.
                    consumer.commit()
                    continue

                if not _is_valid(raw):
                    _log.warning("malformed_message_skipped", keys=list(raw.keys()))
                    consumer.commit()
                    continue

                artist = raw["artist"]
                title = raw["title"]

                result = enricher.enrich(artist, title)
                signal_id = compute_signal_id(artist, title)
                processed_at = datetime.now(tz=UTC).isoformat()
                enriched = _build_output(raw, signal_id, result, processed_at)

                # DB write — part of the open transaction
                repo.upsert_tracked(conn, artist, result.artist_id, result.genres)

                # Kafka emit — must succeed before we commit the DB or the offset
                producer.produce(_OUTPUT_TOPIC, enriched, key=signal_id)
                unflushed = producer.flush(timeout=10.0)
                if unflushed > 0:
                    # Emit timed out: roll back DB write, do not commit Kafka offset.
                    # Message will be redelivered and reprocessed on restart.
                    conn.rollback()
                    _log.error(
                        "kafka_flush_timeout_rolling_back",
                        unflushed=unflushed,
                        signal_id=signal_id[:8],
                    )
                    continue

                # Both side effects succeeded — commit DB then advance Kafka offset
                conn.commit()
                consumer.commit()

                _log.info(
                    "processed",
                    signal_id=signal_id[:8],
                    artist=artist,
                    source=result.enrichment_source,
                    pending=result.pending_enrichment,
                )
        finally:
            consumer.close()

    _log.info("normalizer_stopped")

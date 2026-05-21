import signal
from dataclasses import asdict
from datetime import UTC, datetime

from signal_common.db import get_connection
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
_GROUP_ID = "normalizer-group"
_CLIENT_ID = "normalizer"

_log = get_logger(__name__)


def _is_valid(msg: dict) -> bool:
    return bool(msg.get("artist")) and bool(msg.get("title"))


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
        "played": True,
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

    consumer = KafkaJsonConsumer(settings.kafka_bootstrap_servers, _GROUP_ID, _CLIENT_ID)
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

    while not stop:
        raw = consumer.poll(timeout=1.0)
        if raw is None:
            continue

        if not _is_valid(raw):
            _log.warning("malformed_message_skipped", keys=list(raw.keys()))
            continue

        artist = raw["artist"]
        title = raw["title"]

        result = enricher.enrich(artist, title)
        signal_id = compute_signal_id(artist, title)
        processed_at = datetime.now(tz=UTC).isoformat()
        enriched = _build_output(raw, signal_id, result, processed_at)

        with get_connection(settings.database_url) as conn:
            repo.upsert_tracked(conn, artist, result.artist_id, result.genres)

        producer.produce(_OUTPUT_TOPIC, enriched, key=signal_id)
        producer.flush()
        consumer.commit()

        _log.info(
            "processed",
            signal_id=signal_id[:8],
            artist=artist,
            source=result.enrichment_source,
            pending=result.pending_enrichment,
        )

    consumer.close()
    _log.info("normalizer_stopped")

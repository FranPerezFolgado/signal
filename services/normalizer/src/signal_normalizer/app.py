import signal
from datetime import UTC, datetime

from signal_common.circuit_breaker import CircuitBreaker
from signal_common.kafka_consumer import KafkaJsonConsumer
from signal_common.kafka_producer import KafkaJsonProducer
from signal_common.logger import get_logger
from signal_common.rate_limiter import RateLimiter
from signal_common.spotify import SpotifyServiceError

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


def _build_output(raw: dict, signal_id: str, artist_id: str | None, track_id: str | None, processed_at: str) -> dict:
    source = raw.get("source", "lastfm")
    return {
        "signal_id": signal_id,
        "artist": raw["artist"],
        "artist_id": artist_id,
        "track_id": track_id,
        "title": raw["title"],
        "sources": [source],
        "played": source == "lastfm",
        "played_at": raw.get("played_at"),
        "processed_at": processed_at,
    }


def run_consumer(settings: Settings) -> None:
    rate_limiter = RateLimiter(settings.spotify_rate_limit_per_30s)
    circuit_breaker = CircuitBreaker(
        settings.circuit_breaker_failure_threshold,
        settings.circuit_breaker_timeout_s,
    )
    spotify = SpotifyClient(
        settings.spotify_client_id,
        settings.spotify_client_secret,
        settings.spotify_refresh_token,
        settings.spotify_timeout,
        rate_limiter=rate_limiter,
        retry_after_default=settings.spotify_retry_after_default_s,
        retry_after_max=settings.spotify_retry_after_max_s,
    )

    consumer = KafkaJsonConsumer(
        settings.kafka_bootstrap_servers,
        settings.kafka_consumer_group,
        _CLIENT_ID,
    )
    producer = KafkaJsonProducer(settings.kafka_bootstrap_servers, client_id=_CLIENT_ID)

    stop = False

    def _handle_signal(sig: int, _frame: object) -> None:
        nonlocal stop
        _log.info("shutdown_requested", signal=sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    consumer.subscribe([_INPUT_TOPIC])
    _log.info("normalizer_started")

    try:
        while not stop:
            raw = consumer.poll(timeout=1.0)
            if raw is None:
                continue

            if not _is_valid(raw):
                _log.warning("malformed_message_skipped", keys=list(raw.keys())[:20])
                consumer.commit()
                continue

            artist = raw["artist"]
            title = raw["title"]
            signal_id = compute_signal_id(artist, title)

            if circuit_breaker.should_allow():
                try:
                    artist_id, track_id = spotify.search_track(artist, title)
                    circuit_breaker.record_success()
                except SpotifyServiceError:
                    circuit_breaker.record_failure()
                    artist_id, track_id = None, None
            else:
                _log.warning("circuit_open_skipping_spotify", artist=artist)
                artist_id, track_id = None, None

            processed_at = datetime.now(tz=UTC).isoformat()
            normalized = _build_output(raw, signal_id, artist_id, track_id, processed_at)

            producer.produce(_OUTPUT_TOPIC, normalized, key=signal_id)
            unflushed = producer.flush(timeout=10.0)
            if unflushed > 0:
                _log.error("kafka_flush_timeout", unflushed=unflushed, signal_id=signal_id[:8])
                continue

            consumer.commit()
            _log.info("processed", signal_id=signal_id[:8], artist=artist, spotify_resolved=artist_id is not None)
    finally:
        consumer.close()

    _log.info("normalizer_stopped")

import signal
import time

import psycopg
from psycopg import Error as _PsycopgError
from signal_common.circuit_breaker import CircuitBreaker
from signal_common.kafka_producer import KafkaJsonProducer
from signal_common.logger import get_logger
from signal_common.rate_limiter import RateLimiter
from signal_common.spotify import SpotifyServiceError

from signal_artist_tracker.artist_repository import ArtistRepository
from signal_artist_tracker.settings import Settings
from signal_artist_tracker.spotify_client import SpotifyClient

_log = get_logger(__name__)


def _build_track_message(track: dict, artist_row: dict) -> dict:
    artist_uri = artist_row["external_ids"]["spotify"]
    return {
        "source": "spotify",
        "artist": artist_row["name"],
        "artist_id": artist_uri,
        "track_id": f"spotify:track:{track['id']}",
        "title": track["name"],
        "origin": {
            "type": "ARTIST_TOP_TRACKS",
            "origin_artist_id": artist_uri,
        },
    }


def run_polling(settings: Settings) -> None:
    rate_limiter = RateLimiter(settings.artist_tracker_rate_limit_per_30s)
    circuit_breaker = CircuitBreaker(
        failure_threshold=settings.circuit_breaker_failure_threshold,
        timeout_s=settings.circuit_breaker_timeout_s,
    )
    spotify = SpotifyClient(
        settings.spotify_client_id,
        settings.spotify_client_secret,
        settings.spotify_refresh_token,
        timeout=settings.spotify_timeout,
        rate_limiter=rate_limiter,
        retry_after_default=settings.spotify_retry_after_default_s,
        retry_after_max=settings.spotify_retry_after_max_s,
    )
    producer = KafkaJsonProducer(settings.kafka_bootstrap_servers, client_id="artist-tracker")
    artist_repo = ArtistRepository()

    stop = False

    def _handle_signal(sig: int, _frame: object) -> None:
        nonlocal stop
        _log.info("shutdown_requested", signal=sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    _log.info(
        "artist_tracker_started",
        interval_hours=settings.artist_tracker_interval_hours,
        reexplore_days=settings.artist_reexplore_days,
    )

    while not stop:
        _run_cycle(settings, spotify, circuit_breaker, producer, artist_repo)
        if not stop:
            sleep_s = settings.artist_tracker_interval_hours * 3600
            _log.info("cycle_sleeping", sleep_hours=settings.artist_tracker_interval_hours)
            _interruptible_sleep(sleep_s, lambda: stop)

    _log.info("artist_tracker_stopped")


def _run_cycle(
    settings: Settings,
    spotify: SpotifyClient,
    circuit_breaker: CircuitBreaker,
    producer: KafkaJsonProducer,
    artist_repo: ArtistRepository,
) -> None:
    try:
        conn = psycopg.connect(settings.database_url)
    except _PsycopgError as exc:
        _log.error("db_connection_failed", error=type(exc).__name__)
        return

    try:
        artists = artist_repo.get_eligible(conn, settings.artist_reexplore_days)
    except _PsycopgError as exc:
        _log.error("db_get_eligible_failed", error=type(exc).__name__)
        conn.close()
        return

    explored = skipped = failed = 0
    _log.info("cycle_start", eligible_count=len(artists))

    for artist_row in artists:
        artist_name = artist_row["name"]
        external_ids = artist_row.get("external_ids") or {}

        if "spotify" not in external_ids:
            _log.warning("artist_no_spotify_id", artist=artist_name)
            skipped += 1
            continue

        if not circuit_breaker.should_allow():
            _log.warning("circuit_open_skipping_artist", artist=artist_name)
            skipped += 1
            continue

        try:
            tracks = spotify.get_top_tracks(external_ids["spotify"])
            circuit_breaker.record_success()
        except SpotifyServiceError as exc:
            _log.error("artist_spotify_error", artist=artist_name, error=str(exc))
            circuit_breaker.record_failure()
            failed += 1
            continue

        for track in tracks:
            msg = _build_track_message(track, artist_row)
            producer.produce(settings.kafka_output_topic, msg, key=external_ids["spotify"])

        if tracks:
            unflushed = producer.flush(timeout=10.0)
            if unflushed > 0:
                # Messages remain buffered and will drain on the next flush.
                # Still mark explored to avoid duplicate delivery on the next cycle.
                _log.warning("kafka_flush_timeout", artist=artist_name, unflushed=unflushed)

        try:
            artist_repo.mark_explored(conn, artist_row["id"])
        except _PsycopgError as exc:
            _log.error("db_mark_explored_failed", artist=artist_name, error=type(exc).__name__)
            failed += 1
            continue

        _log.info("artist_explored", artist=artist_name, track_count=len(tracks))
        explored += 1

    conn.close()
    _log.info("cycle_complete", explored=explored, skipped=skipped, failed=failed)


def _interruptible_sleep(total_s: float, should_stop) -> None:
    deadline = time.monotonic() + total_s
    while time.monotonic() < deadline:
        if should_stop():
            break
        time.sleep(min(1.0, deadline - time.monotonic()))

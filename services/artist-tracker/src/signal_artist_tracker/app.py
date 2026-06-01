import contextlib
import signal
import time

import psycopg
from psycopg import Error as _PsycopgError
from psycopg import InterfaceError as _InterfaceError
from psycopg import OperationalError as _OperationalError
from signal_common.circuit_breaker import CircuitBreaker
from signal_common.kafka_producer import KafkaJsonProducer
from signal_common.logger import get_logger
from signal_common.rate_limiter import RateLimiter
from signal_common.spotify import SpotifyResourceError, SpotifyServiceError

from signal_artist_tracker.artist_repository import ArtistRepository
from signal_artist_tracker.lastfm_client import LastfmSimilarClient, SimilarArtist
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


def _build_discovery_message(similar: SimilarArtist, origin_row: dict) -> dict:
    msg: dict = {
        "artist_name": similar.name,
        "source": "LASTFM_SIMILAR",
        "origin_artist_id": str(origin_row["id"]),
        "origin_artist_name": origin_row["name"],
    }
    if similar.mbid:
        msg["lastfm_mbid"] = similar.mbid
    return msg


def _run_similar_expansion_cycle(
    settings: Settings,
    lastfm: LastfmSimilarClient,
    producer: KafkaJsonProducer,
    artist_repo: ArtistRepository,
) -> None:
    try:
        conn = psycopg.connect(settings.database_url)
    except _PsycopgError as exc:
        _log.error("db_connection_failed", error=type(exc).__name__)
        return

    try:
        interval = settings.lastfm_similar_interval_hours
        artists = artist_repo.get_eligible_for_expansion(conn, interval)
    except _PsycopgError as exc:
        _log.error("db_get_eligible_for_expansion_failed", error=type(exc).__name__)
        conn.close()
        return

    inserted = skipped = failed = name_conflicts = 0
    _log.info("similar_expansion_cycle_start", eligible_count=len(artists))

    try:
        for artist_row in artists:
            try:
                similar_artists = lastfm.get_similar(
                    artist_row["name"], settings.lastfm_similar_limit
                )

                for similar in similar_artists:
                    if similar.mbid is not None:
                        found = artist_repo.find_by_mbid(conn, similar.mbid)
                        if found is not None:
                            _, existing_status = found
                            _log.info(
                                "similar_artist_skipped",
                                artist=similar.name,
                                existing_status=existing_status,
                                source_artist=artist_row["name"],
                            )
                            skipped += 1
                            continue

                    new_id = artist_repo.insert_similar_artist(
                        conn, similar.name, similar.mbid, artist_row["id"]
                    )
                    if new_id is not None:
                        msg = _build_discovery_message(similar, artist_row)
                        producer.produce(
                            settings.kafka_discovered_topic, msg, key=similar.name
                        )
                        inserted += 1
                    else:
                        name_conflicts += 1

                artist_repo.mark_similar_explored(conn, artist_row["id"])
            except (_OperationalError, _InterfaceError) as exc:
                _log.error(
                    "similar_expansion_db_connection_lost",
                    artist=artist_row["name"],
                    error=type(exc).__name__,
                )
                failed += 1
                break
            except Exception as exc:  # noqa: BLE001
                with contextlib.suppress(_PsycopgError):
                    conn.rollback()
                _log.warning(
                    "similar_expansion_artist_failed",
                    artist=artist_row["name"],
                    error=type(exc).__name__,
                )
                failed += 1
    finally:
        unflushed = producer.flush(timeout=10.0)
        if unflushed > 0:
            _log.warning("kafka_flush_timeout_expansion", unflushed=unflushed)
        conn.close()

    _log.info(
        "similar_expansion_cycle_complete",
        source_artists=len(artists),
        new_artists=inserted,
        skipped=skipped,
        name_conflicts=name_conflicts,
        failed=failed,
    )


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
    lastfm_rate_limiter = RateLimiter(settings.lastfm_similar_rate_limit_per_30s)
    lastfm = LastfmSimilarClient(settings.lastfm_api_key, lastfm_rate_limiter)
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
        similar_interval_hours=settings.lastfm_similar_interval_hours,
    )

    top_tracks_deadline = time.monotonic()
    similar_deadline = time.monotonic()

    while not stop:
        now = time.monotonic()

        if now >= top_tracks_deadline:
            _run_cycle(settings, spotify, circuit_breaker, producer, artist_repo)
            top_tracks_deadline = time.monotonic() + settings.artist_tracker_interval_hours * 3600

        if now >= similar_deadline:
            _run_similar_expansion_cycle(settings, lastfm, producer, artist_repo)
            similar_deadline = time.monotonic() + settings.lastfm_similar_interval_hours * 3600

        if not stop:
            next_wake = min(top_tracks_deadline, similar_deadline)
            sleep_s = max(0.0, next_wake - time.monotonic())
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
        except SpotifyResourceError as exc:
            _log.warning("artist_spotify_skipped", artist=artist_name, error=str(exc))
            skipped += 1
            continue
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

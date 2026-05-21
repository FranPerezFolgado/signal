import signal
import time

from signal_common.checkpoint import CheckpointRepository
from signal_common.db import get_connection
from signal_common.kafka_producer import KafkaJsonProducer
from signal_common.logger import get_logger

from .client import LastfmClient
from .converter import to_raw_play
from .settings import Settings

_SERVICE = "lastfm-ingester"
_TOPIC = "raw.plays"

_log = get_logger(__name__)


def _make_key(artist: str, title: str) -> str:
    return f"{artist}|{title}".lower()


def _ingest_page(
    client: LastfmClient, producer: KafkaJsonProducer, from_uts: int | None, page: int
) -> tuple[int, int]:
    """Fetches one page, produces to Kafka. Returns (emitted_count, total_pages)."""
    result = client.get_recent_tracks(from_uts=from_uts, page=page)
    emitted = 0
    for track in result.tracks:
        play = to_raw_play(track)
        if play is None:
            continue
        producer.produce(_TOPIC, play, key=_make_key(play["artist"], play["title"]))
        emitted += 1
    producer.flush()
    return emitted, result.total_pages


def run_polling(settings: Settings) -> None:
    client = LastfmClient(settings.lastfm_api_key, settings.lastfm_username)
    producer = KafkaJsonProducer(settings.kafka_bootstrap_servers, client_id=_SERVICE)

    stop = False

    def _handle_signal(sig: int, _frame: object) -> None:
        nonlocal stop
        _log.info("shutdown_requested", signal=sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    _log.info("polling_started", interval_seconds=settings.lastfm_poll_interval_seconds)
    while not stop:
        with get_connection(settings.database_url) as conn:
            repo = CheckpointRepository(conn)
            checkpoint = repo.get(_SERVICE)
            from_uts = int(checkpoint.last_played_at.timestamp()) if checkpoint else None

            emitted, _ = _ingest_page(client, producer, from_uts=from_uts, page=1)

            if emitted > 0:
                _log.info("poll_done", emitted=emitted)
                # checkpoint is updated to now so next poll only fetches new plays
                from datetime import UTC, datetime

                repo.upsert(_SERVICE, datetime.now(tz=UTC))

        if not stop:
            time.sleep(settings.lastfm_poll_interval_seconds)

    producer.flush()
    _log.info("polling_stopped")


def run_backfill(settings: Settings) -> None:
    client = LastfmClient(settings.lastfm_api_key, settings.lastfm_username)
    producer = KafkaJsonProducer(settings.kafka_bootstrap_servers, client_id=_SERVICE)

    _log.info("backfill_started")
    page = 1
    total_emitted = 0

    while True:
        emitted, total_pages = _ingest_page(client, producer, from_uts=None, page=page)
        total_emitted += emitted
        _log.info("backfill_page", page=page, total_pages=total_pages, emitted=emitted)

        if page >= total_pages:
            break
        page += 1

    from datetime import UTC, datetime

    with get_connection(settings.database_url) as conn:
        CheckpointRepository(conn).upsert(_SERVICE, datetime.now(tz=UTC))

    _log.info("backfill_done", total_emitted=total_emitted)

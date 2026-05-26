import signal as _signal
from unittest.mock import MagicMock, patch

import psycopg as _psycopg
from signal_common.spotify import SpotifyServiceError


def _make_settings():
    s = MagicMock()
    s.kafka_bootstrap_servers = "localhost:9092"
    s.database_url = "postgresql://signal:signal@localhost:5432/signal"
    s.kafka_output_topic = "raw.tracks"
    s.artist_tracker_interval_hours = 0.0001  # minimal sleep in tests
    s.artist_reexplore_days = 7
    s.artist_tracker_rate_limit_per_30s = 30
    s.spotify_client_id = "client_id"
    s.spotify_client_secret = "client_secret"
    s.spotify_refresh_token = "refresh_token"
    s.spotify_timeout = 5.0
    s.spotify_retry_after_default_s = 5.0
    s.spotify_retry_after_max_s = 60.0
    s.circuit_breaker_failure_threshold = 5
    s.circuit_breaker_timeout_s = 60.0
    return s


def _make_artist(name="Actress", spotify_id="spotify:artist:3G3Gdm4vNKHNf3jiRfPVzqt", artist_id=1):
    return {
        "id": artist_id,
        "name": name,
        "external_ids": {"spotify": spotify_id} if spotify_id else None,
    }


def _make_track(name="Ascending", track_id="5CXokd", artist_name="Actress", artist_id="3G3Gdm4"):
    return {"name": name, "id": track_id, "artist_name": artist_name, "artist_id": artist_id}


def _run_one_cycle(artists, tracks_by_artist=None, spotify_errors=None):
    """
    Drive one full cycle through run_polling(), then stop immediately.
    tracks_by_artist: dict mapping artist name → list of tracks returned by get_top_tracks
    spotify_errors: set of artist names that raise SpotifyServiceError
    """
    settings = _make_settings()
    tracks_by_artist = tracks_by_artist or {}
    spotify_errors = spotify_errors or set()

    artist_repo = MagicMock()

    spotify = MagicMock()

    def top_tracks_side_effect(artist_uri):
        name = next(
            (
                a["name"]
                for a in artists
                if (a.get("external_ids") or {}).get("spotify") == artist_uri
            ),
            None,
        )
        if name in spotify_errors:
            raise SpotifyServiceError(f"error for {name}")
        return tracks_by_artist.get(name, [])

    spotify.get_top_tracks.side_effect = top_tracks_side_effect

    producer = MagicMock()
    producer.flush.return_value = 0

    circuit_breaker = MagicMock()
    circuit_breaker.should_allow.return_value = True

    handlers: dict = {}

    def register_handler(sig, handler):
        handlers[sig] = handler

    # After the first cycle completes we fire SIGTERM to stop the main loop.
    # We hook into artist_repo.get_eligible: on the second call (next cycle) we stop.
    call_count = [0]

    def get_eligible_with_stop(conn, days):
        call_count[0] += 1
        if call_count[0] > 1:
            if _signal.SIGTERM in handlers:
                handlers[_signal.SIGTERM](_signal.SIGTERM, None)
            return []
        return artists

    artist_repo.get_eligible.side_effect = get_eligible_with_stop

    with (
        patch("signal_artist_tracker.app.KafkaJsonProducer", return_value=producer),
        patch("signal_artist_tracker.app.SpotifyClient", return_value=spotify),
        patch("signal_artist_tracker.app.ArtistRepository", return_value=artist_repo),
        patch("signal_artist_tracker.app.CircuitBreaker", return_value=circuit_breaker),
        patch("signal_artist_tracker.app.psycopg") as mock_psycopg,
        patch("signal_artist_tracker.app.signal") as mock_sig,
        patch("signal_artist_tracker.app._interruptible_sleep"),  # skip real sleep
    ):
        mock_sig.SIGTERM = _signal.SIGTERM
        mock_sig.SIGINT = _signal.SIGINT
        mock_sig.signal.side_effect = register_handler

        mock_conn = MagicMock()
        mock_psycopg.connect.return_value = mock_conn

        from signal_artist_tracker.app import run_polling
        run_polling(settings)

    return artist_repo, spotify, producer


# ---------------------------------------------------------------------------
# Core loop tests
# ---------------------------------------------------------------------------

def test_eligible_artists_fetched_and_tracks_emitted():
    artist = _make_artist()
    tracks = [_make_track(), _make_track(name="X", track_id="abc")]
    artist_repo, spotify, producer = _run_one_cycle(
        [artist],
        tracks_by_artist={"Actress": tracks},
    )

    spotify.get_top_tracks.assert_called_once_with("spotify:artist:3G3Gdm4vNKHNf3jiRfPVzqt")
    assert producer.produce.call_count == 2
    producer.flush.assert_called()

    call_args = producer.produce.call_args_list[0]
    msg = call_args[0][1]
    assert msg["source"] == "spotify"
    assert msg["artist"] == "Actress"
    assert msg["artist_id"] == "spotify:artist:3G3Gdm4vNKHNf3jiRfPVzqt"
    assert msg["track_id"] == "spotify:track:5CXokd"
    assert msg["origin"]["type"] == "ARTIST_TOP_TRACKS"


def test_mark_explored_called_on_success():
    artist = _make_artist()
    artist_repo, _, _ = _run_one_cycle(
        [artist],
        tracks_by_artist={"Actress": [_make_track()]},
    )
    artist_repo.mark_explored.assert_called_once()
    assert artist_repo.mark_explored.call_args[0][1] == artist["id"]


def test_artist_with_no_spotify_id_is_skipped():
    artist = _make_artist(spotify_id=None)
    artist["external_ids"] = None
    artist_repo, spotify, producer = _run_one_cycle([artist])

    spotify.get_top_tracks.assert_not_called()
    producer.produce.assert_not_called()
    artist_repo.mark_explored.assert_not_called()


def test_artist_with_no_external_ids_dict_is_skipped():
    artist = _make_artist()
    artist["external_ids"] = {}  # dict present but no spotify key
    artist_repo, spotify, producer = _run_one_cycle([artist])

    spotify.get_top_tracks.assert_not_called()
    artist_repo.mark_explored.assert_not_called()


def test_empty_top_tracks_updates_last_explored_at_without_emitting():
    artist = _make_artist()
    artist_repo, spotify, producer = _run_one_cycle(
        [artist],
        tracks_by_artist={"Actress": []},
    )

    spotify.get_top_tracks.assert_called_once()
    producer.produce.assert_not_called()
    # mark_explored still called — empty tracklist is a valid exploration result
    artist_repo.mark_explored.assert_called_once()


def test_spotify_error_skips_mark_explored_continues_next_artist():
    good = _make_artist(name="Good Artist", spotify_id="spotify:artist:good", artist_id=1)
    bad = _make_artist(name="Bad Artist", spotify_id="spotify:artist:bad", artist_id=2)

    artist_repo, spotify, producer = _run_one_cycle(
        [bad, good],
        tracks_by_artist={"Good Artist": [_make_track()]},
        spotify_errors={"Bad Artist"},
    )

    assert producer.produce.call_count == 1
    assert artist_repo.mark_explored.call_count == 1


def test_all_artists_fail_cycle_completes_without_crashing():
    artists = [
        _make_artist(name="A", spotify_id="spotify:artist:a", artist_id=1),
        _make_artist(name="B", spotify_id="spotify:artist:b", artist_id=2),
    ]

    artist_repo, spotify, producer = _run_one_cycle(
        artists,
        spotify_errors={"A", "B"},
    )

    producer.produce.assert_not_called()
    artist_repo.mark_explored.assert_not_called()


# ---------------------------------------------------------------------------
# _run_cycle unit tests (direct call — finer control)
# ---------------------------------------------------------------------------

def _make_run_cycle_mocks(artists=None, tracks=None, flush_return=0):
    settings = _make_settings()
    artist_repo = MagicMock()
    artist_repo.get_eligible.return_value = artists or []
    spotify = MagicMock()
    spotify.get_top_tracks.return_value = tracks if tracks is not None else []
    producer = MagicMock()
    producer.flush.return_value = flush_return
    circuit_breaker = MagicMock()
    circuit_breaker.should_allow.return_value = True
    return settings, artist_repo, spotify, producer, circuit_breaker


def test_kafka_flush_timeout_still_marks_explored():
    """At-least-once semantics: flush timeout must not skip mark_explored."""
    artist = _make_artist()
    settings, artist_repo, spotify, producer, circuit_breaker = _make_run_cycle_mocks(
        artists=[artist],
        tracks=[_make_track()],
        flush_return=1,  # 1 message still buffered after flush timeout
    )

    with patch("signal_artist_tracker.app.psycopg") as mock_psycopg:
        mock_psycopg.connect.return_value = MagicMock()
        from signal_artist_tracker.app import _run_cycle
        _run_cycle(settings, spotify, circuit_breaker, producer, artist_repo)

    artist_repo.mark_explored.assert_called_once()


def test_mark_explored_db_failure_increments_failed_continues():
    """DB error during mark_explored should not crash the cycle for the next artist."""
    artist1 = _make_artist(name="Artist1", spotify_id="spotify:artist:a1", artist_id=1)
    artist2 = _make_artist(name="Artist2", spotify_id="spotify:artist:a2", artist_id=2)
    settings, artist_repo, spotify, producer, circuit_breaker = _make_run_cycle_mocks(
        artists=[artist1, artist2],
        tracks=[_make_track()],
    )

    call_count = [0]

    def mark_explored_fail_first(conn, artist_id):
        call_count[0] += 1
        if call_count[0] == 1:
            raise _psycopg.Error("DB write error")

    artist_repo.mark_explored.side_effect = mark_explored_fail_first

    with patch("signal_artist_tracker.app.psycopg") as mock_psycopg:
        mock_psycopg.connect.return_value = MagicMock()
        from signal_artist_tracker.app import _run_cycle
        _run_cycle(settings, spotify, circuit_breaker, producer, artist_repo)

    assert artist_repo.mark_explored.call_count == 2


def test_circuit_breaker_open_skips_artist():
    artist = _make_artist()
    settings, artist_repo, spotify, producer, circuit_breaker = _make_run_cycle_mocks(
        artists=[artist]
    )
    circuit_breaker.should_allow.return_value = False

    with patch("signal_artist_tracker.app.psycopg") as mock_psycopg:
        mock_psycopg.connect.return_value = MagicMock()
        from signal_artist_tracker.app import _run_cycle
        _run_cycle(settings, spotify, circuit_breaker, producer, artist_repo)

    spotify.get_top_tracks.assert_not_called()
    artist_repo.mark_explored.assert_not_called()


def test_db_connection_failure_returns_without_processing():
    """psycopg.connect failure should exit the cycle cleanly."""
    settings, artist_repo, spotify, producer, circuit_breaker = _make_run_cycle_mocks()

    with patch("signal_artist_tracker.app.psycopg") as mock_psycopg:
        mock_psycopg.connect.side_effect = _psycopg.Error("connection refused")
        from signal_artist_tracker.app import _run_cycle
        _run_cycle(settings, spotify, circuit_breaker, producer, artist_repo)

    artist_repo.get_eligible.assert_not_called()
    spotify.get_top_tracks.assert_not_called()

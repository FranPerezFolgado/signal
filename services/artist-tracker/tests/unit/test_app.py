import signal as _signal
from unittest.mock import MagicMock, patch
from uuid import UUID

import psycopg as _psycopg
from signal_artist_tracker.lastfm_client import SimilarArtist
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
    s.lastfm_api_key = "test_lastfm_key"
    s.lastfm_similar_interval_hours = 24.0
    s.lastfm_similar_limit = 10
    s.lastfm_similar_rate_limit_per_30s = 150
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
    artist_repo.get_eligible_for_expansion.return_value = []

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

    mock_lastfm = MagicMock()
    mock_lastfm.get_similar.return_value = []

    with (
        patch("signal_artist_tracker.app.KafkaJsonProducer", return_value=producer),
        patch("signal_artist_tracker.app.SpotifyClient", return_value=spotify),
        patch("signal_artist_tracker.app.LastfmSimilarClient", return_value=mock_lastfm),
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


# ---------------------------------------------------------------------------
# _run_similar_expansion_cycle — helpers
# ---------------------------------------------------------------------------

_ORIGIN_ID = UUID("11111111-1111-1111-1111-111111111111")
_NEW_ID = UUID("22222222-2222-2222-2222-222222222222")


def _make_expansion_settings():
    s = MagicMock()
    s.database_url = "postgresql://signal:signal@localhost:5432/signal"
    s.lastfm_similar_interval_hours = 24.0
    s.lastfm_similar_limit = 10
    s.kafka_discovered_topic = "artist.discovered"
    return s


def _make_origin_row(name="Burial", artist_id=_ORIGIN_ID):
    return {"id": artist_id, "name": name, "external_ids": {}}


def _run_expansion_cycle(artists, lastfm_side_effect=None, repo_overrides=None):
    settings = _make_expansion_settings()
    artist_repo = MagicMock()
    artist_repo.get_eligible_for_expansion.return_value = artists
    artist_repo.find_by_mbid.return_value = None
    artist_repo.insert_similar_artist.return_value = _NEW_ID
    if repo_overrides:
        for attr, val in repo_overrides.items():
            setattr(artist_repo, attr, val)

    lastfm = MagicMock()
    if lastfm_side_effect is not None:
        lastfm.get_similar.side_effect = lastfm_side_effect
    else:
        lastfm.get_similar.return_value = []

    producer = MagicMock()
    producer.flush.return_value = 0

    with patch("signal_artist_tracker.app.psycopg") as mock_psycopg:
        mock_conn = MagicMock()
        mock_psycopg.connect.return_value = mock_conn
        from signal_artist_tracker.app import _run_similar_expansion_cycle
        _run_similar_expansion_cycle(settings, lastfm, producer, artist_repo)

    return artist_repo, lastfm, producer


# ---------------------------------------------------------------------------
# US1: happy path
# ---------------------------------------------------------------------------

class TestSimilarExpansionUS1:
    def test_two_new_artists_inserts_and_produces_twice(self):
        origin = _make_origin_row()
        similar_artists = [
            SimilarArtist(name="Actress", mbid="mbid-1", match_score=0.9),
            SimilarArtist(name="Andy Stott", mbid=None, match_score=0.7),
        ]

        insert_ids = [
            UUID("33333333-3333-3333-3333-333333333333"),
            UUID("44444444-4444-4444-4444-444444444444"),
        ]
        call_count = [0]

        def insert_side_effect(conn, name, mbid, origin_id):
            idx = call_count[0]
            call_count[0] += 1
            return insert_ids[idx]

        artist_repo, lastfm, producer = _run_expansion_cycle(
            [origin],
            lastfm_side_effect=lambda name, limit: similar_artists,
            repo_overrides={"insert_similar_artist": MagicMock(side_effect=insert_side_effect)},
        )

        assert artist_repo.insert_similar_artist.call_count == 2
        assert producer.produce.call_count == 2
        for c in producer.produce.call_args_list:
            assert c[0][0] == "artist.discovered"

    def test_mark_similar_explored_called_once_after_all_results(self):
        origin = _make_origin_row()
        similar_artists = [
            SimilarArtist(name="Actress", mbid=None, match_score=0.8),
            SimilarArtist(name="Burial", mbid=None, match_score=0.6),
        ]
        artist_repo, _, _ = _run_expansion_cycle(
            [origin],
            lastfm_side_effect=lambda name, limit: similar_artists,
        )
        artist_repo.mark_similar_explored.assert_called_once()

    def test_empty_similar_list_calls_mark_explored_zero_inserts(self):
        """FR-011: empty get_similar result is a valid success — mark_explored still called."""
        origin = _make_origin_row()
        artist_repo, _, producer = _run_expansion_cycle(
            [origin],
            lastfm_side_effect=lambda name, limit: [],
        )
        artist_repo.mark_similar_explored.assert_called_once()
        producer.produce.assert_not_called()

    def test_no_kafka_message_when_insert_returns_none(self):
        """ON CONFLICT (name) — insert returns None, no Kafka message."""
        origin = _make_origin_row()
        similar_artists = [SimilarArtist(name="Actress", mbid=None, match_score=0.9)]

        artist_repo, _, producer = _run_expansion_cycle(
            [origin],
            lastfm_side_effect=lambda name, limit: similar_artists,
            repo_overrides={"insert_similar_artist": MagicMock(return_value=None)},
        )

        producer.produce.assert_not_called()

    def test_discovery_message_contains_origin_info(self):
        origin = _make_origin_row(name="Burial", artist_id=_ORIGIN_ID)
        similar_artists = [SimilarArtist(name="Andy Stott", mbid="mbid-x", match_score=0.8)]
        _, _, producer = _run_expansion_cycle(
            [origin],
            lastfm_side_effect=lambda name, limit: similar_artists,
        )
        msg = producer.produce.call_args[0][1]
        assert msg["origin_artist_id"] == str(_ORIGIN_ID)
        assert msg["origin_artist_name"] == "Burial"
        assert msg["source"] == "LASTFM_SIMILAR"
        assert msg["lastfm_mbid"] == "mbid-x"


# ---------------------------------------------------------------------------
# US2: deduplication
# ---------------------------------------------------------------------------

class TestSimilarExpansionUS2:
    def test_mbid_match_skips_insert_and_produce(self):
        origin = _make_origin_row()
        similar_artists = [SimilarArtist(name="Actress", mbid="existing-mbid", match_score=0.9)]
        existing_id = UUID("55555555-5555-5555-5555-555555555555")

        artist_repo, _, producer = _run_expansion_cycle(
            [origin],
            lastfm_side_effect=lambda name, limit: similar_artists,
            repo_overrides={"find_by_mbid": MagicMock(return_value=(existing_id, "BLACKLISTED"))},
        )

        artist_repo.insert_similar_artist.assert_not_called()
        producer.produce.assert_not_called()

    def test_mbid_none_skips_find_by_mbid_calls_insert(self):
        origin = _make_origin_row()
        similar_artists = [SimilarArtist(name="NoMbidArtist", mbid=None, match_score=0.5)]

        artist_repo, _, _ = _run_expansion_cycle(
            [origin],
            lastfm_side_effect=lambda name, limit: similar_artists,
        )

        artist_repo.find_by_mbid.assert_not_called()
        artist_repo.insert_similar_artist.assert_called_once()

    def test_mbid_present_but_not_found_proceeds_to_insert(self):
        origin = _make_origin_row()
        similar_artists = [SimilarArtist(name="NewArtist", mbid="new-mbid", match_score=0.6)]

        find_mock = MagicMock(return_value=None)
        artist_repo, _, _ = _run_expansion_cycle(
            [origin],
            lastfm_side_effect=lambda name, limit: similar_artists,
            repo_overrides={"find_by_mbid": find_mock},
        )

        find_mock.assert_called_once()
        artist_repo.insert_similar_artist.assert_called_once()


# ---------------------------------------------------------------------------
# US3: resilience
# ---------------------------------------------------------------------------

class TestSimilarExpansionUS3:
    def test_get_similar_raises_skips_artist_mark_not_called(self):
        _good_id = UUID("66666666-6666-6666-6666-666666666666")
        _bad_id = UUID("77777777-7777-7777-7777-777777777777")
        good = _make_origin_row(name="GoodArtist", artist_id=_good_id)
        bad = _make_origin_row(name="BadArtist", artist_id=_bad_id)

        def get_similar_side_effect(name, limit):
            if name == "BadArtist":
                raise RuntimeError("network error")
            return [SimilarArtist(name="ArtistX", mbid=None, match_score=0.5)]

        artist_repo, _, _ = _run_expansion_cycle(
            [bad, good],
            lastfm_side_effect=get_similar_side_effect,
        )

        # mark_similar_explored should only be called for the good artist
        assert artist_repo.mark_similar_explored.call_count == 1

    def test_insert_raises_psycopg_error_artist_failed_cycle_continues(self):
        _id1 = UUID("88888888-8888-8888-8888-888888888888")
        _id2 = UUID("99999999-9999-9999-9999-999999999999")
        artist1 = _make_origin_row(name="Artist1", artist_id=_id1)
        artist2 = _make_origin_row(name="Artist2", artist_id=_id2)

        similar_artists = [SimilarArtist(name="SomeNew", mbid=None, match_score=0.6)]
        call_count = [0]

        def insert_side_effect(conn, name, mbid, origin_id):
            call_count[0] += 1
            if call_count[0] == 1:
                raise _psycopg.Error("constraint violation")
            return _NEW_ID

        artist_repo, _, _ = _run_expansion_cycle(
            [artist1, artist2],
            lastfm_side_effect=lambda name, limit: similar_artists,
            repo_overrides={"insert_similar_artist": MagicMock(side_effect=insert_side_effect)},
        )

        # artist1 failed (psycopg error), artist2 should still be processed
        assert artist_repo.mark_similar_explored.call_count == 1

    def test_completion_log_counts_correct(self):
        origins = [
            _make_origin_row(name=n, artist_id=UUID(f"{i:032x}"))
            for i, n in enumerate(["A", "B", "C"], 1)
        ]
        similar_artists = [SimilarArtist(name="NewArtist", mbid=None, match_score=0.5)]

        insert_ids = [_NEW_ID, None, _NEW_ID]
        call_count = [0]

        def insert_side_effect(conn, name, mbid, origin_id):
            idx = call_count[0]
            call_count[0] += 1
            return insert_ids[idx]

        settings = _make_expansion_settings()
        artist_repo = MagicMock()
        artist_repo.get_eligible_for_expansion.return_value = origins
        artist_repo.find_by_mbid.return_value = None
        artist_repo.insert_similar_artist.side_effect = insert_side_effect

        lastfm = MagicMock()
        lastfm.get_similar.return_value = similar_artists
        producer = MagicMock()
        producer.flush.return_value = 0

        log_calls = []
        with (
            patch("signal_artist_tracker.app.psycopg") as mock_psycopg,
            patch("signal_artist_tracker.app._log") as mock_log,
        ):
            mock_psycopg.connect.return_value = MagicMock()
            mock_log.info.side_effect = lambda event, **kw: log_calls.append((event, kw))
            from signal_artist_tracker.app import _run_similar_expansion_cycle
            _run_similar_expansion_cycle(settings, lastfm, producer, artist_repo)

        target = "similar_expansion_cycle_complete"
        completion = next((kw for ev, kw in log_calls if ev == target), None)
        assert completion is not None
        assert completion["source_artists"] == 3
        assert completion["new_artists"] == 2  # artist A and C
        assert completion["skipped"] == 0
        assert completion["name_conflicts"] == 1  # artist B insert returned None
        assert completion["failed"] == 0

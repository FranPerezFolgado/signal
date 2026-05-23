from unittest.mock import MagicMock

import pytest

from signal_history_tracker.history_repository import HistoryRepository


@pytest.fixture
def repo():
    return HistoryRepository()


@pytest.fixture
def sample_msg():
    return {
        "signal_id": "abc123def456" + "0" * 52,
        "artist": "Radiohead",
        "artist_id": "spotify:artist:4Z8W4fKeB5YxbusRsdQVPb",
        "title": "Karma Police",
        "genres": ["alternative rock", "art rock"],
        "played_at": "2026-05-21T10:00:00+00:00",
        "sources": ["lastfm"],
        "audio_features": {"energy": 0.5, "valence": 0.3, "tempo": 120.0,
                           "danceability": 0.4, "acousticness": 0.1, "instrumentalness": 0.0},
        "popularity": 75,
    }


def _make_conn(fetchone_return) -> MagicMock:
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchone.return_value = fetchone_return
    conn.cursor.return_value = cursor
    return conn


def test_upsert_returns_true_on_fresh_insert(repo, sample_msg):
    conn = _make_conn((True,))
    assert repo.upsert(conn, sample_msg) is True


def test_upsert_returns_false_on_conflict(repo, sample_msg):
    conn = _make_conn((False,))
    assert repo.upsert(conn, sample_msg) is False


def test_upsert_returns_false_when_no_row_returned(repo, sample_msg):
    conn = _make_conn(None)
    assert repo.upsert(conn, sample_msg) is False


def test_upsert_sql_contains_on_conflict(repo, sample_msg):
    conn = _make_conn((True,))
    repo.upsert(conn, sample_msg)
    executed_sql = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][0]
    assert "ON CONFLICT (signal_id) DO UPDATE" in executed_sql


def test_upsert_binds_all_nine_fields(repo, sample_msg):
    conn = _make_conn((True,))
    repo.upsert(conn, sample_msg)
    params = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][1]
    for field in ("signal_id", "artist", "artist_id", "title", "genres",
                  "played_at", "sources", "audio_features", "popularity"):
        assert field in params, f"Missing field: {field}"


def test_upsert_handles_null_audio_features(repo, sample_msg):
    sample_msg["audio_features"] = None
    conn = _make_conn((True,))
    repo.upsert(conn, sample_msg)
    params = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][1]
    assert params["audio_features"] is None

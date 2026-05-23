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
        "track_id": "spotify:track:t1",
        "title": "Karma Police",
        "genres": ["alternative rock", "art rock"],
        "played_at": "2026-05-21T10:00:00+00:00",
        "sources": ["lastfm"],
        "artist_popularity": 75,
        "track_popularity": 60,
        "pending_enrichment": False,
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


def test_upsert_binds_v2_fields(repo, sample_msg):
    conn = _make_conn((True,))
    repo.upsert(conn, sample_msg)
    params = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][1]
    for field in ("signal_id", "artist", "artist_id", "track_id", "title", "genres",
                  "played_at", "sources", "artist_popularity", "track_popularity",
                  "pending_enrichment"):
        assert field in params, f"Missing field: {field}"


def test_upsert_has_no_audio_features_field(repo, sample_msg):
    conn = _make_conn((True,))
    repo.upsert(conn, sample_msg)
    params = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][1]
    assert "audio_features" not in params
    assert "popularity" not in params


def test_upsert_coerces_none_genres_to_empty_list(repo, sample_msg):
    sample_msg["genres"] = None
    conn = _make_conn((True,))
    repo.upsert(conn, sample_msg)
    params = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][1]
    assert params["genres"] == []


def test_upsert_pending_enrichment_defaults_false(repo, sample_msg):
    del sample_msg["pending_enrichment"]
    conn = _make_conn((True,))
    repo.upsert(conn, sample_msg)
    params = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][1]
    assert params["pending_enrichment"] is False

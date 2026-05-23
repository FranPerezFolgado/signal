from unittest.mock import MagicMock, patch

import pytest

from signal_history_tracker.artist_repository import ArtistRepository


@pytest.fixture
def repo():
    return ArtistRepository()


def _make_conn(fetchone_return) -> MagicMock:
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchone.return_value = fetchone_return
    conn.cursor.return_value = cursor
    return conn


def _sample_msg(**kwargs):
    msg = {"artist": "Radiohead", "genres": ["alternative rock"]}
    msg.update(kwargs)
    return msg


def test_upsert_returns_true_on_insert(repo):
    conn = _make_conn(("id1", True))
    assert repo.upsert(conn, _sample_msg()) is True


def test_upsert_returns_false_on_conflict(repo):
    conn = _make_conn(("id1", False))
    assert repo.upsert(conn, _sample_msg()) is False


def test_upsert_returns_false_when_no_row(repo):
    conn = _make_conn(None)
    assert repo.upsert(conn, _sample_msg()) is False


def test_upsert_sql_inserts_tracked_status(repo):
    conn = _make_conn(("id1", True))
    repo.upsert(conn, _sample_msg())
    executed_sql = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][0]
    assert "'TRACKED'" in executed_sql


def test_upsert_sql_uses_case_insensitive_conflict(repo):
    conn = _make_conn(("id1", True))
    repo.upsert(conn, _sample_msg())
    executed_sql = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][0]
    assert "LOWER(name)" in executed_sql


def test_upsert_increments_play_count(repo):
    conn = _make_conn(("id1", False))
    repo.upsert(conn, _sample_msg())
    executed_sql = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][0]
    assert "play_count + 1" in executed_sql


def test_upsert_coerces_empty_genres_to_none(repo):
    conn = _make_conn(("id1", True))
    repo.upsert(conn, _sample_msg(genres=[]))
    params = conn.cursor.return_value.__enter__.return_value.execute.call_args[0][1]
    assert params["genres"] is None


def test_upsert_logs_on_insert(repo):
    conn = _make_conn(("id1", True))
    with patch("signal_history_tracker.artist_repository._log") as mock_log:
        repo.upsert(conn, _sample_msg())
    mock_log.info.assert_called_once_with("artist_inserted", artist="Radiohead")

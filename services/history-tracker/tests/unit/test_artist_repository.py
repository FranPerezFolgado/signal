from unittest.mock import MagicMock, patch

import pytest

from signal_history_tracker.artist_repository import ArtistRepository


@pytest.fixture
def repo():
    return ArtistRepository()


def _make_conn(rowcount: int) -> MagicMock:
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.rowcount = rowcount
    conn.cursor.return_value = cursor
    return conn


def test_increment_returns_true_when_artist_found(repo):
    conn = _make_conn(rowcount=1)
    result = repo.increment_play_count(conn, "Radiohead")
    assert result is True


def test_increment_returns_false_when_artist_not_found(repo):
    conn = _make_conn(rowcount=0)
    result = repo.increment_play_count(conn, "Unknown Artist")
    assert result is False


def test_increment_logs_warn_when_not_found(repo):
    conn = _make_conn(rowcount=0)
    with patch("signal_history_tracker.artist_repository._log") as mock_log:
        repo.increment_play_count(conn, "Ghost Artist")
    mock_log.warning.assert_called_once_with("artist_not_found", artist="Ghost Artist")


def test_increment_sql_uses_case_insensitive_match(repo):
    conn = _make_conn(rowcount=1)
    repo.increment_play_count(conn, "Radiohead")
    cursor = conn.cursor.return_value.__enter__.return_value
    executed_sql = cursor.execute.call_args[0][0]
    assert "LOWER(name) = LOWER(" in executed_sql

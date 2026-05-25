from unittest.mock import MagicMock
from uuid import UUID

from signal_artist_tracker.artist_repository import ArtistRepository


def _make_conn(rows=None):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = rows or []
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


class TestGetEligible:
    def test_executes_correct_sql_with_reexplore_days(self):
        conn, cursor = _make_conn()
        repo = ArtistRepository()

        repo.get_eligible(conn, reexplore_days=7)

        cursor.execute.assert_called_once()
        called_sql, called_params = cursor.execute.call_args[0]
        assert "status = 'FOLLOWING'" in called_sql
        assert "last_explored_at" in called_sql
        assert called_params == (7,)

    def test_uses_dict_row_factory(self):
        conn, cursor = _make_conn()
        repo = ArtistRepository()

        repo.get_eligible(conn, reexplore_days=7)

        conn.cursor.assert_called_once()
        call_kwargs = conn.cursor.call_args[1]
        import psycopg
        assert call_kwargs.get("row_factory") is psycopg.rows.dict_row

    def test_returns_fetchall_result(self):
        rows = [{"id": 1, "name": "Actress", "external_ids": {"spotify": "spotify:artist:abc"}}]
        conn, cursor = _make_conn(rows=rows)
        repo = ArtistRepository()

        result = repo.get_eligible(conn, reexplore_days=7)

        assert result == rows

    def test_empty_result_when_no_eligible_artists(self):
        conn, _ = _make_conn(rows=[])
        repo = ArtistRepository()
        result = repo.get_eligible(conn, reexplore_days=7)
        assert result == []


class TestMarkExplored:
    def test_executes_update_sql_with_artist_id(self):
        conn, cursor = _make_conn()
        repo = ArtistRepository()
        artist_id = UUID("12345678-1234-5678-1234-567812345678")

        repo.mark_explored(conn, artist_id)

        cursor.execute.assert_called_once()
        called_sql, called_params = cursor.execute.call_args[0]
        assert "last_explored_at" in called_sql
        assert "UPDATE artists" in called_sql
        assert called_params == (str(artist_id),)

    def test_commits_after_update(self):
        conn, _ = _make_conn()
        repo = ArtistRepository()

        repo.mark_explored(conn, UUID("12345678-1234-5678-1234-567812345678"))

        conn.commit.assert_called_once()

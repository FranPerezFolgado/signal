from unittest.mock import MagicMock
from uuid import UUID

import psycopg
from signal_artist_tracker.artist_repository import ArtistRepository

_ARTIST_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_ORIGIN_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _make_conn(fetchone_return=None, fetchall_return=None):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_return
    cursor.fetchall.return_value = fetchall_return or []
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


class TestGetEligibleForExpansion:
    def test_queries_last_similar_explored_at_with_interval(self):
        conn, cursor = _make_conn()
        repo = ArtistRepository()

        repo.get_eligible_for_expansion(conn, interval_hours=24.0)

        cursor.execute.assert_called_once()
        sql, params = cursor.execute.call_args[0]
        assert "last_similar_explored_at" in sql
        assert "status = 'FOLLOWING'" in sql
        assert params == (24.0,)

    def test_uses_dict_row_factory(self):
        conn, _ = _make_conn()
        repo = ArtistRepository()

        repo.get_eligible_for_expansion(conn, interval_hours=12.0)

        call_kwargs = conn.cursor.call_args[1]
        assert call_kwargs.get("row_factory") is psycopg.rows.dict_row

    def test_returns_fetchall_result(self):
        rows = [{"id": _ARTIST_ID, "name": "Burial", "external_ids": {}}]
        conn, cursor = _make_conn(fetchall_return=rows)
        cursor.fetchall.return_value = rows
        repo = ArtistRepository()

        result = repo.get_eligible_for_expansion(conn, interval_hours=24.0)

        assert result == rows


class TestFindByMbid:
    def test_found_returns_uuid_and_status(self):
        conn, cursor = _make_conn(fetchone_return=(_ARTIST_ID, "FOLLOWING"))
        repo = ArtistRepository()

        result = repo.find_by_mbid(conn, "some-mbid")

        assert result is not None
        found_id, found_status = result
        assert found_id == _ARTIST_ID
        assert found_status == "FOLLOWING"

    def test_not_found_returns_none(self):
        conn, cursor = _make_conn(fetchone_return=None)
        repo = ArtistRepository()

        result = repo.find_by_mbid(conn, "unknown-mbid")

        assert result is None

    def test_queries_external_ids_jsonb_path(self):
        conn, cursor = _make_conn(fetchone_return=None)
        repo = ArtistRepository()

        repo.find_by_mbid(conn, "mbid-value")

        sql, params = cursor.execute.call_args[0]
        assert "lastfm_mbid" in sql
        assert params == ("mbid-value",)


class TestInsertSimilarArtist:
    def test_success_returns_uuid(self):
        conn, cursor = _make_conn(fetchone_return=(_ARTIST_ID,))
        repo = ArtistRepository()

        result = repo.insert_similar_artist(conn, "Burial", "mbid-123", _ORIGIN_ID)

        assert result == _ARTIST_ID
        conn.commit.assert_not_called()

    def test_on_conflict_returns_none(self):
        conn, cursor = _make_conn(fetchone_return=None)
        repo = ArtistRepository()

        result = repo.insert_similar_artist(conn, "ExistingArtist", None, _ORIGIN_ID)

        assert result is None

    def test_inserts_tracked_status_and_lastfm_similar_source(self):
        conn, cursor = _make_conn(fetchone_return=None)
        repo = ArtistRepository()

        repo.insert_similar_artist(conn, "NewArtist", "mbid-abc", _ORIGIN_ID)

        sql, params = cursor.execute.call_args[0]
        assert "'TRACKED'" in sql
        assert "'LASTFM_SIMILAR'" in sql
        assert params[0] == "NewArtist"

    def test_mbid_stored_in_external_ids_json(self):
        import json
        conn, cursor = _make_conn(fetchone_return=None)
        repo = ArtistRepository()

        repo.insert_similar_artist(conn, "Artist", "mbid-xyz", _ORIGIN_ID)

        _sql, params = cursor.execute.call_args[0]
        external_ids = json.loads(params[1])
        assert external_ids.get("lastfm_mbid") == "mbid-xyz"

    def test_no_mbid_stores_empty_external_ids(self):
        import json
        conn, cursor = _make_conn(fetchone_return=None)
        repo = ArtistRepository()

        repo.insert_similar_artist(conn, "Artist", None, _ORIGIN_ID)

        _sql, params = cursor.execute.call_args[0]
        external_ids = json.loads(params[1])
        assert external_ids == {}


class TestMarkSimilarExplored:
    def test_updates_last_similar_explored_at(self):
        conn, cursor = _make_conn()
        repo = ArtistRepository()

        repo.mark_similar_explored(conn, _ARTIST_ID)

        sql, params = cursor.execute.call_args[0]
        assert "last_similar_explored_at" in sql
        assert "UPDATE artists" in sql
        assert params == (str(_ARTIST_ID),)

    def test_commits_after_update(self):
        conn, _ = _make_conn()
        repo = ArtistRepository()

        repo.mark_similar_explored(conn, _ARTIST_ID)

        conn.commit.assert_called_once()

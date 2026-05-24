from unittest.mock import MagicMock, patch

import pytest

from signal_novelty_detector.novelty_repository import NoveltyRepository


def _mock_conn(fetchone_return):
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_return
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


class TestIsArtistNew:
    def test_no_history_returns_true(self):
        conn, _ = _mock_conn((True,))
        assert NoveltyRepository().is_artist_new(conn, "Actress", "sig-abc") is True

    def test_existing_history_returns_false(self):
        conn, _ = _mock_conn((False,))
        assert NoveltyRepository().is_artist_new(conn, "Actress", "sig-abc") is False

    def test_excludes_current_signal_id_in_query(self):
        conn, cur = _mock_conn((True,))
        NoveltyRepository().is_artist_new(conn, "Actress", "sig-123")
        args = cur.execute.call_args[0]
        assert "sig-123" in args[1]

    def test_returns_true_when_fetchone_is_none(self):
        conn, _ = _mock_conn(None)
        assert NoveltyRepository().is_artist_new(conn, "X", "y") is True


class TestGetNewGenres:
    def test_empty_genres_returns_empty_list(self):
        conn, cur = _mock_conn(None)
        result = NoveltyRepository().get_new_genres(conn, [], "sig-abc")
        assert result == []
        cur.execute.assert_not_called()

    def test_none_genres_returns_empty_list(self):
        conn, cur = _mock_conn(None)
        result = NoveltyRepository().get_new_genres(conn, None, "sig-abc")
        assert result == []
        cur.execute.assert_not_called()

    def test_all_genres_new(self):
        conn, _ = _mock_conn((["footwork", "experimental"],))
        result = NoveltyRepository().get_new_genres(conn, ["footwork", "experimental"], "sig-abc")
        assert result == ["footwork", "experimental"]

    def test_partial_overlap(self):
        conn, _ = _mock_conn((["footwork"],))
        result = NoveltyRepository().get_new_genres(conn, ["footwork", "electronic"], "sig-abc")
        assert result == ["footwork"]

    def test_full_overlap_returns_empty(self):
        conn, _ = _mock_conn(([],))
        result = NoveltyRepository().get_new_genres(conn, ["electronic"], "sig-abc")
        assert result == []

    def test_excludes_current_signal_id_in_query(self):
        conn, cur = _mock_conn((["g1"],))
        NoveltyRepository().get_new_genres(conn, ["g1"], "sig-xyz")
        args = cur.execute.call_args[0]
        assert "sig-xyz" in args[1]

    def test_returns_empty_when_db_returns_none_array(self):
        conn, _ = _mock_conn((None,))
        result = NoveltyRepository().get_new_genres(conn, ["g1"], "sig-abc")
        assert result == []


class TestIsTrackNew:
    def test_not_in_history_returns_true(self):
        conn, _ = _mock_conn((True,))
        assert NoveltyRepository().is_track_new(conn, "sig-abc") is True

    def test_in_history_returns_false(self):
        conn, _ = _mock_conn((False,))
        assert NoveltyRepository().is_track_new(conn, "sig-abc") is False

    def test_returns_true_when_fetchone_none(self):
        conn, _ = _mock_conn(None)
        assert NoveltyRepository().is_track_new(conn, "sig-abc") is True

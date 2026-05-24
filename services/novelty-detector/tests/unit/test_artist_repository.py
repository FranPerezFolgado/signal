from unittest.mock import MagicMock

from signal_novelty_detector.artist_repository import ArtistRepository


def _mock_conn(fetchone_return):
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_return
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


class TestGet:
    def test_returns_none_when_artist_missing(self):
        conn, _ = _mock_conn(None)
        assert ArtistRepository().get(conn, "Unknown") is None

    def test_returns_dict_with_correct_fields(self):
        import uuid
        artist_id = uuid.uuid4()
        conn, _ = _mock_conn((artist_id, "TRACKED", 5))
        result = ArtistRepository().get(conn, "Actress")
        assert result == {"id": artist_id, "status": "TRACKED", "scrobble_count": 5}

    def test_returns_following_status(self):
        import uuid
        conn, _ = _mock_conn((uuid.uuid4(), "FOLLOWING", 10))
        result = ArtistRepository().get(conn, "Burial")
        assert result["status"] == "FOLLOWING"


class TestPromoteToFollowing:
    def test_returns_true_when_row_updated(self):
        import uuid
        conn, _ = _mock_conn((uuid.uuid4(),))
        assert ArtistRepository().promote_to_following(conn, "Actress", 3) is True

    def test_returns_false_when_no_row_returned(self):
        conn, _ = _mock_conn(None)
        assert ArtistRepository().promote_to_following(conn, "Actress", 3) is False

    def test_returns_false_when_already_following(self):
        # Simulates the WHERE status='TRACKED' guard preventing the update
        conn, _ = _mock_conn(None)
        assert ArtistRepository().promote_to_following(conn, "Burial", 3) is False

    def test_returns_false_when_scrobble_count_below_threshold(self):
        conn, _ = _mock_conn(None)
        assert ArtistRepository().promote_to_following(conn, "Actress", 10) is False

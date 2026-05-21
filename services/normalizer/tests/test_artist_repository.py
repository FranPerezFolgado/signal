import pytest
import psycopg

from signal_normalizer.artist_repository import ArtistRepository

DATABASE_URL = "postgresql://signal:signal@localhost:5432/signal"


@pytest.fixture
def conn():
    with psycopg.connect(DATABASE_URL) as c:
        c.autocommit = False
        yield c
        c.rollback()


@pytest.fixture
def repo():
    return ArtistRepository()


class TestArtistRepository:
    def test_find_by_name_not_found(self, conn, repo):
        result = repo.find_by_name(conn, "nonexistent artist xyz123")
        assert result is None

    def test_insert_and_find_by_name(self, conn, repo):
        repo.insert_tracked(conn, "Test Artist Alpha", None, ["electronic"])
        result = repo.find_by_name(conn, "test artist alpha")
        assert result is not None

    def test_insert_and_find_by_spotify_id(self, conn, repo):
        repo.insert_tracked(conn, "Test Artist Beta", "spotify123", ["ambient"])
        result = repo.find_by_spotify_id(conn, "spotify123")
        assert result is not None

    def test_insert_sets_status_tracked(self, conn, repo):
        repo.insert_tracked(conn, "Test Artist Gamma", None, [])
        with conn.cursor() as cur:
            cur.execute("SELECT status, source FROM artists WHERE LOWER(name) = %s", ("test artist gamma",))
            row = cur.fetchone()
        assert row is not None
        assert row[0] == "TRACKED"
        assert row[1] == "LASTFM"

    def test_upsert_tracked_idempotent(self, conn, repo):
        repo.upsert_tracked(conn, "Actress", None, ["electronic"])
        repo.upsert_tracked(conn, "Actress", None, ["electronic"])
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM artists WHERE LOWER(name) = 'actress'")
            count = cur.fetchone()[0]
        assert count == 1

    def test_upsert_tracked_case_insensitive(self, conn, repo):
        repo.upsert_tracked(conn, "Burial", None, ["uk garage"])
        repo.upsert_tracked(conn, "BURIAL", None, ["uk garage"])
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM artists WHERE LOWER(name) = 'burial'")
            count = cur.fetchone()[0]
        assert count == 1

    def test_upsert_tracked_spotify_id_dedup(self, conn, repo):
        repo.upsert_tracked(conn, "Andy Stott", "spotify:artist:abc999", ["techno"])
        repo.upsert_tracked(conn, "Andy Stott", "spotify:artist:abc999", ["techno"])
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM artists WHERE external_ids->>'spotify_id' = 'abc999'"
            )
            count = cur.fetchone()[0]
        assert count == 1

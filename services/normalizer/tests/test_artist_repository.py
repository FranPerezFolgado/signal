import os
import uuid

import psycopg
import pytest

from signal_normalizer.artist_repository import ArtistRepository

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://signal:signal@localhost:5432/signal"
)


@pytest.fixture
def conn():
    with psycopg.connect(DATABASE_URL) as c:
        c.autocommit = False
        yield c
        c.rollback()


@pytest.fixture
def repo():
    return ArtistRepository()


def _unique(name: str) -> str:
    """Append a UUID suffix so test runs never collide with each other."""
    return f"{name} {uuid.uuid4().hex[:8]}"


class TestArtistRepository:
    def test_find_by_name_not_found(self, conn, repo):
        result = repo.find_by_name(conn, f"nonexistent {uuid.uuid4().hex}")
        assert result is None

    def test_insert_and_find_by_name(self, conn, repo):
        name = _unique("Test Artist Alpha")
        repo.insert_tracked(conn, name, None, ["electronic"])
        result = repo.find_by_name(conn, name.lower())
        assert result is not None

    def test_insert_and_find_by_spotify_id(self, conn, repo):
        spotify_id = uuid.uuid4().hex
        repo.insert_tracked(conn, _unique("Test Artist Beta"), spotify_id, ["ambient"])
        result = repo.find_by_spotify_id(conn, spotify_id)
        assert result is not None

    def test_insert_sets_status_and_source(self, conn, repo):
        name = _unique("Test Artist Gamma")
        repo.insert_tracked(conn, name, None, [])
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, source FROM artists WHERE LOWER(name) = %s",
                (name.lower(),),
            )
            row = cur.fetchone()
        assert row is not None
        assert row[0] == "TRACKED"
        assert row[1] == "LASTFM"

    def test_upsert_tracked_idempotent(self, conn, repo):
        name = _unique("Actress")
        repo.upsert_tracked(conn, name, None, ["electronic"])
        conn.commit()
        repo.upsert_tracked(conn, name, None, ["electronic"])
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM artists WHERE LOWER(name) = %s", (name.lower(),)
            )
            count = cur.fetchone()[0]
        assert count == 1

    def test_upsert_tracked_case_insensitive(self, conn, repo):
        base = _unique("Burial")
        upper = base.upper()
        repo.upsert_tracked(conn, base, None, ["uk garage"])
        conn.commit()
        repo.upsert_tracked(conn, upper, None, ["uk garage"])
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM artists WHERE LOWER(name) = %s", (base.lower(),)
            )
            count = cur.fetchone()[0]
        assert count == 1

    def test_upsert_updates_genres_on_conflict(self, conn, repo):
        name = _unique("Flying Lotus")
        repo.upsert_tracked(conn, name, None, [])
        conn.commit()
        repo.upsert_tracked(conn, name, None, ["jazz", "hip-hop"])
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT genres FROM artists WHERE LOWER(name) = %s", (name.lower(),))
            genres = cur.fetchone()[0]
        assert set(genres) == {"jazz", "hip-hop"}

    def test_upsert_does_not_overwrite_existing_genres_with_empty(self, conn, repo):
        name = _unique("Emptiness Test")
        repo.upsert_tracked(conn, name, None, ["drone"])
        conn.commit()
        repo.upsert_tracked(conn, name, None, [])
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT genres FROM artists WHERE LOWER(name) = %s", (name.lower(),))
            genres = cur.fetchone()[0]
        assert genres == ["drone"]

    def test_upsert_tracked_spotify_id_stored(self, conn, repo):
        spotify_uri = f"spotify:artist:{uuid.uuid4().hex}"
        name = _unique("Andy Stott")
        repo.upsert_tracked(conn, name, spotify_uri, ["techno"])
        conn.commit()
        bare_id = spotify_uri.split(":")[-1]
        result = repo.find_by_spotify_id(conn, bare_id)
        assert result is not None

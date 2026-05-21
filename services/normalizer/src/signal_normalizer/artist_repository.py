import json
from uuid import UUID

import psycopg

from signal_common.logger import get_logger
from signal_normalizer.signal_id import _norm

_log = get_logger(__name__)


class ArtistRepository:
    def find_by_name(self, conn: psycopg.Connection, normalized_name: str) -> UUID | None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM artists WHERE LOWER(name) = %s",
                (normalized_name,),
            )
            row = cur.fetchone()
            return row[0] if row else None

    def find_by_spotify_id(self, conn: psycopg.Connection, spotify_id: str) -> UUID | None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM artists WHERE external_ids->>'spotify_id' = %s",
                (spotify_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None

    def insert_tracked(
        self,
        conn: psycopg.Connection,
        name: str,
        spotify_id: str | None,
        genres: list[str],
    ) -> None:
        external_ids = json.dumps({"spotify_id": spotify_id}) if spotify_id else json.dumps({})
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO artists (name, external_ids, status, source, genres, first_seen_at)
                VALUES (%s, %s::jsonb, 'TRACKED', 'LASTFM', %s, NOW())
                """,
                (name, external_ids, genres),
            )
        conn.commit()
        _log.info("artist_inserted", name=name, spotify_id=spotify_id)

    def upsert_tracked(
        self,
        conn: psycopg.Connection,
        artist_name: str,
        artist_id: str | None,
        genres: list[str],
    ) -> None:
        normalized = _norm(artist_name)
        existing = self.find_by_name(conn, normalized)
        if existing is not None:
            return

        # Extract bare Spotify artist ID from URI if present (spotify:artist:abc → abc)
        spotify_id: str | None = None
        if artist_id and artist_id.startswith("spotify:artist:"):
            spotify_id = artist_id.split(":")[-1]
            existing = self.find_by_spotify_id(conn, spotify_id)
            if existing is not None:
                return

        self.insert_tracked(conn, artist_name, spotify_id, genres)

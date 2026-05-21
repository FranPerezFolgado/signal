import json
from uuid import UUID

import psycopg

from signal_common.logger import get_logger
from signal_normalizer.signal_id import normalize_text

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
        external_ids = json.dumps({"spotify_id": spotify_id} if spotify_id else {})
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO artists (name, external_ids, status, source, genres, first_seen_at)
                VALUES (%s, %s::jsonb, 'TRACKED', 'LASTFM', %s, NOW())
                ON CONFLICT DO NOTHING
                """,
                (name, external_ids, genres),
            )
        _log.debug("artist_upserted", name=name)

    def upsert_tracked(
        self,
        conn: psycopg.Connection,
        artist_name: str,
        artist_id: str | None,
        genres: list[str],
    ) -> None:
        # Extract bare Spotify ID from URI (spotify:artist:abc → abc)
        spotify_id: str | None = None
        if artist_id and artist_id.startswith("spotify:artist:"):
            spotify_id = artist_id.split(":")[-1]

        self.insert_tracked(conn, artist_name, spotify_id, genres)

import psycopg

from signal_common.logger import get_logger

_log = get_logger(__name__)

_ARTIST_IS_NEW_SQL = """
SELECT NOT EXISTS (
    SELECT 1 FROM listening_history
    WHERE LOWER(artist) = LOWER(%s)
      AND signal_id != %s
) AS artist_is_new
"""

_NEW_GENRES_SQL = """
SELECT ARRAY(
    SELECT g
    FROM unnest(%s::text[]) AS g
    WHERE NOT EXISTS (
        SELECT 1 FROM listening_history
        WHERE genres @> ARRAY[g]
          AND signal_id != %s
    )
) AS new_genres
"""

_TRACK_IS_NEW_SQL = """
SELECT NOT EXISTS (
    SELECT 1 FROM listening_history WHERE signal_id = %s
) AS track_is_new
"""


class NoveltyRepository:
    def is_artist_new(self, conn: psycopg.Connection, artist: str, signal_id: str) -> bool:
        with conn.cursor() as cur:
            cur.execute(_ARTIST_IS_NEW_SQL, (artist, signal_id))
            row = cur.fetchone()
            return bool(row[0]) if row else True

    def get_new_genres(self, conn: psycopg.Connection, genres: list[str], signal_id: str) -> list[str]:
        if not genres:
            return []
        with conn.cursor() as cur:
            cur.execute(_NEW_GENRES_SQL, (genres, signal_id))
            row = cur.fetchone()
            return list(row[0]) if row and row[0] else []

    def is_track_new(self, conn: psycopg.Connection, signal_id: str) -> bool:
        with conn.cursor() as cur:
            cur.execute(_TRACK_IS_NEW_SQL, (signal_id,))
            row = cur.fetchone()
            return bool(row[0]) if row else True

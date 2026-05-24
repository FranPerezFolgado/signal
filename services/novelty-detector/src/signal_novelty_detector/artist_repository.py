import psycopg

_GET_ARTIST_SQL = """
SELECT id, status, scrobble_count
FROM artists
WHERE LOWER(name) = LOWER(%s)
"""

_PROMOTE_SQL = """
UPDATE artists
SET    status = 'FOLLOWING'
WHERE  LOWER(name) = LOWER(%s)
  AND  status = 'TRACKED'
  AND  scrobble_count >= %s
RETURNING id
"""


class ArtistRepository:
    def get(self, conn: psycopg.Connection, artist: str) -> dict | None:
        with conn.cursor() as cur:
            cur.execute(_GET_ARTIST_SQL, (artist,))
            row = cur.fetchone()
            if row is None:
                return None
            return {"id": row[0], "status": row[1], "scrobble_count": row[2]}

    def promote_to_following(
        self, conn: psycopg.Connection, artist: str, min_scrobbles: int
    ) -> bool:
        with conn.cursor() as cur:
            cur.execute(_PROMOTE_SQL, (artist, min_scrobbles))
            return cur.fetchone() is not None

import json
from uuid import UUID

import psycopg
from signal_common.logger import get_logger

_log = get_logger(__name__)

_GET_ELIGIBLE_SQL = """
SELECT id, name, external_ids
FROM artists
WHERE status = 'FOLLOWING'
  AND (last_explored_at IS NULL
       OR last_explored_at < now() - make_interval(days => %s))
ORDER BY last_explored_at ASC NULLS FIRST
"""

_MARK_EXPLORED_SQL = """
UPDATE artists SET last_explored_at = now() WHERE id = %s
"""

_GET_ELIGIBLE_FOR_EXPANSION_SQL = """
SELECT id, name, external_ids
FROM artists
WHERE status = 'FOLLOWING'
  AND (last_similar_explored_at IS NULL
       OR last_similar_explored_at < now() - make_interval(hours => %s))
ORDER BY last_similar_explored_at ASC NULLS FIRST
"""

_FIND_BY_MBID_SQL = """
SELECT id, status FROM artists WHERE external_ids->>'lastfm_mbid' = %s LIMIT 1
"""

_INSERT_SIMILAR_ARTIST_SQL = """
INSERT INTO artists (name, external_ids, status, source, origin_artist_id)
VALUES (%s, %s, 'TRACKED', 'LASTFM_SIMILAR', %s)
ON CONFLICT (LOWER(name)) DO NOTHING
RETURNING id
"""

_MARK_SIMILAR_EXPLORED_SQL = """
UPDATE artists SET last_similar_explored_at = now() WHERE id = %s
"""


class ArtistRepository:
    def get_eligible(self, conn: psycopg.Connection, reexplore_days: int) -> list[dict]:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(_GET_ELIGIBLE_SQL, (reexplore_days,))
            return cur.fetchall()

    def mark_explored(self, conn: psycopg.Connection, artist_id: UUID) -> None:
        with conn.cursor() as cur:
            cur.execute(_MARK_EXPLORED_SQL, (str(artist_id),))
        conn.commit()
        _log.debug("artist_marked_explored", artist_id=str(artist_id)[:8])

    def get_eligible_for_expansion(
        self, conn: psycopg.Connection, interval_hours: float
    ) -> list[dict]:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(_GET_ELIGIBLE_FOR_EXPANSION_SQL, (interval_hours,))
            return cur.fetchall()

    def find_by_mbid(self, conn: psycopg.Connection, mbid: str) -> tuple[UUID, str] | None:
        with conn.cursor() as cur:
            cur.execute(_FIND_BY_MBID_SQL, (mbid,))
            row = cur.fetchone()
            return (UUID(str(row[0])), row[1]) if row else None

    def insert_similar_artist(
        self, conn: psycopg.Connection, name: str, mbid: str | None, origin_artist_id: UUID
    ) -> UUID | None:
        external_ids = json.dumps({"lastfm_mbid": mbid}) if mbid else json.dumps({})
        with conn.cursor() as cur:
            cur.execute(_INSERT_SIMILAR_ARTIST_SQL, (name, external_ids, str(origin_artist_id)))
            row = cur.fetchone()
        return UUID(str(row[0])) if row else None

    def mark_similar_explored(self, conn: psycopg.Connection, artist_id: UUID) -> None:
        with conn.cursor() as cur:
            cur.execute(_MARK_SIMILAR_EXPLORED_SQL, (str(artist_id),))
        conn.commit()
        _log.debug("artist_marked_similar_explored", artist_id=str(artist_id)[:8])

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

import psycopg

from signal_common.logger import get_logger

_log = get_logger(__name__)

_INCREMENT_SQL = """
UPDATE artists
SET play_count = play_count + 1
WHERE LOWER(name) = LOWER(%(artist_name)s)
RETURNING id
"""


class ArtistRepository:
    def increment_play_count(self, conn: psycopg.Connection, artist_name: str) -> bool:
        with conn.cursor() as cur:
            cur.execute(_INCREMENT_SQL, {"artist_name": artist_name})
            if cur.rowcount == 0:
                _log.warning("artist_not_found", artist=artist_name)
                return False
        return True

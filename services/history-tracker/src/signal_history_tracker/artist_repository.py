import psycopg

from signal_common.logger import get_logger

_log = get_logger(__name__)

_UPSERT_ARTIST_SQL = """
INSERT INTO artists (name, status, play_count, scrobble_count, genres)
VALUES (%(artist)s, 'TRACKED', %(play_delta)s, 1, %(genres)s)
ON CONFLICT (LOWER(name)) DO UPDATE
    SET play_count     = artists.play_count + %(play_delta)s,
        scrobble_count = artists.scrobble_count + 1,
        genres         = COALESCE(EXCLUDED.genres, artists.genres)
RETURNING id, (xmax = 0) AS inserted
"""


class ArtistRepository:
    def upsert(self, conn: psycopg.Connection, msg: dict, *, new_track: bool = True) -> bool:
        params = {
            "artist": msg["artist"],
            "genres": msg.get("genres") or None,
            "play_delta": 1 if new_track else 0,
        }
        with conn.cursor() as cur:
            cur.execute(_UPSERT_ARTIST_SQL, params)
            row = cur.fetchone()
            if row is None:
                _log.warning("artist_upsert_no_row", artist=msg["artist"])
                return False
            inserted = bool(row[1])
        if inserted:
            _log.info("artist_inserted", artist=msg["artist"])
        return inserted

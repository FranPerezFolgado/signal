import psycopg

from signal_common.logger import get_logger

_log = get_logger(__name__)

_UPSERT_ARTIST_SQL = """
INSERT INTO artists (name, status, play_count, scrobble_count, genres, external_ids)
VALUES (%(artist)s, 'TRACKED', %(play_delta)s, 1, %(genres)s, %(external_ids)s)
ON CONFLICT (LOWER(name)) DO UPDATE
    SET play_count     = artists.play_count + %(play_delta)s,
        scrobble_count = artists.scrobble_count + 1,
        genres         = COALESCE(EXCLUDED.genres, artists.genres),
        external_ids   = CASE
            WHEN %(external_ids)s IS NOT NULL
            THEN COALESCE(artists.external_ids, '{}'::jsonb) || %(external_ids)s
            ELSE artists.external_ids
        END
RETURNING id, (xmax = 0) AS inserted
"""


class ArtistRepository:
    def upsert(self, conn: psycopg.Connection, msg: dict, *, new_track: bool = True) -> bool:
        artist_id = msg.get("artist_id")
        import json
        external_ids = json.dumps({"spotify": artist_id}) if artist_id else None
        params = {
            "artist": msg["artist"],
            "genres": msg.get("genres") or None,
            "play_delta": 1 if new_track else 0,
            "external_ids": external_ids,
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

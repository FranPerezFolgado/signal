import psycopg

from signal_common.logger import get_logger

_log = get_logger(__name__)

_UPSERT_SQL = """
INSERT INTO listening_history (
    signal_id, artist, artist_id, track_id, title, genres,
    played_at, sources, artist_popularity, track_popularity, pending_enrichment
) VALUES (
    %(signal_id)s, %(artist)s, %(artist_id)s, %(track_id)s, %(title)s, %(genres)s,
    %(played_at)s, %(sources)s, %(artist_popularity)s, %(track_popularity)s, %(pending_enrichment)s
)
ON CONFLICT (signal_id) DO UPDATE
    SET signal_id = EXCLUDED.signal_id
RETURNING (xmax = 0) AS inserted
"""


class HistoryRepository:
    def upsert(self, conn: psycopg.Connection, msg: dict) -> bool:
        params = {
            "signal_id": msg.get("signal_id"),
            "artist": msg.get("artist"),
            "artist_id": msg.get("artist_id"),
            "track_id": msg.get("track_id"),
            "title": msg.get("title"),
            "genres": msg.get("genres") or [],
            "played_at": msg.get("played_at"),
            "sources": msg.get("sources", []),
            "artist_popularity": msg.get("artist_popularity"),
            "track_popularity": msg.get("track_popularity"),
            "pending_enrichment": bool(msg.get("pending_enrichment", False)),
        }
        with conn.cursor() as cur:
            cur.execute(_UPSERT_SQL, params)
            row = cur.fetchone()
            if row is None:
                _log.warning("upsert_no_row_returned", signal_id=str(params["signal_id"])[:8])
                return False
            inserted = bool(row[0])
        _log.debug("upsert", signal_id=str(params["signal_id"])[:8], inserted=inserted)
        return inserted

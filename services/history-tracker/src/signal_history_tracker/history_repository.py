import json

import psycopg

from signal_common.logger import get_logger

_log = get_logger(__name__)

_UPSERT_SQL = """
INSERT INTO listening_history (
    signal_id, artist, artist_id, title, genres,
    played_at, sources, audio_features, popularity
) VALUES (
    %(signal_id)s, %(artist)s, %(artist_id)s, %(title)s, %(genres)s,
    %(played_at)s, %(sources)s, %(audio_features)s::jsonb, %(popularity)s
)
ON CONFLICT (signal_id) DO UPDATE
    SET signal_id = EXCLUDED.signal_id
RETURNING (xmax = 0) AS inserted
"""


class HistoryRepository:
    def upsert(self, conn: psycopg.Connection, msg: dict) -> bool:
        audio = msg.get("audio_features")
        params = {
            "signal_id": msg.get("signal_id"),
            "artist": msg.get("artist"),
            "artist_id": msg.get("artist_id"),
            "title": msg.get("title"),
            "genres": msg.get("genres", []),
            "played_at": msg.get("played_at"),
            "sources": msg.get("sources", []),
            "audio_features": json.dumps(audio) if audio is not None else None,
            "popularity": msg.get("popularity"),
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

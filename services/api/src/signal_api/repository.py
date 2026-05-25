from __future__ import annotations

import json
from uuid import UUID

import psycopg
from psycopg.rows import dict_row


class ArtistRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def list_artists(
        self,
        status: str | None,
        high_priority: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict], int]:
        where, params = self._build_artist_filters(status, high_priority)
        offset = (page - 1) * page_size

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT id, name, status, high_priority, scrobble_count, genres
                FROM artists
                {where}
                ORDER BY scrobble_count DESC
                LIMIT %s OFFSET %s
                """,
                [*params, page_size, offset],
            )
            rows = cur.fetchall()

            cur.execute(
                f"SELECT COUNT(*) AS total FROM artists {where}",
                params,
            )
            total = cur.fetchone()["total"]

        return rows, total

    def get_artist_by_id(self, artist_id: UUID) -> dict | None:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    a.id, a.name, a.status, a.high_priority,
                    a.scrobble_count, a.play_count, a.genres,
                    a.first_seen_at, a.last_explored_at,
                    r.score, r.score_breakdown, r.evidence_tracks, r.updated_at AS rec_updated_at
                FROM artists a
                LEFT JOIN artist_recommendations r ON r.artist_id = a.id
                WHERE a.id = %s
                """,
                [str(artist_id)],
            )
            row = cur.fetchone()

        return row

    def list_recommendations(
        self,
        page: int,
        page_size: int,
        include_following: bool = False,
    ) -> tuple[list[dict], int]:
        offset = (page - 1) * page_size
        # Static constants — never user input; chosen by a bool flag only.
        _REC_STATUS_ALL = "a.status != 'BLACKLISTED'"
        _REC_STATUS_NO_FOLLOWING = "a.status NOT IN ('BLACKLISTED', 'FOLLOWING')"
        status_filter = _REC_STATUS_ALL if include_following else _REC_STATUS_NO_FOLLOWING

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT
                    a.id, a.name, a.status, a.high_priority, a.genres,
                    r.score, r.score_breakdown, r.evidence_tracks, r.updated_at
                FROM artist_recommendations r
                JOIN artists a ON a.id = r.artist_id
                WHERE {status_filter}
                ORDER BY r.score DESC, a.name ASC
                LIMIT %s OFFSET %s
                """,
                [page_size, offset],
            )
            rows = cur.fetchall()

            cur.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM artist_recommendations r
                JOIN artists a ON a.id = r.artist_id
                WHERE {status_filter}
                """,
                [],
            )
            total = cur.fetchone()["total"]

        return rows, total

    def update_artist_status(self, artist_id: UUID, new_status: str) -> dict | None:
        with self._conn.transaction():
            with self._conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE artists
                    SET status = %s
                    WHERE id = %s
                    RETURNING id, name, status
                    """,
                    [new_status, str(artist_id)],
                )
                return cur.fetchone()

    @staticmethod
    def _build_artist_filters(
        status: str | None,
        high_priority: bool | None,
    ) -> tuple[str, list]:
        conditions: list[str] = []
        params: list = []

        if status is not None:
            conditions.append("status = %s")
            params.append(status)
        if high_priority is not None:
            conditions.append("high_priority = %s")
            params.append(high_priority)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return where, params

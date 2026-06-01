from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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
                SELECT
                    a.id, a.name, a.status, a.high_priority,
                    a.scrobble_count, a.genres, a.source, a.origin_artist_id,
                    o.name AS origin_artist_name,
                    a.external_ids->>'spotify' AS spotify_uri
                FROM artists a
                LEFT JOIN artists o ON o.id = a.origin_artist_id
                {where}
                ORDER BY a.scrobble_count DESC
                LIMIT %s OFFSET %s
                """,
                [*params, page_size, offset],
            )
            rows = cur.fetchall()

            cur.execute(
                f"SELECT COUNT(*) AS total FROM artists a {where}",
                params,
            )
            count_row = cur.fetchone()
            assert count_row is not None
            total = count_row["total"]

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
                    a.external_ids->>'spotify' AS spotify_uri,
                    r.score, r.score_breakdown, r.updated_at,
                    (
                        SELECT COALESCE(jsonb_agg(
                            CASE
                                WHEN lh.title IS NOT NULL
                                THEN lh.artist || ' — ' || lh.title
                                ELSE e
                            END
                        ), '[]'::jsonb)
                        FROM jsonb_array_elements_text(r.evidence_tracks) e
                        LEFT JOIN listening_history lh ON lh.signal_id = e
                    ) AS evidence_tracks
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
            count_row = cur.fetchone()
            assert count_row is not None
            total = count_row["total"]

        return rows, total

    def update_artist_status(self, artist_id: UUID, new_status: str) -> dict | None:
        with self._conn.transaction(), self._conn.cursor(row_factory=dict_row) as cur:
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
            conditions.append("a.status = %s")
            params.append(status)
        if high_priority is not None:
            conditions.append("a.high_priority = %s")
            params.append(high_priority)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return where, params


class StatsRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def get_summary(self) -> dict:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT status, COUNT(*) AS cnt FROM artists GROUP BY status")
            rows = cur.fetchall()

        counts: dict[str, int] = {s: 0 for s in ("TRACKED", "FOLLOWING", "PUBLISHED", "BLACKLISTED")}
        for row in rows:
            key = row["status"].upper()
            if key in counts:
                counts[key] = row["cnt"]

        return {
            "tracked": counts["TRACKED"],
            "following": counts["FOLLOWING"],
            "published": counts["PUBLISHED"],
            "blacklisted": counts["BLACKLISTED"],
            "total": sum(counts.values()),
        }

    def get_health(self, threshold_minutes: int) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT service, last_played_at, updated_at FROM ingester_checkpoints ORDER BY service"
            )
            rows = cur.fetchall()

        now = datetime.now(tz=timezone.utc)
        threshold = timedelta(minutes=threshold_minutes)
        return [
            {
                "service": row["service"],
                "last_seen_at": row["last_played_at"],
                "stale": (now - row["last_played_at"].replace(tzinfo=timezone.utc)) > threshold
                if row["last_played_at"].tzinfo is None
                else (now - row["last_played_at"]) > threshold,
            }
            for row in rows
        ]

    def get_genres(self, top_n: int = 10) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT genre, COUNT(*) AS artist_count
                FROM artists, UNNEST(genres) AS genre
                WHERE genre IS NOT NULL AND TRIM(genre) != ''
                GROUP BY genre
                ORDER BY artist_count DESC
                LIMIT %s
                """,
                [top_n],
            )
            return cur.fetchall()

    def get_score_distribution(self) -> dict:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)                                                         AS total_scored,
                    MIN(r.score * 100)                                               AS min_score,
                    MAX(r.score * 100)                                               AS max_score,
                    AVG(r.score * 100)                                               AS mean_score,
                    COUNT(*) FILTER (WHERE r.score * 100 >= 0   AND r.score * 100 < 20)   AS bucket_0,
                    COUNT(*) FILTER (WHERE r.score * 100 >= 20  AND r.score * 100 < 40)   AS bucket_1,
                    COUNT(*) FILTER (WHERE r.score * 100 >= 40  AND r.score * 100 < 60)   AS bucket_2,
                    COUNT(*) FILTER (WHERE r.score * 100 >= 60  AND r.score * 100 < 80)   AS bucket_3,
                    COUNT(*) FILTER (WHERE r.score * 100 >= 80  AND r.score * 100 <= 100) AS bucket_4
                FROM artist_recommendations r
                JOIN artists a ON a.id = r.artist_id
                WHERE a.status != 'BLACKLISTED'
                """
            )
            row = cur.fetchone()
            assert row is not None

        total = row["total_scored"] or 0
        return {
            "total_scored": total,
            "min_score": float(row["min_score"]) if row["min_score"] is not None else None,
            "max_score": float(row["max_score"]) if row["max_score"] is not None else None,
            "mean_score": float(row["mean_score"]) if row["mean_score"] is not None else None,
            "buckets": [
                {"label": "0–20",   "min_score": 0.0,  "max_score": 20.0,  "count": row["bucket_0"] or 0},
                {"label": "20–40",  "min_score": 20.0, "max_score": 40.0,  "count": row["bucket_1"] or 0},
                {"label": "40–60",  "min_score": 40.0, "max_score": 60.0,  "count": row["bucket_2"] or 0},
                {"label": "60–80",  "min_score": 60.0, "max_score": 80.0,  "count": row["bucket_3"] or 0},
                {"label": "80–100", "min_score": 80.0, "max_score": 100.0, "count": row["bucket_4"] or 0},
            ],
        }

    def get_weekly_discoveries(self, num_weeks: int = 12) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    date_trunc('week', added_at AT TIME ZONE 'UTC')::date AS week_start,
                    COUNT(*) AS new_artists
                FROM artists
                WHERE added_at >= NOW() - (INTERVAL '1 week' * %s)
                GROUP BY week_start
                ORDER BY week_start ASC
                """,
                [num_weeks],
            )
            db_rows = {row["week_start"]: row["new_artists"] for row in cur.fetchall()}

        # Generate the last num_weeks Monday dates and zero-fill gaps
        today = date.today()
        # Find the most recent Monday
        days_since_monday = today.weekday()
        current_monday = today - timedelta(days=days_since_monday)
        weeks = []
        for i in range(num_weeks - 1, -1, -1):
            week_start = current_monday - timedelta(weeks=i)
            weeks.append({"week_start": week_start, "new_artists": db_rows.get(week_start, 0)})
        return weeks

    def get_novelty_ratio(self, days: int = 30) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                WITH date_series AS (
                    SELECT generate_series(
                        (NOW() - (INTERVAL '1 day' * %s))::date,
                        NOW()::date,
                        INTERVAL '1 day'
                    )::date AS day
                ),
                daily AS (
                    SELECT
                        lh.played_at::date                                                  AS day,
                        COUNT(*)                                                             AS total_plays,
                        COUNT(*) FILTER (
                            WHERE a.added_at >= lh.played_at - INTERVAL '30 days'
                        )                                                                    AS novel_plays
                    FROM listening_history lh
                    LEFT JOIN artists a ON a.name = lh.artist
                    WHERE lh.played_at >= NOW() - (INTERVAL '1 day' * %s)
                    GROUP BY lh.played_at::date
                )
                SELECT
                    ds.day,
                    COALESCE(
                        CASE WHEN d.total_plays > 0
                             THEN d.novel_plays::float / d.total_plays
                             ELSE 0.0 END,
                        0.0
                    ) AS ratio
                FROM date_series ds
                LEFT JOIN daily d ON d.day = ds.day
                ORDER BY ds.day
                """,
                [days - 1, days],
            )
            return [{"day": row["day"], "ratio": float(row["ratio"])} for row in cur.fetchall()]

    def get_artist_sources(self) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(source, 'unknown') AS source,
                    COUNT(*) AS count
                FROM artists
                WHERE source IS NOT NULL AND source != ''
                GROUP BY source
                ORDER BY count DESC
                LIMIT 10
                """
            )
            return cur.fetchall()

    def get_play_velocity(self, days: int = 30) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                WITH date_series AS (
                    SELECT generate_series(
                        (NOW() - (INTERVAL '1 day' * %s))::date,
                        NOW()::date,
                        INTERVAL '1 day'
                    )::date AS day
                ),
                daily AS (
                    SELECT played_at::date AS day, COUNT(*) AS plays
                    FROM listening_history
                    WHERE played_at >= NOW() - (INTERVAL '1 day' * %s)
                    GROUP BY played_at::date
                )
                SELECT ds.day, COALESCE(d.plays, 0) AS plays
                FROM date_series ds
                LEFT JOIN daily d ON d.day = ds.day
                ORDER BY ds.day
                """,
                [days - 1, days],
            )
            return [{"day": row["day"], "plays": int(row["plays"])} for row in cur.fetchall()]

    def get_score_breakdown_averages(self) -> dict:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    AVG((score_breakdown->>'genre_novelty')::float) * 100  AS avg_genre_novelty,
                    AVG((score_breakdown->>'popularity_norm')::float) * 100 AS avg_popularity_norm,
                    COUNT(*) AS total
                FROM artist_recommendations r
                JOIN artists a ON a.id = r.artist_id
                WHERE a.status != 'BLACKLISTED'
                  AND score_breakdown IS NOT NULL
                  AND score_breakdown ? 'genre_novelty'
                  AND score_breakdown ? 'popularity_norm'
                """
            )
            row = cur.fetchone()
            assert row is not None
            return {
                "avg_genre_novelty": float(row["avg_genre_novelty"]) if row["avg_genre_novelty"] is not None else None,
                "avg_popularity_norm": float(row["avg_popularity_norm"]) if row["avg_popularity_norm"] is not None else None,
                "total": int(row["total"]) if row["total"] else 0,
            }

    def get_exploration_coverage(self) -> dict:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(last_similar_explored_at) AS explored
                FROM artists
                WHERE status = 'FOLLOWING'
                """
            )
            row = cur.fetchone()
            assert row is not None
        total = int(row["total"]) or 0
        explored = int(row["explored"]) or 0
        return {
            "total": total,
            "explored": explored,
            "coverage_pct": round(explored / total * 100, 1) if total > 0 else 0.0,
        }

    def get_pipeline_funnel(self) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    status,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE high_priority = true) AS high_priority
                FROM artists
                GROUP BY status
                ORDER BY
                    CASE status
                        WHEN 'TRACKED'     THEN 1
                        WHEN 'FOLLOWING'   THEN 2
                        WHEN 'PUBLISHED'   THEN 3
                        WHEN 'BLACKLISTED' THEN 4
                        ELSE 5
                    END
                """
            )
            return cur.fetchall()

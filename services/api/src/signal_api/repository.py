from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
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
        genre: str | None = None,
        sort_by: str | None = None,
        order: str = "desc",
    ) -> tuple[list[dict], int]:
        where, params = self._build_artist_filters(status, high_priority, genre)
        offset = (page - 1) * page_size

        # sort_by and order are validated by the router (Literal types); interpolation is safe.
        _SORT_COLS = {
            "first_seen_at": "a.first_seen_at",
            "scrobble_count": "a.scrobble_count",
            "first_play_at": "first_play_at",
        }
        _col = _SORT_COLS.get(sort_by or "", "a.scrobble_count")
        _dir = "ASC" if order == "asc" else "DESC"
        _nulls = "NULLS LAST" if sort_by == "first_play_at" else ""

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT
                    a.id, a.name, a.status, a.high_priority,
                    a.scrobble_count, a.genres, a.source, a.origin_artist_id,
                    o.name AS origin_artist_name,
                    a.external_ids->>'spotify' AS spotify_uri,
                    (SELECT MIN(lh.played_at)
                     FROM listening_history lh
                     WHERE lower(lh.artist) = lower(a.name)) AS first_play_at
                FROM artists a
                LEFT JOIN artists o ON o.id = a.origin_artist_id
                {where}
                ORDER BY {_col} {_dir} {_nulls}
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
                            jsonb_build_object(
                                'text', CASE
                                    WHEN lh.title IS NOT NULL
                                    THEN lh.artist || ' — ' || lh.title
                                    ELSE e
                                END,
                                'track_id', lh.track_id
                            )
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

    def update_artist_spotify(self, artist_id: UUID, spotify_id: str) -> dict | None:
        with self._conn.transaction(), self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE artists
                SET external_ids = COALESCE(external_ids, '{}'::jsonb)
                                 || jsonb_build_object('spotify', %s::text),
                    last_explored_at = NULL
                WHERE id = %s
                RETURNING id, name
                """,
                [f"spotify:artist:{spotify_id}", str(artist_id)],
            )
            return cur.fetchone()

    def update_artist_status(self, artist_id: UUID, new_status: str) -> dict | None:
        with self._conn.transaction(), self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                    UPDATE artists
                    SET status = %s, status_changed_at = now()
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
        genre: str | None = None,
    ) -> tuple[str, list]:
        conditions: list[str] = []
        params: list = []

        if status is not None:
            conditions.append("a.status = %s")
            params.append(status)
        if high_priority is not None:
            conditions.append("a.high_priority = %s")
            params.append(high_priority)
        if genre is not None:
            conditions.append("%s = ANY(a.genres)")
            params.append(genre)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return where, params


class StatsRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def get_summary(self) -> dict:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT status, COUNT(*) AS cnt FROM artists GROUP BY status")
            rows = cur.fetchall()

        statuses = ("TRACKED", "FOLLOWING", "PUBLISHED", "BLACKLISTED")
        counts: dict[str, int] = {s: 0 for s in statuses}
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
                "SELECT service, last_played_at, updated_at"
                " FROM ingester_checkpoints ORDER BY service"
            )
            rows = cur.fetchall()

        now = datetime.now(tz=UTC)
        threshold = timedelta(minutes=threshold_minutes)
        return [
            {
                "service": row["service"],
                "last_seen_at": row["last_played_at"],
                "stale": (now - row["last_played_at"].replace(tzinfo=UTC)) > threshold
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
                    COUNT(*) AS total_scored,
                    MIN(r.score * 100)                                               AS min_score,
                    MAX(r.score * 100)                                               AS max_score,
                    AVG(r.score * 100)                                               AS mean_score,
                    COUNT(*) FILTER (WHERE r.score * 100 >= 0  AND r.score * 100 < 20)  AS bucket_0,
                    COUNT(*) FILTER (WHERE r.score * 100 >= 20 AND r.score * 100 < 40)  AS bucket_1,
                    COUNT(*) FILTER (WHERE r.score * 100 >= 40 AND r.score * 100 < 60)  AS bucket_2,
                    COUNT(*) FILTER (WHERE r.score * 100 >= 60 AND r.score * 100 < 80)  AS bucket_3,
                    COUNT(*) FILTER (WHERE r.score * 100 >= 80 AND r.score * 100 <= 100) AS bucket_4
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
                {"label": "0–20",   "min_score": 0.0,  "max_score": 20.0,
                 "count": row["bucket_0"] or 0},
                {"label": "20–40",  "min_score": 20.0, "max_score": 40.0,
                 "count": row["bucket_1"] or 0},
                {"label": "40–60",  "min_score": 40.0, "max_score": 60.0,
                 "count": row["bucket_2"] or 0},
                {"label": "60–80",  "min_score": 60.0, "max_score": 80.0,
                 "count": row["bucket_3"] or 0},
                {"label": "80–100", "min_score": 80.0, "max_score": 100.0,
                 "count": row["bucket_4"] or 0},
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
                        lh.played_at::date AS day,
                        COUNT(*) AS total_plays,
                        COUNT(*) FILTER (
                            WHERE a.added_at >= lh.played_at - INTERVAL '30 days'
                        ) AS novel_plays
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
                "avg_genre_novelty": (
                    float(row["avg_genre_novelty"])
                    if row["avg_genre_novelty"] is not None
                    else None
                ),
                "avg_popularity_norm": (
                    float(row["avg_popularity_norm"])
                    if row["avg_popularity_norm"] is not None
                    else None
                ),
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

    def get_blacklist_rate(self) -> dict:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'BLACKLISTED') AS blacklisted,
                    COUNT(*) AS total_meaningful
                FROM artists
                WHERE status IN ('FOLLOWING', 'PUBLISHED', 'BLACKLISTED')
                """
            )
            row = cur.fetchone()
            assert row is not None
        blacklisted = int(row["blacklisted"])
        total = int(row["total_meaningful"])
        return {
            "blacklisted": blacklisted,
            "total_meaningful": total,
            "rate": round(blacklisted / max(total, 1), 4),
        }

    def get_active_genres(self, top_n: int = 20) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT genre, COUNT(*) AS artist_count
                FROM artists, UNNEST(genres) AS genre
                WHERE status IN ('TRACKED', 'FOLLOWING')
                  AND genre IS NOT NULL AND TRIM(genre) != ''
                GROUP BY genre
                ORDER BY artist_count DESC
                LIMIT %s
                """,
                [top_n],
            )
            return cur.fetchall()

    def get_stale_recs(self, threshold_days: int = 14) -> dict:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS count, MIN(status_changed_at) AS oldest_status_changed_at
                FROM artists
                WHERE status = 'TRACKED'
                  AND (
                    -- NULL means the artist was seeded before status_changed_at was tracked;
                    -- treat as "never reviewed" and therefore stale
                    status_changed_at IS NULL
                    OR status_changed_at < now() - make_interval(days => %s)
                  )
                """,
                [threshold_days],
            )
            row = cur.fetchone()
            assert row is not None
        return {
            "count": int(row["count"]),
            "threshold_days": threshold_days,
            "oldest_status_changed_at": row["oldest_status_changed_at"],
        }

    def get_score_freshness(self) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                WITH raw AS (
                    SELECT
                        CASE
                            WHEN updated_at >= now() - interval '1 day'   THEN 1
                            WHEN updated_at >= now() - interval '7 days'  THEN 2
                            WHEN updated_at >= now() - interval '30 days' THEN 3
                            ELSE 4
                        END AS bucket
                    FROM artist_recommendations
                )
                SELECT
                    CASE bucket
                        WHEN 1 THEN '<1D' WHEN 2 THEN '1-7D'
                        WHEN 3 THEN '7-30D' ELSE '>30D'
                    END AS label,
                    bucket AS sort_order,
                    CASE bucket
                        WHEN 1 THEN 1 WHEN 2 THEN 7
                        WHEN 3 THEN 30 ELSE NULL
                    END AS max_age_days,
                    COUNT(*) AS count
                FROM raw
                GROUP BY bucket
                ORDER BY bucket
                """
            )
            return [
                {"label": r["label"], "max_age_days": r["max_age_days"], "count": int(r["count"])}
                for r in cur.fetchall()
            ]


class ReportsRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def _date_filter(self, from_date: date | None, to_date: date | None) -> tuple[str, list]:
        if from_date and to_date:
            return (
                "AND played_at >= %s AND played_at < %s",
                [from_date, to_date + timedelta(days=1)],
            )
        return "", []

    def get_headline(self, from_date: date | None, to_date: date | None) -> dict:
        clause, params = self._date_filter(from_date, to_date)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT COUNT(*) AS total_plays, COUNT(DISTINCT LOWER(artist)) AS unique_artists"
                f" FROM listening_history WHERE TRUE {clause}",
                params,
            )
            row = cur.fetchone()
            assert row is not None
        return {
            "total_plays": int(row["total_plays"]),
            "unique_artists": int(row["unique_artists"]),
        }

    def get_top_artists(self, from_date: date | None, to_date: date | None) -> list[dict]:
        clause, params = self._date_filter(from_date, to_date)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT artist AS name, COUNT(*) AS plays
                FROM listening_history
                WHERE TRUE {clause}
                GROUP BY artist
                ORDER BY plays DESC
                LIMIT 20
                """,
                params,
            )
            rows = cur.fetchall()
        if not rows:
            return []
        max_plays = rows[0]["plays"]
        return [
            {
                "rank": i + 1,
                "name": row["name"],
                "plays": int(row["plays"]),
                "weight": round(row["plays"] / max_plays, 4),
            }
            for i, row in enumerate(rows)
        ]

    def get_plays_trend(self, from_date: date | None, to_date: date | None) -> list[dict]:
        clause, params = self._date_filter(from_date, to_date)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT date_trunc('day', played_at AT TIME ZONE 'UTC')::date AS play_date,
                       COUNT(*) AS plays
                FROM listening_history
                WHERE played_at IS NOT NULL {clause}
                GROUP BY play_date
                ORDER BY play_date
                """,
                params,
            )
            rows = {str(r["play_date"]): int(r["plays"]) for r in cur.fetchall()}

        if not rows:
            return []

        if from_date and to_date:
            current = from_date
            result = []
            while current <= to_date:
                key = str(current)
                result.append({"date": key, "plays": rows.get(key, 0)})
                current += timedelta(days=1)
            return result

        if rows:
            all_dates = sorted(rows.keys())
            start = date.fromisoformat(all_dates[0])
            end = date.fromisoformat(all_dates[-1])
            current = start
            result = []
            while current <= end:
                key = str(current)
                result.append({"date": key, "plays": rows.get(key, 0)})
                current += timedelta(days=1)
            return result
        return []

    def get_genres(self, from_date: date | None, to_date: date | None) -> list[dict]:
        clause, params = self._date_filter(from_date, to_date)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT g AS genre, COUNT(*) AS plays
                FROM listening_history, LATERAL unnest(genres) AS g
                WHERE g IS NOT NULL {clause}
                GROUP BY genre
                ORDER BY plays DESC
                LIMIT 20
                """,
                params,
            )
            rows = cur.fetchall()
        if not rows:
            return []
        max_plays = rows[0]["plays"]
        return [
            {
                "genre": row["genre"],
                "plays": int(row["plays"]),
                "weight": round(row["plays"] / max_plays, 4),
            }
            for row in rows
        ]

    def get_discovery_timeline(self, from_date: date | None, to_date: date | None) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            if from_date and to_date:
                cur.execute(
                    """
                    SELECT to_char(date_trunc('month', first_seen_at), 'YYYY-MM') AS month,
                           COUNT(*) AS count
                    FROM artists
                    WHERE first_seen_at IS NOT NULL
                      AND first_seen_at >= %s AND first_seen_at < %s
                    GROUP BY month
                    ORDER BY month
                    """,
                    [from_date, to_date + timedelta(days=1)],
                )
            else:
                cur.execute(
                    """
                    SELECT to_char(date_trunc('month', first_seen_at), 'YYYY-MM') AS month,
                           COUNT(*) AS count
                    FROM artists
                    WHERE first_seen_at IS NOT NULL
                    GROUP BY month
                    ORDER BY month
                    """
                )
            rows = {r["month"]: int(r["count"]) for r in cur.fetchall()}

        if not rows:
            return []

        months = sorted(rows.keys())
        start_month = months[0]
        end_month = months[-1]

        from datetime import datetime as _dt
        start_dt = _dt.strptime(start_month, "%Y-%m")
        end_dt = _dt.strptime(end_month, "%Y-%m")
        result = []
        current = start_dt
        while current <= end_dt:
            key = current.strftime("%Y-%m")
            result.append({"month": key, "count": rows.get(key, 0)})
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        return result

    def get_listening_ratio(self, from_date: date | None, to_date: date | None) -> dict:
        clause, params = self._date_filter(from_date, to_date)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT lh.artist, COUNT(*) AS plays, a.first_seen_at
                FROM listening_history lh
                LEFT JOIN artists a ON LOWER(a.name) = LOWER(lh.artist)
                WHERE TRUE {clause}
                GROUP BY lh.artist, a.first_seen_at
                """,
                params,
            )
            rows = cur.fetchall()

        if from_date is None:
            total = sum(int(r["plays"]) for r in rows)
            return {
                "familiar_plays": total,
                "new_plays": 0,
                "unknown_plays": 0,
                "familiar_pct": 100.0 if total > 0 else 0.0,
                "new_pct": 0.0,
            }

        familiar = new = unknown = 0
        for row in rows:
            plays = int(row["plays"])
            fsa = row["first_seen_at"]
            if fsa is None:
                unknown += plays
            elif fsa.date() < from_date:
                familiar += plays
            else:
                new += plays

        total = familiar + new + unknown
        return {
            "familiar_plays": familiar,
            "new_plays": new,
            "unknown_plays": unknown,
            "familiar_pct": round(familiar / total * 100, 1) if total > 0 else 0.0,
            "new_pct": round(new / total * 100, 1) if total > 0 else 0.0,
        }

    def get_streak(self, from_date: date | None, to_date: date | None) -> dict:
        clause, params = self._date_filter(from_date, to_date)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT DISTINCT date_trunc('day', played_at AT TIME ZONE 'UTC')::date AS play_date
                FROM listening_history
                WHERE played_at IS NOT NULL {clause}
                ORDER BY play_date
                """,
                params,
            )
            play_dates = [r["play_date"] for r in cur.fetchall()]

        if not play_dates:
            return {"current": 0, "longest": 0}

        period_end = to_date or date.today()

        longest = current_run = 1
        for i in range(1, len(play_dates)):
            if (play_dates[i] - play_dates[i - 1]).days == 1:
                current_run += 1
                longest = max(longest, current_run)
            else:
                current_run = 1

        current = 0
        for _ in range(len(play_dates) - 1, -1, -1):
            expected = period_end - timedelta(days=current)
            if play_dates[-(current + 1)] == expected:
                current += 1
            else:
                break

        return {"current": current, "longest": longest}

    def get_funnel(self, from_date: date | None, to_date: date | None) -> dict:
        period_filtered = False
        entries = []

        if from_date and to_date:
            with self._conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT status, COUNT(*) AS count
                    FROM artists
                    WHERE status_changed_at >= %s AND status_changed_at < %s
                    GROUP BY status
                    """,
                    [from_date, to_date + timedelta(days=1)],
                )
                rows = cur.fetchall()
            if rows:
                period_filtered = True
                entries = [{"status": r["status"], "count": int(r["count"])} for r in rows]

        if not entries:
            with self._conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT status, COUNT(*) AS count FROM artists GROUP BY status")
                entries = [
                    {"status": r["status"], "count": int(r["count"])} for r in cur.fetchall()
                ]

        status_order = {"TRACKED": 1, "FOLLOWING": 2, "PUBLISHED": 3, "BLACKLISTED": 4}
        entries.sort(key=lambda e: status_order.get(e["status"], 5))
        return {"entries": entries, "period_filtered": period_filtered}

    def get_listening_clock(self, from_date: date | None, to_date: date | None) -> list[dict]:
        clause, params = self._date_filter(from_date, to_date)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT EXTRACT(HOUR FROM played_at AT TIME ZONE 'UTC')::int AS hour,
                       COUNT(*) AS plays
                FROM listening_history
                WHERE played_at IS NOT NULL {clause}
                GROUP BY hour
                ORDER BY hour
                """,
                params,
            )
            rows = {int(r["hour"]): int(r["plays"]) for r in cur.fetchall()}
        return [{"hour": h, "plays": rows.get(h, 0)} for h in range(24)]

    def get_fingerprint(self, from_date: date | None, to_date: date | None) -> dict:
        clause, date_params = self._date_filter(from_date, to_date)
        today = date.today()

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS total_plays,
                    COUNT(DISTINCT LOWER(artist)) AS unique_artists,
                    COUNT(DISTINCT
                        date_trunc('day', played_at AT TIME ZONE 'UTC')::date
                    ) AS listening_days,
                    MIN(played_at AT TIME ZONE 'UTC')::date AS first_day,
                    MAX(played_at AT TIME ZONE 'UTC')::date AS last_day
                FROM listening_history
                WHERE played_at IS NOT NULL {clause}
                """,
                date_params,
            )
            row = cur.fetchone()
            if not row or row["total_plays"] == 0:
                return {
                    "consistency": 0.0, "variety": 0.0, "discovery": 0.0,
                    "night_owl": 0.0, "depth": 0.0,
                }

            total_plays = int(row["total_plays"])
            unique_artists = int(row["unique_artists"])
            listening_days = int(row["listening_days"])
            first_day: date | None = row["first_day"]
            last_day: date | None = row["last_day"]

            if from_date and to_date:
                period_days = (to_date - from_date).days + 1
            elif first_day and last_day:
                period_days = (last_day - first_day).days + 1
            else:
                period_days = 1

            consistency = round(min(listening_days / max(period_days, 1), 1.0), 4)

            cur.execute(
                f"""
                SELECT COUNT(*) AS plays
                FROM listening_history
                WHERE played_at IS NOT NULL {clause}
                GROUP BY LOWER(artist)
                ORDER BY plays DESC
                LIMIT 1
                """,
                date_params,
            )
            top_row = cur.fetchone()
            top_plays = int(top_row["plays"]) if top_row else 0
            variety = round(1.0 - (top_plays / total_plays), 4)

            cur.execute(
                f"""
                SELECT COUNT(*) AS night_plays
                FROM listening_history
                WHERE played_at IS NOT NULL
                  AND (EXTRACT(HOUR FROM played_at AT TIME ZONE 'UTC') >= 20
                       OR EXTRACT(HOUR FROM played_at AT TIME ZONE 'UTC') < 4)
                  {clause}
                """,
                date_params,
            )
            night_row = cur.fetchone()
            night_plays = int(night_row["night_plays"]) if night_row else 0
            night_owl = round(night_plays / total_plays, 4)

            cur.execute(
                f"""
                SELECT COUNT(*) AS deep_artists
                FROM (
                    SELECT LOWER(artist)
                    FROM listening_history
                    WHERE played_at IS NOT NULL {clause}
                    GROUP BY LOWER(artist)
                    HAVING COUNT(*) >= 2
                ) t
                """,
                date_params,
            )
            depth_row = cur.fetchone()
            deep_artists = int(depth_row["deep_artists"]) if depth_row else 0
            depth = round(deep_artists / max(unique_artists, 1), 4)

            if from_date and to_date:
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT LOWER(lh.artist)) AS new_artists
                    FROM listening_history lh
                    JOIN artists a ON LOWER(a.name) = LOWER(lh.artist)
                    WHERE lh.played_at IS NOT NULL
                      AND lh.played_at >= %s AND lh.played_at < %s
                      AND a.first_seen_at >= %s AND a.first_seen_at < %s
                    """,
                    [
                        from_date, to_date + timedelta(days=1),
                        from_date, to_date + timedelta(days=1),
                    ],
                )
            else:
                cutoff = today - timedelta(days=90)
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT LOWER(lh.artist)) AS new_artists
                    FROM listening_history lh
                    JOIN artists a ON LOWER(a.name) = LOWER(lh.artist)
                    WHERE lh.played_at IS NOT NULL
                      AND a.first_seen_at >= %s
                    """,
                    [cutoff],
                )
            disc_row = cur.fetchone()
            new_artists = int(disc_row["new_artists"]) if disc_row else 0
            discovery = round(new_artists / max(unique_artists, 1), 4)

        return {
            "consistency": consistency,
            "variety": variety,
            "discovery": discovery,
            "night_owl": night_owl,
            "depth": depth,
        }

    def get_genre_stream(
        self, from_date: date | None, to_date: date | None, top_n: int = 8
    ) -> dict:
        clause, date_params = self._date_filter(from_date, to_date)

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT g AS genre, COUNT(*) AS total_plays
                FROM listening_history, LATERAL unnest(genres) AS g
                WHERE g IS NOT NULL {clause}
                GROUP BY genre
                ORDER BY total_plays DESC
                LIMIT %s
                """,
                [*date_params, top_n],
            )
            top_genres = [r["genre"] for r in cur.fetchall()]

            if not top_genres:
                return {"top_genres": [], "points": []}

            cur.execute(
                f"""
                SELECT
                    to_char(
                        date_trunc('week', played_at AT TIME ZONE 'UTC'),
                        'YYYY-MM-DD'
                    ) AS week_start,
                    g AS genre,
                    COUNT(*) AS plays
                FROM listening_history, LATERAL unnest(genres) AS g
                WHERE g IS NOT NULL AND g = ANY(%s::text[]) {clause}
                GROUP BY week_start, genre
                ORDER BY week_start
                """,
                [top_genres, *date_params],
            )
            rows = cur.fetchall()

        week_map: dict[str, dict[str, int]] = {}
        for r in rows:
            ws = r["week_start"]
            if ws not in week_map:
                week_map[ws] = {}
            week_map[ws][r["genre"]] = int(r["plays"])

        points = [{"week_start": ws, "plays": week_map[ws]} for ws in sorted(week_map.keys())]
        return {"top_genres": top_genres, "points": points}

    def get_weekly_discovery_rate(self, from_date: date | None, to_date: date | None) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            if from_date and to_date:
                cur.execute(
                    """
                    SELECT to_char(
                               date_trunc('week', first_seen_at AT TIME ZONE 'UTC'),
                               'YYYY-MM-DD'
                           ) AS week_start,
                           COUNT(*) AS count
                    FROM artists
                    WHERE first_seen_at IS NOT NULL
                      AND first_seen_at >= %s AND first_seen_at < %s
                    GROUP BY week_start
                    ORDER BY week_start
                    """,
                    [from_date, to_date + timedelta(days=1)],
                )
            else:
                cur.execute(
                    """
                    SELECT to_char(
                               date_trunc('week', first_seen_at AT TIME ZONE 'UTC'),
                               'YYYY-MM-DD'
                           ) AS week_start,
                           COUNT(*) AS count
                    FROM artists
                    WHERE first_seen_at IS NOT NULL
                    GROUP BY week_start
                    ORDER BY week_start
                    """
                )
            return [
                {"week_start": r["week_start"], "count": int(r["count"])}
                for r in cur.fetchall()
            ]

    def get_discovery_highlight(self, from_date: date | None, to_date: date | None) -> dict | None:
        if not from_date or not to_date:
            return None
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT lh.artist AS name, COUNT(*) AS plays,
                       a.first_seen_at, a.genres,
                       a.external_ids->>'spotify' AS spotify_uri
                FROM listening_history lh
                JOIN artists a ON LOWER(a.name) = LOWER(lh.artist)
                WHERE lh.played_at >= %s AND lh.played_at < %s
                  AND a.first_seen_at >= %s AND a.first_seen_at < %s
                GROUP BY lh.artist, a.first_seen_at, a.genres, a.external_ids->>'spotify'
                ORDER BY plays DESC
                LIMIT 1
                """,
                [from_date, to_date + timedelta(days=1), from_date, to_date + timedelta(days=1)],
            )
            row = cur.fetchone()
        if not row:
            return None
        spotify_uri = row["spotify_uri"]
        spotify_id = spotify_uri.replace("spotify:artist:", "") if spotify_uri else None
        return {
            "name": row["name"],
            "plays": int(row["plays"]),
            "first_seen_at": row["first_seen_at"],
            "genres": list(row["genres"] or []),
            "spotify_id": spotify_id,
        }

    def get_genre_drift(self, from_date: date | None, to_date: date | None) -> dict:
        if not from_date or not to_date:
            return {"current": [], "previous": [], "period_days": None}
        period_days = (to_date - from_date).days + 1
        prev_to = from_date - timedelta(days=1)
        prev_from = prev_to - timedelta(days=period_days - 1)

        def _top5(fd: date, td: date) -> list[dict]:
            clause, params = self._date_filter(fd, td)
            with self._conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT g AS genre, COUNT(*) AS plays
                    FROM listening_history, LATERAL unnest(genres) AS g
                    WHERE g IS NOT NULL {clause}
                    GROUP BY genre
                    ORDER BY plays DESC
                    LIMIT 5
                    """,
                    params,
                )
                rows = cur.fetchall()
            if not rows:
                return []
            max_p = rows[0]["plays"]
            return [
                {
                    "genre": r["genre"],
                    "plays": int(r["plays"]),
                    "weight": round(r["plays"] / max_p, 4),
                }
                for r in rows
            ]

        return {
            "current": _top5(from_date, to_date),
            "previous": _top5(prev_from, prev_to),
            "period_days": period_days,
        }

    def get_calendar(self, from_date: date | None, to_date: date | None) -> dict:
        today = date.today()
        cal_from = from_date if from_date else today - timedelta(days=364)
        cal_to = to_date if to_date else today

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT date_trunc('day', played_at AT TIME ZONE 'UTC')::date AS play_date,
                       COUNT(*) AS plays
                FROM listening_history
                WHERE played_at IS NOT NULL
                  AND played_at >= %s AND played_at < %s
                GROUP BY play_date
                ORDER BY play_date
                """,
                [cal_from, cal_to + timedelta(days=1)],
            )
            rows = {str(r["play_date"]): int(r["plays"]) for r in cur.fetchall()}

        result = []
        current = cal_from
        while current <= cal_to:
            key = str(current)
            result.append({"date": key, "plays": rows.get(key, 0)})
            current += timedelta(days=1)

        return {"days": result, "from_date": str(cal_from), "to_date": str(cal_to)}

    def get_loyal_artists(self, from_date: date | None, to_date: date | None) -> list[dict]:
        cutoff = date.today() - timedelta(days=183)
        clause, date_params = self._date_filter(from_date, to_date)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT lh.artist AS name, COUNT(*) AS plays
                FROM listening_history lh
                JOIN artists a ON LOWER(a.name) = LOWER(lh.artist)
                WHERE lh.played_at IS NOT NULL
                  AND a.first_seen_at IS NOT NULL
                  AND a.first_seen_at < %s
                  {clause}
                GROUP BY lh.artist
                ORDER BY plays DESC
                LIMIT 20
                """,
                [cutoff, *date_params],
            )
            rows = cur.fetchall()
        if not rows:
            return []
        max_plays = rows[0]["plays"]
        return [
            {
                "rank": i + 1,
                "name": row["name"],
                "plays": int(row["plays"]),
                "weight": round(row["plays"] / max_plays, 4),
            }
            for i, row in enumerate(rows)
        ]

    def get_source_effectiveness(self, from_date: date | None, to_date: date | None) -> list[dict]:
        # Filters on first_seen_at (artist discovery date), not played_at, so _date_filter()
        # is intentionally not used here — it targets listening_history.played_at.
        if from_date and to_date:
            where_extra = "AND first_seen_at >= %s AND first_seen_at < %s"
            params: list = [from_date, to_date + timedelta(days=1)]
        else:
            where_extra = ""
            params = []
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT COALESCE(source, 'UNKNOWN') AS source,
                       COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status = 'PUBLISHED') AS published
                FROM artists
                WHERE status IN ('FOLLOWING', 'PUBLISHED', 'BLACKLISTED')
                  {where_extra}
                GROUP BY source
                ORDER BY total DESC
                """,
                params,
            )
            rows = cur.fetchall()
        return [
            {
                "source": r["source"],
                "total": int(r["total"]),
                "published": int(r["published"]),
                "publish_rate": round(int(r["published"]) / max(int(r["total"]), 1), 4),
            }
            for r in rows
        ]


class GraphRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def get_graph_data(
        self,
        status: str | None,
        genre: str | None,
        min_score: float | None,
        min_genre_artists: int,
        limit: int,
    ) -> dict:
        conditions: list[str] = []
        params: list = []

        if status is not None:
            conditions.append("a.status = %s")
            params.append(status)
        if genre is not None:
            conditions.append("%s = ANY(a.genres)")
            params.append(genre)
        if min_score is not None:
            conditions.append("r.score >= %s")
            params.append(min_score)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT
                    a.id::text AS id,
                    a.name,
                    a.status,
                    a.scrobble_count,
                    a.genres,
                    a.origin_artist_id::text AS origin_artist_id,
                    a.external_ids->>'spotify' AS spotify_uri,
                    r.score
                FROM artists a
                LEFT JOIN artist_recommendations r ON r.artist_id = a.id
                {where}
                ORDER BY a.scrobble_count DESC
                LIMIT %s
                """,
                [*params, limit],
            )
            rows = cur.fetchall()

        artist_ids: set[str] = {row["id"] for row in rows}

        genre_artist_count: dict[str, int] = defaultdict(int)
        for row in rows:
            for g in (row["genres"] or []):
                genre_artist_count[g] += 1

        nodes: list[dict] = []
        edges: list[dict] = []

        for row in rows:
            artist_key = f"artist:{row['id']}"
            spotify_uri = row.get("spotify_uri") or ""
            spotify_id: str | None = None
            if spotify_uri:
                spotify_id = spotify_uri.replace("spotify:artist:", "") or None

            nodes.append({
                "key": artist_key,
                "attributes": {
                    "nodeType": "artist",
                    "label": row["name"],
                    "status": row["status"],
                    "score": row["score"],
                    "scrobble_count": row["scrobble_count"],
                    "genres": row["genres"] or [],
                    "spotify_id": spotify_id,
                },
            })

            for g in (row["genres"] or []):
                if genre_artist_count[g] >= min_genre_artists:
                    edges.append({
                        "key": f"e:{artist_key}:genre:{g}",
                        "source": artist_key,
                        "target": f"genre:{g}",
                        "attributes": {"edgeType": "tagged"},
                    })

            origin = row.get("origin_artist_id")
            if origin and origin in artist_ids and origin != row["id"]:
                edges.append({
                    "key": f"e:{artist_key}:artist:{origin}",
                    "source": artist_key,
                    "target": f"artist:{origin}",
                    "attributes": {"edgeType": "similar"},
                })

        for g, count in genre_artist_count.items():
            if count >= min_genre_artists:
                nodes.append({
                    "key": f"genre:{g}",
                    "attributes": {
                        "nodeType": "genre",
                        "label": g,
                        "artist_count": count,
                    },
                })

        return {"nodes": nodes, "edges": edges}

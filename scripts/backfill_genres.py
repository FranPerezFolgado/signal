# /// script
# requires-python = ">=3.12"
# dependencies = ["requests>=2.31", "psycopg[binary]>=3.1"]
# ///
"""
Backfill genres for all artists that have no genres in the DB, using Last.fm
artist.getTopTags (works by artist name, no OAuth needed).

Note: Spotify removed genres from their API in late 2024; Last.fm is now the
reliable source for artist genre tags.

Run against a live DB (services do not need to be stopped):
    uv run --no-project python scripts/backfill_genres.py

Options:
    --min-count N   Minimum Last.fm tag count to include (default: 15).
                    Tags below this threshold are usually user noise, not genres.
    --max-tags N    Maximum genres to store per artist (default: 5).
    --limit N       Process at most N artists (useful for testing).

Required env vars (set in .env or shell):
    LASTFM_API_KEY
    DATABASE_URL
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import psycopg
import psycopg.rows
import requests

_LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"
_DELAY = 0.22  # ~4.5 req/s — comfortably within Last.fm's guidelines


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    env = Path(__file__).parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _get_artist_tags(artist: str, api_key: str, min_count: int, max_tags: int) -> list[str]:
    """Fetch top genre tags for an artist from Last.fm. Returns [] on any failure."""
    try:
        resp = requests.get(
            _LASTFM_URL,
            params={
                "method": "artist.getTopTags",
                "artist": artist,
                "api_key": api_key,
                "format": "json",
                "autocorrect": 1,
            },
            timeout=10,
        )
    except requests.RequestException:
        return []

    if resp.status_code != 200:
        return []

    data = resp.json()
    if "error" in data:
        return []

    tags = data.get("toptags", {}).get("tag", [])
    return [
        t["name"].lower()
        for t in tags
        if isinstance(t.get("count"), int) and t["count"] >= min_count and t.get("name")
    ][:max_tags]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _fetch_candidates(conn: psycopg.Connection, limit: int | None) -> list[dict]:
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            SELECT id, name
            FROM artists
            WHERE genres IS NULL OR array_length(genres, 1) IS NULL
            ORDER BY
                CASE status
                    WHEN 'FOLLOWING' THEN 0
                    WHEN 'TRACKED'   THEN 1
                    ELSE 2
                END,
                play_count DESC
            """
            + (f" LIMIT {int(limit)}" if limit else ""),
        )
        return cur.fetchall()


def _update_genres(conn: psycopg.Connection, artist_id: str, genres: list[str]) -> None:
    with conn.cursor() as cur:
        cur.execute("UPDATE artists SET genres = %s WHERE id = %s", (genres, artist_id))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill artist genres from Last.fm")
    parser.add_argument("--min-count", type=int, default=15,
                        help="Minimum Last.fm tag count to include (default: 15)")
    parser.add_argument("--max-tags", type=int, default=5,
                        help="Maximum genres per artist (default: 5)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N artists (for testing)")
    args = parser.parse_args()

    _load_dotenv()

    api_key = os.environ.get("LASTFM_API_KEY", "")
    db_url = os.environ.get("DATABASE_URL", "postgresql://signal:signal@localhost:5432/signal")

    if not api_key:
        print("[error] LASTFM_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    print("Signal — Genre Backfill (Last.fm)")
    print("=" * 44)

    updated = skipped = errors = 0

    with psycopg.connect(db_url) as conn:
        candidates = _fetch_candidates(conn, args.limit)
        total = len(candidates)
        print(f"Artists without genres: {total}")
        print(f"Settings: min_count={args.min_count}, max_tags={args.max_tags}")
        print()

        for i, row in enumerate(candidates, 1):
            name = row["name"]
            print(f"  [{i}/{total}] {name[:42]:<42}", end=" ", flush=True)

            try:
                genres = _get_artist_tags(name, api_key, args.min_count, args.max_tags)
            except Exception as exc:
                print(f"ERROR: {exc}")
                errors += 1
                time.sleep(_DELAY)
                continue

            if not genres:
                print("—")
                skipped += 1
            else:
                _update_genres(conn, str(row["id"]), genres)
                conn.commit()
                print(", ".join(genres))
                updated += 1

            time.sleep(_DELAY)

    print()
    print("Results")
    print("-" * 44)
    print(f"  Updated  : {updated}")
    print(f"  Skipped  : {skipped}  (not on Last.fm or no tags above threshold)")
    print(f"  Errors   : {errors}")


if __name__ == "__main__":
    main()

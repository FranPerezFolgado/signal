# /// script
# requires-python = ">=3.12"
# dependencies = ["requests>=2.31", "psycopg[binary]>=3.1"]
# ///
"""
One-shot backfill: populate external_ids->>'spotify' for FOLLOWING artists
that were inserted before the history-tracker external_ids fix.

Run against a live DB (services do not need to be stopped):
    uv run python scripts/backfill_artist_external_ids.py

Required env vars (same as other services, set in .env or shell):
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN
    DATABASE_URL
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import psycopg
import requests

_TOKEN_URL = "https://accounts.spotify.com/api/token"
_API_BASE = "https://api.spotify.com/v1"
_RATE_LIMIT_DELAY = 0.2  # 5 req/s — well within Spotify's limit


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


def _refresh_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    resp = requests.post(
        _TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=(client_id, client_secret),
        timeout=10,
    )
    if resp.status_code != 200:
        print(f"[error] token refresh failed: HTTP {resp.status_code}", file=sys.stderr)
        sys.exit(1)
    token = resp.json().get("access_token")
    if not token:
        print("[error] access_token missing from response", file=sys.stderr)
        sys.exit(1)
    return token


def _search_artist(name: str, access_token: str) -> str | None:
    """Return the Spotify artist URI for the best-matching artist name, or None."""
    while True:
        resp = requests.get(
            f"{_API_BASE}/search",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"q": f"artist:{name}", "type": "artist", "limit": 1, "market": "from_token"},
            timeout=10,
        )
        if resp.status_code == 429:
            try:
                retry_after = int(resp.headers.get("Retry-After", 5))
            except (ValueError, TypeError):
                retry_after = 5
            if retry_after > 120:
                print(f"\n[quota exhausted] Spotify says retry after {retry_after}s ({retry_after // 3600}h).")
                print("Re-run the script later — it will skip already-resolved artists.")
                sys.exit(0)
            print(f"  [rate-limited] sleeping {retry_after}s …")
            time.sleep(retry_after)
            continue
        if resp.status_code != 200:
            print(f"  [warn] search failed for '{name}': HTTP {resp.status_code}")
            return None
        items = resp.json().get("artists", {}).get("items", [])
        if not items:
            return None
        artist = items[0]
        return f"spotify:artist:{artist['id']}"


def _get_artists_missing_spotify_id(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("""
            SELECT id, name, status
            FROM artists
            WHERE external_ids IS NULL
               OR external_ids->>'spotify' IS NULL
            ORDER BY
                CASE status
                    WHEN 'FOLLOWING' THEN 0
                    WHEN 'TRACKED'   THEN 1
                    ELSE 2
                END,
                play_count DESC
        """)
        return cur.fetchall()


def _patch_external_id(conn: psycopg.Connection, artist_id: str, spotify_uri: str) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE artists
            SET external_ids = COALESCE(external_ids, '{}'::jsonb) || %s::jsonb
            WHERE id = %s
        """, (json.dumps({"spotify": spotify_uri}), artist_id))
    conn.commit()


def main() -> None:
    _load_dotenv()

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN", "")
    database_url = os.environ.get("DATABASE_URL", "")

    for var, val in [
        ("SPOTIFY_CLIENT_ID", client_id),
        ("SPOTIFY_CLIENT_SECRET", client_secret),
        ("SPOTIFY_REFRESH_TOKEN", refresh_token),
        ("DATABASE_URL", database_url),
    ]:
        if not val:
            print(f"[error] {var} is not set", file=sys.stderr)
            sys.exit(1)

    access_token = _refresh_token(client_id, client_secret, refresh_token)

    with psycopg.connect(database_url) as conn:
        artists = _get_artists_missing_spotify_id(conn)

        if not artists:
            print("No FOLLOWING artists missing a Spotify ID — nothing to do.")
            return

        print(f"Found {len(artists)} artist(s) to backfill:\n")

        resolved = skipped = 0
        for row in artists:
            name = row["name"]
            print(f"  [{row['status']}] {name} … ", end="", flush=True)

            spotify_uri = _search_artist(name, access_token)
            time.sleep(_RATE_LIMIT_DELAY)

            if not spotify_uri:
                print("not found on Spotify")
                skipped += 1
                continue

            _patch_external_id(conn, row["id"], spotify_uri)
            print(f"→ {spotify_uri}")
            resolved += 1

    print(f"\nDone. Resolved: {resolved}  Not found: {skipped}")
    if skipped:
        print("Artists not found on Spotify will continue to be skipped by artist-tracker.")


if __name__ == "__main__":
    main()

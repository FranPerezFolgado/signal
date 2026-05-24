# /// script
# requires-python = ">=3.12"
# dependencies = ["requests>=2.31", "psycopg[binary]>=3.1"]
# ///
"""
One-shot artist onboarding script for Signal.

Run AFTER `make up`, BEFORE starting pipeline services:
    uv run python scripts/onboarding.py

What it does (in order):
  1. Reads all artists you follow on Spotify → sets status=FOLLOWING in the DB.
  2. Remaining artists with play_count >= INITIAL_HIGH_PRIORITY_PLAYS → high_priority=true.
  3. Everything else is left as TRACKED (the default from the normalizer).

Required env vars (set in .env or shell):
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN
    DATABASE_URL
    INITIAL_HIGH_PRIORITY_PLAYS  (default: 20)
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import psycopg
import requests

# ---------------------------------------------------------------------------
# .env loader — simple line parser so we don't need python-dotenv
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


# ---------------------------------------------------------------------------
# Spotify helpers
# ---------------------------------------------------------------------------

_TOKEN_URL = "https://accounts.spotify.com/api/token"
_API_BASE = "https://api.spotify.com/v1"


def _refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    resp = requests.post(
        _TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=(client_id, client_secret),
        timeout=10,
    )
    if resp.status_code != 200:
        print(f"[error] Spotify token refresh failed: HTTP {resp.status_code}", file=sys.stderr)
        sys.exit(1)
    token = resp.json().get("access_token")
    if not token:
        print("[error] Spotify token response missing access_token field", file=sys.stderr)
        sys.exit(1)
    return token


def _get_followed_artist_names(access_token: str) -> set[str]:
    """Fetch all Spotify-followed artists and return their lowercase names."""
    names: set[str] = set()
    url = f"{_API_BASE}/me/following"
    params: dict = {"type": "artist", "limit": 50}

    while url:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=10,
        )
        if resp.status_code == 401:
            print("[error] Spotify returned 401 — check that your refresh token has 'user-follow-read' scope.", file=sys.stderr)
            sys.exit(1)
        if resp.status_code != 200:
            print(f"[error] Spotify /me/following returned HTTP {resp.status_code}", file=sys.stderr)
            sys.exit(1)

        data = resp.json().get("artists", {})
        for artist in data.get("items", []):
            name = artist.get("name", "")
            if name:
                names.add(name.lower())

        url = data.get("next")
        params = {}  # cursor is embedded in the `next` URL
        if url:
            time.sleep(0.1)  # stay well within Spotify rate limits

    return names


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _promote_following(conn: psycopg.Connection, followed_names: set[str]) -> int:
    """Set status=FOLLOWING for artists whose lowercased name is in followed_names."""
    if not followed_names:
        return 0
    result = conn.execute(
        """
        UPDATE artists
           SET status = 'FOLLOWING'
         WHERE LOWER(name) = ANY(%s)
           AND status != 'FOLLOWING'
        RETURNING id
        """,
        (list(followed_names),),
    )
    return result.rowcount


def _mark_high_priority(conn: psycopg.Connection, min_scrobbles: int) -> int:
    """Set high_priority=true for TRACKED artists at or above the scrobble threshold."""
    result = conn.execute(
        """
        UPDATE artists
           SET high_priority = true
         WHERE status = 'TRACKED'
           AND scrobble_count >= %s
           AND high_priority = false
        RETURNING id
        """,
        (min_scrobbles,),
    )
    return result.rowcount


def _count_by_status(conn: psycopg.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT status, COUNT(*) FROM artists GROUP BY status ORDER BY status"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _load_dotenv()

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN", "")
    db_url = os.environ.get("DATABASE_URL", "postgresql://signal:signal@localhost:5432/signal")
    min_plays = int(os.environ.get("INITIAL_HIGH_PRIORITY_PLAYS", "20"))

    missing = [k for k, v in {
        "SPOTIFY_CLIENT_ID": client_id,
        "SPOTIFY_CLIENT_SECRET": client_secret,
        "SPOTIFY_REFRESH_TOKEN": refresh_token,
    }.items() if not v]
    if missing:
        print(f"[error] Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        print("  Run scripts/get_spotify_token.py to obtain a refresh token.", file=sys.stderr)
        sys.exit(1)

    print("Signal — Artist Onboarding")
    print("=" * 40)

    # 1. Spotify
    print("Refreshing Spotify access token...")
    access_token = _refresh_access_token(client_id, client_secret, refresh_token)
    print("Fetching artists you follow on Spotify...")
    followed = _get_followed_artist_names(access_token)
    print(f"  Found {len(followed)} followed artist(s) on Spotify.")

    # 2. Database
    print("Connecting to database...")
    with psycopg.connect(db_url) as conn:
        before = _count_by_status(conn)

        promoted = _promote_following(conn, followed)
        high_priority_marked = _mark_high_priority(conn, min_plays)

        conn.commit()
        after = _count_by_status(conn)

    # 3. Report
    print()
    print("Results")
    print("-" * 40)
    print(f"  Artists promoted to FOLLOWING : {promoted}")
    print(f"  Artists marked high_priority  : {high_priority_marked}  (scrobble_count >= {min_plays})")
    print()
    print("Artist distribution after onboarding:")
    for status, count in after.items():
        delta = count - before.get(status, 0)
        change = f" (+{delta})" if delta > 0 else ""
        print(f"  {status:<12} {count}{change}")
    print()
    print("Onboarding complete. You can now start the pipeline services.")


if __name__ == "__main__":
    main()

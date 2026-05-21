from datetime import UTC, datetime


def to_raw_play(track: dict) -> dict | None:
    """Returns None for nowplaying tracks (no date.uts yet)."""
    if track.get("@attr", {}).get("nowplaying") == "true":
        return None
    date = track.get("date")
    if date is None:
        return None

    played_at = datetime.fromtimestamp(int(date["uts"]), tz=UTC).isoformat()
    mbid = track.get("mbid") or None  # coerce empty string to None

    return {
        "source": "lastfm",
        "artist": track["artist"]["#text"],
        "title": track["name"],
        "played_at": played_at,
        "external_ids": {"lastfm_mbid": mbid},
        "raw": track,
    }

from signal_common.spotify import BaseSpotifyClient, SpotifyAuthError, SpotifyServiceError  # noqa: F401

_API_BASE = "https://api.spotify.com/v1"


class SpotifyClient(BaseSpotifyClient):
    def search_track(self, artist: str, title: str) -> tuple[str | None, str | None]:
        """Return (artist_id_uri, track_id_uri) or (None, None) when not found.
        Raises SpotifyServiceError on transport/auth/rate-limit failures."""
        query = f"track:{title} artist:{artist}"
        data = self._get(f"{_API_BASE}/search", params={"q": query, "type": "track", "limit": 1})
        items = data.get("tracks", {}).get("items", [])
        if not items:
            return None, None
        item = items[0]
        track_id = item.get("id")
        track_artists = item.get("artists", [])
        if not track_id or not track_artists:
            return None, None
        artist_id = track_artists[0].get("id")
        if not artist_id:
            return None, None
        return f"spotify:artist:{artist_id}", f"spotify:track:{track_id}"

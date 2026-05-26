import re

from signal_common.spotify import BaseSpotifyClient, SpotifyServiceError

_API_BASE = "https://api.spotify.com/v1"
_URI_PREFIX = "spotify:artist:"
_BASE62_RE = re.compile(r"^[A-Za-z0-9]+$")


class SpotifyClient(BaseSpotifyClient):
    def get_top_tracks(self, artist_uri: str) -> list[dict]:
        """Return top tracks for an artist. artist_uri may be a full URI or bare ID."""
        artist_id = artist_uri.removeprefix(_URI_PREFIX)
        if not _BASE62_RE.match(artist_id):
            raise SpotifyServiceError("invalid Spotify artist ID format")
        data = self._get(
            f"{_API_BASE}/artists/{artist_id}/top-tracks",
            params={"market": "from_token"},
        )
        tracks = data.get("tracks", [])
        result = []
        for t in tracks:
            artists = t.get("artists") or []
            if not artists:
                continue
            result.append(
                {
                    "name": t["name"],
                    "id": t["id"],
                    "artist_name": artists[0].get("name", ""),
                    "artist_id": artists[0].get("id", ""),
                }
            )
        return result

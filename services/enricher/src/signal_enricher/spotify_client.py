import re

from signal_common.logger import get_logger
from signal_common.spotify import (  # noqa: F401
    BaseSpotifyClient,
    SpotifyAuthError,
    SpotifyServiceError,
)

_log = get_logger(__name__)

_API_BASE = "https://api.spotify.com/v1"

# Spotify IDs are base-62 strings, typically 22 chars. Allow 10–30 to be safe.
_SPOTIFY_ID_RE = re.compile(r"^[A-Za-z0-9]{10,30}$")


class EnricherSpotifyClient(BaseSpotifyClient):
    def _strip_uri_prefix(self, uri: str | None, kind: str) -> str | None:
        """Extract and validate a raw Spotify ID from a URI like spotify:artist:xxx."""
        if not uri:
            return None
        prefix = f"spotify:{kind}:"
        if not uri.startswith(prefix):
            _log.warning("invalid_spotify_uri_format", kind=kind, uri=uri[:40])
            return None
        raw_id = uri[len(prefix):]
        if not _SPOTIFY_ID_RE.match(raw_id):
            _log.warning("invalid_spotify_id_format", kind=kind, raw_id=raw_id[:40])
            return None
        return raw_id

    def get_artist_data(self, artist_id_uri: str | None) -> dict | None:
        """Return genres, popularity, followers for an artist URI.
        Returns None for an invalid URI. Raises SpotifyServiceError on API failure."""
        raw_id = self._strip_uri_prefix(artist_id_uri, "artist")
        if not raw_id:
            return None
        data = self._get(f"{_API_BASE}/artists/{raw_id}")
        return {
            "genres": data.get("genres", []),
            "artist_popularity": data.get("popularity"),
            "followers": data.get("followers", {}).get("total"),
        }

    def get_track_data(self, track_id_uri: str | None) -> dict | None:
        """Return track popularity and duration for a track URI.
        Returns None for an invalid URI. Raises SpotifyServiceError on API failure."""
        raw_id = self._strip_uri_prefix(track_id_uri, "track")
        if not raw_id:
            return None
        data = self._get(f"{_API_BASE}/tracks/{raw_id}")
        return {
            "track_popularity": data.get("popularity"),
            "duration_ms": data.get("duration_ms"),
        }

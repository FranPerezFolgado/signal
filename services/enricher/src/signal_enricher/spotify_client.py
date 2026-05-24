import re
import time

import requests

from signal_common.logger import get_logger
from signal_common.rate_limiter import RateLimiter

_log = get_logger(__name__)

_TOKEN_URL = "https://accounts.spotify.com/api/token"
_API_BASE = "https://api.spotify.com/v1"

# Spotify IDs are base-62 strings, typically 22 chars. Allow 10–30 to be safe.
_SPOTIFY_ID_RE = re.compile(r"^[A-Za-z0-9]{10,30}$")


class SpotifyAuthError(Exception):
    pass


class EnricherSpotifyClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        timeout: float = 5.0,
        rate_limiter: RateLimiter | None = None,
        retry_after_default: float = 5.0,
        retry_after_max: float = 60.0,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._timeout = timeout
        self._rate_limiter = rate_limiter
        self._retry_after_default = retry_after_default
        self._retry_after_max = retry_after_max
        self._access_token: str = ""

    def _refresh_access_token(self) -> None:
        resp = requests.post(
            _TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
            auth=(self._client_id, self._client_secret),
            timeout=10,
        )
        if resp.status_code != 200:
            raise SpotifyAuthError(f"Token refresh failed: {resp.status_code}")
        self._access_token = resp.json()["access_token"]
        _log.info("spotify_token_refreshed")

    def _get(self, url: str) -> dict | None:
        if not self._access_token:
            try:
                self._refresh_access_token()
            except SpotifyAuthError as exc:
                _log.error("spotify_token_unavailable", error=str(exc))
                return None

        if self._rate_limiter:
            self._rate_limiter.acquire()

        try:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {self._access_token}"},
                timeout=self._timeout,
            )
        except requests.Timeout:
            _log.warning("spotify_timeout", url=url)
            return None
        except requests.RequestException as exc:
            _log.warning("spotify_request_error", error=str(exc))
            return None

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 401:
            _log.warning("spotify_401_refreshing_token")
            try:
                self._refresh_access_token()
                if self._rate_limiter:
                    self._rate_limiter.acquire()
                resp = requests.get(
                    url,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    timeout=self._timeout,
                )
                if resp.status_code == 200:
                    return resp.json()
            except (SpotifyAuthError, requests.RequestException):
                return None

        if resp.status_code == 429:
            try:
                retry_after = float(resp.headers.get("Retry-After", self._retry_after_default))
            except (ValueError, TypeError):
                retry_after = self._retry_after_default
            sleep_s = min(retry_after, self._retry_after_max)
            _log.warning("spotify_rate_limited", retry_after=sleep_s)
            time.sleep(sleep_s)
            if self._rate_limiter:
                self._rate_limiter.acquire()
            try:
                resp = requests.get(
                    url,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    timeout=self._timeout,
                )
                if resp.status_code == 200:
                    return resp.json()
            except requests.RequestException:
                return None

        _log.warning("spotify_non_200", status=resp.status_code, url=url)
        return None

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
        """Return genres, popularity, followers for an artist URI."""
        raw_id = self._strip_uri_prefix(artist_id_uri, "artist")
        if not raw_id:
            return None
        data = self._get(f"{_API_BASE}/artists/{raw_id}")
        if not data:
            return None
        return {
            "genres": data.get("genres", []),
            "artist_popularity": data.get("popularity"),
            "followers": data.get("followers", {}).get("total"),
        }

    def get_track_data(self, track_id_uri: str | None) -> dict | None:
        """Return track popularity and duration for a track URI."""
        raw_id = self._strip_uri_prefix(track_id_uri, "track")
        if not raw_id:
            return None
        data = self._get(f"{_API_BASE}/tracks/{raw_id}")
        if not data:
            return None
        return {
            "track_popularity": data.get("popularity"),
            "duration_ms": data.get("duration_ms"),
        }

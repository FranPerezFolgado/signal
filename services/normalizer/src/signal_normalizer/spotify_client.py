import time

import requests

from signal_common.logger import get_logger
from signal_common.rate_limiter import RateLimiter

_log = get_logger(__name__)

_TOKEN_URL = "https://accounts.spotify.com/api/token"
_API_BASE = "https://api.spotify.com/v1"


class SpotifyAuthError(Exception):
    pass


class SpotifyClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        timeout: float = 2.0,
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
            raise SpotifyAuthError(f"Token refresh failed with status {resp.status_code}")
        self._access_token = resp.json()["access_token"]
        _log.info("spotify_token_refreshed")

    def _get(self, url: str, params: dict | None = None) -> dict | None:
        if not self._access_token:
            try:
                self._refresh_access_token()
            except SpotifyAuthError as exc:
                _log.error("spotify_token_unavailable", error=str(exc))
                return None

        if self._rate_limiter:
            self._rate_limiter.acquire()

        token_refreshed = False
        try:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {self._access_token}"},
                params=params,
                timeout=self._timeout,
            )
        except requests.Timeout:
            _log.warning("spotify_search_timeout", url=url)
            return None
        except requests.RequestException as exc:
            _log.warning("spotify_request_error", error=str(exc))
            return None

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 401 and not token_refreshed:
            _log.warning("spotify_401_refreshing_token")
            try:
                self._refresh_access_token()
                token_refreshed = True
            except SpotifyAuthError as exc:
                _log.error("spotify_token_refresh_failed", error=str(exc))
                return None
            try:
                resp = requests.get(
                    url,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    params=params,
                    timeout=self._timeout,
                )
                if resp.status_code == 200:
                    return resp.json()
            except requests.RequestException:
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
                    params=params,
                    timeout=self._timeout,
                )
                if resp.status_code == 200:
                    return resp.json()
            except requests.RequestException:
                return None

        _log.warning("spotify_non_200", status=resp.status_code, url=url)
        return None

    def search_track(self, artist: str, title: str) -> tuple[str | None, str | None]:
        """Return (artist_id_uri, track_id_uri) or (None, None) on failure."""
        query = f"track:{title} artist:{artist}"
        data = self._get(f"{_API_BASE}/search", params={"q": query, "type": "track", "limit": 1})
        if not data:
            return None, None
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

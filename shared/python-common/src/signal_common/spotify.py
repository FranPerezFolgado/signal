import time

import requests

from signal_common.logger import get_logger
from signal_common.rate_limiter import RateLimiter

_log = get_logger(__name__)

_TOKEN_URL = "https://accounts.spotify.com/api/token"


class SpotifyAuthError(Exception):
    pass


class SpotifyServiceError(Exception):
    """Raised on transport failures, auth failures, or rate-limit exhaustion."""
    pass


class BaseSpotifyClient:
    """Shared HTTP machinery for Spotify API clients.

    Subclasses add domain methods (search_track, get_artist_data, …).
    _get() raises SpotifyServiceError on all failures so callers can
    distinguish a genuine service error from an empty/not-found result.
    """

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
            raise SpotifyAuthError(f"token refresh failed: {resp.status_code}")
        self._access_token = resp.json()["access_token"]
        _log.info("spotify_token_refreshed")

    def _get(self, url: str, params: dict | None = None) -> dict:
        """Authenticated GET. Returns the response JSON on 200.
        Raises SpotifyServiceError on any failure (transport, auth, rate limit)."""
        if not self._access_token:
            try:
                self._refresh_access_token()
            except SpotifyAuthError as exc:
                raise SpotifyServiceError(f"auth unavailable: {exc}") from exc

        if self._rate_limiter:
            self._rate_limiter.acquire()

        try:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {self._access_token}"},
                params=params,
                timeout=self._timeout,
            )
        except requests.Timeout:
            raise SpotifyServiceError("request timed out") from None
        except requests.RequestException as exc:
            raise SpotifyServiceError(str(exc)) from exc

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 401:
            _log.warning("spotify_401_refreshing_token")
            try:
                self._refresh_access_token()
            except SpotifyAuthError as exc:
                raise SpotifyServiceError(f"token refresh failed after 401: {exc}") from exc
            if self._rate_limiter:
                self._rate_limiter.acquire()
            try:
                resp = requests.get(
                    url,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    params=params,
                    timeout=self._timeout,
                )
            except requests.Timeout:
                raise SpotifyServiceError("request timed out after token refresh") from None
            except requests.RequestException as exc:
                raise SpotifyServiceError(str(exc)) from exc
            if resp.status_code == 200:
                return resp.json()
            # fall through — handle 429 or log non-200 below

        if resp.status_code == 429:
            try:
                retry_after = float(resp.headers.get("Retry-After", self._retry_after_default))
            except (ValueError, TypeError):
                retry_after = self._retry_after_default
            sleep_s = max(0.0, min(retry_after, self._retry_after_max))
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
            except requests.Timeout:
                raise SpotifyServiceError("request timed out after 429 retry") from None
            except requests.RequestException as exc:
                raise SpotifyServiceError(str(exc)) from exc
            if resp.status_code == 200:
                return resp.json()

        _log.warning("spotify_non_200", status=resp.status_code, url=url.split("?")[0])
        raise SpotifyServiceError(f"non-200 status {resp.status_code}")

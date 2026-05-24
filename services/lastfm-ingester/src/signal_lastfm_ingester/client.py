import time
from dataclasses import dataclass

import requests

from signal_common.rate_limiter import RateLimiter

_BASE_URL = "http://ws.audioscrobbler.com/2.0/"
_MAX_RETRIES = 3


@dataclass
class RecentTracksPage:
    tracks: list[dict]
    page: int
    total_pages: int


class LastfmClient:
    def __init__(self, api_key: str, username: str, rate_limiter: RateLimiter | None = None):
        self.api_key = api_key
        self.username = username
        self._rate_limiter = rate_limiter

    def get_recent_tracks(
        self,
        from_uts: int | None = None,
        page: int = 1,
        limit: int = 200,
    ) -> RecentTracksPage:
        params: dict = {
            "method": "user.getrecenttracks",
            "user": self.username,
            "api_key": self.api_key,
            "format": "json",
            "limit": limit,
            "page": page,
        }
        if from_uts is not None:
            params["from"] = from_uts

        data = self._get_with_retry(params)
        tracks = data["recenttracks"]["track"]
        # API returns a dict (not list) when there's only one track
        if isinstance(tracks, dict):
            tracks = [tracks]
        total_pages = int(data["recenttracks"]["@attr"]["totalPages"])
        return RecentTracksPage(tracks=tracks, page=page, total_pages=total_pages)

    def _get_with_retry(self, params: dict) -> dict:
        delay = 1.0
        for attempt in range(_MAX_RETRIES):
            if self._rate_limiter:
                self._rate_limiter.acquire()
            response = requests.get(_BASE_URL, params=params, timeout=10)
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
            response.raise_for_status()
            return response.json()
        response.raise_for_status()
        return response.json()

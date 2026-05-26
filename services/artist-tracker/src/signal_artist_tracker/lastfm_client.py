from dataclasses import dataclass

import requests
from signal_common.logger import get_logger
from signal_common.rate_limiter import RateLimiter

_log = get_logger(__name__)

_API_URL = "https://ws.audioscrobbler.com/2.0/"


@dataclass
class SimilarArtist:
    name: str
    mbid: str | None
    match_score: float


class LastfmSimilarClient:
    def __init__(self, api_key: str, rate_limiter: RateLimiter) -> None:
        self._api_key = api_key
        self._rate_limiter = rate_limiter

    def get_similar(self, artist_name: str, limit: int) -> list[SimilarArtist]:
        self._rate_limiter.acquire()
        try:
            params: dict[str, str | int] = {
                "method": "artist.getSimilar",
                "artist": artist_name,
                "api_key": self._api_key,
                "limit": limit,
                "format": "json",
                "autocorrect": "1",
            }
            resp = requests.get(_API_URL, params=params, timeout=10)
            if resp.status_code == 429:
                _log.warning("lastfm_rate_limited", artist=artist_name)
                return []
            if resp.status_code != 200:
                _log.warning("lastfm_similar_non_200", artist=artist_name, status=resp.status_code)
                return []
            data = resp.json()
            if "error" in data:
                _log.debug(
                    "lastfm_similar_api_error",
                    artist=artist_name,
                    code=data.get("error"),
                    message=data.get("message"),
                )
                return []
            artists = data.get("similarartists", {}).get("artist", [])
            return [
                SimilarArtist(
                    name=a["name"],
                    mbid=a.get("mbid") or None,
                    match_score=float(a.get("match", 0)),
                )
                for a in artists
                if a.get("name")
            ]
        except (requests.RequestException, KeyError, ValueError) as exc:
            _log.warning("lastfm_similar_error", artist=artist_name, error=type(exc).__name__)
            return []

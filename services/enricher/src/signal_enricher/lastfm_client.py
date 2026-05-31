import requests
from signal_common.logger import get_logger

_log = get_logger(__name__)

_API_URL = "https://ws.audioscrobbler.com/2.0/"
_MAX_TAGS = 5
_MIN_TAG_COUNT = 10  # relative score (0–100); below this threshold = noise


class LastfmFallbackClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def get_artist_tags(self, artist: str) -> list[str]:
        """Fetch top genre tags for an artist via artist.getTopTags."""
        try:
            resp = requests.get(
                _API_URL,
                params={
                    "method": "artist.getTopTags",
                    "artist": artist,
                    "api_key": self._api_key,
                    "format": "json",
                    "autocorrect": 1,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                _log.warning("lastfm_non_200", status=resp.status_code, artist=artist)
                return []
            data = resp.json()
            if "error" in data:
                _log.debug("lastfm_artist_not_found", artist=artist)
                return []
            tags = data.get("toptags", {}).get("tag", [])
            return [
                t["name"].lower()
                for t in tags[:_MAX_TAGS]
                if t.get("name") and int(t.get("count", 0)) >= _MIN_TAG_COUNT
            ]
        except (OSError, requests.RequestException, KeyError, ValueError) as exc:
            _log.warning("lastfm_artist_tags_error", artist=artist, error=str(exc))
            return []

    def get_tags(self, artist: str, title: str) -> list[str]:
        try:
            resp = requests.get(
                _API_URL,
                params={
                    "method": "track.getInfo",
                    "api_key": self._api_key,
                    "artist": artist,
                    "track": title,
                    "format": "json",
                    "autocorrect": 1,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                _log.warning("lastfm_non_200", status=resp.status_code, artist=artist)
                return []
            data = resp.json()
            if "error" in data:
                _log.debug("lastfm_track_not_found", artist=artist, title=title)
                return []
            tags = data.get("track", {}).get("toptags", {}).get("tag", [])
            return [t["name"] for t in tags[:_MAX_TAGS] if t.get("name")]
        except (OSError, requests.RequestException, KeyError, ValueError) as exc:
            _log.warning("lastfm_fallback_error", artist=artist, error=str(exc))
            return []

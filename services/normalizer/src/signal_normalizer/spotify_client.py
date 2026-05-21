import time
from dataclasses import dataclass

import requests

from signal_common.logger import get_logger

_log = get_logger(__name__)

_TOKEN_URL = "https://accounts.spotify.com/api/token"
_API_BASE = "https://api.spotify.com/v1"


@dataclass
class SpotifyTrack:
    track_id: str
    artist_id: str
    artist_name: str
    genres: list[str]
    popularity: int


@dataclass
class AudioFeatures:
    energy: float
    valence: float
    tempo: float
    danceability: float
    acousticness: float
    instrumentalness: float


class SpotifyAuthError(Exception):
    pass


class SpotifyClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        max_retries: int = 3,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._max_retries = max_retries
        self._access_token: str = ""
        self._refresh_access_token()

    def _refresh_access_token(self) -> None:
        resp = requests.post(
            _TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
            auth=(self._client_id, self._client_secret),
            timeout=10,
        )
        if resp.status_code != 200:
            raise SpotifyAuthError(f"Token refresh failed: {resp.status_code} {resp.text}")
        self._access_token = resp.json()["access_token"]
        _log.info("spotify_token_refreshed")

    def _get(self, url: str, params: dict | None = None) -> dict | None:
        for attempt in range(self._max_retries + 1):
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {self._access_token}"},
                params=params,
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 401:
                if attempt == 0:
                    _log.warning("spotify_401_refreshing_token")
                    self._refresh_access_token()
                    continue
                raise SpotifyAuthError("Spotify returned 401 after token refresh")
            if resp.status_code == 429:
                if attempt >= self._max_retries:
                    _log.warning("spotify_rate_limit_exhausted", max_retries=self._max_retries)
                    return None
                retry_after = int(resp.headers.get("Retry-After", 1))
                wait = retry_after * (2**attempt) + (attempt * 0.1)
                _log.warning("spotify_rate_limited", wait_seconds=wait, attempt=attempt + 1)
                time.sleep(wait)
                continue
            if resp.status_code == 404:
                return None
            if resp.status_code >= 500:
                if attempt >= self._max_retries:
                    _log.error("spotify_server_error_exhausted", status=resp.status_code)
                    return None
                wait = 2**attempt
                _log.warning("spotify_server_error_retrying", status=resp.status_code, wait=wait)
                time.sleep(wait)
                continue
            _log.warning("spotify_unexpected_status", status=resp.status_code, url=url)
            return None
        return None

    def search_track(self, artist: str, title: str) -> SpotifyTrack | None:
        query = f"track:{title} artist:{artist}"
        data = self._get(f"{_API_BASE}/search", params={"q": query, "type": "track", "limit": 1})
        if not data:
            return None
        items = data.get("tracks", {}).get("items", [])
        if not items:
            return None
        item = items[0]
        track_id = item["id"]
        track_artists = item.get("artists", [])
        if not track_artists:
            return None
        artist_id = track_artists[0]["id"]
        artist_name = track_artists[0]["name"]
        popularity = item.get("popularity", 0)
        genres = self._get_artist_genres(artist_id)
        return SpotifyTrack(
            track_id=track_id,
            artist_id=artist_id,
            artist_name=artist_name,
            genres=genres,
            popularity=popularity,
        )

    def _get_artist_genres(self, artist_id: str) -> list[str]:
        data = self._get(f"{_API_BASE}/artists/{artist_id}")
        if not data:
            return []
        return data.get("genres", [])

    def get_audio_features(self, track_id: str) -> AudioFeatures | None:
        data = self._get(f"{_API_BASE}/audio-features/{track_id}")
        if not data:
            return None
        try:
            return AudioFeatures(
                energy=data["energy"],
                valence=data["valence"],
                tempo=data["tempo"],
                danceability=data["danceability"],
                acousticness=data["acousticness"],
                instrumentalness=data["instrumentalness"],
            )
        except KeyError:
            return None

import random
import time

from signal_common.logger import get_logger

from signal_enricher.circuit_breaker import CircuitBreaker
from signal_enricher.lastfm_client import LastfmFallbackClient
from signal_enricher.rate_limiter import RateLimiter
from signal_enricher.spotify_client import EnricherSpotifyClient
from signal_enricher.settings import Settings

_log = get_logger(__name__)


class Enricher:
    def __init__(self, settings: Settings) -> None:
        self._spotify = EnricherSpotifyClient(
            settings.spotify_client_id,
            settings.spotify_client_secret,
            settings.spotify_refresh_token,
            settings.spotify_timeout,
        )
        self._lastfm = (
            LastfmFallbackClient(settings.lastfm_api_key)
            if settings.lastfm_fallback_enabled
            else None
        )
        self._rate_limiter = RateLimiter(settings.spotify_rate_limit_per_30s)
        self._circuit_breaker = CircuitBreaker(
            settings.circuit_breaker_failure_threshold,
            settings.circuit_breaker_timeout_s,
        )
        self._backoff_base = settings.backoff_base_s
        self._backoff_max = settings.backoff_max_s

    def _spotify_with_backoff(self, artist_id: str, track_id: str) -> dict | None:
        """Attempt Spotify enrichment with exponential backoff + jitter."""
        for attempt in range(3):
            self._rate_limiter.acquire()
            artist_data = self._spotify.get_artist_data(artist_id)
            track_data = self._spotify.get_track_data(track_id)
            if artist_data is not None and track_data is not None:
                return {**artist_data, **track_data}
            delay = min(
                self._backoff_base * (2 ** attempt) + random.uniform(0, 0.5),
                self._backoff_max,
            )
            _log.warning("spotify_enrichment_failed", attempt=attempt, retry_in=delay)
            self._circuit_breaker.record_failure()
            if self._circuit_breaker.is_open:
                _log.warning("circuit_breaker_opened_mid_backoff")
                return None
            time.sleep(delay)
        return None

    def enrich(self, normalized: dict) -> dict:
        """
        Enrich a normalized track message.
        Returns the enriched dict; pending_enrichment=True when enrichment unavailable.
        """
        artist_id = normalized.get("artist_id")
        track_id = normalized.get("track_id")
        artist = normalized["artist"]
        title = normalized["title"]

        enrichment_source: str = "pending"
        genres: list[str] | None = None
        artist_popularity: int | None = None
        track_popularity: int | None = None
        pending = True

        if artist_id and track_id and not self._circuit_breaker.is_open:
            result = self._spotify_with_backoff(artist_id, track_id)
            if result:
                self._circuit_breaker.record_success()
                genres = result.get("genres") or []
                artist_popularity = result.get("artist_popularity")
                track_popularity = result.get("track_popularity")
                enrichment_source = "spotify"
                pending = False
            else:
                # Fallback to Last.fm for genres only
                if self._lastfm:
                    tags = self._lastfm.get_tags(artist, title)
                    if tags:
                        genres = tags
                        enrichment_source = "lastfm"
                        pending = False
                        _log.info("lastfm_fallback_used", artist=artist)

        elif artist_id and track_id and self._circuit_breaker.is_open:
            _log.warning("circuit_open_skipping_spotify", artist=artist)
            if self._lastfm:
                tags = self._lastfm.get_tags(artist, title)
                if tags:
                    genres = tags
                    enrichment_source = "lastfm"
                    pending = False

        return {
            **normalized,
            "genres": genres,
            "artist_popularity": artist_popularity,
            "track_popularity": track_popularity,
            "enrichment_source": enrichment_source,
            "pending_enrichment": pending,
        }

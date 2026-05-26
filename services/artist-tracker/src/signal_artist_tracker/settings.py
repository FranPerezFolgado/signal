from signal_common.settings import CommonSettings


class Settings(CommonSettings):
    spotify_client_id: str
    spotify_client_secret: str
    spotify_refresh_token: str
    spotify_timeout: float = 5.0
    artist_tracker_interval_hours: float = 6.0
    artist_reexplore_days: int = 7
    artist_tracker_rate_limit_per_30s: int = 30
    kafka_output_topic: str = "raw.tracks"
    spotify_retry_after_default_s: float = 5.0
    spotify_retry_after_max_s: float = 60.0
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_timeout_s: float = 60.0
    lastfm_api_key: str  # Required: Last.fm API key for artist.getSimilar expansion
    lastfm_similar_interval_hours: float = 24.0
    lastfm_similar_limit: int = 10
    lastfm_similar_rate_limit_per_30s: int = 150
    kafka_discovered_topic: str = "artist.discovered"

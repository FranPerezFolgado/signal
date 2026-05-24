from signal_common.settings import CommonSettings


class Settings(CommonSettings):
    spotify_client_id: str
    spotify_client_secret: str
    spotify_refresh_token: str
    spotify_timeout: float = 5.0

    lastfm_api_key: str = ""
    lastfm_fallback_enabled: bool = True

    spotify_rate_limit_per_30s: int = 180
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_timeout_s: float = 60.0
    backoff_base_s: float = 1.0
    backoff_max_s: float = 30.0
    spotify_retry_after_default_s: float = 5.0
    spotify_retry_after_max_s: float = 60.0

    kafka_consumer_group: str = "enricher-group"

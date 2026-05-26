from signal_common.settings import CommonSettings


class Settings(CommonSettings):
    lastfm_api_key: str
    lastfm_username: str
    lastfm_poll_interval_seconds: int = 60
    lastfm_rate_limit_per_30s: int = 150
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_timeout_s: float = 120.0

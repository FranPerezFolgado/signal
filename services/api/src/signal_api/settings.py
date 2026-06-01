from signal_common.settings import CommonSettings


class Settings(CommonSettings):
    api_host: str = "0.0.0.0"  # noqa: S104 — restricted to loopback at Docker level via ports binding
    api_port: int = 8000
    pool_min_size: int = 1
    pool_max_size: int = 10
    # API has no Kafka dependency; override to avoid requiring the env var
    kafka_bootstrap_servers: str = ""
    stats_stale_threshold_minutes: int = 30


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

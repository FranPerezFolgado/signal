from signal_common.settings import CommonSettings


class Settings(CommonSettings):
    spotify_client_id: str
    spotify_client_secret: str
    spotify_refresh_token: str
    spotify_timeout: float = 2.0
    kafka_consumer_group: str = "normalizer-group"

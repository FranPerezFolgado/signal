from signal_common.settings import CommonSettings


class Settings(CommonSettings):
    spotify_client_id: str
    spotify_client_secret: str
    spotify_refresh_token: str
    lastfm_api_key: str
    spotify_max_retries: int = 3

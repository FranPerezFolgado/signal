from pydantic_settings import BaseSettings, SettingsConfigDict
from signal_common.settings import CommonSettings


class Settings(CommonSettings):
    lastfm_api_key: str
    lastfm_username: str
    lastfm_poll_interval_seconds: int = 60

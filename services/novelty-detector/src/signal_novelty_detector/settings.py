from signal_common.settings import CommonSettings


class Settings(CommonSettings):
    kafka_consumer_group: str = "novelty-detector"
    auto_follow_plays: int = 3

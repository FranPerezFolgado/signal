from signal_common.settings import CommonSettings


class Settings(CommonSettings):
    kafka_consumer_group: str = "history-tracker-enriched-group"

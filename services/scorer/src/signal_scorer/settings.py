from signal_common.settings import CommonSettings


class Settings(CommonSettings):
    kafka_consumer_group: str = "scorer"
    kafka_input_topic: str = "tracks.novel"
    kafka_dlq_topic: str = "scorer.dlq"
    w1: float = 0.6
    w2: float = 0.4
    hp_bonus: float = 1.2
    scorer_stats_interval: int = 100

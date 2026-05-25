from signal_common.logger import configure_logging, get_logger

from signal_scorer.app import run_consumer
from signal_scorer.settings import Settings

_log = get_logger(__name__)


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    if abs(settings.w1 + settings.w2 - 1.0) > 0.01:
        _log.warning(
            "weight_sum_deviation",
            w1=settings.w1,
            w2=settings.w2,
            sum=round(settings.w1 + settings.w2, 4),
        )
    run_consumer(settings)


if __name__ == "__main__":
    main()

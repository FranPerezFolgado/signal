from signal_common.logger import configure_logging

from signal_history_tracker.app import run_consumer
from signal_history_tracker.settings import Settings


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    run_consumer(settings)


if __name__ == "__main__":
    main()

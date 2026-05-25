from signal_common.logger import configure_logging

from signal_artist_tracker.app import run_polling
from signal_artist_tracker.settings import Settings


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    run_polling(settings)


if __name__ == "__main__":
    main()

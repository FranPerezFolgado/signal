import argparse

from signal_common.logger import configure_logging

from signal_lastfm_ingester.app import run_backfill, run_polling
from signal_lastfm_ingester.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Last.fm ingester for Signal")
    parser.add_argument("--backfill", action="store_true", help="Load full history and exit")
    args = parser.parse_args()

    settings = Settings()
    configure_logging(settings.log_level)

    if args.backfill:
        run_backfill(settings)
    else:
        run_polling(settings)


if __name__ == "__main__":
    main()

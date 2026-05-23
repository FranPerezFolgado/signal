from signal_enricher.app import run_consumer
from signal_enricher.settings import Settings


def main() -> None:
    run_consumer(Settings())


if __name__ == "__main__":
    main()

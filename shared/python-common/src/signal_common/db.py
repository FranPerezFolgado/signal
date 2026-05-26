from collections.abc import Generator
from contextlib import contextmanager

import psycopg


@contextmanager
def get_connection(database_url: str) -> Generator[psycopg.Connection, None, None]:
    with psycopg.connect(database_url) as conn:
        yield conn

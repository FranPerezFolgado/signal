from contextlib import contextmanager
from typing import Generator

import psycopg


@contextmanager
def get_connection(database_url: str) -> Generator[psycopg.Connection, None, None]:
    with psycopg.connect(database_url) as conn:
        yield conn

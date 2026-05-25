from collections.abc import Generator

import psycopg
from fastapi import Request


def get_db(request: Request) -> Generator[psycopg.Connection, None, None]:
    with request.app.state.pool.connection() as conn:
        yield conn

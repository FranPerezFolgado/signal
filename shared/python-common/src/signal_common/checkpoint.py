from dataclasses import dataclass
from datetime import datetime

import psycopg


@dataclass(frozen=True)
class Checkpoint:
    service: str
    last_played_at: datetime


class CheckpointRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def get(self, service: str) -> Checkpoint | None:
        row = self._conn.execute(
            "SELECT service, last_played_at FROM ingester_checkpoints WHERE service = %s",
            (service,),
        ).fetchone()
        if row is None:
            return None
        return Checkpoint(service=row[0], last_played_at=row[1])

    def upsert(self, service: str, last_played_at: datetime) -> None:
        self._conn.execute(
            """
            INSERT INTO ingester_checkpoints (service, last_played_at, updated_at)
            VALUES (%s, %s, now())
            ON CONFLICT (service)
            DO UPDATE SET last_played_at = EXCLUDED.last_played_at, updated_at = now()
            """,
            (service, last_played_at),
        )
        self._conn.commit()

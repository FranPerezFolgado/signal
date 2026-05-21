from datetime import UTC, datetime
from unittest.mock import MagicMock

from signal_common.checkpoint import Checkpoint, CheckpointRepository


def test_get_returns_none_when_no_checkpoint() -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    repo = CheckpointRepository(conn)
    assert repo.get("lastfm-ingester") is None


def test_get_returns_checkpoint_when_exists() -> None:
    ts = datetime(2026, 1, 17, 2, 20, 0, tzinfo=UTC)
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("lastfm-ingester", ts)
    repo = CheckpointRepository(conn)
    result = repo.get("lastfm-ingester")
    assert result == Checkpoint(service="lastfm-ingester", last_played_at=ts)


def test_upsert_calls_execute_and_commit() -> None:
    ts = datetime(2026, 1, 17, 2, 20, 0, tzinfo=UTC)
    conn = MagicMock()
    repo = CheckpointRepository(conn)
    repo.upsert("lastfm-ingester", ts)
    conn.execute.assert_called_once()
    conn.commit.assert_called_once()


def test_upsert_sql_uses_on_conflict() -> None:
    ts = datetime(2026, 1, 17, 2, 20, 0, tzinfo=UTC)
    conn = MagicMock()
    repo = CheckpointRepository(conn)
    repo.upsert("lastfm-ingester", ts)
    sql = conn.execute.call_args[0][0]
    assert "ON CONFLICT" in sql
    assert "DO UPDATE" in sql

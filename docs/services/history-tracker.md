# history-tracker

Consumes enriched tracks from `tracks.enriched`, persists them to PostgreSQL, upserts the artist record, and forwards each event to `listening.history` for downstream consumers.

## Topics

| Direction | Topic | Notes |
|-----------|-------|-------|
| Consumes  | `tracks.enriched` | Consumer group `history-tracker-group` |
| Produces  | `listening.history` | Forwarded on successful DB commit; same payload as input |
| Produces  | `history-tracker.dlq` | Failed messages with error reason |

## Database writes

### `listening_history` table

One row per unique `signal_id`. If the same track arrives again (idempotent upsert), the scrobble count is incremented and the `last_played_at` timestamp is updated. No duplicate rows.

### `artists` table

An artist row is upserted on every track. On the first encounter the artist is created with `status = TRACKED`. Subsequent plays increment `scrobble_count`.

## Dead-letter queue

Messages that fail PostgreSQL writes or Kafka produce calls are routed to `history-tracker.dlq` with an `error_reason` field. The consumer offset is still committed so the main pipeline never stalls. Errors in the DLQ topic itself are logged but do not halt the service.

See [ADR-005](../adr/ADR-005-dead-letter-queue-pattern.md) for the DLQ rationale.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker |
| `DATABASE_URL` | — | PostgreSQL DSN (required) |

## Running locally

```bash
make history-tracker-up
make history-tracker-logs
```

## Tests

```bash
uv run pytest services/history-tracker/
```

Tests cover repository upsert logic, DLQ publishing, and the integration behaviour of the consumer loop.

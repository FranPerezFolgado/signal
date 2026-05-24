# signal-common

Shared Python library (`shared/python-common/`) used by all Signal services. Provides infrastructure primitives so individual services contain only domain logic.

## Modules

### `kafka_producer` / `kafka_consumer`

Thin wrappers around `confluent-kafka` that handle JSON serialisation, offset management, and structured logging. Services pass the bootstrap server and consumer group — no boilerplate.

### `logger`

Structured JSON logger built on `structlog`. All services call `get_logger(__name__)` and emit key-value log events (`_log.info("processed", signal_id=...)`).

### `settings` (`CommonSettings`)

Base Pydantic Settings class that reads from environment variables. Each service extends it with its own fields.

### `rate_limiter`

Token-bucket rate limiter. Constructed with a `requests_per_30s` cap; services call `limiter.acquire()` before each API call.

### `circuit_breaker`

Three-state circuit breaker (CLOSED → OPEN → HALF_OPEN). Services call `cb.should_allow()` before a protected call, then `cb.record_success()` or `cb.record_failure()` after.

See [ADR-010](../adr/ADR-010-shared-resilience-primitives.md) for the rationale behind these being shared rather than per-service copies.

### `checkpoint`

Repository for the `checkpoints` PostgreSQL table. Used by `lastfm-ingester` to persist its last-polled timestamp across restarts.

### `db`

Helper for opening a `psycopg` connection from a DSN string.

### `spotify`

`SpotifyServiceError` base exception used by services that call Spotify APIs.

## Adding a dependency on signal-common

In a service's `pyproject.toml`:

```toml
[project]
dependencies = ["signal-common"]

[tool.uv.sources]
signal-common = { workspace = true }
```

## Tests

```bash
uv run pytest shared/python-common/
```

Tests cover `CheckpointRepository`, `CircuitBreaker`, and `RateLimiter`.

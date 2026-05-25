# signal-common

Shared Python library used by all Signal services. Provides infrastructure primitives so individual services contain only domain logic.

## Modules

### `kafka_producer` / `kafka_consumer`

Thin wrappers around `confluent-kafka` that handle JSON serialisation, offset management, and structured logging.

### `logger`

Structured JSON logger built on `structlog`. Services call `get_logger(__name__)` and emit key-value log events.

### `settings` (`CommonSettings`)

Base Pydantic Settings class that reads from environment variables and `.env` files. Each service extends it with its own fields.

### `rate_limiter`

Token-bucket rate limiter. Constructed with a `requests_per_30s` cap; services call `limiter.acquire()` before each API call.

### `circuit_breaker`

Three-state circuit breaker (CLOSED → OPEN → HALF_OPEN). Services call `cb.should_allow()` before a protected call, then `cb.record_success()` or `cb.record_failure()` after.

See [ADR-010](../../docs/adr/ADR-010-shared-resilience-primitives.md) for the rationale behind these being shared rather than per-service copies.

### `checkpoint`

Repository for the `checkpoints` PostgreSQL table. Used by `lastfm-ingester` to persist its last-polled timestamp across restarts.

### `models`

Shared domain models and enums. `ArtistStatus` (`TRACKED`, `FOLLOWING`, `PUBLISHED`, `BLACKLISTED`) is a `str`-based enum used by all services that interact with the `artists` table.

### `spotify`

`SpotifyServiceError` base exception and shared Spotify auth/retry logic. See [ADR-011](../../docs/adr/ADR-011-base-spotify-client-and-service-error.md).

## Adding signal-common as a dependency

In a service's `pyproject.toml`:

```toml
[project]
dependencies = ["signal-common"]

[tool.uv.sources]
signal-common = { workspace = true }
```

## Tests

```bash
cd shared/python-common
uv run pytest tests/ -q
```

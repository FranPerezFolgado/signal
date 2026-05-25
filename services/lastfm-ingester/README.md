# lastfm-ingester

[![CI](https://github.com/FranPerezFolgado/signal/actions/workflows/ci-lastfm-ingester.yml/badge.svg)](https://github.com/FranPerezFolgado/signal/actions/workflows/ci-lastfm-ingester.yml)

Polls the Last.fm API for recent scrobbles and publishes them to the `raw.plays` Kafka topic.

## Topics

| Direction | Topic | Notes |
|-----------|-------|-------|
| Produces  | `raw.plays` | One message per scrobble; JSON; keyed by `artist|title` (lowercase) |

## Message schema (`raw.plays`)

```json
{
  "source": "lastfm",
  "artist": "Actress",
  "title": "Rims",
  "played_at": "2026-05-01T21:00:00Z",
  "raw": { ... }
}
```

## Modes

| Mode | Command | Description |
|------|---------|-------------|
| **Polling** (default) | `make ingester-poll` | Runs continuously; polls every `LASTFM_POLL_INTERVAL_SECONDS`. Reads the last-seen timestamp from the PostgreSQL `checkpoints` table so no scrobble is re-emitted. |
| **Backfill** | `make ingester-backfill` | One-shot; pages through the entire Last.fm history from oldest to newest, then exits. |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LASTFM_API_KEY` | — | Last.fm API key (required) |
| `LASTFM_USERNAME` | — | Last.fm username to fetch (required) |
| `LASTFM_POLL_INTERVAL_SECONDS` | `60` | Seconds between poll cycles |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address |
| `DATABASE_URL` | `postgresql://signal:signal@localhost:5432/signal` | PostgreSQL DSN (checkpoint persistence) |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Consecutive failures before the circuit opens |
| `CIRCUIT_BREAKER_TIMEOUT_S` | `60.0` | Seconds the circuit stays open before half-open probe |

## Resilience

- **Rate limiter** — token-bucket gate respects Last.fm's public rate limits.
- **Circuit breaker** — opens after N consecutive API failures; the polling loop skips calls while the circuit is open, then probes again after the timeout.
- **Checkpoint** — the last `played_at` timestamp is persisted in PostgreSQL so polling resumes from the correct position after a restart.

## Running locally

```bash
# Polling (requires .env loaded in shell or in .env file)
make ingester-poll

# Backfill (full history, one-shot)
make ingester-backfill

# As Docker container
make ingester-up
make ingester-logs
```

## Tests

```bash
cd services/lastfm-ingester
uv run pytest tests/ -q
```

Integration tests require a live stack (`make up`) and auto-skip otherwise:

```bash
uv run pytest tests/integration/ -q
```

# artist-tracker

[![CI](https://github.com/FranPerezFolgado/signal/actions/workflows/ci-artist-tracker.yml/badge.svg)](https://github.com/FranPerezFolgado/signal/actions/workflows/ci-artist-tracker.yml)

Polls Spotify for the top tracks of all `FOLLOWING` artists and emits them to `raw.tracks`, feeding the normaliser to discover new releases via the listening pipeline.

## Topics

| Direction | Topic | Notes |
|-----------|-------|-------|
| Produces  | `raw.tracks` | One message per track; same schema as `raw.plays` |

## How it works

On each polling cycle the tracker:

1. Queries PostgreSQL for `FOLLOWING` artists whose `last_explored_at` is older than `ARTIST_REEXPLORE_DAYS` (or never explored).
2. Fetches the artist's top tracks from Spotify.
3. Emits each track to `raw.tracks`, which is consumed by the normaliser.
4. Marks the artist as explored (`last_explored_at = now()`).

The cycle repeats every `ARTIST_TRACKER_INTERVAL_HOURS`. Artists are processed in ascending `last_explored_at` order so long-unvisited artists are prioritised.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker |
| `DATABASE_URL` | `postgresql://signal:signal@localhost:5432/signal` | PostgreSQL DSN (required) |
| `SPOTIFY_CLIENT_ID` | — | Required |
| `SPOTIFY_CLIENT_SECRET` | — | Required |
| `SPOTIFY_REFRESH_TOKEN` | — | Required |
| `ARTIST_TRACKER_INTERVAL_HOURS` | `6.0` | Hours between polling cycles |
| `ARTIST_REEXPLORE_DAYS` | `7` | Days before an artist is eligible for re-exploration |
| `ARTIST_TRACKER_RATE_LIMIT_PER_30S` | `30` | Max Spotify calls per 30-second window |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Failures before Spotify circuit opens |
| `CIRCUIT_BREAKER_TIMEOUT_S` | `60.0` | Circuit open duration (seconds) |

## Running locally

```bash
docker compose -f infra/docker-compose.yml --profile services up artist-tracker
```

Or directly:

```bash
set -a && source .env && set +a
uv run signal-artist-tracker
```

## Tests

```bash
cd services/artist-tracker
uv run pytest tests/unit/ -q
```

Integration tests require a live stack (`make up`) and auto-skip otherwise:

```bash
uv run pytest tests/integration/ -q
```

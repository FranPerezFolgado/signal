# artist-tracker

[![CI](https://github.com/FranPerezFolgado/signal/actions/workflows/ci-artist-tracker.yml/badge.svg)](https://github.com/FranPerezFolgado/signal/actions/workflows/ci-artist-tracker.yml)

Polls Spotify for the top tracks of all `FOLLOWING` artists and performs 1-hop similarity expansion via Last.fm to discover new artists. Feeds the normaliser pipeline and the `artist.discovered` topic.

## Topics

| Direction | Topic | Notes |
|-----------|-------|-------|
| Produces  | `raw.tracks` | One message per track; same schema as `raw.plays` |
| Produces  | `artist.discovered` | One message per newly inserted similar artist (source: `LASTFM_SIMILAR`) |

## How it works

The service runs two independent polling cycles sharing a single process:

**Top-tracks cycle** (every `ARTIST_TRACKER_INTERVAL_HOURS`):

1. Queries PostgreSQL for `FOLLOWING` artists whose `last_explored_at` is older than `ARTIST_REEXPLORE_DAYS`.
2. Fetches the artist's top tracks from Spotify.
3. Emits each track to `raw.tracks`.
4. Marks the artist as explored (`last_explored_at = now()`).

**Similar-artist expansion cycle** (every `LASTFM_SIMILAR_INTERVAL_HOURS`):

1. Queries PostgreSQL for `FOLLOWING` artists whose `last_similar_explored_at` has expired.
2. Calls `Last.fm artist.getSimilar` for each artist.
3. Deduplicates by Last.fm MBID (`external_ids->>'lastfm_mbid'`); falls back to name uniqueness.
4. Inserts new artists as `TRACKED` with `source='LASTFM_SIMILAR'` and `origin_artist_id` FK.
5. Emits an `artist.discovered` event for each new insertion.
6. Marks the artist as similar-explored only on success.

Both cycles fire immediately on startup. A single `time.monotonic()` deadline per cycle ensures they run independently without blocking each other.

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
| `LASTFM_API_KEY` | — | Required; Last.fm API key |
| `LASTFM_SIMILAR_INTERVAL_HOURS` | `24.0` | Hours between similarity expansion cycles |
| `LASTFM_SIMILAR_LIMIT` | `10` | Max similar artists to fetch per artist |
| `LASTFM_SIMILAR_RATE_LIMIT_PER_30S` | `150` | Max Last.fm calls per 30-second window |

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

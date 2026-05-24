# normalizer

Consumes raw scrobbles from `raw.plays`, resolves Spotify IDs for the artist and track, and emits a unified normalised message to `tracks.normalized`.

## Topics

| Direction | Topic | Notes |
|-----------|-------|-------|
| Consumes  | `raw.plays` | Consumer group `normalizer-group` |
| Produces  | `tracks.normalized` | Keyed by `signal_id` (SHA-256 of normalised `artist|title`) |

## Message schema (`tracks.normalized`)

```json
{
  "signal_id": "a3f9...",
  "artist": "Actress",
  "artist_id": "spotify:artist:...",
  "track_id": "spotify:track:...",
  "title": "Rims",
  "sources": ["lastfm"],
  "played": true,
  "played_at": "2026-05-01T21:00:00Z",
  "processed_at": "2026-05-01T21:00:05Z"
}
```

`artist_id` and `track_id` may be `null` when Spotify is unavailable (circuit open) or the track is not found. Downstream services handle missing IDs gracefully.

## signal_id

A deterministic SHA-256 hash of the lowercase, stripped `artist` + `title`. This canonical ID ties together the same track arriving from multiple sources (Last.fm play, Spotify enrichment, etc.) without needing a central ID registry.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker |
| `SPOTIFY_CLIENT_ID` | — | Spotify app client ID (required) |
| `SPOTIFY_CLIENT_SECRET` | — | Spotify app client secret (required) |
| `SPOTIFY_REFRESH_TOKEN` | — | Long-lived refresh token (required) |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Failures before Spotify circuit opens |
| `CIRCUIT_BREAKER_TIMEOUT_S` | `60.0` | Circuit open duration (seconds) |

## Resilience

- **Circuit breaker** — protects Spotify search; when open, `artist_id`/`track_id` are emitted as `null` so the pipeline keeps flowing rather than stalling.
- **Rate limiter** — per-service token bucket for Spotify API calls.
- **Malformed message handling** — messages without `artist` or `title` are logged and committed (skipped); they do not block the consumer.

## Running locally

```bash
make normalizer-up
make normalizer-logs
```

## Tests

```bash
uv run pytest services/normalizer/
```

Tests cover `signal_id` computation, Spotify client interactions, and the consumer loop behaviour.

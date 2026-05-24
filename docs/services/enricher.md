# enricher

Consumes normalised tracks from `tracks.normalized`, fetches genre and popularity metadata from Spotify (with a Last.fm fallback), and emits enriched events to `tracks.enriched`.

## Topics

| Direction | Topic | Notes |
|-----------|-------|-------|
| Consumes  | `tracks.normalized` | Consumer group `enricher-group` |
| Produces  | `tracks.enriched` | Keyed by `signal_id` |

## Message schema (`tracks.enriched`)

```json
{
  "signal_id": "a3f9...",
  "artist": "Actress",
  "artist_id": "spotify:artist:...",
  "title": "Rims",
  "genres": ["ambient", "experimental electronic"],
  "artist_popularity": 38,
  "track_popularity": 22,
  "enrichment_source": "spotify",
  "pending_enrichment": false,
  "played_at": "2026-05-01T21:00:00Z",
  "processed_at": "2026-05-01T21:00:06Z"
}
```

`pending_enrichment: true` means Spotify was unavailable; the novelty-detector skips these messages rather than computing novelty with incomplete data.

## Enrichment fallback chain

1. **Spotify** — genres from the artist object, popularity from both artist and track endpoints.
2. **Last.fm** — `artist.getTopTags` as fallback when Spotify is unavailable or returns no genres.
3. **Pending** — if both APIs fail, `pending_enrichment` is set to `true` and the message is forwarded without genre data.

See [ADR-004](../adr/ADR-004-enrichment-fallback-chain.md) for the rationale behind this chain.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker |
| `SPOTIFY_CLIENT_ID` | — | Required |
| `SPOTIFY_CLIENT_SECRET` | — | Required |
| `SPOTIFY_REFRESH_TOKEN` | — | Required |
| `LASTFM_API_KEY` | `""` | Optional; enables Last.fm fallback |
| `LASTFM_FALLBACK_ENABLED` | `true` | Toggle Last.fm fallback |
| `SPOTIFY_RATE_LIMIT_PER_30S` | `180` | Spotify token-bucket window |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Failures before Spotify circuit opens |
| `CIRCUIT_BREAKER_TIMEOUT_S` | `60.0` | Circuit open duration (seconds) |
| `BACKOFF_BASE_S` | `1.0` | Base delay for exponential backoff |
| `BACKOFF_MAX_S` | `30.0` | Maximum backoff delay |

## Resilience

- **Rate limiter** — token bucket capped at `SPOTIFY_RATE_LIMIT_PER_30S` requests per 30-second window.
- **Circuit breaker** — three-state (CLOSED → OPEN → HALF_OPEN); the Last.fm fallback is only attempted when Spotify is available but returns no genres, not when the circuit is open.
- **Exponential backoff** — applied on Spotify 429 responses, respecting the `Retry-After` header.

See [ADR-010](../adr/ADR-010-shared-resilience-primitives.md) for why these primitives live in `signal_common`.

## Running locally

```bash
make enricher-up
make enricher-logs
```

## Tests

```bash
uv run pytest services/enricher/
```

Tests cover Spotify and Last.fm client interactions, the fallback chain logic, and the consumer loop.

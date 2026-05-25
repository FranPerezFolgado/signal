# novelty-detector

[![CI](https://github.com/FranPerezFolgado/signal/actions/workflows/ci-novelty-detector.yml/badge.svg)](https://github.com/FranPerezFolgado/signal/actions/workflows/ci-novelty-detector.yml)

Consumes enriched tracks from `tracks.enriched`, cross-references them against the listening history and artist table in PostgreSQL, and emits a novelty event to `tracks.novel` whenever an artist or genre is new.

## Topics

| Direction | Topic | Notes |
|-----------|-------|-------|
| Consumes  | `tracks.enriched` | Consumer group `novelty-detector-group` |
| Produces  | `tracks.novel` | Only emitted when novelty is detected |
| Produces  | `novelty-detector.dlq` | Failed or malformed messages |

## Novelty logic

For each enriched track the detector checks:

1. **Artist is new** — the artist has not appeared in the listening history before.
2. **New genres** — one or more of the track's genres have never been seen in the listening history.
3. **Track is new** — the specific `signal_id` (artist + title hash) has not been seen before.

A track is emitted to `tracks.novel` if condition 1 or 2 is true. Tracks where `pending_enrichment: true` are skipped entirely and not sent to the DLQ.

## Message schema (`tracks.novel`)

```json
{
  "signal_id": "a3f9...",
  "artist": "Actress",
  "artist_id": "spotify:artist:...",
  "genres": ["ambient", "experimental electronic"],
  "artist_popularity": 38,
  "track_popularity": 22,
  "played_at": "2026-05-01T21:00:00Z",
  "novelty_signals": {
    "track_is_new": true,
    "artist_is_new": true,
    "new_genres": ["experimental electronic"],
    "known_genres": ["ambient"],
    "genre_novelty_ratio": 0.5
  }
}
```

## Artist auto-promotion

When a `TRACKED` artist accumulates scrobbles equal to or exceeding `AUTO_FOLLOW_PLAYS`, the detector promotes them to `FOLLOWING` in the same database transaction. A DB failure logs a warning and rolls back the promotion without blocking the novelty event.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker |
| `DATABASE_URL` | `postgresql://signal:signal@localhost:5432/signal` | PostgreSQL DSN (required) |
| `AUTO_FOLLOW_PLAYS` | `3` | Scrobble threshold for auto-promotion to `FOLLOWING` |

## Running locally

```bash
make novelty-detector-up
make novelty-detector-logs
```

## Tests

```bash
cd services/novelty-detector
uv run pytest tests/unit/ -q
```

Integration tests require a live stack (`make up`) and auto-skip otherwise:

```bash
uv run pytest tests/integration/ -q
```

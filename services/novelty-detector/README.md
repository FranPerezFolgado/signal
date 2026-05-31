# novelty-detector

[![CI](https://github.com/FranPerezFolgado/signal/actions/workflows/novelty-detector.yml/badge.svg)](https://github.com/FranPerezFolgado/signal/actions/workflows/novelty-detector.yml)

Consumes enriched tracks from `tracks.enriched`, cross-references them against the listening history and artist table in PostgreSQL, and emits a novelty event to `tracks.novel` whenever an artist or genre is new. Written in Go.

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
3. **Track is new** — the specific `signal_id` has not been seen before.

A track is emitted to `tracks.novel` if condition 1 or 2 is true. Tracks where `pending_enrichment: true` are skipped silently (not DLQ'd).

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

When a `TRACKED` artist accumulates scrobbles equal to or exceeding `AUTO_FOLLOW_PLAYS`, the detector promotes them to `FOLLOWING`. A DB failure during promotion logs a warning and does not block the novelty event (best-effort).

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address |
| `DATABASE_URL` | — | PostgreSQL DSN (required) |
| `KAFKA_CONSUMER_GROUP` | `novelty-detector-group` | Consumer group ID |
| `LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARN`, `ERROR`) |
| `AUTO_FOLLOW_PLAYS` | `3` | Scrobble threshold for auto-promotion to `FOLLOWING` |
| `KAFKA_FLUSH_TIMEOUT_MS` | `10000` | Max ms to wait for Kafka flush before skipping commit |

## Project layout

```
novelty-detector/
├── cmd/novelty-detector/   # main package — wires deps, handles OS signals
├── internal/
│   ├── config/             # environment-based configuration
│   ├── consumer/           # core processing loop + tests
│   ├── dlq/                # dead-letter queue publisher
│   ├── kafka/              # Consumer/Producer interfaces + confluent wrappers
│   ├── novelty/            # Compute/ShouldEmit pure logic + unit tests
│   └── repository/         # pgx implementations of ArtistRepo/NoveltyRepo
├── Dockerfile
└── go.mod
```

## Build

Requires Go 1.22+ and `librdkafka-dev` (for `confluent-kafka-go`):

```bash
cd services/novelty-detector
go build -tags musl -o novelty-detector ./cmd/novelty-detector/
```

## Unit tests

```bash
cd services/novelty-detector
go test ./...
```

## Integration tests

Requires Docker (testcontainers-go spins up Kafka and PostgreSQL automatically):

```bash
cd services/novelty-detector
go test -tags integration ./internal/consumer/ -v -timeout 180s
```

## Running locally

```bash
make up          # starts Kafka + PostgreSQL
# set DATABASE_URL, then:
./novelty-detector
```

Or via Docker Compose (the `infra/docker-compose.yml` entry builds this Dockerfile):

```bash
make up
```

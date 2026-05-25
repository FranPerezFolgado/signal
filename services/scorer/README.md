# scorer

[![CI](https://github.com/FranPerezFolgado/signal/actions/workflows/ci-scorer.yml/badge.svg)](https://github.com/FranPerezFolgado/signal/actions/workflows/ci-scorer.yml)

Terminal consumer that reads novel artist events from `tracks.novel`, computes a 2-factor discovery score, and upserts the result into the `artist_recommendations` PostgreSQL table. No output topic is produced.

## Topics

| Direction | Topic | Notes |
|-----------|-------|-------|
| Consumes  | `tracks.novel` | Consumer group `scorer` |
| Produces  | `scorer.dlq` | Malformed messages or unresolvable artists |

## Scoring formula

```
popularity_norm = (artist_popularity ?? 0) / 100
genre_novelty   = W1 * genre_novelty_ratio
pop_component   = W2 * (1 - popularity_norm)
raw_score       = genre_novelty + pop_component
score           = min(raw_score * HP_BONUS, 1.0)   # only if high_priority=true
score           = min(raw_score, 1.0)               # otherwise
```

`score_breakdown` stores `{"genre_novelty": float, "popularity_norm": float}`.

## Upsert behaviour (`artist_recommendations`)

- `updated_at` is always refreshed.
- `score` and `score_breakdown` are only updated when the new score strictly exceeds the stored score.
- `evidence_tracks` (list of `signal_id` values) is appended when the score improves **and** the `signal_id` is not already present (JSONB `@>` deduplication).

## Artist lookup

1. Match `artists.external_ids->>'spotify'` against the incoming Spotify URI.
2. If not found, fall back to case-insensitive `LOWER(name)` match.
3. If both fail, the message is sent to `scorer.dlq` with `error_reason: artist_not_found`.

## DLQ triggers

| `error_reason` | Cause |
|---|---|
| `validation_failed` | Missing `signal_id`, `artist`, `novelty_signals`; `genre_novelty_ratio` out of `[0.0, 1.0]` |
| `artist_not_found` | Spotify URI and name both unresolvable in the `artists` table |
| `processing_error` | Unexpected runtime error during scoring or upsert |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker |
| `DATABASE_URL` | `postgresql://signal:signal@localhost:5432/signal` | PostgreSQL DSN (required) |
| `W1` | `0.6` | Genre novelty weight |
| `W2` | `0.4` | Popularity norm weight |
| `HP_BONUS` | `1.2` | Score multiplier for `high_priority` artists |
| `SCORER_STATS_INTERVAL` | `100` | Log counters every N messages |

A startup warning is logged if `|W1 + W2 - 1.0| > 0.01`.

## Running locally

```bash
docker compose -f infra/docker-compose.yml --profile services up scorer
```

## Tests

```bash
cd services/scorer
uv run pytest tests/unit/ -q
```

Integration tests require a live stack (`make up`) and auto-skip otherwise:

```bash
uv run pytest tests/integration/ -q
```

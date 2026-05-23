# ADR-007 — Separate normalizer and enricher into distinct services

- **Status**: Accepted
- **Date**: 2026-05-23

## Context

In MVP v1, the normalizer called Spotify synchronously inside the Kafka poll loop: search → genres → audio features → Last.fm fallback. Each message processing could block for several seconds waiting on Spotify.

On 2026-05-21, this caused a production failure: `max.poll.interval.ms` (300 seconds) was exceeded by 423 milliseconds. Kafka expelled the normalizer from the consumer group and 61,436 messages accumulated as lag on `raw.plays`. The service recovered after restart but the root cause was not addressed.

The Kafka consumer contract requires that `poll()` is called at regular intervals. Any synchronous I/O inside the poll loop that exceeds `max.poll.interval.ms` causes consumer group rebalance and lag accumulation.

## Decision

Split the normalizer into two services with distinct responsibilities:

- **normalizer**: schema unification, `signal_id` computation, Spotify ID resolution via `GET /search` (2-second timeout, zero retries). No enrichment. No database writes. Pure Kafka consumer/producer.
- **enricher**: reads from `tracks.normalized`, calls `GET /artists/{id}` and `GET /tracks/{id}` for genres and popularity, falls back to Last.fm, emits to `tracks.enriched`. Owns all resilience mechanisms: rate limiter, circuit breaker, exponential backoff with jitter.

The enricher manages its own consumer group (`enricher-group`) and its own Kafka offsets. If Spotify is slow, lag accumulates on `tracks.normalized` — which is the correct Kafka behaviour. The normalizer is never blocked.

## Alternatives considered

**Increase `max.poll.interval.ms`**: Setting it to 600s or higher would prevent the timeout. Rejected because it treats the symptom, not the cause. Any sufficiently slow Spotify response (or increase in traffic) would trigger the same failure. It also makes debugging harder by masking genuine consumer hangs.

**Async I/O inside the normalizer**: Using `asyncio` or threading to make Spotify calls non-blocking inside the poll loop. Rejected because it adds significant complexity (async Kafka consumer, thread management, error propagation) without changing the architectural coupling. The normalizer would still own two concerns.

**Larger batch processing**: Calling Spotify in batches after accumulating N messages. Rejected because Spotify does not offer batch endpoints for `GET /artists/{id}`, and batching adds state management complexity without solving the blocking problem.

## Consequences

- Consumer lag on `tracks.normalized` is now decoupled from Spotify latency.
- The enricher can be scaled, restarted, or reconfigured independently of the normalizer.
- Adding a new enrichment source (e.g., MusicBrainz) requires changes only to the enricher service.
- A new Kafka topic `tracks.enriched` is introduced. Downstream consumers (history-tracker, novelty-detector) must be updated to consume from it.
- The normalizer loses its PostgreSQL dependency entirely, simplifying its failure modes.

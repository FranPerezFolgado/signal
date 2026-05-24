# ADR-010: Shared Resilience Primitives (RateLimiter + CircuitBreaker) in signal_common

- **Status**: Accepted
- **Date**: 2026-05-24

## Context

Three Signal services call external APIs: `normalizer` (Spotify search), `enricher` (Spotify artist/track data), and `lastfm-ingester` (Last.fm recent tracks). The enricher had working `RateLimiter` (token bucket) and `CircuitBreaker` (3-state CLOSED/OPEN/HALF_OPEN) implementations as local files. The normalizer had no rate limiting at all, causing sustained 429 bursts from Spotify where affected tracks were forwarded with null IDs and never retried. The lastfm-ingester had only hardcoded exponential backoff with no rate gate. Duplicating the algorithm into each service would mean any fix (e.g. Retry-After handling) must be applied in N places.

## Decision

`RateLimiter` and `CircuitBreaker` are promoted from `signal_enricher` into `signal_common`, and every service that calls an external API wires them in via constructor injection with its own Settings-backed thresholds.

## Alternatives considered

**Keep per-service copies** — *Rejected*
Each service already diverged within one sprint (enricher had both primitives, normalizer had neither, lastfm-ingester had partial retry logic). Keeping copies guarantees drift: a bug fix in one service never reaches the others.

**Single global rate limiter shared across services** — *Rejected*
Spotify and Last.fm have different rate limits (180 req/30 s vs 150 req/30 s), and each service runs as an independent container. A shared cross-process rate limiter would require Redis or a sidecar, adding infrastructure for a problem that per-process token buckets already solve correctly given single-instance deployment.

**Shared primitives in signal_common** — *Accepted*

## Consequences

✅ A single fix to `RateLimiter` or `CircuitBreaker` (e.g. state-transition logging, window parameter) propagates to all services via the shared package.
✅ New services that call external APIs adopt resilience via three lines of constructor injection — no algorithm code to write.
✅ Each service configures its own thresholds (`circuit_breaker_failure_threshold`, `lastfm_rate_limit_per_30s`, etc.) via its own Settings class; no cross-service coupling at runtime.
❌ `signal_common` now carries HTTP-layer concerns (rate limiting, circuit breaking) alongside infrastructure concerns (Kafka, DB, logging). As the library grows this becomes a grab-bag; a future `signal_common.resilience` sub-module may be warranted.
❌ Per-process rate limiting is only correct for single-instance deployments. If any service scales to multiple replicas, the token bucket will be per-replica and the effective rate will be multiplied by the replica count.

## When to reconsider

If any service is horizontally scaled beyond one replica, replace per-process `RateLimiter` with a Redis-backed distributed rate limiter and revisit whether `CircuitBreaker` state also needs to be shared across replicas.

# ADR-004: Enrichment fallback chain — Spotify → Last.fm → pending_enrichment

- **Status**: Accepted
- **Date**: 2026-05-21

## Context

The pipeline must attach genres and artist identity to every raw Last.fm scrobble before it enters the scoring stage. Last.fm scrobbles contain only artist name and track title — no Spotify IDs, no genres. Spotify is the primary enrichment source, but underground tracks, live bootlegs, limited releases, and artists with non-Latin names are disproportionately absent from Spotify's catalogue. These tracks are precisely the most valuable discovery candidates: the system exists to surface artists the listener doesn't already know. Silently dropping unenriched tracks would bias the pipeline toward mainstream artists and defeat the product's core purpose.

**Update (ADR-007, 2026-05-23):** This decision was originally implemented inside the `normalizer` service. A production MAXPOLL failure caused by synchronous Spotify calls inside the Kafka poll loop required extracting enrichment into a dedicated `enricher` service. The fallback strategy described in this ADR is unchanged; the owning service is now `enricher`, not `normalizer`. See ADR-007 for the architectural rationale.

## Decision

Enrich each track via a three-step fallback chain executed in order: (1) Spotify full enrichment via `GET /artists/{id}` + `GET /tracks/{id}`, (2) Last.fm crowd-sourced tags as genres, (3) emit with `pending_enrichment=true`. Every normalized play produces exactly one `tracks.enriched` message regardless of enrichment outcome — no track is ever dropped.

## Alternatives considered

**Spotify only, drop on miss** — *Rejected*
Loses underground and niche tracks, which are the most interesting discovery candidates. A system that only processes tracks already in Spotify's catalogue is not a discovery tool.

**MusicBrainz as second fallback** — *Rejected*
Better catalogue coverage for classical and folk than Last.fm tags, but adds a third external HTTP dependency and client implementation. Deferred to v2 if Last.fm tag coverage proves insufficient in practice.

**Block pipeline until enrichment succeeds (retry in place)** — *Rejected*
Creates head-of-line blocking: one unavailable external API stalls all downstream consumers on the same Kafka partition. The Kafka at-least-once model already retries on restart — no additional blocking is needed.

**Separate retry queue / enrichment service** — *Accepted (ADR-007)*
Originally rejected at MVP scale as adding unnecessary complexity. After a production MAXPOLL failure this approach was adopted: enrichment now lives in a dedicated `enricher` service with its own consumer group, rate limiter, circuit breaker, and backoff logic.

**Spotify → Last.fm → Last.fm (retry queue)** — *Accepted*

## Consequences

✅ Every scrobble reaches downstream consumers, including underground tracks with no Spotify presence — the pipeline is not biased toward mainstream artists.

✅ Partial enrichment (Last.fm tags as genres) provides enough signal for the genre-novelty factor in the scorer, even without audio features.

✅ The `pending_enrichment` flag is an explicit, inspectable state: `SELECT COUNT(*) FROM listening_history WHERE pending_enrichment = true` shows the re-enrichment backlog at any time.

✅ The Kafka offset is committed only after the `tracks.enriched` emit succeeds. On Spotify 429 or transient network failure the enricher retries from the same offset after restart, with no data loss.

❌ `pending_enrichment=true` tracks accumulate without being re-enriched. The scorer handles missing genres/popularity by scoring on the factors that are available.

❌ The three-step chain makes each message up to two sequential Spotify calls (`GET /artists/{id}` + `GET /tracks/{id}`), plus a Last.fm fallback call. Under Spotify's rate limit the enricher uses a token-bucket limiter and exponential backoff with jitter to stay within quota.

❌ A sustained Spotify outage opens the circuit breaker and causes the enricher to emit `pending_enrichment=true` for all subsequent messages until the breaker recovers. The dead-letter queue pattern (ADR-005) handles messages that cannot be processed at all.

## When to reconsider

If more than 20% of `tracks.normalized` messages have `pending_enrichment=true` after a full backfill, Last.fm tag coverage is insufficient for the genre-novelty signal and MusicBrainz should be evaluated as a second fallback. Measure after the first complete backfill run.

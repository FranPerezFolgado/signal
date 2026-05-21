# ADR-004: Enrichment fallback chain — Spotify → Last.fm → pending_enrichment

- **Status**: Accepted
- **Date**: 2026-05-21

## Context

The `normalizer` service must attach genres, audio features, and artist identity to every raw Last.fm scrobble before it enters the pipeline. Last.fm scrobbles contain only artist name and track title — no Spotify IDs, no genres, no audio features. Spotify is the primary enrichment source, but underground tracks, live bootlegs, limited releases, and artists with non-Latin names are disproportionately absent from Spotify's catalogue. These tracks are precisely the most valuable discovery candidates: the system exists to surface artists the listener doesn't already know. Silently dropping unenriched tracks would bias the pipeline toward mainstream artists and defeat the product's core purpose.

## Decision

Enrich each track via a three-step fallback chain executed in order: (1) Spotify full enrichment, (2) Last.fm crowd-sourced tags as genres, (3) emit with `pending_enrichment=true`. Every raw play produces exactly one `tracks.normalized` message regardless of enrichment outcome — no track is ever dropped.

## Alternatives considered

**Spotify only, drop on miss** — *Rejected*
Loses underground and niche tracks, which are the most interesting discovery candidates. A system that only processes tracks already in Spotify's catalogue is not a discovery tool.

**MusicBrainz as second fallback** — *Rejected*
Better catalogue coverage for classical and folk than Last.fm tags, but adds a third external HTTP dependency and client implementation. Deferred to v2 if Last.fm tag coverage proves insufficient in practice.

**Block pipeline until enrichment succeeds (retry in place)** — *Rejected*
Creates head-of-line blocking: one unavailable external API stalls all downstream consumers on the same Kafka partition. The Kafka at-least-once model already retries on restart — no additional blocking is needed.

**Separate retry queue / enrichment service** — *Rejected*
Decouples enrichment latency from pipeline throughput and enables targeted re-enrichment of `pending_enrichment=true` tracks. Architecturally cleaner, but adds an extra service and Kafka topic at MVP scale where a single normalizer instance is sufficient. Accepted as a post-MVP improvement.

**Spotify → Last.fm → Last.fm (retry queue)** — *Accepted*

## Consequences

✅ Every scrobble reaches downstream consumers, including underground tracks with no Spotify presence — the pipeline is not biased toward mainstream artists.

✅ Partial enrichment (Last.fm tags as genres) provides enough signal for the genre-novelty factor in the scorer, even without audio features.

✅ The `pending_enrichment` flag is an explicit, inspectable state: `SELECT COUNT(*) FROM listening_history WHERE pending_enrichment = true` shows the re-enrichment backlog at any time.

✅ The Kafka offset is committed only after both the PostgreSQL write and the `tracks.normalized` emit succeed. On Spotify 429 or transient network failure the message is retried from the same offset after restart, with no data loss.

❌ `pending_enrichment=true` tracks accumulate without being re-enriched. The scorer must handle `audio_features: null` by omitting the `audio_distance` term and re-normalising W1 and W2. This makes scores for pending tracks less precise.

❌ The three-step chain makes each message potentially three sequential HTTP calls (Spotify search, Spotify artist genres, audio features), plus a Last.fm fallback call. Under Spotify's standard rate limit (~100 req/min) a full 61k-scrobble backfill will take approximately 30 minutes with backoff.

❌ Spotify 429 responses trigger exponential backoff capped at 25 seconds (below the Kafka `session.timeout.ms` of 30 seconds to avoid consumer group rebalance during sleep). A sustained Spotify outage will stall the pipeline indefinitely with no dead-letter mechanism.

## When to reconsider

If more than 20% of `tracks.normalized` messages have `pending_enrichment=true` after a full backfill, Last.fm tag coverage is insufficient for the genre-novelty signal and MusicBrainz should be evaluated as a second fallback. Measure after the first complete backfill run.

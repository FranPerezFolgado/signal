# ADR-016: Last.fm `artist.getSimilar` as Graph Expansion Source

- **Status**: Accepted
- **Date**: 2026-05-26

## Context

The MVP `artist-tracker` service only fetches top-tracks for artists the user already follows. It does not discover new artists. The core discovery value of v3 is closing this loop: given that the user follows artist X, Signal should automatically surface artists similar to X as candidates for review.

Spotify's `/v1/artists/{id}/related-artists` endpoint was the original plan but was deprecated for new apps in November 2024 (ADR-012 notes this). An alternative source is needed.

Additionally, introducing new artists from similarity expansion requires a way to emit discovery events for pipeline tracing and future consumers (v5 stats collector, v6 curator-aggregator). This means adding a new Kafka topic — a messaging topology change requiring this ADR.

## Decision

### Similarity source: Last.fm `artist.getSimilar`

Use Last.fm `artist.getSimilar` as the sole similarity source for v3. It returns up to N ranked similar artists by name and optional MBID.

### Topology change: new `artist.discovered` topic

A new append-only Kafka topic `artist.discovered` is introduced. The `artist-tracker` produces to it when a new similar artist is inserted into the `artists` table. No consumer exists in v3; the topic serves as an audit log and future subscription point.

### Schema change: two new columns on `artists`

- `last_similar_explored_at TIMESTAMPTZ NULL` — tracks per-artist similarity exploration state independently of the existing `last_explored_at` (top-tracks cadence)
- `origin_artist_id UUID NULL` — FK to `artists.id`; records which FOLLOWED artist triggered each LASTFM_SIMILAR discovery

### Deduplication: MBID-first via `external_ids` JSONB

Artist identity is established by Last.fm MBID stored under `external_ids->>'lastfm_mbid'`. The existing `idx_artists_name_lower` unique index acts as a safety net for MBID-less artists.

## Alternatives considered

**Spotify `/v1/artists/{id}/related-artists`** — *Rejected*
Deprecated for new apps since November 2024. Not available.

**MusicBrainz `artist/browse` with relationship type `similar`** — *Rejected*
More complex query pattern; requires MBIDs as input (which we may not have for all FOLLOWING artists); no similarity ranking; slower API with stricter rate limits. Last.fm is simpler and more appropriate for music discovery use cases.

**Paid graph API (e.g. Songkick, Discogs, custom ML)** — *Rejected*
Unnecessary cost and complexity for a personal tool. Last.fm's public API is free, well-documented, and covers substantially all artists likely to appear in a listening history.

**Emit to `raw.tracks` with `origin.type=ARTIST_SIMILAR`** — *Rejected*
`raw.tracks` carries track-level messages; similar artists have no associated track at discovery time. Routing artist-level events through the track pipeline conflates two distinct concepts and would require the normalizer to handle a new message shape.

**Direct DB insert only (no Kafka event)** — *Rejected*
The spec requires the `origin_artist_id` to be carried in an event message for pipeline tracing (FR-004) and future consumers need a subscribable event stream without a future migration. A dedicated topic is the correct abstraction.

## Consequences

✅ Last.fm `artist.getSimilar` is free, available, and covers the target artist domain well.
✅ 1-hop expansion is sufficient for v3: user follows X → Signal surfaces artists similar to X → those enter the TRACKED review queue.
✅ Independent expansion cadence (`LASTFM_SIMILAR_INTERVAL_HOURS`, default 24h) avoids coupling similarity expansion to the 6-hour top-tracks cycle.
✅ `artist.discovered` topic is available for v5 stats and v6 curators without a future migration.
✅ MBID-based deduplication prevents re-queuing known artists; name uniqueness index is a secondary safety net.
❌ Last.fm MBID is optional in responses — artists without an MBID fall back to name-based dedup, which may miss variant spellings.
❌ `artist.discovered` has no consumer in v3 — the topic produces events that go unread until v5/v6.
❌ Precision of `artist.getSimilar` is opaque (algorithm is Last.fm's, not ours). Quality of recommendations is not measurable until v5 stats are built.

## When to reconsider

If Last.fm `artist.getSimilar` is deprecated or rate-limited more aggressively, evaluate MusicBrainz or a self-hosted collaborative filtering model. If MBID-less duplicate artists become a measurable data quality problem, add a fuzzy name-match dedup pass or require MBIDs at insert time.

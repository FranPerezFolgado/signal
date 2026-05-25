# ADR-013: `played` Boolean Field for Source Discrimination

- **Status**: Accepted
- **Date**: 2026-05-25

## Context

When artist-tracker was added, it started emitting Spotify top-tracks into `raw.tracks`, which the normalizer processes and forwards to `tracks.normalized` → `tracks.enriched`. This created an ambiguity: `tracks.enriched` is now consumed by history-tracker (which should only persist tracks the user actually listened to) and by novelty-detector and scorer (which should process all tracks, including recommendations, to score them). Without a way to distinguish user-played tracks from Spotify-sourced recommendations, history-tracker would inflate `play_count`, `scrobble_count`, and `listening_history` with tracks the user never heard.

## Decision

Add a `played: bool` field to the `tracks.normalized` and `tracks.enriched` schemas. The normalizer sets it as `played = (source == "lastfm")`. History-tracker skips the DB upsert when `played is False`; novelty-detector and scorer ignore the field and process all messages.

## Alternatives considered

**Separate output topics by intent** (`tracks.normalized.played` / `tracks.normalized.discovery`) — *Rejected*
Would require enricher, novelty-detector, and scorer to each subscribe to two topics instead of one. Doubles the topic count and forces changes to three services that currently need no awareness of track origin; the enrichment logic is identical regardless of source.

**Dedicated `raw.discovery` topic (keep raw.tracks for plays only)** — *Rejected*
Same topology problem one layer earlier: normalizer would still need to fan out to two output topics, or downstream consumers would need two subscriptions. The normalizer and enricher processing is source-agnostic, so splitting at ingestion creates complexity without benefit.

**Check `source` field directly in history-tracker** — *Rejected*
`source` is an open string ("lastfm", "spotify", and potentially others in future). Having history-tracker hard-code `source != "lastfm"` embeds a closed list assumption and leaks routing logic into a service that should not care about provenance — only about intent.

**`played` boolean field** — *Accepted*

## Consequences

✅ Zero changes to enricher, novelty-detector, and scorer: they consume the same single topic with the same subscription, unmodified.
✅ Backward compatible: legacy messages without a `played` field are treated as `played=True` in history-tracker, so existing Last.fm data is unaffected.
✅ Explicit intent in the schema: `played=False` is self-documenting; the field name captures the business meaning, not the implementation detail of which service produced it.
❌ Silent failure risk: a new consumer that processes `tracks.enriched` without checking `played` will silently corrupt play counts or listening history — the schema does not enforce the invariant.
❌ Schema coupling: all consumers must understand the `played` field semantics even if they don't act on it; the convention must be documented and kept consistent across services.

## When to reconsider

If a third track source is introduced that requires different routing for more than two consumer types (e.g., some consumers need only played, some only discovery, some both, some a third category), the single boolean is no longer expressive enough and per-intent topics become the cleaner model.

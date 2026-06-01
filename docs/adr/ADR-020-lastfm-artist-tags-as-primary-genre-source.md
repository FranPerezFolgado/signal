# ADR-020: Last.fm artist.getTopTags as primary genre source

- **Status**: Accepted
- **Date**: 2026-06-01

## Context

The `enricher` service attaches genre tags to every track before it reaches the scorer. Until November 2024, Spotify's artist endpoint returned a `genres` array; the enricher used this as the primary source and fell back to Last.fm `track.getInfo` only when Spotify had no data. Spotify silently removed `genres` from their API in November 2024 — the endpoint still responds 200 but returns an empty array for every artist, regardless of popularity. This made the Spotify genre path permanently useless and left all 9,000+ artists in the database without genre data, breaking the genre-novelty factor in the scorer.

## Decision

Use Last.fm `artist.getTopTags` as the primary genre source in the `enricher` pipeline, with `track.getTopTags` as a secondary fallback, and `pending_enrichment` as the last resort. A one-shot backfill script was written to retroactively populate genres for existing artists using only the artist name.

## Alternatives considered

**Keep Spotify as primary, accept empty genres** — *Rejected*
Spotify returns an empty `genres` array for 100% of artists since November 2024; keeping it as primary would permanently zero out genre data and break the genre_novelty scoring factor.

**MusicBrainz genre tags** — *Rejected*
MusicBrainz genre matching requires an MBID, which the pipeline does not resolve — we store only Spotify URIs. Mapping artist names to MBIDs would add a new uncontrolled resolution step with its own failure modes.

**Scrape Spotify web app for genre data** — *Rejected*
The Spotify web app still displays genres but scraping it violates Spotify's Terms of Service, creating legal and operational risk that outweighs any data quality benefit.

**Last.fm artist.getTopTags** — *Accepted*

## Consequences

✅ Genres now populate for artists using only the artist name — no Spotify OAuth or MBID resolution required, which also means the backfill works for artists that have no Spotify URI.
✅ Tag count threshold (≥10 relative score) filters user-noise tags, keeping genre data signal-quality rather than crowdsourced noise.
✅ Artist-level tags are more stable than track-level tags — the same artist gets consistent genres across plays, avoiding genre drift from single-track tag variance.
❌ Last.fm genre tags are crowd-sourced; niche or newly-popular artists may have sparse or inaccurate tags until the community catches up.
❌ Tag count thresholds are heuristics — the `_MIN_TAG_COUNT = 10` constant was chosen empirically and may need tuning as the corpus grows.
❌ Adds a Last.fm API call to every enrichment cycle (artist-level), increasing per-message latency and Last.fm rate-limit exposure.

## When to reconsider

If Spotify re-adds a genres field to their API (detectable by monitoring the `genres` array in artist responses going non-empty), revert to Spotify as primary to reduce Last.fm API dependency. Also reconsider if Last.fm rate-limit errors appear in enricher logs at a rate above 1% of messages — at that point, a local genre cache keyed by artist name would be needed.

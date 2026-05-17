# ADR-002 — PostgreSQL as the sole database instead of NoSQL

- **Status**: Accepted
- **Date**: 2026-05-17

## Context

Signal needs to persist three types of data:

- **`listening_history`**: play history (append-only, high cardinality, queries by artist and by genre).
- **`artists`**: entities with lifecycle and state (`TRACKED → FOLLOWING → PUBLISHED / BLACKLISTED`), frequent joins with `listening_history` to compute `play_count`, status distribution queries.
- **`artist_recommendations`**: derived table with score, per-factor breakdown, and evidence tracks. Related to `artists`.

The data is structurally relational: recommendations reference artists, history is grouped by artist, and the `scorer` needs joins across all three tables to compute the user's audio profile.

## Decision

PostgreSQL 16 as the sole database for the MVP.

## Rationale

**MongoDB rejected because**:
- The data is relational. MongoDB has no efficient native joins; modelling relationships requires denormalisation or application-side queries that replace the join.
- We lose transactional consistency (important for `listening_history` upserts and artist state updates).
- The usual argument for MongoDB is schema flexibility, but PostgreSQL with `JSONB` covers variable fields without giving up query capability.

**DynamoDB (or any cloud-managed DB) rejected because**:
- No native joins or flexible aggregations.
- Tied to a cloud provider. The MVP runs entirely locally in Docker.
- MVP volume (thousands of artists, tens of thousands of plays) does not justify a distributed database.

**Neo4j rejected for the MVP because**:
- Relevant when `artist-tracker` does multi-hop graph expansion in v2 and path queries become the bottleneck.
- In the MVP `artist-tracker` does a single hop from `FOLLOWING` artists: a simple Postgres join is sufficient.
- Adding Neo4j now would be a second persistence technology with no concrete benefit yet.

**PostgreSQL accepted because**:
- Native joins, aggregations, and constraints — exactly what the pipeline needs.
- `JSONB` for variable fields (`external_ids`, `audio_features`, `score_breakdown`) with full indexing and query support (`@>`, `->>`, GIN indexes).
- Native arrays (`TEXT[]` for genres) with GIN index for queries like "does any genre of this track appear in the user's history?"
- A single persistence technology: less operational surface, one connection per service, simple backups.

## Consequences

**Benefits**:
- Native relational joins across `listening_history`, `artists`, and `artist_recommendations`.
- `JSONB` handles the heterogeneity of `audio_features` (not all tracks have them) and `score_breakdown` without sacrificing query capability.
- Arrays with GIN enable `SELECT * FROM listening_history WHERE genres @> ARRAY['footwork']` efficiently.
- Strongly typed schema with constraints: integrity guarantees that a document store does not provide by default.

**Costs**:
- Vertical scaling before horizontal. Acceptable: MVP volume will not require it for months or years.
- Explicit schema migrations as tables evolve (desirable — forces changes to be deliberate).

## When to reconsider

When `artist-tracker` expands the graph to multiple hops and path queries (related artists of related artists, with relevance filters) become expensive in Postgres → evaluate Neo4j as a secondary graph database, keeping Postgres as the source of truth for state and recommendations.

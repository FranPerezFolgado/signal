# ADR-021: Stats Endpoints Co-located in signal-api

- **Status**: Accepted
- **Date**: 2026-06-01

## Context

The stats-collector spec (`specs/015-stats-collector/plan.md`) described a new "v5 sink service": a Kafka consumer that would aggregate pipeline statistics into PostgreSQL and expose them via REST. In practice, all the data the dashboard `/stats` page needs already exists in PostgreSQL tables populated by other services (`artists`, `listening_history`, `artist_recommendations`, `ingester_checkpoints`). No Kafka stream aggregation is required — every stat is a SQL query. The `signal-api` service already holds an active PostgreSQL connection pool, runs FastAPI, and is deployed in the same Docker Compose stack.

## Decision

Stats endpoints (`/v1/stats/*`) are added directly to `signal-api` via a new `StatsRepository` class and `routers/stats.py` router. No new container is created.

## Alternatives considered

**New stats-collector microservice (as specced)** — *Rejected*
Would require a new container, separate health checks, and its own DB connection pool for queries that are already within `signal-api`'s reach. The Kafka consumer component described in the spec adds no value here because all source data is already materialised in PostgreSQL — not in stream-only topics.

**Separate read-replica service for stats** — *Rejected*
Read load from the dashboard is negligible (single user, polling every few minutes). Splitting into a read-replica service would be premature optimisation with meaningful operational cost.

**Stats endpoints in signal-api** — *Accepted*

## Consequences

✅ Zero new containers, no new health check, no new Docker Compose profile entry — the dashboard stats page works with `make up` and no extra steps.
✅ `StatsRepository` queries run in the same transaction-safe psycopg connection used by artist and recommendation endpoints; no cross-service synchronisation needed.
✅ All SQL for stats lives in one file (`repository.py`) alongside the rest of the data access layer, making it easy to extend.
❌ `signal-api` now owns two distinct domains (artist management + pipeline observability). If stats queries become expensive or the API is exposed externally, they will share the same connection pool and process.
❌ The spec artefact (`specs/015-stats-collector/`) describes a service that was never built. Future contributors reading it without this ADR will be confused.

## When to reconsider

If stats queries (e.g. novelty ratio, score distribution) start taking >500 ms under normal load, or if `signal-api` is ever exposed beyond the internal Docker network, extract stats into a dedicated read-only service at that point.

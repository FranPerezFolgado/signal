# ADR-012: Artist-tracker as Active Polling Loop

- **Status**: Accepted
- **Date**: 2026-05-25

## Context

The Signal pipeline is entirely reactive: every service is a Kafka consumer that processes messages produced by upstream services. The artist-tracker has no upstream to react to — its job is to proactively discover tracks for artists the user is FOLLOWING by calling Spotify's top-tracks API on a schedule. There is no external event that triggers this; the service must initiate the work itself. A decision was needed on how to schedule and run this periodic work.

## Decision

Artist-tracker runs as a simple Python `while not stop` polling loop with a configurable sleep interval (`ARTIST_TRACKER_INTERVAL_HOURS`, default 6), a SIGTERM handler for graceful shutdown, and no Kafka consumer subscription.

## Alternatives considered

**Kafka-triggered scheduler** — *Rejected*
A separate scheduler service could produce "explore artist" events to a dedicated Kafka topic. This is pure ceremony for a single-user MVP: it splits a simple periodic job across two services, adds a topic to manage, and provides distributed coordination that nobody needs.

**OS cron / Kubernetes CronJob** — *Rejected*
Cron is a natural fit for periodic work, but it couples the deployment model to the scheduler. In Docker Compose (the target environment for this MVP) a CronJob abstraction doesn't exist, and a host cron entry is fragile across environments. It also prevents running the full stack with a single `make up`.

**APScheduler or Celery Beat** — *Rejected*
A framework adds dependencies and concepts (worker pools, broker connections, task serialization) without any benefit for a single periodic task that is inherently sequential and single-instance.

**Simple polling loop** — *Accepted*

## Consequences

✅ Self-contained: no upstream Kafka dependency; the service starts, queries Postgres, calls Spotify, and sleeps — entirely under its own control.
✅ Simple to reason about: no consumer group rebalancing, no offset management, no DLQ for this path.
✅ Graceful shutdown: SIGTERM sets a stop flag that the interruptible sleep checks every second, so the service exits cleanly between artist iterations.
❌ Not reactive: a newly FOLLOWED artist is not discovered until the next cycle — up to `ARTIST_TRACKER_INTERVAL_HOURS` hours later.
❌ No backpressure: if the FOLLOWING list grows large and Spotify is slow, a cycle can extend well beyond the nominal interval without any alerting.
❌ Couples through PostgreSQL: the service reads artist state directly from the DB rather than receiving it via Kafka, creating an implicit dependency on the DB schema shared with other services.

## When to reconsider

If the FOLLOWING artist list grows beyond ~500 artists and the cycle duration consistently exceeds the configured interval (observable via `cycle_complete` log timing), or if near-real-time discovery after following an artist becomes a product requirement. At that point, shard by artist initial, parallelize with a thread pool, or migrate to a Kafka-triggered fan-out pattern.

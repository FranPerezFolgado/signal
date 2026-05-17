# ADR-001 — Kafka as event bus instead of simple queues or synchronous HTTP

- **Status**: Accepted
- **Date**: 2026-05-17

## Context

The Signal pipeline connects 7 services that process music plays at very different ingestion rates: `lastfm-ingester` polls every N minutes, `artist-tracker` expands the graph every N hours, and `normalizer`/`history-tracker`/`novelty-detector` process continuously. We need a communication channel between them.

Three realistic alternatives:

1. **Synchronous HTTP** — each service calls the next one directly.
2. **Simple queue** (RabbitMQ, SQS) — messages in a queue consumed by a single consumer.
3. **Kafka** — distributed event log where multiple consumers can read the same stream independently.

## Decision

Kafka as the central event bus.

## Rationale

**Synchronous HTTP rejected because**:
- Temporal coupling: if `history-tracker` goes down, `normalizer` also fails even though the data arrived.
- No buffer between producers and consumers running at different rates.
- No replay capability: if `scorer` changes its logic, there is no way to reprocess history without re-ingesting from Last.fm.

**RabbitMQ (or any work queue) rejected because**:
- Designed for the "one message, one consumer" pattern. A message in a RabbitMQ queue disappears once a consumer processes it.
- `tracks.normalized` needs to be read by **two consumers simultaneously**: `history-tracker` (to persist in Postgres) and `novelty-detector` (to detect new artists). With RabbitMQ, we either duplicate the message in two queues (coupling, potential desync) or a single consumer distributes it internally (losing decoupling).
- Kafka's consumer group model solves this naturally: each service maintains its own offset and advances at its own pace.

**Kafka accepted because**:
- Independent consumer groups per service: each one maintains its own offset and can run faster or slower without affecting others.
- Native replay: if we recalibrate the `scorer` weights (W1, W2, W3), we can reprocess `tracks.novel` from the beginning without touching Last.fm or Spotify.
- Natural buffer between producers running at different rates and continuous consumers.

## Consequences

**Benefits**:
- Multiple consumers of the same topic with no coupling or message duplication.
- Stream replay to reprocess without re-ingesting from external sources.
- Temporal decoupling: a consumer can go down and recover by reading from its last offset.

**Costs**:
- More operationally heavy than a simple queue (controller, partitions, offsets, consumer group management).
- Oversized for the actual MVP volume (tens of plays per day, not millions). We accept this cost deliberately for the replay and multi-consumer capabilities.

## When to reconsider

If after 6 months of real usage replay has never been used and every topic always has a single consumer, it is worth evaluating simplifying to RabbitMQ or even HTTP + retry.

# ADR-005: Dead-letter queue pattern for unprocessable Kafka messages

- **Status**: Accepted
- **Date**: 2026-05-23

## Context

The normalizer handles bad messages with a skip-and-warn approach: log a warning, commit the offset, and continue. This works for malformed JSON (already handled inside `KafkaJsonConsumer`) and structurally invalid plays, because those failures are deterministic — retrying would never succeed. history-tracker introduces two new failure categories that require more than a silent skip: `NULL_SIGNAL_ID` (a contract violation from the normalizer) and `DB_FAILURE` / `KAFKA_EMIT_FAILURE` (infrastructure failures where the original payload needs to be preserved for diagnosis and potential replay). Simply dropping these messages would make pipeline errors invisible and unrecoverable without re-ingesting from Last.fm.

## Decision

Unprocessable messages are routed to a per-service dead-letter topic (`<service>.dlq`) with a structured envelope containing `error_reason`, `error_detail`, `original_payload`, and `failed_at`. The Kafka offset is committed after the DLQ emit so the message is permanently removed from the normal processing flow.

## Alternatives considered

**Skip-and-warn (normalizer pattern)** — *Rejected for infrastructure failures*
Acceptable for deterministically invalid messages (bad JSON, wrong schema) but loses the original payload on `DB_FAILURE` or `KAFKA_EMIT_FAILURE`, making root-cause analysis and replay impossible. Kept for structurally invalid messages in history-tracker (`_is_valid()` guard skips without DLQ).

**Retry queue with backoff** — *Rejected*
Transient DB or Kafka failures that survive a few retries likely indicate a sustained outage; retrying indefinitely would stall the consumer and block all downstream processing. The MVP runs a single consumer instance with no horizontal scaling, so a stalled consumer means a stalled pipeline. DLQ + manual replay is the safer escape hatch at this scale.

**Commit offset without DLQ (silent drop)** — *Rejected*
Permanently loses data. Incompatible with the artist discovery goal where every play event contributes to novelty scoring.

**Dead-letter queue** — *Accepted*

## Consequences

✅ Unprocessable messages are preserved with full context (`original_payload`, `failed_at`, `error_reason`) — enables manual inspection via kafka-ui and targeted replay once the root cause is fixed  
✅ Consumer never stalls: every code path commits the offset, so a sustained failure on one message does not block processing of subsequent messages  
✅ `error_reason` enum (`NULL_SIGNAL_ID`, `DB_FAILURE`, `KAFKA_EMIT_FAILURE`, `MALFORMED_JSON`) makes failure categories monitorable and alertable by type  
❌ DLQ messages require manual review and replay — there is no automated replay mechanism in the MVP; messages that go to DLQ are effectively dead until an operator acts  
❌ DLQ emit failure is silently swallowed (logged, not re-raised) to avoid infinite loops — if the Kafka broker is down, both the original message and the DLQ record are lost  
❌ Adds a second `KafkaJsonProducer` instance per service (one for output, one for DLQ) to prevent a flush timeout on the output path from accidentally delivering rolled-back messages via a shared producer queue

## When to reconsider

If the volume of DLQ messages consistently exceeds ~1% of total throughput, the silent-swallow approach for DLQ emit failures becomes a real data-loss risk at scale — at that point, implement an automated replay worker and a circuit breaker that pauses the consumer when the DLQ topic itself is unreachable.

# ADR-015: E2E Tests Verify Consumer Group Membership Before Injecting Events

- **Status**: Accepted
- **Date**: 2026-05-26

## Context

The Signal e2e smoke test injects a synthetic `tracks.enriched` Kafka message and then polls PostgreSQL waiting for a recommendation row to appear. During development, the test was found to reliably time out even when all three pipeline containers (`signal-history-tracker`, `signal-novelty-detector`, `signal-scorer`) were running.

Root cause: Kafka has a session timeout (`session.timeout.ms`, default 45 s). If a consumer process crashes and restarts without properly rejoining, the consumer group can enter a "zombie" state — the container is `running` per Docker, the service logs show no errors, but the group has no active members (CONSUMER-ID = `-` in `kafka-consumer-groups --describe`). Messages accumulate as unconsumed LAG. The test's 60-second poll loop never sees a recommendation because no service is actually processing.

A `docker inspect` health check on container state (`running` vs `exited`) does not detect this condition.

## Decision

Before the e2e fixture produces any test message, `services_healthy()` is called. It uses Kafka's `AdminClient.describe_consumer_groups()` to query the three pipeline consumer groups (`history-tracker-enriched-group`, `novelty-detector`, `scorer`). If any group has zero members, the test is skipped with an actionable message rather than allowed to run and time out.

```python
def services_healthy() -> bool:
    admin = AdminClient({"bootstrap.servers": KAFKA, "socket.timeout.ms": 3000})
    futures = admin.describe_consumer_groups(_PIPELINE_GROUPS)
    for group_id in _PIPELINE_GROUPS:
        group = futures[group_id].result(timeout=5)
        if not group.members:
            return False
    return True
```

In CI, the workflow waits for containers to reach `running` state and then sleeps 5 seconds to allow consumer group registration before the test suite starts.

## Alternatives considered

**Docker health check on container state** — *Rejected*
`docker inspect --format "{{.State.Status}}"` only distinguishes `running` from `exited`. A zombie consumer is `running`. This was the original check; it failed silently because the container was alive but the group had no members.

**`docker compose ps | grep healthy`** — *Rejected*
Only applicable if containers define a `HEALTHCHECK` instruction. The pipeline service containers do not; adding one would require each service to expose a health endpoint or bundle `kafka-consumer-groups` tooling into the image.

**Retry with exponential backoff inside the test** — *Rejected*
Retrying the assertion loop does not fix the underlying problem. If the consumer group has no members, no amount of retrying will produce a recommendation. It just turns a fast skip into a slow timeout.

**`pytest.mark.skipif(not stack_available(), ...)`** — *Rejected as sole guard*
`stack_available()` only checks that Kafka and PostgreSQL ports accept connections. A running Kafka cluster with zombie consumers passes this check. It is kept as a prerequisite for infrastructure availability but is insufficient to detect service health.

## Consequences

✅ Tests skip immediately with a clear message instead of hanging for 60–90 seconds on zombie consumer state.
✅ The check is cheap: `describe_consumer_groups` completes in under 100 ms on a healthy cluster.
✅ The skip message includes the exact `docker restart` command needed to recover.
❌ The check requires `confluent-kafka` in the root dev dependency group (not just the service packages), since e2e tests run from the workspace root.
❌ If a consumer group is temporarily rebalancing (e.g., immediately after restart), `members` may briefly be empty, causing a false skip. The 5-second sleep in CI partially mitigates this; local developers may need to wait a few seconds before re-running.

## When to reconsider

If pipeline services are given proper `HEALTHCHECK` instructions (e.g., via a `/health` HTTP endpoint that verifies consumer group membership internally), the `services_healthy()` pre-check can be simplified or removed in favour of `docker compose --wait`.

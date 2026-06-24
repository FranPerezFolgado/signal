# ADR-023: Prometheus + Grafana Observability Stack as Optional Docker Compose Profile

- **Status**: Accepted
- **Date**: 2026-06-24

## Context

Signal runs as a multi-service event-driven pipeline. With 7 services each consuming and producing Kafka topics, there is no single place to observe end-to-end throughput, consumer lag, or error rates without reading logs from multiple containers. As the pipeline grows (artist-tracker adding discovered artists, scorer re-scoring), operators need to identify which service is falling behind or failing without tailing logs. All services are local Docker Compose deployments with no cloud infrastructure, so SaaS monitoring (Datadog, New Relic) would require an agent and network egress that doesn't fit the local-first philosophy.

## Decision

Add Prometheus, Grafana, and kafka-exporter as a Docker Compose `tools` profile — opt-in, not started by default alongside the pipeline services. Each service exposes a `/metrics` HTTP endpoint on `METRICS_PORT` (default 9100). Grafana is provisioned via file-based configuration with a pre-built "Signal Pipeline" dashboard covering throughput, consumer lag, and error rates.

## Alternatives considered

**Always-on in the `services` profile** — *Rejected*
Prometheus and Grafana are resource-heavy relative to the pipeline services and unnecessary for development or CI. Making them always-on would slow `make up` and add noise for contributors who only want to run the pipeline.

**Log-based observability only** — *Rejected*
Structured logs (already in place via `signal_common.logger`) answer per-event questions but are not suited for aggregate rate queries — e.g. "events/min over the last hour for the enricher." Consumer lag in particular requires querying broker offsets, not logs.

**SaaS monitoring (Datadog, Grafana Cloud)** — *Rejected*
Signal has no cloud infrastructure and `.env` secrets are not committed. Adding an agent with an API key would break the local-first, secrets-free development model and introduce a paid dependency.

**Prometheus + Grafana as optional `tools` profile** — *Accepted*

## Consequences

✅ Throughput, consumer lag, and error rates are visible in a single Grafana dashboard without reading logs.
✅ Grafana provisioning is file-based (datasource + dashboard JSON), so the dashboard is reproducible and version-controlled — no manual UI setup required.
✅ The `tools` profile is fully opt-in; `make up` and CI are unaffected.
✅ kafka-exporter exposes `kafka_consumergroup_lag_sum` per group/topic, making it trivial to detect a stalled consumer group.
❌ Prometheus scrape configs must be kept in sync with service additions manually — there is no service-discovery; a new service requires a new `scrape_config` entry in `infra/prometheus/prometheus.yml`.
❌ Metrics are ephemeral: Prometheus uses a local volume with no long-term storage config, so history is lost on `obs-down -v`. This is acceptable for local development but would need a retention policy or remote write if the stack were ever deployed persistently.

## When to reconsider

If the pipeline is deployed to a persistent environment (VM, k8s) and operators need metrics retention beyond local sessions, configure Prometheus remote write to a time-series backend (e.g. Thanos, Mimir) or replace with a managed solution. Also revisit if service count exceeds ~15 — at that point static scrape configs become a maintenance burden and a service-discovery mechanism (Docker labels, Consul) should be adopted.

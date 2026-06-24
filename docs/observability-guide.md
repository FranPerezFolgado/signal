# Signal Observability Guide

All pipeline services expose Prometheus metrics on `/metrics`. An optional Docker Compose `tools` profile brings up Prometheus, Grafana, and a Kafka consumer-lag exporter for local monitoring.

## Starting the observability stack

```bash
make obs-up
```

This starts three containers alongside the pipeline:
- **Prometheus** at `http://localhost:9090` — scrapes all services every 15 s
- **Grafana** at `http://localhost:3000` — pre-provisioned dashboard (login: `admin` / `admin`)
- **kafka-exporter** — exposes consumer group lag as `kafka_consumergroup_lag_sum`

The stack is independent of `make up` / `make services-up`. Stop it with:

```bash
make obs-down     # stop containers (keep volumes)
make obs-logs     # tail Prometheus + Grafana logs
```

## Signal Pipeline dashboard

Grafana loads the **Signal Pipeline** dashboard automatically. It has three sections:

### Throughput

| Panel | Query | What to look for |
|-------|-------|-----------------|
| Events consumed / min | `rate(signal_events_consumed_total[2m]) * 60` | Each service line. Flat line means the service has stopped consuming. |
| Events produced / min | `rate(signal_events_produced_total[2m]) * 60` | Should track consumed for most services. Scorer produces no events (writes to DB). |

### Consumer Lag

| Panel | Query | What to look for |
|-------|-------|-----------------|
| Lag by group | `kafka_consumergroup_lag_sum` | Sustained lag > 0 on a group means the consumer is falling behind. |
| Total lag (stat) | `sum(kafka_consumergroup_lag_sum)` | Green = 0, Yellow = >100, Red = >1 000. |

### Errors

| Panel | Query | What to look for |
|-------|-------|-----------------|
| Error rate by service + type | `rate(signal_processing_errors_total[5m])` | Any non-zero rate indicates failures being routed to the DLQ. |
| Error rate by service (summed) | `sum by (service)(rate(...))` | Useful for identifying which service is the source. |

## Available metrics

### Python services (via `signal_common.metrics`)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `signal_events_consumed_total` | Counter | `service`, `topic` | Kafka messages successfully committed |
| `signal_events_produced_total` | Counter | `service`, `topic` | Kafka messages successfully flushed |
| `signal_processing_errors_total` | Counter | `service`, `error_type` | Errors by type |

`error_type` values: `kafka_consume`, `kafka_produce`, `db_write`, `external_api`, `deserialization`

### Go novelty-detector (via `prometheus/client_golang`)

Same metric names and labels as the Python services. Exposed on the same `METRICS_PORT` (default `9100`).

### kafka-exporter

| Metric | Description |
|--------|-------------|
| `kafka_consumergroup_lag_sum` | Total lag per consumer group + topic |
| `kafka_consumergroup_members` | Number of active members per group |

## Troubleshooting

**Prometheus shows "No data" for a service**

Check that the service is running and exposing metrics:
```bash
curl http://localhost:9100/metrics | grep signal_events
```
If the service is in the `services` Docker network, Prometheus reaches it by container name. If you're running a service locally (not in Docker), Prometheus won't scrape it — add a `localhost` scrape job to `infra/prometheus/prometheus.yml`.

**Grafana shows "No data" on a panel**

1. Verify Prometheus is scraping: `http://localhost:9090/targets` — all targets should be `UP`.
2. Check the time range: the default view is the last hour. If services just started, extend to "Last 5 minutes".
3. Counters pre-initialise at zero (`init_labels`), so even idle services appear in Prometheus immediately after startup.

**Metrics history is lost after `make obs-down -v`**

Prometheus uses a local Docker volume with no long-term retention config. For persistent history, configure a remote write endpoint (e.g. Thanos, Grafana Cloud) in `infra/prometheus/prometheus.yml`. This is out of scope for local development.

**Adding a new service**

1. Import `signal_common.metrics` in the service's `app.py` and call `start_metrics_server()` + `init_labels()` at startup.
2. Add a scrape job to `infra/prometheus/prometheus.yml`:
   ```yaml
   - job_name: my-new-service
     static_configs:
       - targets: ['signal-my-new-service:9100']
   ```
3. Set `METRICS_PORT: "9100"` in the service's environment block in `infra/docker-compose.yml`.

## Design rationale

See [ADR-023](adr/ADR-023-prometheus-grafana-observability-stack.md) for why Prometheus + Grafana was chosen over SaaS monitoring, why the stack is opt-in rather than always-on, and when to reconsider.

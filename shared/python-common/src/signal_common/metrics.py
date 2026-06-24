from __future__ import annotations

import os
import threading

from prometheus_client import Counter, start_http_server

_events_consumed = Counter(
    "signal_events_consumed_total",
    "Total Kafka events consumed",
    ["service", "topic"],
)

_events_produced = Counter(
    "signal_events_produced_total",
    "Total Kafka events produced",
    ["service", "topic"],
)

_processing_errors = Counter(
    "signal_processing_errors_total",
    "Total processing errors",
    ["service", "error_type"],
)

_VALID_ERROR_TYPES = frozenset(
    {"kafka_consume", "kafka_produce", "db_write", "external_api", "deserialization"}
)

_server_started = False
_lock = threading.Lock()


def start_metrics_server(port: int | None = None) -> None:
    """Start the Prometheus metrics HTTP server in a background thread. Idempotent."""
    global _server_started
    with _lock:
        if _server_started:
            return
        resolved_port = port if port is not None else int(os.getenv("METRICS_PORT", "9100"))
        start_http_server(resolved_port)
        _server_started = True


def inc_consumed(service: str, topic: str) -> None:
    _events_consumed.labels(service=service, topic=topic).inc()


def inc_produced(service: str, topic: str) -> None:
    _events_produced.labels(service=service, topic=topic).inc()


def inc_error(service: str, error_type: str) -> None:
    _processing_errors.labels(service=service, error_type=error_type).inc()


def init_labels(service: str, topics_consumed: list[str], topics_produced: list[str]) -> None:
    """Pre-initialise counters at zero so Prometheus emits them before the first event."""
    for topic in topics_consumed:
        _events_consumed.labels(service=service, topic=topic)
    for topic in topics_produced:
        _events_produced.labels(service=service, topic=topic)
    for error_type in _VALID_ERROR_TYPES:
        _processing_errors.labels(service=service, error_type=error_type)

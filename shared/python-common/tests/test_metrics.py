from unittest.mock import patch

from prometheus_client import REGISTRY

from signal_common import metrics as m


def _get(metric_name: str, **labels: str) -> float:
    """Return current sample value (0.0 if label set not yet initialised)."""
    return REGISTRY.get_sample_value(metric_name + "_total", labels) or 0.0


class TestCounterIncrements:
    def test_inc_consumed_increments_by_one(self):
        before = _get("signal_events_consumed", service="t-consumed", topic="raw.plays")
        m.inc_consumed("t-consumed", "raw.plays")
        assert _get("signal_events_consumed", service="t-consumed", topic="raw.plays") - before == 1.0

    def test_inc_produced_increments_by_one(self):
        before = _get("signal_events_produced", service="t-produced", topic="tracks.out")
        m.inc_produced("t-produced", "tracks.out")
        assert _get("signal_events_produced", service="t-produced", topic="tracks.out") - before == 1.0

    def test_inc_error_increments_by_one(self):
        before = _get("signal_processing_errors", service="t-error", error_type="db_write")
        m.inc_error("t-error", "db_write")
        assert _get("signal_processing_errors", service="t-error", error_type="db_write") - before == 1.0

    def test_multiple_increments_accumulate(self):
        before = _get("signal_events_consumed", service="t-accum", topic="raw.plays")
        m.inc_consumed("t-accum", "raw.plays")
        m.inc_consumed("t-accum", "raw.plays")
        m.inc_consumed("t-accum", "raw.plays")
        assert _get("signal_events_consumed", service="t-accum", topic="raw.plays") - before == 3.0


class TestInitLabels:
    def test_pre_initialises_consumed_at_zero(self):
        m.init_labels("t-init", ["t-topic-in"], ["t-topic-out"])
        assert _get("signal_events_consumed", service="t-init", topic="t-topic-in") == 0.0

    def test_pre_initialises_produced_at_zero(self):
        m.init_labels("t-init2", [], ["produced-topic"])
        assert _get("signal_events_produced", service="t-init2", topic="produced-topic") == 0.0

    def test_pre_initialises_all_error_types(self):
        m.init_labels("t-errinit", [], [])
        for error_type in m._VALID_ERROR_TYPES:
            assert _get("signal_processing_errors", service="t-errinit", error_type=error_type) == 0.0


class TestStartMetricsServer:
    def test_does_not_raise_and_calls_start_http_server(self, monkeypatch):
        monkeypatch.setattr(m, "_server_started", False)
        with patch("signal_common.metrics.start_http_server") as mock_srv:
            m.start_metrics_server(port=19100)
        mock_srv.assert_called_once_with(19100)

    def test_idempotent_second_call_skipped(self, monkeypatch):
        monkeypatch.setattr(m, "_server_started", False)
        with patch("signal_common.metrics.start_http_server") as mock_srv:
            m.start_metrics_server(port=19101)
            m.start_metrics_server(port=19101)
        mock_srv.assert_called_once()

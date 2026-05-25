def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_metrics_endpoint_exists(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text or "# HELP" in resp.text


def test_docs_endpoint_exists(client):
    resp = client.get("/docs")
    assert resp.status_code == 200

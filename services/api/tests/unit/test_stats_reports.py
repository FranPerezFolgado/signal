from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

# ─── _validate_dates ──────────────────────────────────────────────────────────

def _validate_dates(from_date, to_date, today=date(2026, 6, 1)):
    """Mirror of reports.py _validate_dates, injectable today for testing."""
    if to_date and to_date > today:
        to_date = today
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date must be before to_date")
    return from_date, to_date


def test_validate_dates_clamps_future_to_date():
    fd, td = _validate_dates(None, date(2099, 12, 31))
    assert td == date(2026, 6, 1)


def test_validate_dates_passes_past_to_date():
    fd, td = _validate_dates(None, date(2025, 1, 1))
    assert td == date(2025, 1, 1)


def test_validate_dates_both_none():
    fd, td = _validate_dates(None, None)
    assert fd is None and td is None


def test_validate_dates_raises_when_from_after_to():
    with pytest.raises(HTTPException) as exc:
        _validate_dates(date(2025, 6, 1), date(2025, 1, 1))
    assert exc.value.status_code == 400


def test_validate_dates_equal_dates_pass():
    fd, td = _validate_dates(date(2025, 1, 1), date(2025, 1, 1))
    assert fd == td == date(2025, 1, 1)


# ─── Stats endpoints ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_stats_repo(mock_conn):
    with patch("signal_api.routers.stats.StatsRepository") as MockRepo:
        instance = MagicMock()
        MockRepo.return_value = instance
        yield instance


def test_blacklist_rate_returns_data(client, mock_stats_repo):
    mock_stats_repo.get_blacklist_rate.return_value = {
        "blacklisted": 10, "total_meaningful": 100, "rate": 0.1
    }
    resp = client.get("/v1/stats/blacklist-rate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["blacklisted"] == 10
    assert body["rate"] == pytest.approx(0.1)


def test_active_genres_returns_list(client, mock_stats_repo):
    mock_stats_repo.get_active_genres.return_value = [
        {"genre": "indie", "artist_count": 5},
    ]
    resp = client.get("/v1/stats/active-genres")
    assert resp.status_code == 200
    assert resp.json()["genres"][0]["genre"] == "indie"


def test_stale_recs_default_threshold(client, mock_stats_repo):
    mock_stats_repo.get_stale_recs.return_value = {
        "count": 3, "threshold_days": 14, "oldest_status_changed_at": None
    }
    resp = client.get("/v1/stats/stale")
    assert resp.status_code == 200
    mock_stats_repo.get_stale_recs.assert_called_once_with(14)


def test_stale_recs_custom_threshold(client, mock_stats_repo):
    mock_stats_repo.get_stale_recs.return_value = {
        "count": 0, "threshold_days": 30, "oldest_status_changed_at": None
    }
    resp = client.get("/v1/stats/stale?threshold_days=30")
    assert resp.status_code == 200
    mock_stats_repo.get_stale_recs.assert_called_once_with(30)


def test_stale_recs_rejects_zero_threshold(client, mock_stats_repo):
    resp = client.get("/v1/stats/stale?threshold_days=0")
    assert resp.status_code == 422


def test_stale_recs_rejects_negative_threshold(client, mock_stats_repo):
    resp = client.get("/v1/stats/stale?threshold_days=-1")
    assert resp.status_code == 422


def test_stale_recs_rejects_oversized_threshold(client, mock_stats_repo):
    resp = client.get("/v1/stats/stale?threshold_days=9999")
    assert resp.status_code == 422


def test_score_freshness_returns_buckets(client, mock_stats_repo):
    mock_stats_repo.get_score_freshness.return_value = [
        {"label": "<1D", "max_age_days": 1, "count": 20},
        {"label": "1-7D", "max_age_days": 7, "count": 15},
    ]
    resp = client.get("/v1/stats/score-freshness")
    assert resp.status_code == 200
    assert len(resp.json()["buckets"]) == 2


# ─── Reports endpoints ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_reports_repo(mock_conn):
    with patch("signal_api.routers.reports.ReportsRepository") as MockRepo:
        instance = MagicMock()
        MockRepo.return_value = instance
        yield instance


def test_weekly_discovery_rate_returns_weeks(client, mock_reports_repo):
    mock_reports_repo.get_weekly_discovery_rate.return_value = [
        {"week_start": "2026-05-25", "count": 3},
    ]
    resp = client.get("/v1/reports/weekly-discovery-rate")
    assert resp.status_code == 200
    assert resp.json()["weeks"][0]["count"] == 3


def test_discovery_highlight_available(client, mock_reports_repo):
    mock_reports_repo.get_discovery_highlight.return_value = {
        "name": "Cool Band",
        "plays": 12,
        "first_seen_at": "2026-05-01T00:00:00",
        "genres": ["indie"],
        "spotify_id": "abc123",
    }
    resp = client.get("/v1/reports/discovery-highlight?from_date=2026-05-01&to_date=2026-05-31")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["name"] == "Cool Band"


def test_discovery_highlight_no_data(client, mock_reports_repo):
    mock_reports_repo.get_discovery_highlight.return_value = None
    resp = client.get("/v1/reports/discovery-highlight?from_date=2026-05-01&to_date=2026-05-31")
    assert resp.status_code == 200
    assert resp.json()["available"] is False


def test_genre_drift_returns_current_and_previous(client, mock_reports_repo):
    mock_reports_repo.get_genre_drift.return_value = {
        "current": [{"genre": "indie", "plays": 50, "weight": 1.0}],
        "previous": [{"genre": "metal", "plays": 30, "weight": 1.0}],
        "period_days": 30,
    }
    resp = client.get("/v1/reports/genre-drift?from_date=2026-05-01&to_date=2026-05-31")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current"][0]["genre"] == "indie"
    assert body["previous"][0]["genre"] == "metal"


def test_calendar_returns_days(client, mock_reports_repo):
    mock_reports_repo.get_calendar.return_value = {
        "days": [{"date": "2026-05-01", "plays": 5}],
        "from_date": "2026-05-01",
        "to_date": "2026-05-31",
    }
    resp = client.get("/v1/reports/calendar")
    assert resp.status_code == 200
    assert resp.json()["days"][0]["plays"] == 5


def test_loyal_artists_returns_ranked_list(client, mock_reports_repo):
    mock_reports_repo.get_loyal_artists.return_value = [
        {"rank": 1, "name": "Old Friend", "plays": 200, "weight": 1.0},
    ]
    resp = client.get("/v1/reports/loyal-artists")
    assert resp.status_code == 200
    assert resp.json()["artists"][0]["name"] == "Old Friend"


def test_source_effectiveness_returns_sources(client, mock_reports_repo):
    mock_reports_repo.get_source_effectiveness.return_value = [
        {"source": "lastfm", "total": 50, "published": 5, "publish_rate": 0.1},
    ]
    resp = client.get("/v1/reports/source-effectiveness")
    assert resp.status_code == 200
    assert resp.json()["sources"][0]["source"] == "lastfm"


def test_reports_rejects_from_after_to(client, mock_reports_repo):
    resp = client.get("/v1/reports/calendar?from_date=2026-06-01&to_date=2026-01-01")
    assert resp.status_code == 400

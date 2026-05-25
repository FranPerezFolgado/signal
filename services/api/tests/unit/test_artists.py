from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

_NOW = datetime(2026, 5, 25, 12, 0, 0, tzinfo=timezone.utc)
_ARTIST_ID = uuid4()


def _make_detail_row(**kwargs):
    return {
        "id": _ARTIST_ID,
        "name": "Test Artist",
        "status": "FOLLOWING",
        "high_priority": False,
        "scrobble_count": 10,
        "play_count": 15,
        "genres": ["indie"],
        "first_seen_at": _NOW,
        "last_explored_at": _NOW,
        "score": 0.75,
        "score_breakdown": {"genre_novelty": 0.8, "popularity_norm": 0.7},
        "evidence_tracks": ["sig1"],
        "rec_updated_at": _NOW,
        **kwargs,
    }


@pytest.fixture(autouse=True)
def mock_repo(mock_conn):
    with patch("signal_api.routers.artists.ArtistRepository") as MockRepo:
        instance = MagicMock()
        MockRepo.return_value = instance
        yield instance


# ── GET /v1/artists/{id} ──────────────────────────────────────────────────────

def test_get_artist_with_recommendation(client, mock_repo):
    mock_repo.get_artist_by_id.return_value = _make_detail_row()
    resp = client.get(f"/v1/artists/{_ARTIST_ID}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Test Artist"
    assert body["recommendation"]["score"] == 0.75
    assert body["recommendation"]["breakdown"]["genre_novelty"] == 0.8


def test_get_artist_without_recommendation(client, mock_repo):
    row = _make_detail_row(score=None, score_breakdown=None, evidence_tracks=None, rec_updated_at=None)
    mock_repo.get_artist_by_id.return_value = row
    resp = client.get(f"/v1/artists/{_ARTIST_ID}")
    assert resp.status_code == 200
    assert resp.json()["recommendation"] is None


def test_get_artist_not_found(client, mock_repo):
    mock_repo.get_artist_by_id.return_value = None
    resp = client.get(f"/v1/artists/{uuid4()}")
    assert resp.status_code == 404


def test_get_artist_malformed_uuid(client, mock_repo):
    resp = client.get("/v1/artists/not-a-uuid")
    assert resp.status_code == 422


# ── PATCH /v1/artists/{id}/status ────────────────────────────────────────────

def test_patch_status_success(client, mock_repo):
    mock_repo.update_artist_status.return_value = {
        "id": _ARTIST_ID,
        "name": "Test Artist",
        "status": "BLACKLISTED",
    }
    resp = client.patch(f"/v1/artists/{_ARTIST_ID}/status", json={"status": "BLACKLISTED"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "BLACKLISTED"


def test_patch_status_idempotent(client, mock_repo):
    mock_repo.update_artist_status.return_value = {
        "id": _ARTIST_ID,
        "name": "Test Artist",
        "status": "BLACKLISTED",
    }
    resp = client.patch(f"/v1/artists/{_ARTIST_ID}/status", json={"status": "BLACKLISTED"})
    assert resp.status_code == 200


def test_patch_status_not_found(client, mock_repo):
    mock_repo.update_artist_status.return_value = None
    resp = client.patch(f"/v1/artists/{uuid4()}/status", json={"status": "BLACKLISTED"})
    assert resp.status_code == 404


def test_patch_status_invalid_value(client, mock_repo):
    resp = client.patch(f"/v1/artists/{_ARTIST_ID}/status", json={"status": "NONEXISTENT"})
    assert resp.status_code == 422


def test_patch_status_malformed_uuid(client, mock_repo):
    resp = client.patch("/v1/artists/not-a-uuid/status", json={"status": "BLACKLISTED"})
    assert resp.status_code == 422


def test_patch_status_missing_body_field(client, mock_repo):
    resp = client.patch(f"/v1/artists/{_ARTIST_ID}/status", json={})
    assert resp.status_code == 422

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

_NOW = datetime(2026, 5, 25, 12, 0, 0, tzinfo=UTC)


def _make_row(name="Artist", score=0.5, status="FOLLOWING", **kwargs):
    return {
        "id": uuid4(),
        "name": name,
        "status": status,
        "high_priority": False,
        "genres": ["indie"],
        "score": score,
        "score_breakdown": {"genre_novelty": 0.6, "popularity_norm": 0.4},
        "evidence_tracks": ["abc123"],
        "updated_at": _NOW,
        **kwargs,
    }


@pytest.fixture(autouse=True)
def mock_repo(mock_conn):
    with patch("signal_api.routers.recommendations.ArtistRepository") as MockRepo:
        instance = MagicMock()
        MockRepo.return_value = instance
        yield instance


def test_empty_list(client, mock_repo):
    mock_repo.list_recommendations.return_value = ([], 0)
    resp = client.get("/v1/recommendations")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["pages"] == 0


def test_results_ordered_by_score(client, mock_repo):
    rows = [_make_row("B", score=0.9), _make_row("A", score=0.7)]
    mock_repo.list_recommendations.return_value = (rows, 2)
    resp = client.get("/v1/recommendations")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["score"] == 0.9
    assert items[1]["score"] == 0.7


def test_ties_broken_by_name(client, mock_repo):
    rows = [_make_row("Zebra", score=0.8), _make_row("Alpha", score=0.8)]
    mock_repo.list_recommendations.return_value = (rows, 2)
    resp = client.get("/v1/recommendations")
    items = resp.json()["items"]
    assert items[0]["name"] == "Zebra"
    assert items[1]["name"] == "Alpha"


def test_pagination_metadata(client, mock_repo):
    rows = [_make_row(f"A{i}", score=1.0 - i * 0.1) for i in range(3)]
    mock_repo.list_recommendations.return_value = (rows, 50)
    resp = client.get("/v1/recommendations?page=2&page_size=3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 2
    assert body["page_size"] == 3
    assert body["total"] == 50
    assert body["pages"] == 17
    mock_repo.list_recommendations.assert_called_once_with(
        page=2, page_size=3, include_following=False
    )


def test_invalid_page_returns_422(client, mock_repo):
    resp = client.get("/v1/recommendations?page=0")
    assert resp.status_code == 422


def test_page_size_too_large_returns_422(client, mock_repo):
    resp = client.get("/v1/recommendations?page_size=101")
    assert resp.status_code == 422


def test_score_breakdown_present(client, mock_repo):
    rows = [_make_row("A", score=0.7)]
    mock_repo.list_recommendations.return_value = (rows, 1)
    item = client.get("/v1/recommendations").json()["items"][0]
    assert item["breakdown"]["genre_novelty"] == 0.6
    assert item["breakdown"]["popularity_norm"] == 0.4


def test_null_score_breakdown(client, mock_repo):
    row = _make_row("A", score=0.7)
    row["score_breakdown"] = None
    mock_repo.list_recommendations.return_value = ([row], 1)
    item = client.get("/v1/recommendations").json()["items"][0]
    assert item["breakdown"] is None


def test_following_excluded_by_default(client, mock_repo):
    mock_repo.list_recommendations.return_value = ([], 0)
    client.get("/v1/recommendations")
    mock_repo.list_recommendations.assert_called_once_with(
        page=1, page_size=20, include_following=False
    )


def test_include_following_param_passed_through(client, mock_repo):
    mock_repo.list_recommendations.return_value = ([], 0)
    client.get("/v1/recommendations?include_following=true")
    mock_repo.list_recommendations.assert_called_once_with(
        page=1, page_size=20, include_following=True
    )


def test_score_breakdown_as_json_string(client, mock_repo):
    row = _make_row("A", score=0.7)
    row["score_breakdown"] = '{"genre_novelty": 0.3, "popularity_norm": 0.7}'
    mock_repo.list_recommendations.return_value = ([row], 1)
    item = client.get("/v1/recommendations").json()["items"][0]
    assert item["breakdown"]["genre_novelty"] == 0.3
    assert item["breakdown"]["popularity_norm"] == 0.7


def test_evidence_tracks_as_json_string(client, mock_repo):
    row = _make_row("A", score=0.7)
    row["evidence_tracks"] = '["sig1", "sig2"]'
    mock_repo.list_recommendations.return_value = ([row], 1)
    item = client.get("/v1/recommendations").json()["items"][0]
    assert item["evidence_tracks"] == ["sig1", "sig2"]

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


def _make_row(name="Artist", status="TRACKED", high_priority=False):
    return {
        "id": uuid4(),
        "name": name,
        "status": status,
        "high_priority": high_priority,
        "scrobble_count": 5,
        "genres": ["rock"],
    }


@pytest.fixture(autouse=True)
def mock_repo(mock_conn):
    with patch("signal_api.routers.artists.ArtistRepository") as MockRepo:
        instance = MagicMock()
        MockRepo.return_value = instance
        yield instance


def test_list_all_artists(client, mock_repo):
    rows = [_make_row("A"), _make_row("B")]
    mock_repo.list_artists.return_value = (rows, 2)
    resp = client.get("/v1/artists")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2
    mock_repo.list_artists.assert_called_once_with(
        status=None, high_priority=None, page=1, page_size=20
    )


def test_filter_by_status(client, mock_repo):
    mock_repo.list_artists.return_value = ([_make_row(status="FOLLOWING")], 1)
    resp = client.get("/v1/artists?status=FOLLOWING")
    assert resp.status_code == 200
    mock_repo.list_artists.assert_called_once_with(
        status="FOLLOWING", high_priority=None, page=1, page_size=20
    )


def test_filter_by_high_priority(client, mock_repo):
    mock_repo.list_artists.return_value = ([_make_row(high_priority=True)], 1)
    resp = client.get("/v1/artists?high_priority=true")
    assert resp.status_code == 200
    mock_repo.list_artists.assert_called_once_with(
        status=None, high_priority=True, page=1, page_size=20
    )


def test_combined_filters(client, mock_repo):
    mock_repo.list_artists.return_value = ([], 0)
    resp = client.get("/v1/artists?status=FOLLOWING&high_priority=true")
    assert resp.status_code == 200
    mock_repo.list_artists.assert_called_once_with(
        status="FOLLOWING", high_priority=True, page=1, page_size=20
    )


def test_empty_result(client, mock_repo):
    mock_repo.list_artists.return_value = ([], 0)
    resp = client.get("/v1/artists?status=BLACKLISTED")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["pages"] == 0


def test_invalid_status_value(client, mock_repo):
    resp = client.get("/v1/artists?status=UNKNOWN")
    assert resp.status_code == 422


def test_page_size_zero_returns_422(client, mock_repo):
    resp = client.get("/v1/artists?page_size=0")
    assert resp.status_code == 422


def test_negative_page_returns_422(client, mock_repo):
    resp = client.get("/v1/artists?page=-1")
    assert resp.status_code == 422


def test_page_size_max_boundary(client, mock_repo):
    mock_repo.list_artists.return_value = ([], 0)
    resp = client.get("/v1/artists?page_size=100")
    assert resp.status_code == 200
    mock_repo.list_artists.assert_called_once_with(
        status=None, high_priority=None, page=1, page_size=100
    )

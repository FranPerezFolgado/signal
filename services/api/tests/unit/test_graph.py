from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

_ARTIST_ID = str(uuid4())
_ORIGIN_ID = str(uuid4())

_ARTIST_NODE = {
    "key": f"artist:{_ARTIST_ID}",
    "attributes": {
        "nodeType": "artist",
        "label": "Test Artist",
        "status": "FOLLOWING",
        "score": 0.75,
        "scrobble_count": 42,
        "genres": ["indie pop"],
        "spotify_id": None,
    },
}
_GENRE_NODE = {
    "key": "genre:indie pop",
    "attributes": {
        "nodeType": "genre",
        "label": "indie pop",
        "artist_count": 3,
    },
}
_EDGE = {
    "key": f"e:artist:{_ARTIST_ID}:genre:indie pop",
    "source": f"artist:{_ARTIST_ID}",
    "target": "genre:indie pop",
    "attributes": {"edgeType": "tagged"},
}

_GRAPH_RESPONSE = {"nodes": [_ARTIST_NODE, _GENRE_NODE], "edges": [_EDGE]}


@pytest.fixture(autouse=True)
def mock_graph_repo(mock_conn):
    with patch("signal_api.routers.graph.GraphRepository") as MockRepo:
        instance = MagicMock()
        MockRepo.return_value = instance
        instance.get_graph_data.return_value = _GRAPH_RESPONSE
        yield instance


def test_graph_data_returns_200(client):
    resp = client.get("/v1/graph/data")
    assert resp.status_code == 200


def test_graph_data_has_nodes_and_edges(client):
    resp = client.get("/v1/graph/data")
    body = resp.json()
    assert "nodes" in body
    assert "edges" in body
    assert isinstance(body["nodes"], list)
    assert isinstance(body["edges"], list)


def test_graph_data_has_artist_node(client):
    resp = client.get("/v1/graph/data")
    nodes = resp.json()["nodes"]
    artist_nodes = [n for n in nodes if n["attributes"]["nodeType"] == "artist"]
    assert len(artist_nodes) >= 1
    assert artist_nodes[0]["attributes"]["label"] == "Test Artist"


def test_graph_data_has_genre_node(client):
    resp = client.get("/v1/graph/data")
    nodes = resp.json()["nodes"]
    genre_nodes = [n for n in nodes if n["attributes"]["nodeType"] == "genre"]
    assert len(genre_nodes) >= 1


def test_graph_data_passes_filters_to_repo(client, mock_graph_repo):
    client.get("/v1/graph/data?status=FOLLOWING&min_score=0.5&min_genre_artists=3&limit=100")
    mock_graph_repo.get_graph_data.assert_called_once_with(
        "FOLLOWING", None, 0.5, 3, 100
    )


def test_graph_data_defaults(client, mock_graph_repo):
    client.get("/v1/graph/data")
    mock_graph_repo.get_graph_data.assert_called_once_with(None, None, None, 2, 500)

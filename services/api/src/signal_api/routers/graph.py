from __future__ import annotations

from fastapi import APIRouter, Depends

from signal_api.deps import get_db
from signal_api.models import GraphResponse
from signal_api.repository import GraphRepository

router = APIRouter()


@router.get("/graph/data", response_model=GraphResponse, response_model_by_alias=True)
def get_graph_data(
    status: str | None = None,
    genre: str | None = None,
    min_score: float | None = None,
    min_genre_artists: int = 2,
    limit: int = 500,
    conn=Depends(get_db),
) -> GraphResponse:
    repo = GraphRepository(conn)
    return repo.get_graph_data(status, genre, min_score, min_genre_artists, limit)

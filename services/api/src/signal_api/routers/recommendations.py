from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Query

from signal_api.deps import get_db
from signal_api.models import PaginatedResponse, RecommendationListItem
from signal_api.repository import ArtistRepository
from signal_api.utils import build_score_breakdown, calc_pages, parse_jsonb

router = APIRouter()


def _to_recommendation(row: dict) -> RecommendationListItem:
    evidence_raw = parse_jsonb(row.get("evidence_tracks"))
    evidence: list[str] = evidence_raw if isinstance(evidence_raw, list) else []
    spotify_uri: str | None = row.get("spotify_uri")
    spotify_id = spotify_uri.split(":")[-1] if spotify_uri else None
    return RecommendationListItem(
        id=row["id"],
        name=row["name"],
        status=row["status"],
        high_priority=row["high_priority"],
        genres=row["genres"] or [],
        score=row["score"],
        breakdown=build_score_breakdown(row.get("score_breakdown")),
        evidence_tracks=evidence,
        spotify_id=spotify_id,
        updated_at=row["updated_at"],
    )


@router.get("/recommendations", response_model=PaginatedResponse[RecommendationListItem])
def list_recommendations(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    include_following: bool = False,
    conn: psycopg.Connection = Depends(get_db),
):
    repo = ArtistRepository(conn)
    rows, total = repo.list_recommendations(
        page=page, page_size=page_size, include_following=include_following
    )
    return PaginatedResponse(
        items=[_to_recommendation(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=calc_pages(total, page_size),
    )

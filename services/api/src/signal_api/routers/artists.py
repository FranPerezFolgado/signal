from __future__ import annotations

from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from signal_api.deps import get_db
from signal_api.models import (
    ArtistDetail,
    ArtistListItem,
    ArtistRecommendation,
    ArtistStatus,
    PaginatedResponse,
    PatchStatusRequest,
    PatchStatusResponse,
)
from signal_api.repository import ArtistRepository
from signal_api.utils import build_score_breakdown, calc_pages, parse_jsonb

router = APIRouter()


def _to_artist_list_item(row: dict) -> ArtistListItem:
    spotify_uri: str | None = row.get("spotify_uri")
    return ArtistListItem(
        id=row["id"],
        name=row["name"],
        status=row["status"],
        high_priority=row["high_priority"],
        scrobble_count=row["scrobble_count"],
        genres=row["genres"] or [],
        spotify_id=spotify_uri.split(":")[-1] if spotify_uri else None,
        source=row.get("source"),
        origin_artist_id=row.get("origin_artist_id"),
        origin_artist_name=row.get("origin_artist_name"),
    )


def _to_artist_detail(row: dict) -> ArtistDetail:
    recommendation = None
    if row.get("score") is not None:
        evidence_raw = parse_jsonb(row.get("evidence_tracks"))
        evidence: list[str] = evidence_raw if isinstance(evidence_raw, list) else []
        recommendation = ArtistRecommendation(
            score=row["score"],
            breakdown=build_score_breakdown(row.get("score_breakdown")),
            evidence_tracks=evidence,
            updated_at=row["rec_updated_at"],
        )

    return ArtistDetail(
        id=row["id"],
        name=row["name"],
        status=row["status"],
        high_priority=row["high_priority"],
        scrobble_count=row["scrobble_count"],
        genres=row["genres"] or [],
        play_count=row["play_count"],
        first_seen_at=row.get("first_seen_at"),
        last_explored_at=row.get("last_explored_at"),
        recommendation=recommendation,
    )


@router.get("/artists", response_model=PaginatedResponse[ArtistListItem])
def list_artists(
    status: ArtistStatus | None = None,
    high_priority: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    conn: psycopg.Connection = Depends(get_db),
):
    repo = ArtistRepository(conn)
    rows, total = repo.list_artists(
        status=status.value if status else None,
        high_priority=high_priority,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[_to_artist_list_item(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=calc_pages(total, page_size),
    )


@router.get("/artists/{artist_id}", response_model=ArtistDetail)
def get_artist(
    artist_id: UUID,
    conn: psycopg.Connection = Depends(get_db),
):
    repo = ArtistRepository(conn)
    row = repo.get_artist_by_id(artist_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Artist not found")
    return _to_artist_detail(row)


@router.patch("/artists/{artist_id}/status", response_model=PatchStatusResponse)
def update_artist_status(
    artist_id: UUID,
    body: PatchStatusRequest,
    conn: psycopg.Connection = Depends(get_db),
):
    repo = ArtistRepository(conn)
    row = repo.update_artist_status(artist_id, body.status.value)
    if row is None:
        raise HTTPException(status_code=404, detail="Artist not found")
    return PatchStatusResponse(id=row["id"], name=row["name"], status=row["status"])

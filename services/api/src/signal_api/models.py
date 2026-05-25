from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field
from signal_common.models import ArtistStatus  # noqa: F401 — re-exported for API consumers

T = TypeVar("T")


class ScoreBreakdown(BaseModel):
    genre_novelty: float
    popularity_norm: float


class ArtistRecommendation(BaseModel):
    score: float
    breakdown: ScoreBreakdown | None
    evidence_tracks: list[str]
    updated_at: datetime


class ArtistListItem(BaseModel):
    id: UUID
    name: str
    status: ArtistStatus
    high_priority: bool
    scrobble_count: int
    genres: list[str]


class ArtistDetail(ArtistListItem):
    play_count: int
    first_seen_at: datetime | None
    last_explored_at: datetime | None
    recommendation: ArtistRecommendation | None


class RecommendationListItem(BaseModel):
    id: UUID
    name: str
    status: ArtistStatus
    high_priority: bool
    genres: list[str]
    score: float
    breakdown: ScoreBreakdown | None
    evidence_tracks: list[str]
    updated_at: datetime


class PatchStatusRequest(BaseModel):
    status: ArtistStatus


class PatchStatusResponse(BaseModel):
    id: UUID
    name: str
    status: ArtistStatus


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class HealthResponse(BaseModel):
    status: str = Field(default="ok")

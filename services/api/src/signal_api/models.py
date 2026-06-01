from __future__ import annotations

from datetime import date, datetime
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
    spotify_id: str | None = None
    source: str | None = None
    origin_artist_id: UUID | None = None
    origin_artist_name: str | None = None


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
    spotify_id: str | None
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


# --- Stats models ---

class ArtistStatusCounts(BaseModel):
    tracked: int
    following: int
    published: int
    blacklisted: int
    total: int


class ServiceCheckpoint(BaseModel):
    service: str
    last_seen_at: datetime
    stale: bool


class ServiceHealthResponse(BaseModel):
    services: list[ServiceCheckpoint]
    stale_threshold_minutes: int


class GenreCount(BaseModel):
    genre: str
    artist_count: int


class GenreStatsResponse(BaseModel):
    genres: list[GenreCount]


class ScoreBucket(BaseModel):
    label: str
    min_score: float
    max_score: float
    count: int


class ScoreDistributionResponse(BaseModel):
    total_scored: int
    min_score: float | None
    max_score: float | None
    mean_score: float | None
    buckets: list[ScoreBucket]


class WeeklyCount(BaseModel):
    week_start: date
    new_artists: int


class WeeklyDiscoveriesResponse(BaseModel):
    weeks: list[WeeklyCount]


class NoveltyPoint(BaseModel):
    day: date
    ratio: float


class NoveltyRatioResponse(BaseModel):
    points: list[NoveltyPoint]


class SourceCount(BaseModel):
    source: str
    count: int


class ArtistSourcesResponse(BaseModel):
    sources: list[SourceCount]


class PlayVelocityPoint(BaseModel):
    day: date
    plays: int


class PlayVelocityResponse(BaseModel):
    points: list[PlayVelocityPoint]


class ScoreBreakdownAverages(BaseModel):
    avg_genre_novelty: float | None
    avg_popularity_norm: float | None
    total: int


class ExplorationCoverageResponse(BaseModel):
    total: int
    explored: int
    coverage_pct: float


class StatusBucket(BaseModel):
    status: str
    total: int
    high_priority: int


class PipelineFunnelResponse(BaseModel):
    statuses: list[StatusBucket]

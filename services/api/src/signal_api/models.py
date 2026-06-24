from __future__ import annotations

from datetime import date, datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from signal_common.models import ArtistStatus  # noqa: F401 — re-exported for API consumers

T = TypeVar("T")


class ScoreBreakdown(BaseModel):
    genre_novelty: float
    popularity_norm: float


class EvidenceTrack(BaseModel):
    text: str
    track_id: str | None = None


class ArtistRecommendation(BaseModel):
    score: float
    breakdown: ScoreBreakdown | None
    evidence_tracks: list[EvidenceTrack]
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
    evidence_tracks: list[EvidenceTrack]
    spotify_id: str | None
    updated_at: datetime


class PatchStatusRequest(BaseModel):
    status: ArtistStatus


class PatchStatusResponse(BaseModel):
    id: UUID
    name: str
    status: ArtistStatus


class SpotifyPatchRequest(BaseModel):
    spotify_id: str


class SpotifyPatchResponse(BaseModel):
    id: UUID
    name: str


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


# --- Pipeline stats models ---

class PipelineServiceStat(BaseModel):
    service: str
    group: str
    topic: str
    status: str          # ACTIVE | PROCESSING | STALLED | IDLE
    lag: int
    processed: int
    consumers: int


class PipelineStatsResponse(BaseModel):
    services: list[PipelineServiceStat]


# --- Reports models ---

class HeadlineResponse(BaseModel):
    total_plays: int
    unique_artists: int


class TopArtistEntry(BaseModel):
    rank: int
    name: str
    plays: int
    weight: float


class TopArtistsResponse(BaseModel):
    artists: list[TopArtistEntry]


class LoyalArtistEntry(TopArtistEntry):
    pass


class LoyalArtistsResponse(BaseModel):
    artists: list[LoyalArtistEntry]


class DailyPlayPoint(BaseModel):
    date: str
    plays: int


class PlaysTrendResponse(BaseModel):
    days: list[DailyPlayPoint]


class GenreEntry(BaseModel):
    genre: str
    plays: int
    weight: float


class GenreLandscapeResponse(BaseModel):
    genres: list[GenreEntry]


class DiscoveryMonthPoint(BaseModel):
    month: str
    count: int


class DiscoveryTimelineResponse(BaseModel):
    months: list[DiscoveryMonthPoint]


class ListeningRatioResponse(BaseModel):
    familiar_plays: int
    new_plays: int
    unknown_plays: int
    familiar_pct: float
    new_pct: float


class StreakResponse(BaseModel):
    current: int
    longest: int


class FunnelEntry(BaseModel):
    status: str
    count: int


class ReportsFunnelResponse(BaseModel):
    entries: list[FunnelEntry]
    period_filtered: bool


class HourlyPlayPoint(BaseModel):
    hour: int
    plays: int


class ListeningClockResponse(BaseModel):
    hours: list[HourlyPlayPoint]


class FingerprintResponse(BaseModel):
    consistency: float
    variety: float
    discovery: float
    night_owl: float
    depth: float


class GenreStreamPoint(BaseModel):
    week_start: str
    plays: dict[str, int]


class GenreStreamResponse(BaseModel):
    top_genres: list[str]
    points: list[GenreStreamPoint]


# --- Stats backlog models ---

class BlacklistRateResponse(BaseModel):
    blacklisted: int
    total_meaningful: int
    rate: float


class StaleRecsResponse(BaseModel):
    count: int
    threshold_days: int
    oldest_status_changed_at: datetime | None


class ScoreFreshnessBucket(BaseModel):
    label: str
    max_age_days: int | None
    count: int


class ScoreFreshnessResponse(BaseModel):
    buckets: list[ScoreFreshnessBucket]


# --- Reports backlog models ---

class WeeklyDiscoveryPoint(BaseModel):
    week_start: str
    count: int


class WeeklyDiscoveryRateResponse(BaseModel):
    weeks: list[WeeklyDiscoveryPoint]


class DiscoveryHighlightResponse(BaseModel):
    available: bool
    name: str | None = None
    plays: int | None = None
    first_seen_at: datetime | None = None
    genres: list[str] = []
    spotify_id: str | None = None


class GenreDriftResponse(BaseModel):
    current: list[GenreEntry]
    previous: list[GenreEntry]
    period_days: int | None


class CalendarDay(BaseModel):
    date: str
    plays: int


class CalendarResponse(BaseModel):
    days: list[CalendarDay]
    from_date: str
    to_date: str


class SourceEffectivenessEntry(BaseModel):
    source: str
    total: int
    published: int
    publish_rate: float


class SourceEffectivenessResponse(BaseModel):
    sources: list[SourceEffectivenessEntry]


# --- Graph models ---

class GraphNodeAttributes(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    node_type: Literal["artist", "genre"] = Field(alias="nodeType")
    label: str
    status: ArtistStatus | None = None
    score: float | None = None
    scrobble_count: int | None = None
    genres: list[str] | None = None
    spotify_id: str | None = None
    artist_count: int | None = None


class GraphNode(BaseModel):
    key: str
    attributes: GraphNodeAttributes


class GraphEdgeAttributes(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    edge_type: Literal["tagged", "similar"] = Field(alias="edgeType")


class GraphEdge(BaseModel):
    key: str
    source: str
    target: str
    attributes: GraphEdgeAttributes


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]

from __future__ import annotations

from fastapi import APIRouter, Depends

from signal_api.deps import get_db
from signal_api.models import (
    ArtistSourcesResponse,
    ArtistStatusCounts,
    GenreCount,
    GenreStatsResponse,
    NoveltyPoint,
    NoveltyRatioResponse,
    ScoreDistributionResponse,
    ServiceCheckpoint,
    ServiceHealthResponse,
    SourceCount,
    WeeklyCount,
    WeeklyDiscoveriesResponse,
)
from signal_api.repository import StatsRepository
from signal_api.settings import get_settings

import psycopg

router = APIRouter()


@router.get("/stats/summary", response_model=ArtistStatusCounts)
def get_stats_summary(
    conn: psycopg.Connection = Depends(get_db),
) -> ArtistStatusCounts:
    result = StatsRepository(conn).get_summary()
    return ArtistStatusCounts(**result)


@router.get("/stats/health", response_model=ServiceHealthResponse)
def get_stats_health(
    conn: psycopg.Connection = Depends(get_db),
) -> ServiceHealthResponse:
    settings = get_settings()
    rows = StatsRepository(conn).get_health(settings.stats_stale_threshold_minutes)
    return ServiceHealthResponse(
        services=[ServiceCheckpoint(**r) for r in rows],
        stale_threshold_minutes=settings.stats_stale_threshold_minutes,
    )


@router.get("/stats/genres", response_model=GenreStatsResponse)
def get_stats_genres(
    conn: psycopg.Connection = Depends(get_db),
) -> GenreStatsResponse:
    rows = StatsRepository(conn).get_genres()
    return GenreStatsResponse(genres=[GenreCount(**r) for r in rows])


@router.get("/stats/scores", response_model=ScoreDistributionResponse)
def get_stats_scores(
    conn: psycopg.Connection = Depends(get_db),
) -> ScoreDistributionResponse:
    result = StatsRepository(conn).get_score_distribution()
    return ScoreDistributionResponse(**result)


@router.get("/stats/discoveries", response_model=WeeklyDiscoveriesResponse)
def get_stats_discoveries(
    conn: psycopg.Connection = Depends(get_db),
) -> WeeklyDiscoveriesResponse:
    rows = StatsRepository(conn).get_weekly_discoveries()
    return WeeklyDiscoveriesResponse(weeks=[WeeklyCount(**r) for r in rows])


@router.get("/stats/novelty", response_model=NoveltyRatioResponse)
def get_stats_novelty(
    conn: psycopg.Connection = Depends(get_db),
) -> NoveltyRatioResponse:
    rows = StatsRepository(conn).get_novelty_ratio()
    return NoveltyRatioResponse(points=[NoveltyPoint(**r) for r in rows])


@router.get("/stats/sources", response_model=ArtistSourcesResponse)
def get_stats_sources(
    conn: psycopg.Connection = Depends(get_db),
) -> ArtistSourcesResponse:
    rows = StatsRepository(conn).get_artist_sources()
    return ArtistSourcesResponse(sources=[SourceCount(**r) for r in rows])

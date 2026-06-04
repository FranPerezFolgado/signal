from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, Query

from signal_api.deps import get_db
from signal_api.kafka_admin import get_pipeline_stats
from signal_api.models import (
    ArtistSourcesResponse,
    ArtistStatusCounts,
    BlacklistRateResponse,
    ExplorationCoverageResponse,
    GenreCount,
    GenreStatsResponse,
    NoveltyPoint,
    NoveltyRatioResponse,
    PipelineFunnelResponse,
    PipelineServiceStat,
    PipelineStatsResponse,
    PlayVelocityPoint,
    PlayVelocityResponse,
    ScoreBreakdownAverages,
    ScoreDistributionResponse,
    ScoreFreshnessBucket,
    ScoreFreshnessResponse,
    ServiceCheckpoint,
    ServiceHealthResponse,
    SourceCount,
    StaleRecsResponse,
    StatusBucket,
    WeeklyCount,
    WeeklyDiscoveriesResponse,
)
from signal_api.repository import StatsRepository
from signal_api.settings import get_settings

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


@router.get("/stats/velocity", response_model=PlayVelocityResponse)
def get_stats_velocity(
    conn: psycopg.Connection = Depends(get_db),
) -> PlayVelocityResponse:
    rows = StatsRepository(conn).get_play_velocity()
    return PlayVelocityResponse(points=[PlayVelocityPoint(**r) for r in rows])


@router.get("/stats/breakdown", response_model=ScoreBreakdownAverages)
def get_stats_breakdown(
    conn: psycopg.Connection = Depends(get_db),
) -> ScoreBreakdownAverages:
    result = StatsRepository(conn).get_score_breakdown_averages()
    return ScoreBreakdownAverages(**result)


@router.get("/stats/coverage", response_model=ExplorationCoverageResponse)
def get_stats_coverage(
    conn: psycopg.Connection = Depends(get_db),
) -> ExplorationCoverageResponse:
    result = StatsRepository(conn).get_exploration_coverage()
    return ExplorationCoverageResponse(**result)


@router.get("/stats/funnel", response_model=PipelineFunnelResponse)
def get_stats_funnel(
    conn: psycopg.Connection = Depends(get_db),
) -> PipelineFunnelResponse:
    rows = StatsRepository(conn).get_pipeline_funnel()
    return PipelineFunnelResponse(statuses=[StatusBucket(**r) for r in rows])


@router.get("/stats/blacklist-rate", response_model=BlacklistRateResponse)
def get_stats_blacklist_rate(
    conn: psycopg.Connection = Depends(get_db),
) -> BlacklistRateResponse:
    result = StatsRepository(conn).get_blacklist_rate()
    return BlacklistRateResponse(**result)


@router.get("/stats/active-genres", response_model=GenreStatsResponse)
def get_stats_active_genres(
    conn: psycopg.Connection = Depends(get_db),
) -> GenreStatsResponse:
    rows = StatsRepository(conn).get_active_genres()
    return GenreStatsResponse(genres=[GenreCount(**r) for r in rows])


@router.get("/stats/stale", response_model=StaleRecsResponse)
def get_stats_stale(
    threshold_days: int = Query(default=14, ge=1, le=3650),
    conn: psycopg.Connection = Depends(get_db),
) -> StaleRecsResponse:
    result = StatsRepository(conn).get_stale_recs(threshold_days)
    return StaleRecsResponse(**result)


@router.get("/stats/score-freshness", response_model=ScoreFreshnessResponse)
def get_stats_score_freshness(
    conn: psycopg.Connection = Depends(get_db),
) -> ScoreFreshnessResponse:
    rows = StatsRepository(conn).get_score_freshness()
    return ScoreFreshnessResponse(buckets=[ScoreFreshnessBucket(**r) for r in rows])


@router.get("/stats/pipeline", response_model=PipelineStatsResponse)
def get_stats_pipeline() -> PipelineStatsResponse:
    settings = get_settings()
    if not settings.kafka_bootstrap_servers:
        return PipelineStatsResponse(services=[])
    rows = get_pipeline_stats(settings.kafka_bootstrap_servers)
    return PipelineStatsResponse(services=[PipelineServiceStat(**r) for r in rows])

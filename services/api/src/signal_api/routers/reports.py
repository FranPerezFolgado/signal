from __future__ import annotations

from datetime import date

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from signal_api.deps import get_db
from signal_api.models import (
    DiscoveryTimelineResponse,
    GenreLandscapeResponse,
    HeadlineResponse,
    ListeningRatioResponse,
    PlaysTrendResponse,
    ReportsFunnelResponse,
    StreakResponse,
    TopArtistsResponse,
)
from signal_api.repository import ReportsRepository

router = APIRouter()

_today = date.today


def _validate_dates(from_date: date | None, to_date: date | None) -> tuple[date | None, date | None]:
    today = _today()
    if to_date and to_date > today:
        to_date = today
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date must be before to_date")
    return from_date, to_date


@router.get("/reports/headline", response_model=HeadlineResponse)
def get_reports_headline(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> HeadlineResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    result = ReportsRepository(conn).get_headline(from_date, to_date)
    return HeadlineResponse(**result)


@router.get("/reports/top-artists", response_model=TopArtistsResponse)
def get_reports_top_artists(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> TopArtistsResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    rows = ReportsRepository(conn).get_top_artists(from_date, to_date)
    return TopArtistsResponse(artists=rows)


@router.get("/reports/plays-trend", response_model=PlaysTrendResponse)
def get_reports_plays_trend(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> PlaysTrendResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    days = ReportsRepository(conn).get_plays_trend(from_date, to_date)
    return PlaysTrendResponse(days=days)


@router.get("/reports/genres", response_model=GenreLandscapeResponse)
def get_reports_genres(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> GenreLandscapeResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    rows = ReportsRepository(conn).get_genres(from_date, to_date)
    return GenreLandscapeResponse(genres=rows)


@router.get("/reports/discovery-timeline", response_model=DiscoveryTimelineResponse)
def get_reports_discovery_timeline(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> DiscoveryTimelineResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    months = ReportsRepository(conn).get_discovery_timeline(from_date, to_date)
    return DiscoveryTimelineResponse(months=months)


@router.get("/reports/listening-ratio", response_model=ListeningRatioResponse)
def get_reports_listening_ratio(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> ListeningRatioResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    result = ReportsRepository(conn).get_listening_ratio(from_date, to_date)
    return ListeningRatioResponse(**result)


@router.get("/reports/streak", response_model=StreakResponse)
def get_reports_streak(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> StreakResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    result = ReportsRepository(conn).get_streak(from_date, to_date)
    return StreakResponse(**result)


@router.get("/reports/funnel", response_model=ReportsFunnelResponse)
def get_reports_funnel(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> ReportsFunnelResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    result = ReportsRepository(conn).get_funnel(from_date, to_date)
    return ReportsFunnelResponse(**result)

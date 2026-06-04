from __future__ import annotations

from datetime import date

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from signal_api.deps import get_db
from signal_api.models import (
    CalendarResponse,
    DailyPlayPoint,
    DiscoveryHighlightResponse,
    DiscoveryMonthPoint,
    DiscoveryTimelineResponse,
    FingerprintResponse,
    GenreDriftResponse,
    GenreEntry,
    GenreLandscapeResponse,
    GenreStreamResponse,
    HeadlineResponse,
    HourlyPlayPoint,
    ListeningClockResponse,
    ListeningRatioResponse,
    LoyalArtistEntry,
    LoyalArtistsResponse,
    PlaysTrendResponse,
    ReportsFunnelResponse,
    SourceEffectivenessEntry,
    SourceEffectivenessResponse,
    StreakResponse,
    TopArtistEntry,
    TopArtistsResponse,
    WeeklyDiscoveryPoint,
    WeeklyDiscoveryRateResponse,
)
from signal_api.repository import ReportsRepository

router = APIRouter()

_today = date.today


def _validate_dates(
    from_date: date | None, to_date: date | None
) -> tuple[date | None, date | None]:
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
    return TopArtistsResponse(artists=[TopArtistEntry(**r) for r in rows])


@router.get("/reports/plays-trend", response_model=PlaysTrendResponse)
def get_reports_plays_trend(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> PlaysTrendResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    days = ReportsRepository(conn).get_plays_trend(from_date, to_date)
    return PlaysTrendResponse(days=[DailyPlayPoint(**r) for r in days])


@router.get("/reports/genres", response_model=GenreLandscapeResponse)
def get_reports_genres(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> GenreLandscapeResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    rows = ReportsRepository(conn).get_genres(from_date, to_date)
    return GenreLandscapeResponse(genres=[GenreEntry(**r) for r in rows])


@router.get("/reports/discovery-timeline", response_model=DiscoveryTimelineResponse)
def get_reports_discovery_timeline(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> DiscoveryTimelineResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    months = ReportsRepository(conn).get_discovery_timeline(from_date, to_date)
    return DiscoveryTimelineResponse(months=[DiscoveryMonthPoint(**r) for r in months])


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


@router.get("/reports/listening-clock", response_model=ListeningClockResponse)
def get_reports_listening_clock(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> ListeningClockResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    hours = ReportsRepository(conn).get_listening_clock(from_date, to_date)
    return ListeningClockResponse(hours=[HourlyPlayPoint(**r) for r in hours])


@router.get("/reports/fingerprint", response_model=FingerprintResponse)
def get_reports_fingerprint(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> FingerprintResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    result = ReportsRepository(conn).get_fingerprint(from_date, to_date)
    return FingerprintResponse(**result)


@router.get("/reports/genre-stream", response_model=GenreStreamResponse)
def get_reports_genre_stream(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> GenreStreamResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    result = ReportsRepository(conn).get_genre_stream(from_date, to_date)
    return GenreStreamResponse(**result)


@router.get("/reports/weekly-discovery-rate", response_model=WeeklyDiscoveryRateResponse)
def get_reports_weekly_discovery_rate(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> WeeklyDiscoveryRateResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    weeks = ReportsRepository(conn).get_weekly_discovery_rate(from_date, to_date)
    return WeeklyDiscoveryRateResponse(weeks=[WeeklyDiscoveryPoint(**r) for r in weeks])


@router.get("/reports/discovery-highlight", response_model=DiscoveryHighlightResponse)
def get_reports_discovery_highlight(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> DiscoveryHighlightResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    row = ReportsRepository(conn).get_discovery_highlight(from_date, to_date)
    if not row:
        return DiscoveryHighlightResponse(available=False)
    return DiscoveryHighlightResponse(available=True, **row)


@router.get("/reports/genre-drift", response_model=GenreDriftResponse)
def get_reports_genre_drift(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> GenreDriftResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    result = ReportsRepository(conn).get_genre_drift(from_date, to_date)
    return GenreDriftResponse(**result)


@router.get("/reports/calendar", response_model=CalendarResponse)
def get_reports_calendar(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> CalendarResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    result = ReportsRepository(conn).get_calendar(from_date, to_date)
    return CalendarResponse(**result)


@router.get("/reports/loyal-artists", response_model=LoyalArtistsResponse)
def get_reports_loyal_artists(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> LoyalArtistsResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    rows = ReportsRepository(conn).get_loyal_artists(from_date, to_date)
    return LoyalArtistsResponse(artists=[LoyalArtistEntry(**r) for r in rows])


@router.get("/reports/source-effectiveness", response_model=SourceEffectivenessResponse)
def get_reports_source_effectiveness(
    from_date: date | None = None,
    to_date: date | None = None,
    conn: psycopg.Connection = Depends(get_db),
) -> SourceEffectivenessResponse:
    from_date, to_date = _validate_dates(from_date, to_date)
    rows = ReportsRepository(conn).get_source_effectiveness(from_date, to_date)
    return SourceEffectivenessResponse(sources=[SourceEffectivenessEntry(**r) for r in rows])

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from psycopg_pool import ConnectionPool
from signal_common.logger import get_logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from signal_api.metrics import instrument_app
from signal_api.settings import get_settings

_log = get_logger("signal_api")

_EXCLUDED_LOG_PATHS = {"/health", "/metrics"}


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _EXCLUDED_LOG_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            _log.exception(
                "request_error",
                method=request.method,
                path=request.url.path,
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000)
        _log.info(
            "request_complete",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    pool = ConnectionPool(
        settings.database_url,
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
        open=False,
    )
    pool.open(wait=False)
    app.state.pool = pool
    yield
    pool.close()


def create_app() -> FastAPI:
    from signal_api.routers.artists import router as artists_router
    from signal_api.routers.health import router as health_router
    from signal_api.routers.recommendations import router as recommendations_router

    app = FastAPI(
        title="Signal API",
        description="Artist management and recommendations for Signal",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestLogMiddleware)

    instrument_app(app)

    app.include_router(recommendations_router, prefix="/v1", tags=["recommendations"])
    app.include_router(artists_router, prefix="/v1", tags=["artists"])
    app.include_router(health_router, tags=["health"])

    return app

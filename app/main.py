import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, coach, goals, health, plans, profile, runs, stats
from app.config import settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import register_rate_limit
from app.core.redis import redis_client


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    logger = structlog.get_logger()
    try:
        await redis_client.ping()
        logger.info("redis_connected", url=settings.REDIS_URL)
    except Exception:
        logger.warning("redis_unavailable", url=settings.REDIS_URL)
    yield
    await redis_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Running Coach API",
        version="0.1.0",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    register_rate_limit(app)
    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(runs.router)
    app.include_router(stats.router)
    app.include_router(goals.router)
    app.include_router(plans.router)
    app.include_router(coach.router)

    return app


app = create_app()

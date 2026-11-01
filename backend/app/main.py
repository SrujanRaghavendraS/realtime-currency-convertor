"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.api.routes import router
from app.config import Settings, get_settings
from app.models.domain import Clock, system_clock
from app.providers.base import RateProvider
from app.providers.exchangerate_dev import ExchangeRateDevProvider
from app.services.container import build_services


def create_app(
    settings: Optional[Settings] = None,
    redis: Optional[Redis] = None,
    provider: Optional[RateProvider] = None,
    clock: Clock = system_clock,
    start_collector: Optional[bool] = None,
) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx logs full request URLs at INFO; keep it quiet (the key is a header, but be safe).
    logging.getLogger("httpx").setLevel(logging.WARNING)

    redis = redis or Redis.from_url(settings.redis_url, decode_responses=True)
    provider = provider or ExchangeRateDevProvider(settings, clock=clock)
    services = build_services(settings, redis, provider, clock)
    run_collector = settings.collector_enabled if start_collector is None else start_collector

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if run_collector:
            services.collector.start()
        try:
            yield
        finally:
            await services.collector.stop()

    app = FastAPI(title="FX Rate Monitor", version="1.0.0", lifespan=lifespan)
    app.state.services = services
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.exception_handler(RedisError)
    async def redis_down(_: Request, exc: RedisError):
        logging.getLogger(__name__).error("Redis error: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "Rate store (Redis) is unavailable. Please try again shortly."})

    app.include_router(router)
    return app


app = create_app()

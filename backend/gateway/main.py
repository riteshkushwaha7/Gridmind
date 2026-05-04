"""Gateway entrypoint — single FastAPI app exposed to the frontend."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from gateway.routes import dashboard, forecast, health, schedule, zones
from shared import postgres_client, redis_consumer
from shared.observability import install_observability

log = logging.getLogger("gridmind.gateway")
SERVICE = "backend-gateway"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_consumer.connect()
    await postgres_client.connect()
    log.info("gateway ready")
    yield
    await redis_consumer.close()
    await postgres_client.close()


app = FastAPI(
    title="GRIDMIND Gateway",
    version="1.0.0",
    description="Aggregated REST surface for the GRIDMIND operator UI.",
    lifespan=lifespan,
)
install_observability(app, service=SERVICE)

app.include_router(health.router,    tags=["health"])
app.include_router(forecast.router,  tags=["forecast"])
app.include_router(schedule.router,  tags=["schedule"])
app.include_router(zones.router,     tags=["zones"])
app.include_router(dashboard.router, tags=["dashboard"])

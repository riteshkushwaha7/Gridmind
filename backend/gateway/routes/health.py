"""Gateway health — aggregates upstream service health."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from fastapi import APIRouter

from config import CLUSTERING_URL, DATA_NODES_URL, LSTM_URL, PPO_URL
from shared import postgres_client, redis_consumer
from shared.observability import uptime_seconds
from shared.schemas import HealthResponse

router = APIRouter()
log = logging.getLogger("gridmind.gateway.health")
SERVICE = "backend-gateway"

UPSTREAMS = {
    "lstm":       f"{LSTM_URL}/health",
    "ppo":        f"{PPO_URL}/health",
    "clustering": f"{CLUSTERING_URL}/health",
    "data-nodes": f"{DATA_NODES_URL}/health",
}


async def _ping(name: str, url: str) -> tuple[str, str]:
    try:
        async with httpx.AsyncClient(timeout=2.5) as cli:
            r = await cli.get(url)
            return name, "ok" if r.status_code < 500 else f"http_{r.status_code}"
    except Exception:
        return name, "down"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    upstream_results = await asyncio.gather(*[_ping(n, u) for n, u in UPSTREAMS.items()])
    deps: dict[str, str] = {k: v for k, v in upstream_results}
    deps["redis"] = "ok" if await redis_consumer.healthy() else "down"
    deps["postgres"] = "ok" if await postgres_client.healthy() else "down"
    return HealthResponse(
        status="ok",
        service=SERVICE,
        uptime_seconds=uptime_seconds(),
        dependencies=deps,
    )

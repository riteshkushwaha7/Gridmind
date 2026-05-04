"""Zone ranking + per-zone history."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from config import CACHE_TTL, CLUSTERING_URL, DATA_NODES_URL, ZONES
from shared import http_client, redis_consumer

router = APIRouter()
log = logging.getLogger("gridmind.gateway.zones")

CACHE_KEY = "gateway:zones:ranking"

METRIC_TO_NODE = {
    "demand":     ("ev",   "/ev/zone/{zone_id}/metrics"),
    "grid":       ("grid", "/grid/feeder/{zone_id}/history"),
    "solar":      ("solar","/solar/{zone_id}/forecast"),
}


@router.get("/zones/ranking")
async def zones_ranking() -> dict[str, Any]:
    cached = await redis_consumer.cache_get(CACHE_KEY)
    if cached:
        return cached
    payload = await http_client.get(f"{CLUSTERING_URL}/clustering/zones/ranking")
    await redis_consumer.cache_set(CACHE_KEY, payload, ttl_seconds=CACHE_TTL["zones"])
    return payload


@router.get("/zones/{zone_id}/history")
async def zone_history(
    zone_id: str,
    metric: str = Query("demand", pattern="^(demand|grid|solar)$"),
    hours: int = Query(168, ge=1, le=24 * 30),
) -> dict[str, Any]:
    if zone_id not in ZONES:
        raise HTTPException(status_code=404, detail=f"unknown zone {zone_id}")
    _, path_tmpl = METRIC_TO_NODE[metric]
    url = f"{DATA_NODES_URL}{path_tmpl.format(zone_id=zone_id)}"
    return await http_client.get(url, params={"hours": hours})

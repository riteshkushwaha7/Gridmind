"""Gateway → LSTM proxy with Redis caching."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from config import CACHE_TTL, LSTM_URL, ZONES
from shared import http_client, redis_consumer

router = APIRouter()
log = logging.getLogger("gridmind.gateway.forecast")


def _cache_key(zone_id: str, hours: int) -> str:
    return f"gateway:forecast:{zone_id}:{hours}"


async def _fetch_one(zone_id: str, hours: int) -> dict[str, Any]:
    cached = await redis_consumer.cache_get(_cache_key(zone_id, hours))
    if cached:
        return cached
    payload = await http_client.post(
        f"{LSTM_URL}/lstm/forecast",
        json={"zone_id": zone_id, "horizon_hours": hours},
    )
    await redis_consumer.cache_set(_cache_key(zone_id, hours), payload, ttl_seconds=CACHE_TTL["forecast"])
    return payload


@router.get("/forecast/{zone_id}")
async def forecast_for_zone(zone_id: str, hours: int = Query(4, ge=1, le=24)) -> dict[str, Any]:
    if zone_id not in ZONES:
        raise HTTPException(status_code=404, detail=f"unknown zone {zone_id}")
    return await _fetch_one(zone_id, hours)


@router.get("/forecast/all")
async def forecast_all(hours: int = Query(4, ge=1, le=24)) -> dict[str, Any]:
    results = await asyncio.gather(*[_fetch_one(z, hours) for z in ZONES], return_exceptions=True)
    forecasts: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for zone_id, res in zip(ZONES, results):
        if isinstance(res, Exception):
            errors.append({"zone_id": zone_id, "error": str(res)})
        else:
            forecasts.append(res)
    return {"horizon_hours": hours, "forecasts": forecasts, "errors": errors}

"""Gateway → PPO proxy + manual operator overrides."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from config import CACHE_TTL, DATA_NODES_URL, LSTM_URL, PPO_URL, ZONES
from shared import http_client, postgres_client, redis_consumer
from shared.observability import correlation_id
from shared.schemas import ScheduleOverride

router = APIRouter()
log = logging.getLogger("gridmind.gateway.schedule")

CACHE_KEY = "gateway:schedule:current"


async def _live_zone_states() -> tuple[list[dict[str, Any]], float]:
    """Pull latest zone snapshots from data-nodes for the PPO request."""
    snap = await http_client.get(f"{DATA_NODES_URL}/ev/zones/snapshot")
    grid_summary = await http_client.get(f"{DATA_NODES_URL}/grid/feeders/summary")
    solar_summary = await http_client.get(f"{DATA_NODES_URL}/solar/summary")
    tariff = await http_client.get(f"{DATA_NODES_URL}/tariff/current")

    grid_by_zone = {f["zone_id"]: f for f in grid_summary.get("feeders", [])}
    solar_by_zone = {s["zone_id"]: s for s in solar_summary.get("zones", [])}
    states: list[dict[str, Any]] = []
    for z in snap.get("zones", []):
        zid = z["zone_id"]
        states.append({
            "zone_id": zid,
            "active_evs": z.get("active_sessions", 0),
            "avg_soc": z.get("avg_soc_arriving", 50.0),
            "feeder_headroom_pct": grid_by_zone.get(zid, {}).get("headroom_pct", 100.0),
            "solar_output_kw": solar_by_zone.get(zid, {}).get("pv_output_kw", 0.0),
            "battery_soc": solar_by_zone.get(zid, {}).get("battery_soc_pct", 50.0),
        })
    return states, float(tariff.get("rate_inr_per_kwh", 7.0))


async def _build_request_body() -> dict[str, Any]:
    states, tariff = await _live_zone_states()
    # Pull a 16-step demand forecast for the heaviest zone as a proxy.
    forecast_zone = states[0]["zone_id"] if states else ZONES[0]
    fc = await http_client.post(f"{LSTM_URL}/lstm/forecast", json={"zone_id": forecast_zone, "horizon_hours": 4})
    forecast = [p["demand_kwh"] for p in fc.get("forecast", [])][:16]
    while len(forecast) < 16:
        forecast.append(0.0)
    return {"zones": states, "tariff_current": tariff, "demand_forecast": forecast}


@router.get("/schedule/current")
async def schedule_current() -> dict[str, Any]:
    cached = await redis_consumer.cache_get(CACHE_KEY)
    if cached:
        return cached
    body = await _build_request_body()
    payload = await http_client.post(f"{PPO_URL}/ppo/schedule", json=body)
    await redis_consumer.cache_set(CACHE_KEY, payload, ttl_seconds=CACHE_TTL["schedule"])
    return payload


@router.post("/schedule/override")
async def schedule_override(override: ScheduleOverride) -> dict[str, Any]:
    cached = await redis_consumer.cache_get(CACHE_KEY)
    schedule_id = (cached or {}).get("schedule_id")
    row_id = await postgres_client.insert_override(
        schedule_id=schedule_id,
        zone_id=override.zone_id,
        operator_id=override.operator_id,
        power_kw=override.power_kw,
        reason=override.reason,
    )
    await postgres_client.insert_audit(
        service="backend-gateway", action="schedule_override",
        actor=override.operator_id, correlation_id=correlation_id(),
        payload=override.model_dump(),
    )
    await redis_consumer.cache_set(CACHE_KEY, cached or {}, ttl_seconds=1)  # invalidate cache
    return {
        "override_id": row_id,
        "schedule_id": schedule_id,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted",
    }

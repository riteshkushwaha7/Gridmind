"""Aggregated dashboard endpoints — single fan-out per request to keep TTL low."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from config import (
    CACHE_TTL,
    CLUSTERING_URL,
    DATA_NODES_URL,
    INFLUXDB_BUCKET,
    PPO_URL,
    ZONES,
)
from shared import http_client, influx_client, redis_consumer
from shared.schemas import (
    Alert,
    DashboardOverview,
    GridTotal,
    Severity,
    SolarTotal,
    SystemStatus,
    TariffNow,
    ZoneSummary,
)

router = APIRouter()
log = logging.getLogger("gridmind.gateway.dashboard")

CACHE_KEY_OVERVIEW = "gateway:dashboard:overview"
CACHE_KEY_ALERTS = "gateway:dashboard:alerts"


# ─────────────── Overview ───────────────
async def _gather_sources() -> dict[str, Any]:
    grid, solar, tariff, snap, ranking, schedule = await asyncio.gather(
        http_client.get(f"{DATA_NODES_URL}/grid/feeders/summary"),
        http_client.get(f"{DATA_NODES_URL}/solar/summary"),
        http_client.get(f"{DATA_NODES_URL}/tariff/current"),
        http_client.get(f"{DATA_NODES_URL}/ev/zones/snapshot"),
        http_client.get(f"{CLUSTERING_URL}/clustering/zones/ranking"),
        _maybe(http_client.post(f"{PPO_URL}/ppo/schedule", json=await _schedule_request())),
        return_exceptions=True,
    )
    return {
        "grid": grid if not isinstance(grid, Exception) else {},
        "solar": solar if not isinstance(solar, Exception) else {},
        "tariff": tariff if not isinstance(tariff, Exception) else {},
        "snap": snap if not isinstance(snap, Exception) else {},
        "ranking": ranking if not isinstance(ranking, Exception) else {},
        "schedule": schedule if not isinstance(schedule, Exception) else {},
    }


async def _maybe(coro):
    try:
        return await coro
    except Exception:
        return {}


async def _schedule_request() -> dict[str, Any]:
    snap = await http_client.get(f"{DATA_NODES_URL}/ev/zones/snapshot")
    grid = await http_client.get(f"{DATA_NODES_URL}/grid/feeders/summary")
    solar = await http_client.get(f"{DATA_NODES_URL}/solar/summary")
    tariff = await http_client.get(f"{DATA_NODES_URL}/tariff/current")
    grid_by = {f["zone_id"]: f for f in grid.get("feeders", [])}
    solar_by = {s["zone_id"]: s for s in solar.get("zones", [])}
    states = []
    for z in snap.get("zones", []):
        zid = z["zone_id"]
        states.append({
            "zone_id": zid,
            "active_evs": z.get("active_sessions", 0),
            "avg_soc": z.get("avg_soc_arriving", 50.0),
            "feeder_headroom_pct": grid_by.get(zid, {}).get("headroom_pct", 100.0),
            "solar_output_kw": solar_by.get(zid, {}).get("pv_output_kw", 0.0),
            "battery_soc": solar_by.get(zid, {}).get("battery_soc_pct", 50.0),
        })
    return {
        "zones": states,
        "tariff_current": tariff.get("rate_inr_per_kwh", 7.0),
        "demand_forecast": [0.0] * 16,
    }


def _system_status(grid: dict[str, Any]) -> SystemStatus:
    constraints = grid.get("constraints") or []
    if len(constraints) >= 3:
        return SystemStatus.CRITICAL
    if constraints:
        return SystemStatus.DEGRADED
    return SystemStatus.HEALTHY


def _zones_summary(snap: dict, grid: dict, ranking: dict) -> list[ZoneSummary]:
    grid_by = {f["zone_id"]: f for f in grid.get("feeders", [])}
    rank_by = {z["zone_id"]: z for z in ranking.get("zones", [])}
    out: list[ZoneSummary] = []
    for z in snap.get("zones", []):
        zid = z["zone_id"]
        g = grid_by.get(zid, {})
        r = rank_by.get(zid, {})
        cap = g.get("feeder_capacity_kw", 1.0) or 1.0
        load = g.get("total_load_kw", 0.0) or 0.0
        out.append(ZoneSummary(
            zone_id=zid,
            status=g.get("feeder_status", "NORMAL"),
            load_pct=round(load / cap * 100.0, 2),
            active_evs=int(z.get("active_sessions", 0)),
            score=float(r.get("score", 0.0)),
        ))
    return out


def _peak_reduction_today(schedule: dict) -> float:
    return float(schedule.get("peak_reduction_vs_unmanaged_pct", 0.0))


async def _cost_savings_today_inr() -> float:
    flux = f'''
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "ppo_schedule" and r._field == "power_kw")
  |> aggregateWindow(every: 15m, fn: mean, createEmpty: false)
  |> sum()
'''
    rows = await influx_client.query(flux)
    if not rows:
        return 0.0
    managed_kw_15m = sum(float(r["value"] or 0.0) for r in rows)
    # rough delta: assume 20 % cheaper than naive ToU peak rate
    return round(managed_kw_15m * 0.25 * 9.5 * 0.20, 2)


async def _alerts(grid: dict, snap: dict) -> list[Alert]:
    now = datetime.now(timezone.utc)
    out: list[Alert] = []
    for f in grid.get("feeders", []):
        if f.get("constraint_flag"):
            out.append(Alert(
                zone_id=f["zone_id"],
                severity=Severity.WARNING,
                message=f"Feeder {f['feeder_id']} status={f['feeder_status']} (headroom {f['headroom_pct']:.1f}%)",
                timestamp=now,
            ))
    for z in snap.get("zones", []):
        if z.get("queued_evs", 0) > 0:
            out.append(Alert(
                zone_id=z["zone_id"],
                severity=Severity.INFO,
                message=f"{z['queued_evs']} EVs queued — utilisation {z.get('utilization_pct', 0):.0f}%",
                timestamp=now,
            ))
    return out


@router.get("/dashboard/overview", response_model=DashboardOverview)
async def overview() -> DashboardOverview:
    cached = await redis_consumer.cache_get(CACHE_KEY_OVERVIEW)
    if cached:
        return DashboardOverview.model_validate(cached)

    src = await _gather_sources()
    grid = src["grid"]
    grid_total = GridTotal(
        total_load_kw=float(grid.get("total_load_kw", 0.0)),
        total_capacity_kw=float(grid.get("total_capacity_kw", 0.0)),
        system_headroom_pct=round(
            (float(grid.get("total_headroom_kw", 0.0)) / max(1.0, float(grid.get("total_capacity_kw", 1.0)))) * 100,
            2,
        ),
    )
    tariff_now = TariffNow(
        tier=src["tariff"].get("tier", "MID_PEAK"),
        rate_inr=float(src["tariff"].get("rate_inr_per_kwh", 7.0)),
        next_change_minutes=int(src["tariff"].get("next_tier_change_minutes", 0)),
    )
    solar_total = SolarTotal(
        generation_kw=float(src["solar"].get("total_pv_output_kw", 0.0)),
        battery_soc_avg=float(
            sum(z.get("battery_soc_pct", 0.0) for z in src["solar"].get("zones", []))
            / max(1, len(src["solar"].get("zones", [])))
        ),
        self_consumption_pct=float(src["solar"].get("fleet_yield_pct", 0.0)),
    )
    overview = DashboardOverview(
        timestamp=datetime.now(timezone.utc),
        system_status=_system_status(grid),
        zones_summary=_zones_summary(src["snap"], grid, src["ranking"]),
        grid_total=grid_total,
        current_tariff=tariff_now,
        solar_total=solar_total,
        active_sessions_total=sum(z.get("active_sessions", 0) for z in src["snap"].get("zones", [])),
        peak_reduction_today_pct=_peak_reduction_today(src["schedule"]),
        cost_savings_today_inr=await _cost_savings_today_inr(),
        alerts=await _alerts(grid, src["snap"]),
    )
    await redis_consumer.cache_set(CACHE_KEY_OVERVIEW, overview.model_dump(mode="json"), ttl_seconds=CACHE_TTL["dashboard"])
    return overview


@router.get("/dashboard/zone/{zone_id}")
async def dashboard_zone(zone_id: str) -> dict[str, Any]:
    if zone_id not in ZONES:
        raise HTTPException(status_code=404, detail=f"unknown zone {zone_id}")
    grid, solar, ev, ocpp = await asyncio.gather(
        http_client.get(f"{DATA_NODES_URL}/grid/feeder/{zone_id}/status"),
        http_client.get(f"{DATA_NODES_URL}/solar/{zone_id}/current"),
        http_client.get(f"{DATA_NODES_URL}/ev/zone/{zone_id}/metrics", params={"hours": 24}),
        http_client.get(f"{DATA_NODES_URL}/ocpp/sessions/active/{zone_id}"),
        return_exceptions=True,
    )
    return {
        "zone_id": zone_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "grid":   grid if not isinstance(grid, Exception) else {"error": str(grid)},
        "solar":  solar if not isinstance(solar, Exception) else {"error": str(solar)},
        "ev":     ev if not isinstance(ev, Exception) else {"error": str(ev)},
        "ocpp":   ocpp if not isinstance(ocpp, Exception) else {"error": str(ocpp)},
    }


@router.get("/dashboard/alerts")
async def dashboard_alerts() -> dict[str, Any]:
    cached = await redis_consumer.cache_get(CACHE_KEY_ALERTS)
    if cached:
        return cached
    grid = await _maybe(http_client.get(f"{DATA_NODES_URL}/grid/feeders/summary"))
    snap = await _maybe(http_client.get(f"{DATA_NODES_URL}/ev/zones/snapshot"))
    alerts = await _alerts(grid or {}, snap or {})
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "count": len(alerts),
        "alerts": [a.model_dump(mode="json") for a in alerts],
    }
    await redis_consumer.cache_set(CACHE_KEY_ALERTS, payload, ttl_seconds=CACHE_TTL["dashboard"])
    return payload

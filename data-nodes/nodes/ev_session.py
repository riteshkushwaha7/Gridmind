"""Node 5 — EV session aggregates per zone (separate analytics layer over OCPP)."""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, Query

import redis_client
from config import (
    BACKFILL_DAYS,
    DATA_DIR,
    HOURLY_PROFILES,
    STREAMS,
    TICK_EV,
    ZONES,
    ZONES_BY_ID,
)
from nodes import ocpp as ocpp_node

NODE_ID = "ev_session"
STREAM = STREAMS["ev_session"]
DB_PATH = os.path.join(DATA_DIR, "ev_session.db")
log = logging.getLogger("gridmind.ev_session")
router = APIRouter()

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id   TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ev_zone_ts ON history(zone_id, timestamp);
"""

# Rolling windows of (timestamp, kwh) for 1h / 24h sums per zone
_WINDOW_1H: dict[str, deque] = {z.id: deque() for z in ZONES}
_WINDOW_24H: dict[str, deque] = {z.id: deque() for z in ZONES}

# India fleet mix
EV_TYPE_MIX = {
    "two_wheeler_pct": 60.0,
    "three_wheeler_pct": 20.0,
    "four_wheeler_pct": 15.0,
    "bus_pct": 5.0,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _r2(x: float) -> float:
    return round(float(x), 2)


def _trim(window: deque, since: datetime) -> None:
    while window and window[0][0] < since:
        window.popleft()


def _peak_hour_today(rows: list[tuple[str, float]]) -> int:
    """rows: list of (iso_ts, kwh) for today; returns hour with max sum."""
    if not rows:
        return 0
    by_hour: dict[int, float] = {}
    for ts, kwh in rows:
        try:
            h = datetime.fromisoformat(ts.replace("Z", "+00:00")).hour
        except Exception:
            continue
        by_hour[h] = by_hour.get(h, 0.0) + kwh
    return max(by_hour, key=by_hour.get) if by_hour else 0


async def _zone_metrics(zone, now: datetime) -> dict[str, Any]:
    # Active OCPP sessions for this zone
    active = [s for s in ocpp_node.SESSIONS.values() if s.zone_id == zone.id and s.state == "active"]
    chargers = [c for c in ocpp_node.CHARGERS.values() if c.zone_id == zone.id]
    available = sum(1 for c in chargers if c.status == "Available")
    total = len(chargers)
    occupied = sum(1 for c in chargers if c.status == "Occupied")

    # Recent stopped sessions (last 24h) from sqlite for averages
    since_24h = (now - timedelta(hours=24)).isoformat()
    since_15m = (now - timedelta(minutes=15)).isoformat()
    async with aiosqlite.connect(ocpp_node.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT soc_start_pct, soc_end_pct, duration_min, energy_kwh, started_at "
            "FROM sessions WHERE zone_id=? AND started_at>=?",
            (zone.id, since_24h),
        )
        rows24 = [dict(r) for r in await cur.fetchall()]
        cur2 = await db.execute(
            "SELECT energy_kwh, started_at FROM sessions "
            "WHERE zone_id=? AND stopped_at IS NOT NULL AND stopped_at>=?",
            (zone.id, since_15m),
        )
        last15 = [dict(r) for r in await cur2.fetchall()]

    energy_15m = sum((r["energy_kwh"] or 0.0) for r in last15)

    # Update rolling windows
    _WINDOW_1H[zone.id].append((now, energy_15m))
    _WINDOW_24H[zone.id].append((now, energy_15m))
    _trim(_WINDOW_1H[zone.id], now - timedelta(hours=1))
    _trim(_WINDOW_24H[zone.id], now - timedelta(hours=24))
    demand_1h = sum(k for _, k in _WINDOW_1H[zone.id])
    demand_24h = sum(k for _, k in _WINDOW_24H[zone.id])

    avg_soc_in = sum(r["soc_start_pct"] or 0 for r in rows24) / len(rows24) if rows24 else 0.0
    avg_soc_out = sum(r["soc_end_pct"] or 0 for r in rows24) / len(rows24) if rows24 else 0.0
    avg_dur = sum(r["duration_min"] or 0 for r in rows24) / len(rows24) if rows24 else 0.0
    avg_kwh = sum(r["energy_kwh"] or 0 for r in rows24) / len(rows24) if rows24 else 0.0

    # Queue heuristic: if all chargers occupied + arrival rate elevated, simulate queue
    daykey = "weekday" if now.weekday() < 5 else "weekend"
    arrivals_per_hour = HOURLY_PROFILES[(zone.type, daykey)][now.hour] * 2.0
    queued = 0
    if available == 0 and arrivals_per_hour > 3:
        queued = max(0, int(arrivals_per_hour / 4) + random.randint(0, 2))

    peak_h = _peak_hour_today([(r["started_at"], r["energy_kwh"] or 0.0) for r in rows24])
    forecast_1h = _r2((demand_1h * 0.7) + (avg_kwh * arrivals_per_hour * 0.3))

    util = (occupied / total * 100.0) if total else 0.0
    return {
        "zone_id": zone.id,
        "node_id": NODE_ID,
        "timestamp": now.isoformat(),
        "active_sessions": len(active),
        "queued_evs": queued,
        "available_chargers": available,
        "total_chargers": total,
        "utilization_pct": _r2(util),
        "avg_soc_arriving": _r2(avg_soc_in),
        "avg_soc_departing": _r2(avg_soc_out),
        "avg_session_duration_min": _r2(avg_dur),
        "avg_energy_per_session_kwh": _r2(avg_kwh),
        "total_energy_delivered_kwh": _r2(energy_15m),
        "demand_kwh_15min": _r2(energy_15m),
        "demand_kwh_1h": _r2(demand_1h),
        "demand_kwh_24h": _r2(demand_24h),
        "ev_types": EV_TYPE_MIX,
        "peak_hour_today": peak_h,
        "demand_forecast_1h_kwh": forecast_1h,
    }


async def init() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def backfill() -> None:
    """Generate historical 15-min aggregates from OCPP backfilled sessions."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM history")
        if (await cur.fetchone())[0] > 0:
            return
        end = _now().replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(days=BACKFILL_DAYS)

        # Load sessions once and bucket per zone × 15-min
        async with aiosqlite.connect(ocpp_node.DB_PATH) as ocpp_db:
            ocpp_db.row_factory = aiosqlite.Row
            scur = await ocpp_db.execute(
                "SELECT zone_id, stopped_at, energy_kwh, soc_start_pct, soc_end_pct, duration_min "
                "FROM sessions WHERE stopped_at IS NOT NULL AND stopped_at>=?",
                (start.isoformat(),),
            )
            sessions = [dict(r) for r in await scur.fetchall()]

        rows: list[tuple] = []
        cur_ts = start
        while cur_ts < end:
            bin_end = cur_ts + timedelta(minutes=15)
            for z in ZONES:
                in_bin = [
                    s for s in sessions
                    if s["zone_id"] == z.id
                    and s["stopped_at"]
                    and cur_ts.isoformat() <= s["stopped_at"] < bin_end.isoformat()
                ]
                energy = sum(s["energy_kwh"] or 0.0 for s in in_bin)
                count = len(in_bin)
                payload = {
                    "zone_id": z.id,
                    "node_id": NODE_ID,
                    "timestamp": cur_ts.isoformat(),
                    "active_sessions": count,
                    "queued_evs": 0,
                    "available_chargers": z.chargers - min(count, z.chargers),
                    "total_chargers": z.chargers,
                    "utilization_pct": _r2(min(count, z.chargers) / z.chargers * 100.0),
                    "avg_soc_arriving": _r2(sum(s["soc_start_pct"] or 0 for s in in_bin) / count) if count else 0.0,
                    "avg_soc_departing": _r2(sum(s["soc_end_pct"] or 0 for s in in_bin) / count) if count else 0.0,
                    "avg_session_duration_min": _r2(sum(s["duration_min"] or 0 for s in in_bin) / count) if count else 0.0,
                    "avg_energy_per_session_kwh": _r2(energy / count) if count else 0.0,
                    "total_energy_delivered_kwh": _r2(energy),
                    "demand_kwh_15min": _r2(energy),
                    "demand_kwh_1h": _r2(energy * 4),
                    "demand_kwh_24h": _r2(energy * 96),
                    "ev_types": EV_TYPE_MIX,
                    "peak_hour_today": cur_ts.hour,
                    "demand_forecast_1h_kwh": _r2(energy * 4),
                }
                rows.append((z.id, cur_ts.isoformat(), json.dumps(payload)))
            cur_ts = bin_end
        await db.executemany(
            "INSERT INTO history(zone_id, timestamp, payload) VALUES(?,?,?)", rows,
        )
        await db.commit()
        log.info("ev_session backfill done rows=%d", len(rows))


async def _persist_and_publish(payloads: list[dict[str, Any]]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT INTO history(zone_id, timestamp, payload) VALUES(?,?,?)",
            [(p["zone_id"], p["timestamp"], json.dumps(p)) for p in payloads],
        )
        await db.commit()
    for p in payloads:
        await redis_client.publish(STREAM, p)


async def run() -> None:
    while True:
        try:
            now = _now()
            payloads = [await _zone_metrics(z, now) for z in ZONES]
            await _persist_and_publish(payloads)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("ev_session tick failed")
        await asyncio.sleep(TICK_EV)


# ─────────────── Endpoints ───────────────
@router.get("/zones/snapshot")
async def zones_snapshot() -> dict[str, Any]:
    out = []
    async with aiosqlite.connect(DB_PATH) as db:
        for z in ZONES:
            cur = await db.execute(
                "SELECT payload FROM history WHERE zone_id=? ORDER BY timestamp DESC LIMIT 1", (z.id,),
            )
            row = await cur.fetchone()
            if row:
                out.append(json.loads(row[0]))
    return {
        "node_id": NODE_ID,
        "timestamp": _now().isoformat(),
        "zones": out,
    }


@router.get("/zone/{zone_id}/metrics")
async def zone_metrics(zone_id: str, hours: int = Query(24, ge=1, le=24 * 7)) -> dict[str, Any]:
    if zone_id not in ZONES_BY_ID:
        raise HTTPException(status_code=404, detail=f"zone {zone_id} not found")
    since = (_now() - timedelta(hours=hours)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT timestamp, payload FROM history WHERE zone_id=? AND timestamp>=? ORDER BY timestamp",
            (zone_id, since),
        )
        rows = await cur.fetchall()
    return {
        "zone_id": zone_id,
        "node_id": NODE_ID,
        "timestamp": _now().isoformat(),
        "window_hours": hours,
        "count": len(rows),
        "points": [json.loads(r[1]) for r in rows],
    }


@router.get("/fleet/summary")
async def fleet_summary() -> dict[str, Any]:
    snap = await zones_snapshot()
    zones = snap["zones"]
    return {
        "node_id": NODE_ID,
        "timestamp": _now().isoformat(),
        "total_active_sessions": sum(z["active_sessions"] for z in zones),
        "total_queued_evs": sum(z["queued_evs"] for z in zones),
        "total_chargers": sum(z["total_chargers"] for z in zones),
        "available_chargers": sum(z["available_chargers"] for z in zones),
        "fleet_utilization_pct": _r2(
            sum(z["utilization_pct"] * z["total_chargers"] for z in zones) /
            max(1, sum(z["total_chargers"] for z in zones))
        ),
        "total_demand_kwh_15min": _r2(sum(z["demand_kwh_15min"] for z in zones)),
        "total_demand_kwh_24h": _r2(sum(z["demand_kwh_24h"] for z in zones)),
        "ev_types": EV_TYPE_MIX,
        "zones": zones,
    }

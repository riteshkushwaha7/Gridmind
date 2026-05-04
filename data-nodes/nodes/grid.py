"""Node 2 — Distribution feeder / transformer monitor per zone."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, Query

import redis_client
from config import (
    BACKFILL_DAYS,
    BASE_LOAD_PROFILES,
    DATA_DIR,
    STREAMS,
    TICK_GRID,
    TIMEZONE_OFFSET_HOURS,
    ZONES,
    ZONES_BY_ID,
    transformer_limit_kw,
)

NODE_ID = "grid"
STREAM = STREAMS["grid"]
EV_STREAM = STREAMS["ev_session"]
DB_PATH = os.path.join(DATA_DIR, "grid.db")
log = logging.getLogger("gridmind.grid")
router = APIRouter()

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id   TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_grid_zone_ts ON history(zone_id, timestamp);
"""

# Per-zone running peak today
PEAK_TODAY: dict[str, tuple[str, float]] = {}  # zone_id → (date_iso, peak_kw)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _r2(x: float) -> float:
    return round(float(x), 2)


def _ist(now_utc: datetime) -> datetime:
    return now_utc + timedelta(hours=TIMEZONE_OFFSET_HOURS)


def _base_load(zone_type: str, now_utc: datetime) -> float:
    profile = BASE_LOAD_PROFILES[zone_type]
    h = _ist(now_utc).hour
    return profile[h] * random.uniform(0.95, 1.05)


def _feeder_status(load: float, capacity: float, transformer_lim: float) -> tuple[str, bool]:
    if load > capacity:
        return "OVERLOAD", True
    if load > transformer_lim:
        return "CONSTRAINED", True
    if load > 0.85 * capacity:
        return "WARNING", False
    return "NORMAL", False


def _voltage_pu(load: float, capacity: float) -> float:
    # Light loading slightly above 1.0; heavy loading droops toward 0.93
    util = min(1.2, load / max(1.0, capacity))
    pu = 1.02 - 0.10 * util + random.uniform(-0.005, 0.005)
    return _r2(max(0.90, min(1.06, pu)))


def _frequency_hz() -> float:
    return _r2(50.0 + random.uniform(-0.05, 0.05))


def _power_factor(util: float) -> float:
    pf = 0.97 - 0.10 * util + random.uniform(-0.01, 0.01)
    return _r2(max(0.85, min(0.98, pf)))


def _peak_today(zone_id: str, today_iso: str, candidate_kw: float) -> float:
    cur = PEAK_TODAY.get(zone_id)
    if cur is None or cur[0] != today_iso:
        PEAK_TODAY[zone_id] = (today_iso, candidate_kw)
        return candidate_kw
    if candidate_kw > cur[1]:
        PEAK_TODAY[zone_id] = (today_iso, candidate_kw)
        return candidate_kw
    return cur[1]


async def _ev_load_for_zone(zone_id: str) -> tuple[float, int]:
    """(ev_load_kw, active_evs) — read from ev_session latest payload, fallback synth."""
    payload = await redis_client.get_latest(EV_STREAM)
    # ev_session publishes one message per zone in turn; we cannot rely on
    # a single key holding *all* zones. Fall back to ev_session sqlite below.
    if payload and payload.get("zone_id") == zone_id:
        kwh_15m = float(payload.get("demand_kwh_15min", 0.0))
        ev_kw = kwh_15m * 4.0
        return _r2(ev_kw), int(payload.get("active_sessions", 0))
    # SQLite lookup of latest ev_session row for zone
    try:
        ev_db = os.path.join(DATA_DIR, "ev_session.db")
        async with aiosqlite.connect(ev_db) as db:
            cur = await db.execute(
                "SELECT payload FROM history WHERE zone_id=? ORDER BY timestamp DESC LIMIT 1",
                (zone_id,),
            )
            row = await cur.fetchone()
        if row:
            p = json.loads(row[0])
            return _r2(float(p.get("demand_kwh_15min", 0.0)) * 4.0), int(p.get("active_sessions", 0))
    except Exception:
        pass
    # Synthetic fallback
    return _r2(random.uniform(20, 80)), random.randint(2, 10)


def _build_payload(zone, now: datetime, base_kw: float, ev_kw: float, active_evs: int) -> dict[str, Any]:
    total = base_kw + ev_kw
    cap = zone.feeder_capacity_kw
    txlim = transformer_limit_kw(zone)
    headroom = cap - total
    util = total / cap if cap else 1.0
    status, constraint = _feeder_status(total, cap, txlim)
    today = _ist(now).date().isoformat()
    peak = _peak_today(zone.id, today, total)
    dr_active = status in ("CONSTRAINED", "OVERLOAD") or _ist(now).hour in (19, 20, 21)
    return {
        "zone_id": zone.id,
        "feeder_id": f"BESCOM-F-{zone.id}",
        "node_id": NODE_ID,
        "timestamp": now.isoformat(),
        "feeder_capacity_kw": _r2(cap),
        "transformer_capacity_kva": _r2(zone.transformer_kva),
        "transformer_limit_kw": _r2(txlim),
        "base_load_kw": _r2(base_kw),
        "ev_load_kw": _r2(ev_kw),
        "total_load_kw": _r2(total),
        "headroom_kw": _r2(headroom),
        "headroom_pct": _r2(headroom / cap * 100.0) if cap else 0.0,
        "load_factor": _r2(util),
        "power_factor": _power_factor(util),
        "voltage_pu": _voltage_pu(total, cap),
        "frequency_hz": _frequency_hz(),
        "active_evs": active_evs,
        "feeder_status": status,
        "constraint_flag": constraint,
        "peak_today_kw": _r2(peak),
        "demand_response_active": dr_active,
    }


async def init() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def backfill() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM history")
        if (await cur.fetchone())[0] > 0:
            return
        end = _now().replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(days=BACKFILL_DAYS)
        rows: list[tuple] = []
        cur_ts = start
        while cur_ts < end:
            for z in ZONES:
                base = _base_load(z.type, cur_ts)
                # synthetic EV contribution proportional to base profile shape
                ev = base * random.uniform(0.05, 0.30)
                payload = _build_payload(z, cur_ts, base, ev, max(1, int(ev / 7)))
                rows.append((z.id, payload["timestamp"], json.dumps(payload)))
            cur_ts += timedelta(minutes=15)
        await db.executemany(
            "INSERT INTO history(zone_id, timestamp, payload) VALUES(?,?,?)", rows,
        )
        await db.commit()
        log.info("grid backfill done rows=%d", len(rows))


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
            payloads = []
            for z in ZONES:
                base = _base_load(z.type, now)
                ev_kw, active = await _ev_load_for_zone(z.id)
                payloads.append(_build_payload(z, now, base, ev_kw, active))
            await _persist_and_publish(payloads)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("grid tick failed")
        await asyncio.sleep(TICK_GRID)


# ─────────────── Endpoints ───────────────
@router.get("/feeder/{zone_id}/status")
async def feeder_status(zone_id: str) -> dict[str, Any]:
    if zone_id not in ZONES_BY_ID:
        raise HTTPException(status_code=404, detail=f"zone {zone_id} not found")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT payload FROM history WHERE zone_id=? ORDER BY timestamp DESC LIMIT 1",
            (zone_id,),
        )
        row = await cur.fetchone()
    if row:
        return json.loads(row[0])
    z = ZONES_BY_ID[zone_id]
    base = _base_load(z.type, _now())
    return _build_payload(z, _now(), base, 0.0, 0)


@router.get("/feeder/{zone_id}/history")
async def feeder_history(zone_id: str, hours: int = Query(24, ge=1, le=24 * 7)) -> dict[str, Any]:
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


@router.get("/feeders/summary")
async def feeders_summary() -> dict[str, Any]:
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
        "feeder_count": len(out),
        "total_capacity_kw": _r2(sum(p["feeder_capacity_kw"] for p in out)),
        "total_load_kw": _r2(sum(p["total_load_kw"] for p in out)),
        "total_headroom_kw": _r2(sum(p["headroom_kw"] for p in out)),
        "constraints": [p["zone_id"] for p in out if p["constraint_flag"]],
        "feeders": out,
    }

"""Node 4 — BESCOM ToU tariff signals."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import aiosqlite
from fastapi import APIRouter, Query

import redis_client
from config import (
    BACKFILL_DAYS,
    DATA_DIR,
    DEMAND_CHARGE_INR_PER_KW,
    EV_INCENTIVE_OFFPEAK_RATE_INR,
    STREAMS,
    TICK_TARIFF,
    TIMEZONE_OFFSET_HOURS,
)

NODE_ID = "tariff"
STREAM = STREAMS["tariff"]
DB_PATH = os.path.join(DATA_DIR, "tariff.db")
log = logging.getLogger("gridmind.tariff")
router = APIRouter()

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    tier TEXT NOT NULL,
    rate_inr_per_kwh REAL NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tariff_ts ON history(timestamp);
"""

TOU_LITERAL: dict[str, dict[str, Any]] = {
    "off_peak":   {"hours": "23:00-06:00", "rate": 4.50},
    "mid_peak":   {"hours": "06:00-17:00", "rate": 7.00},
    "peak":       {"hours": "17:00-21:00", "rate": 9.50},
    "super_peak": {"hours": "21:00-23:00", "rate": 11.00},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _r2(x: float) -> float:
    return round(float(x), 2)


def _ist(now_utc: datetime) -> datetime:
    return now_utc + timedelta(hours=TIMEZONE_OFFSET_HOURS)


def _tier_at(now_utc: datetime) -> tuple[str, float]:
    """Return (tier, rate) for the IST hour at this UTC instant."""
    h = _ist(now_utc).hour
    if 6 <= h < 17:
        return "MID_PEAK", 7.00
    if 17 <= h < 21:
        return "PEAK", 9.50
    if 21 <= h < 23:
        return "SUPER_PEAK", 11.00
    return "OFF_PEAK", 4.50


def _next_change(now_utc: datetime) -> tuple[str, int]:
    ist = _ist(now_utc)
    boundaries_h = [6, 17, 21, 23, 30]  # 30 = next day 06:00
    cur_h = ist.hour + ist.minute / 60.0 + ist.second / 3600.0
    for b in boundaries_h:
        if cur_h < b:
            mins = int((b - cur_h) * 60)
            tier, _ = _tier_at(now_utc + timedelta(minutes=mins + 1))
            return tier, mins
    return "MID_PEAK", int((30 - cur_h) * 60)


def _grid_stress(tier: str, rtp_premium_pct: float) -> str:
    if tier == "SUPER_PEAK":
        return "CRITICAL" if rtp_premium_pct > 10 else "HIGH"
    if tier == "PEAK":
        return "HIGH" if rtp_premium_pct > 5 else "MEDIUM"
    if tier == "MID_PEAK":
        return "MEDIUM" if rtp_premium_pct > 10 else "LOW"
    return "LOW"


def _build_payload(now: datetime, *, zone_id: str = "ALL") -> dict[str, Any]:
    tier, base_rate = _tier_at(now)
    next_tier, mins_to_change = _next_change(now)
    rtp_premium = round(random.uniform(-20, 20), 2)
    rate = _r2(base_rate * (1 + rtp_premium / 100.0))
    incentive_active = tier == "OFF_PEAK"
    return {
        "zone_id": zone_id,
        "node_id": NODE_ID,
        "timestamp": now.isoformat(),
        "pricing_mode": "ToU",
        "tier": tier,
        "rate_inr_per_kwh": rate,
        "next_tier": next_tier,
        "next_tier_change_minutes": mins_to_change,
        "demand_charge_inr_per_kw": DEMAND_CHARGE_INR_PER_KW,
        "tou_schedule": TOU_LITERAL,
        "rtp_premium_pct": rtp_premium,
        "ev_incentive_active": incentive_active,
        "ev_incentive_rate_inr": EV_INCENTIVE_OFFPEAK_RATE_INR if incentive_active else 0.0,
        "grid_stress_signal": _grid_stress(tier, rtp_premium),
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
            payload = _build_payload(cur_ts)
            rows.append((payload["timestamp"], payload["tier"], payload["rate_inr_per_kwh"], json.dumps(payload)))
            cur_ts += timedelta(minutes=15)
        await db.executemany(
            "INSERT INTO history(timestamp, tier, rate_inr_per_kwh, payload) VALUES(?,?,?,?)", rows,
        )
        await db.commit()
        log.info("tariff backfill done rows=%d", len(rows))


async def _persist_and_publish(payload: dict[str, Any]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO history(timestamp, tier, rate_inr_per_kwh, payload) VALUES(?,?,?,?)",
            (payload["timestamp"], payload["tier"], payload["rate_inr_per_kwh"], json.dumps(payload)),
        )
        await db.commit()
    await redis_client.publish(STREAM, payload)


async def run() -> None:
    """Tick every minute to detect tier changes; publish on change + every 15 min."""
    last_tier: str | None = None
    last_publish = _now() - timedelta(minutes=TICK_TARIFF)
    while True:
        try:
            now = _now()
            tier, _ = _tier_at(now)
            tier_changed = (last_tier is not None and tier != last_tier)
            heartbeat = (now - last_publish).total_seconds() >= TICK_TARIFF
            if tier_changed or heartbeat or last_tier is None:
                payload = _build_payload(now)
                await _persist_and_publish(payload)
                last_publish = now
            last_tier = tier
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("tariff tick failed")
        await asyncio.sleep(60)


# ─────────────── Endpoints ───────────────
@router.get("/current")
async def current() -> dict[str, Any]:
    payload = await redis_client.get_latest(STREAM) or _build_payload(_now())
    return payload


@router.get("/forecast")
async def forecast(hours: int = Query(24, ge=1, le=72)) -> dict[str, Any]:
    now = _now()
    points = []
    for i in range(hours):
        t = now + timedelta(hours=i)
        tier, base = _tier_at(t)
        points.append({
            "timestamp": t.isoformat(),
            "tier": tier,
            "rate_inr_per_kwh": _r2(base),
        })
    return {
        "node_id": NODE_ID,
        "timestamp": now.isoformat(),
        "horizon_hours": hours,
        "points": points,
    }


@router.get("/history")
async def history(hours: int = Query(48, ge=1, le=24 * 7)) -> dict[str, Any]:
    since = (_now() - timedelta(hours=hours)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT timestamp, tier, rate_inr_per_kwh FROM history WHERE timestamp>=? ORDER BY timestamp",
            (since,),
        )
        rows = await cur.fetchall()
    return {
        "node_id": NODE_ID,
        "timestamp": _now().isoformat(),
        "window_hours": hours,
        "count": len(rows),
        "points": [dict(r) for r in rows],
    }

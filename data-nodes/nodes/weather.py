"""Node 6 — Weather. Fetches Open-Meteo + adds grid-relevant derived metrics."""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import aiosqlite
import httpx
from fastapi import APIRouter, Query

import redis_client
from config import (
    BACKFILL_DAYS,
    BENGALURU_LAT,
    BENGALURU_LON,
    DATA_DIR,
    OPENMETEO_BASE_URL,
    STREAMS,
    TICK_WEATHER,
)

NODE_ID = "weather"
STREAM = STREAMS["weather"]
DB_PATH = os.path.join(DATA_DIR, "weather.db")
log = logging.getLogger("gridmind.weather")
router = APIRouter()

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    payload   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_weather_ts ON history(timestamp);
"""

OPENMETEO_PARAMS = {
    "latitude": BENGALURU_LAT,
    "longitude": BENGALURU_LON,
    "current": ",".join([
        "temperature_2m", "apparent_temperature", "relative_humidity_2m",
        "wind_speed_10m", "precipitation", "cloud_cover", "visibility",
        "uv_index", "shortwave_radiation",
    ]),
    "timezone": "Asia/Kolkata",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _r2(x: float) -> float:
    return round(float(x), 2)


def _is_monsoon(month: int) -> bool:
    return 6 <= month <= 9


def _condition(cloud: float, precip: float) -> str:
    if precip > 5:
        return "STORMY"
    if precip > 0.5:
        return "RAINY"
    if cloud > 80:
        return "OVERCAST"
    if cloud > 30:
        return "PARTLY_CLOUDY"
    return "CLEAR"


def _ev_demand_modifier(temp_c: float, precip_mm: float) -> float:
    m = 1.0
    if temp_c > 32:
        m += 0.05 * (temp_c - 32) / 5
    if precip_mm > 1:
        m -= 0.10 * min(precip_mm / 10, 1.0)
    return _r2(max(0.8, min(1.2, m)))


def _solar_modifier(cloud_pct: float) -> float:
    return _r2(max(0.1, 1.0 - cloud_pct / 100.0 * 0.85))


def _grid_stress(temp_c: float) -> str:
    if temp_c >= 35:
        return "HIGH"
    if temp_c >= 30:
        return "MEDIUM"
    return "LOW"


def _split_radiation(global_wm2: float, cloud_pct: float) -> tuple[float, float]:
    """Rough Erbs-style split of global into direct and diffuse."""
    diffuse_frac = 0.2 + 0.6 * (cloud_pct / 100.0)
    diffuse = global_wm2 * diffuse_frac
    direct = max(0.0, global_wm2 - diffuse)
    return _r2(direct), _r2(diffuse)


def _synth_payload(now: datetime) -> dict[str, Any]:
    """Fallback synthetic weather when Open-Meteo is unreachable."""
    ist = now + timedelta(hours=5.5)
    h = ist.hour + ist.minute / 60.0
    monsoon = _is_monsoon(ist.month)
    temp = 22 + 8 * math.sin((h - 9) / 24 * 2 * math.pi) + random.uniform(-1, 1)
    cloud = random.uniform(60, 90) if monsoon else random.uniform(10, 30)
    precip = random.choice([0, 0, 0, 0.2, 1.5]) if monsoon else 0.0
    humidity = 80 if monsoon else 55
    wind = random.uniform(5, 18)
    visibility = 8 if precip > 1 else 10
    uv = max(0.0, 9 * math.sin(max(0, (h - 6) / 12) * math.pi)) if 6 <= h <= 18 else 0.0
    global_rad = max(0.0, 1000 * math.sin(max(0, (h - 6) / 12) * math.pi)) * (1 - cloud / 100 * 0.7) if 6 <= h <= 18 else 0.0
    direct, diffuse = _split_radiation(global_rad, cloud)
    payload = {
        "zone_id": "ALL",
        "node_id": NODE_ID,
        "timestamp": now.isoformat(),
        "temperature_c": _r2(temp),
        "feels_like_c": _r2(temp + (humidity - 50) / 50.0),
        "humidity_pct": _r2(humidity + random.uniform(-5, 5)),
        "wind_speed_kmh": _r2(wind),
        "precipitation_mm": _r2(precip),
        "cloud_cover_pct": _r2(cloud),
        "visibility_km": _r2(visibility),
        "uv_index": _r2(uv),
        "direct_radiation_wm2": direct,
        "diffuse_radiation_wm2": diffuse,
        "global_radiation_wm2": _r2(global_rad),
        "is_monsoon": monsoon,
        "weather_condition": _condition(cloud, precip),
        "ev_demand_modifier": _ev_demand_modifier(temp, precip),
        "solar_generation_modifier": _solar_modifier(cloud),
        "grid_stress_weather": _grid_stress(temp),
    }
    return payload


async def _fetch_openmeteo(now: datetime) -> dict[str, Any]:
    url = f"{OPENMETEO_BASE_URL}/forecast"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=OPENMETEO_PARAMS)
            r.raise_for_status()
            data = r.json()
    except Exception:
        log.warning("openmeteo fetch failed; using synthetic payload")
        return _synth_payload(now)

    cur = data.get("current", {})
    temp = float(cur.get("temperature_2m") or 25)
    feels = float(cur.get("apparent_temperature") or temp)
    humidity = float(cur.get("relative_humidity_2m") or 60)
    wind = float(cur.get("wind_speed_10m") or 0)
    precip = float(cur.get("precipitation") or 0)
    cloud = float(cur.get("cloud_cover") or 0)
    visibility_m = float(cur.get("visibility") or 10000)
    uv = float(cur.get("uv_index") or 0)
    global_rad = float(cur.get("shortwave_radiation") or 0)
    direct, diffuse = _split_radiation(global_rad, cloud)
    monsoon = _is_monsoon((now + timedelta(hours=5.5)).month)
    return {
        "zone_id": "ALL",
        "node_id": NODE_ID,
        "timestamp": now.isoformat(),
        "temperature_c": _r2(temp),
        "feels_like_c": _r2(feels),
        "humidity_pct": _r2(humidity),
        "wind_speed_kmh": _r2(wind),
        "precipitation_mm": _r2(precip),
        "cloud_cover_pct": _r2(cloud),
        "visibility_km": _r2(visibility_m / 1000.0),
        "uv_index": _r2(uv),
        "direct_radiation_wm2": direct,
        "diffuse_radiation_wm2": diffuse,
        "global_radiation_wm2": _r2(global_rad),
        "is_monsoon": monsoon,
        "weather_condition": _condition(cloud, precip),
        "ev_demand_modifier": _ev_demand_modifier(temp, precip),
        "solar_generation_modifier": _solar_modifier(cloud),
        "grid_stress_weather": _grid_stress(temp),
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
            payload = _synth_payload(cur_ts)
            rows.append((payload["timestamp"], json.dumps(payload)))
            cur_ts += timedelta(minutes=30)
        await db.executemany("INSERT INTO history(timestamp, payload) VALUES(?,?)", rows)
        await db.commit()
        log.info("weather backfill done rows=%d", len(rows))


async def _persist_and_publish(payload: dict[str, Any]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO history(timestamp, payload) VALUES(?,?)",
            (payload["timestamp"], json.dumps(payload)),
        )
        await db.commit()
    await redis_client.publish(STREAM, payload)


async def run() -> None:
    while True:
        try:
            payload = await _fetch_openmeteo(_now())
            await _persist_and_publish(payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("weather tick failed")
        await asyncio.sleep(TICK_WEATHER)


# ─────────────── Endpoints ───────────────
@router.get("/current")
async def current() -> dict[str, Any]:
    payload = await redis_client.get_latest(STREAM)
    if payload is None:
        payload = await _fetch_openmeteo(_now())
    return payload


@router.get("/forecast")
async def forecast(hours: int = Query(24, ge=1, le=72)) -> dict[str, Any]:
    now = _now()
    url = f"{OPENMETEO_BASE_URL}/forecast"
    params = {
        **OPENMETEO_PARAMS,
        "hourly": "temperature_2m,cloud_cover,precipitation,shortwave_radiation",
        "forecast_hours": hours,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        hourly = data.get("hourly", {})
        times = hourly.get("time") or []
        temps = hourly.get("temperature_2m") or []
        clouds = hourly.get("cloud_cover") or []
        precip = hourly.get("precipitation") or []
        rad = hourly.get("shortwave_radiation") or []
        points = [
            {
                "timestamp": t,
                "temperature_c": _r2(temps[i] if i < len(temps) else 0),
                "cloud_cover_pct": _r2(clouds[i] if i < len(clouds) else 0),
                "precipitation_mm": _r2(precip[i] if i < len(precip) else 0),
                "global_radiation_wm2": _r2(rad[i] if i < len(rad) else 0),
            }
            for i, t in enumerate(times[:hours])
        ]
    except Exception:
        log.warning("forecast fetch failed; returning synthetic forecast")
        points = [
            {**{k: v for k, v in _synth_payload(now + timedelta(hours=i)).items()
                 if k in ("timestamp", "temperature_c", "cloud_cover_pct",
                         "precipitation_mm", "global_radiation_wm2")}}
            for i in range(hours)
        ]
    return {
        "node_id": NODE_ID,
        "timestamp": now.isoformat(),
        "horizon_hours": hours,
        "points": points,
    }

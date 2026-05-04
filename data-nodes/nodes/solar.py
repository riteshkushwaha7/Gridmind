"""Node 3 — Rooftop solar PV per zone. Reads cloud cover from weather node."""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, Query

import redis_client
from config import (
    BACKFILL_DAYS,
    DATA_DIR,
    STREAMS,
    TICK_SOLAR,
    TIMEZONE_OFFSET_HOURS,
    ZONES,
    ZONES_BY_ID,
)

NODE_ID = "solar"
STREAM = STREAMS["solar"]
WEATHER_STREAM = STREAMS["weather"]
DB_PATH = os.path.join(DATA_DIR, "solar.db")
log = logging.getLogger("gridmind.solar")
router = APIRouter()

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id   TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_solar_zone_ts ON history(zone_id, timestamp);
"""

# Per-zone battery SOC carried across ticks.
BATTERY_SOC: dict[str, float] = {z.id: 50.0 for z in ZONES}

# Bengaluru civil sunrise/sunset (approx, fine for simulation)
def _sun_times(d: date) -> tuple[time, time, float]:
    # Day length swings ~10:50 (Dec) – 13:10 (Jun); centred ~12:00 IST
    doy = d.timetuple().tm_yday
    span_h = 12.0 + 1.1 * math.sin(2 * math.pi * (doy - 80) / 365)
    sunrise_h = 12.0 - span_h / 2
    sunset_h = 12.0 + span_h / 2
    sr = time(int(sunrise_h), int((sunrise_h % 1) * 60))
    ss = time(int(sunset_h), int((sunset_h % 1) * 60))
    return sr, ss, round(span_h, 2)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _r2(x: float) -> float:
    return round(float(x), 2)


def _ist_hour(now_utc: datetime) -> float:
    ist = now_utc + timedelta(hours=TIMEZONE_OFFSET_HOURS)
    return ist.hour + ist.minute / 60.0 + ist.second / 3600.0


def _seasonal_peak_wm2(d: date) -> float:
    """± 15 % seasonal swing around 1000 W/m²."""
    doy = d.timetuple().tm_yday
    return 1000.0 * (1.0 + 0.15 * math.sin(2 * math.pi * (doy - 80) / 365))


def _irradiance(now_utc: datetime, cloud_pct: float) -> float:
    h = _ist_hour(now_utc)
    sr, ss, _ = _sun_times((now_utc + timedelta(hours=TIMEZONE_OFFSET_HOURS)).date())
    sr_h = sr.hour + sr.minute / 60.0
    ss_h = ss.hour + ss.minute / 60.0
    if h < sr_h or h > ss_h:
        return 0.0
    # Bell curve over the daylight window, peaking at solar noon (≈12:30 IST)
    span = ss_h - sr_h
    rel = (h - sr_h) / span  # 0..1
    base = math.sin(rel * math.pi) ** 1.5
    peak = _seasonal_peak_wm2((now_utc + timedelta(hours=TIMEZONE_OFFSET_HOURS)).date())
    cloud_atten = 1.0 - (cloud_pct / 100.0) * 0.85
    noise = random.uniform(0.95, 1.05)
    return max(0.0, peak * base * cloud_atten * noise)


def _panel_temp(ambient_c: float, irradiance: float) -> float:
    # NOCT ≈ +25 °C above ambient at 800 W/m² insolation
    return ambient_c + 25.0 * (irradiance / 800.0)


def _efficiency_pct(panel_temp_c: float) -> float:
    # 20 % rated at 25 °C, –0.4 %/°C derating, clamp to [15, 22] window
    eta = 20.0 - 0.4 * (panel_temp_c - 25.0)
    return max(15.0, min(22.0, eta))


def _condition_loss(weather_condition: str) -> float:
    return 0.85 if weather_condition in ("RAINY", "STORMY") else 1.0


async def _weather_inputs() -> tuple[float, float, str]:
    """(cloud_cover_pct, ambient_c, condition) from weather node."""
    w = await redis_client.get_latest(WEATHER_STREAM)
    if w is None:
        return 30.0, 26.0, "PARTLY_CLOUDY"
    return (
        float(w.get("cloud_cover_pct", 30.0)),
        float(w.get("temperature_c", 26.0)),
        str(w.get("weather_condition", "PARTLY_CLOUDY")),
    )


def _build_payload(zone, now: datetime, cloud: float, ambient: float, condition: str) -> dict[str, Any]:
    irr = _irradiance(now, cloud) * _condition_loss(condition)
    panel_t = _panel_temp(ambient, irr)
    eta = _efficiency_pct(panel_t)
    # PV output in kW: capacity × (irr/1000) × (eta / rated_eta=20)
    pv_kw = zone.pv_capacity_kw * (irr / 1000.0) * (eta / 20.0)
    pv_kw = max(0.0, pv_kw)

    soc = BATTERY_SOC[zone.id]
    self_consumption = min(pv_kw, zone.pv_capacity_kw * 0.4)  # half PV → on-site EV
    surplus = max(0.0, pv_kw - self_consumption)
    # Charge battery first if SOC < 95 %, else export
    capacity_kwh = zone.battery_kwh
    chargeable_kwh = max(0.0, (95.0 - soc) / 100.0 * capacity_kwh)
    # Convert per-tick capacity (kW × 0.25 h) to kWh
    tick_h = TICK_SOLAR / 3600.0
    take_kwh = min(surplus * tick_h, chargeable_kwh)
    battery_charge_kw = take_kwh / tick_h if tick_h > 0 else 0.0
    grid_export_kw = surplus - battery_charge_kw
    # Discharge after sundown, slowly
    if pv_kw < 1.0 and soc > 20:
        discharge_kw = min(zone.pv_capacity_kw * 0.2, (soc - 20) / 100.0 * capacity_kwh / max(tick_h, 0.01))
        battery_charge_kw = -discharge_kw
        grid_export_kw = 0.0
        self_consumption = discharge_kw
    # Update SOC
    delta_kwh = battery_charge_kw * tick_h
    new_soc = max(0.0, min(100.0, soc + delta_kwh / capacity_kwh * 100.0))
    BATTERY_SOC[zone.id] = new_soc

    sr, ss, day_len = _sun_times((now + timedelta(hours=TIMEZONE_OFFSET_HOURS)).date())
    forecast_4h = pv_kw * 4 * 0.85  # crude: assume ~85 % of current sustained for 4h

    return {
        "zone_id": zone.id,
        "node_id": NODE_ID,
        "timestamp": now.isoformat(),
        "pv_capacity_kw": _r2(zone.pv_capacity_kw),
        "irradiance_wm2": _r2(irr),
        "temperature_c": _r2(panel_t),
        "cloud_cover_pct": _r2(cloud),
        "pv_output_kw": _r2(pv_kw),
        "pv_efficiency_pct": _r2(eta),
        "battery_soc_pct": _r2(new_soc),
        "battery_capacity_kwh": _r2(capacity_kwh),
        "battery_charge_kw": _r2(battery_charge_kw),
        "grid_export_kw": _r2(grid_export_kw),
        "self_consumption_kw": _r2(self_consumption),
        "forecast_generation_kwh": _r2(forecast_4h),
        "sunrise": sr.isoformat(),
        "sunset": ss.isoformat(),
        "day_length_hours": day_len,
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
        # Reset SOCs to a fixed seed for backfill
        for z in ZONES:
            BATTERY_SOC[z.id] = 50.0
        while cur_ts < end:
            cloud = random.uniform(20, 60)
            ambient = 22 + 6 * math.sin((_ist_hour(cur_ts) - 9) / 24 * 2 * math.pi)
            for z in ZONES:
                payload = _build_payload(z, cur_ts, cloud, ambient, "PARTLY_CLOUDY")
                rows.append((z.id, payload["timestamp"], json.dumps(payload)))
            cur_ts += timedelta(minutes=15)
        await db.executemany(
            "INSERT INTO history(zone_id, timestamp, payload) VALUES(?,?,?)", rows,
        )
        await db.commit()
        # Reset SOCs again so live ticks start fresh
        for z in ZONES:
            BATTERY_SOC[z.id] = 50.0
        log.info("solar backfill done rows=%d", len(rows))


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
            cloud, ambient, cond = await _weather_inputs()
            payloads = [_build_payload(z, now, cloud, ambient, cond) for z in ZONES]
            await _persist_and_publish(payloads)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("solar tick failed")
        await asyncio.sleep(TICK_SOLAR)


# ─────────────── Endpoints ───────────────
@router.get("/{zone_id}/current")
async def current(zone_id: str) -> dict[str, Any]:
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
    cloud, ambient, cond = await _weather_inputs()
    return _build_payload(ZONES_BY_ID[zone_id], _now(), cloud, ambient, cond)


@router.get("/{zone_id}/forecast")
async def forecast(zone_id: str, hours: int = Query(24, ge=1, le=72)) -> dict[str, Any]:
    if zone_id not in ZONES_BY_ID:
        raise HTTPException(status_code=404, detail=f"zone {zone_id} not found")
    z = ZONES_BY_ID[zone_id]
    cloud, ambient, _ = await _weather_inputs()
    now = _now()
    points = []
    for i in range(hours):
        t = now + timedelta(hours=i)
        irr = _irradiance(t, cloud)
        panel_t = _panel_temp(ambient, irr)
        eta = _efficiency_pct(panel_t)
        pv_kw = max(0.0, z.pv_capacity_kw * (irr / 1000.0) * (eta / 20.0))
        points.append({
            "timestamp": t.isoformat(),
            "irradiance_wm2": _r2(irr),
            "pv_output_kw": _r2(pv_kw),
            "pv_kwh": _r2(pv_kw),  # 1-hour bucket
        })
    return {
        "zone_id": zone_id,
        "node_id": NODE_ID,
        "timestamp": now.isoformat(),
        "horizon_hours": hours,
        "points": points,
    }


@router.get("/summary")
async def summary() -> dict[str, Any]:
    out = []
    async with aiosqlite.connect(DB_PATH) as db:
        for z in ZONES:
            cur = await db.execute(
                "SELECT payload FROM history WHERE zone_id=? ORDER BY timestamp DESC LIMIT 1",
                (z.id,),
            )
            row = await cur.fetchone()
            if row:
                out.append(json.loads(row[0]))
    total_pv = _r2(sum(p["pv_output_kw"] for p in out))
    total_cap = _r2(sum(p["pv_capacity_kw"] for p in out))
    return {
        "node_id": NODE_ID,
        "timestamp": _now().isoformat(),
        "total_pv_output_kw": total_pv,
        "total_pv_capacity_kw": total_cap,
        "fleet_yield_pct": _r2(total_pv / total_cap * 100.0) if total_cap else 0.0,
        "zones": out,
    }

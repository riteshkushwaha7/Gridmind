"""Node 1 — OCPP charger event simulator.

Drives a fleet of chargers (one per zone × Zone.chargers) and emits OCPP
events (StartTransaction, MeterValues, StopTransaction, StatusNotification)
according to a time-of-day arrival profile that varies by zone type and
weekday vs weekend.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, Query

import redis_client
from config import (
    ARRIVAL_SCALE,
    BACKFILL_DAYS,
    CHARGER_TYPES,
    CONNECTOR_FAULT_RATE,
    DATA_DIR,
    HOURLY_PROFILES,
    OCPP_VERSIONS,
    SESSION_DURATION_MIN,
    STREAMS,
    TICK_OCPP,
    ZONES,
    ZONES_BY_ID,
)

NODE_ID = "ocpp"
STREAM = STREAMS["ocpp"]
DB_PATH = os.path.join(DATA_DIR, "ocpp.db")
log = logging.getLogger("gridmind.ocpp")
router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _r2(x: float) -> float:
    return round(float(x), 2)


def _weighted(items: list[tuple[Any, float, float]]) -> tuple[Any, float]:
    """items: list of (label, value, weight) → (label, value) sampled by weight."""
    total = sum(w for _, _, w in items)
    pick = random.random() * total
    acc = 0.0
    for label, value, w in items:
        acc += w
        if pick <= acc:
            return label, value
    return items[-1][0], items[-1][1]


# ─────────────── Charger fleet ───────────────
@dataclass
class Charger:
    charger_id: str
    zone_id: str
    connector_id: int
    charger_type: str
    rated_kw: float
    ocpp_version: str
    status: str  # "Available", "Occupied", "Faulted", "Unavailable"
    cumulative_wh: float = 0.0
    session_id: Optional[str] = None


@dataclass
class Session:
    session_id: str
    charger_id: str
    zone_id: str
    connector_id: int
    id_tag: str
    charger_type: str
    rated_kw: float
    ocpp_version: str
    started_at: datetime
    duration_planned_min: float
    soc_start_pct: float
    soc_target_pct: float
    meter_start_wh: float
    last_meter_emit: datetime
    state: str = "active"  # "active" | "stopped"


CHARGERS: dict[str, Charger] = {}
SESSIONS: dict[str, Session] = {}


def _init_fleet() -> None:
    if CHARGERS:
        return
    rng = random.Random(42)  # deterministic fleet
    for z in ZONES:
        for i in range(1, z.chargers + 1):
            label, rated = _weighted(CHARGER_TYPES)
            cid = f"{z.id}-C{i:03d}"
            faulted = rng.random() < CONNECTOR_FAULT_RATE
            CHARGERS[cid] = Charger(
                charger_id=cid,
                zone_id=z.id,
                connector_id=1,
                charger_type=label,
                rated_kw=rated,
                ocpp_version=rng.choice(OCPP_VERSIONS),
                status="Faulted" if faulted else "Available",
            )


# ─────────────── SQLite ───────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    charger_id TEXT NOT NULL,
    zone_id    TEXT NOT NULL,
    id_tag     TEXT NOT NULL,
    charger_type TEXT NOT NULL,
    started_at TEXT NOT NULL,
    stopped_at TEXT,
    duration_min REAL,
    soc_start_pct REAL,
    soc_end_pct   REAL,
    energy_kwh    REAL,
    power_kw      REAL,
    state         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_zone_started ON sessions(zone_id, started_at);
CREATE INDEX IF NOT EXISTS idx_sessions_state        ON sessions(state);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    zone_id   TEXT NOT NULL,
    charger_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_zone_ts ON events(zone_id, timestamp);
"""


async def init() -> None:
    _init_fleet()
    os.makedirs(DATA_DIR, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()
    log.info("ocpp init chargers=%d", len(CHARGERS))


# ─────────────── Event construction ───────────────
def _make_event_payload(
    *,
    charger: Charger,
    session: Optional[Session],
    event_type: str,
    timestamp: datetime,
    error_code: Optional[str] = None,
) -> dict[str, Any]:
    if session:
        elapsed_min = (timestamp - session.started_at).total_seconds() / 60.0
        if session.state == "stopped":
            energy_kwh = (charger.cumulative_wh - session.meter_start_wh) / 1000.0
            power_kw = 0.0
            stopped_at = timestamp
            meter_stop_wh = charger.cumulative_wh
            soc_end = session.soc_target_pct
        else:
            # interpolate SOC linearly across planned duration
            frac = min(1.0, elapsed_min / max(1.0, session.duration_planned_min))
            energy_kwh = (charger.cumulative_wh - session.meter_start_wh) / 1000.0
            power_kw = charger.rated_kw if event_type != "StatusNotification" else 0.0
            stopped_at = None
            meter_stop_wh = None
            soc_end = session.soc_start_pct + frac * (session.soc_target_pct - session.soc_start_pct)
        payload = {
            "charger_id": charger.charger_id,
            "zone_id": charger.zone_id,
            "node_id": NODE_ID,
            "timestamp": timestamp.isoformat(),
            "event_type": event_type,
            "connector_id": charger.connector_id,
            "id_tag": session.id_tag,
            "meter_start_wh": _r2(session.meter_start_wh),
            "meter_stop_wh": _r2(meter_stop_wh) if meter_stop_wh is not None else None,
            "timestamp_start": session.started_at.isoformat(),
            "timestamp_stop": stopped_at.isoformat() if stopped_at else None,
            "duration_minutes": _r2(elapsed_min),
            "energy_delivered_kwh": _r2(energy_kwh) if session.state == "stopped" else None,
            "power_kw": _r2(power_kw),
            "connector_status": "Occupied" if session.state == "active" else "Available",
            "soc_start_pct": _r2(session.soc_start_pct),
            "soc_end_pct": _r2(soc_end),
            "charger_type": charger.charger_type,
            "ocpp_version": charger.ocpp_version,
            "error_code": error_code,
        }
    else:
        payload = {
            "charger_id": charger.charger_id,
            "zone_id": charger.zone_id,
            "node_id": NODE_ID,
            "timestamp": timestamp.isoformat(),
            "event_type": event_type,
            "connector_id": charger.connector_id,
            "id_tag": "",
            "meter_start_wh": _r2(charger.cumulative_wh),
            "meter_stop_wh": None,
            "timestamp_start": timestamp.isoformat(),
            "timestamp_stop": None,
            "duration_minutes": 0.0,
            "energy_delivered_kwh": None,
            "power_kw": 0.0,
            "connector_status": charger.status,
            "soc_start_pct": 0.0,
            "soc_end_pct": 0.0,
            "charger_type": charger.charger_type,
            "ocpp_version": charger.ocpp_version,
            "error_code": error_code,
        }
    return payload


async def _record_event(payload: dict[str, Any]) -> None:
    """Persist event + session-state row, then publish to Redis."""
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO events(timestamp, zone_id, charger_id, event_type, payload) VALUES(?,?,?,?,?)",
            (
                payload["timestamp"],
                payload["zone_id"],
                payload["charger_id"],
                payload["event_type"],
                json.dumps(payload),
            ),
        )
        if payload["event_type"] == "StartTransaction":
            await db.execute(
                """INSERT OR REPLACE INTO sessions
                   (session_id, charger_id, zone_id, id_tag, charger_type, started_at,
                    stopped_at, duration_min, soc_start_pct, soc_end_pct, energy_kwh, power_kw, state)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"{payload['charger_id']}:{payload['timestamp_start']}",
                    payload["charger_id"], payload["zone_id"], payload["id_tag"],
                    payload["charger_type"], payload["timestamp_start"],
                    None, payload["duration_minutes"],
                    payload["soc_start_pct"], payload["soc_end_pct"],
                    0.0, payload["power_kw"], "active",
                ),
            )
        elif payload["event_type"] == "StopTransaction":
            await db.execute(
                """UPDATE sessions
                   SET stopped_at=?, duration_min=?, soc_end_pct=?, energy_kwh=?, power_kw=?, state='stopped'
                   WHERE session_id=?""",
                (
                    payload["timestamp_stop"],
                    payload["duration_minutes"],
                    payload["soc_end_pct"],
                    payload["energy_delivered_kwh"] or 0.0,
                    payload["power_kw"],
                    f"{payload['charger_id']}:{payload['timestamp_start']}",
                ),
            )
        await db.commit()
    await redis_client.publish(STREAM, payload)


# ─────────────── Session lifecycle ───────────────
def _arrival_lambda(zone_type: str, ts: datetime) -> float:
    daykey = "weekday" if ts.weekday() < 5 else "weekend"
    return HOURLY_PROFILES[(zone_type, daykey)][ts.hour] * ARRIVAL_SCALE


def _planned_session(charger: Charger, now: datetime) -> Session:
    lo, hi = SESSION_DURATION_MIN[charger.charger_type]
    duration = random.uniform(lo, hi)
    soc_start = random.uniform(10, 40)
    soc_target = random.uniform(70, 95)
    sid = uuid.uuid4().hex[:12]
    return Session(
        session_id=sid,
        charger_id=charger.charger_id,
        zone_id=charger.zone_id,
        connector_id=charger.connector_id,
        id_tag=f"USR-{uuid.uuid4().hex[:8].upper()}",
        charger_type=charger.charger_type,
        rated_kw=charger.rated_kw,
        ocpp_version=charger.ocpp_version,
        started_at=now,
        duration_planned_min=duration,
        soc_start_pct=soc_start,
        soc_target_pct=soc_target,
        meter_start_wh=charger.cumulative_wh,
        last_meter_emit=now,
    )


async def _start_session(charger: Charger, now: datetime) -> None:
    sess = _planned_session(charger, now)
    SESSIONS[sess.session_id] = sess
    charger.session_id = sess.session_id
    charger.status = "Occupied"
    payload = _make_event_payload(charger=charger, session=sess, event_type="StartTransaction", timestamp=now)
    await _record_event(payload)


async def _advance_active_session(sess: Session, charger: Charger, now: datetime) -> None:
    elapsed_s = (now - sess.last_meter_emit).total_seconds()
    delivered_wh = charger.rated_kw * 1000.0 * (elapsed_s / 3600.0)
    charger.cumulative_wh += delivered_wh
    sess.last_meter_emit = now

    elapsed_min = (now - sess.started_at).total_seconds() / 60.0
    if elapsed_min >= sess.duration_planned_min:
        sess.state = "stopped"
        charger.status = "Available" if random.random() > CONNECTOR_FAULT_RATE / 5 else "Faulted"
        charger.session_id = None
        payload = _make_event_payload(charger=charger, session=sess, event_type="StopTransaction", timestamp=now)
        await _record_event(payload)
        SESSIONS.pop(sess.session_id, None)
    elif random.random() < 0.25:
        payload = _make_event_payload(charger=charger, session=sess, event_type="MeterValues", timestamp=now)
        await _record_event(payload)


async def _tick(now: datetime) -> None:
    # 1. Spawn new sessions per zone according to arrival rate.
    for z in ZONES:
        lam = _arrival_lambda(z.type, now)
        prob_per_tick = lam / 3600.0 * TICK_OCPP
        if random.random() >= prob_per_tick:
            continue
        idle = [c for c in CHARGERS.values() if c.zone_id == z.id and c.status == "Available"]
        if not idle:
            continue
        chosen = random.choice(idle)
        await _start_session(chosen, now)

    # 2. Advance active sessions.
    for sess in list(SESSIONS.values()):
        ch = CHARGERS.get(sess.charger_id)
        if ch is None:
            continue
        await _advance_active_session(sess, ch, now)

    # 3. Occasional StatusNotification heartbeats from idle/faulted chargers.
    if random.random() < 0.05:
        ch = random.choice(list(CHARGERS.values()))
        if ch.session_id is None:
            err = "ConnectorLockFailure" if ch.status == "Faulted" else None
            payload = _make_event_payload(charger=ch, session=None, event_type="StatusNotification", timestamp=now, error_code=err)
            await _record_event(payload)


# ─────────────── Backfill ───────────────
async def backfill() -> None:
    """Generate BACKFILL_DAYS of historical sessions into SQLite."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM sessions")
        existing = (await cur.fetchone())[0]
        if existing > 0:
            log.info("ocpp backfill skipped existing=%d", existing)
            return

        rng = random.Random(123)
        rows: list[tuple] = []
        end = _now().replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(days=BACKFILL_DAYS)
        cur_ts = start
        while cur_ts < end:
            for z in ZONES:
                lam = _arrival_lambda(z.type, cur_ts)
                # poisson approx by drawing N bernoullis at 1-min granularity = lam per hour
                k = sum(1 for _ in range(60) if rng.random() < lam / 60.0)
                for _ in range(k):
                    label, rated = _weighted(CHARGER_TYPES)
                    lo, hi = SESSION_DURATION_MIN[label]
                    dur = rng.uniform(lo, hi)
                    soc_s = rng.uniform(10, 40)
                    soc_e = rng.uniform(70, 95)
                    energy = rated * (dur / 60.0) * rng.uniform(0.7, 0.95)
                    started = cur_ts + timedelta(minutes=rng.uniform(0, 60))
                    stopped = started + timedelta(minutes=dur)
                    cid = f"{z.id}-C{rng.randint(1, z.chargers):03d}"
                    rows.append((
                        f"{cid}:{started.isoformat()}", cid, z.id,
                        f"USR-{uuid.uuid4().hex[:8].upper()}", label,
                        started.isoformat(), stopped.isoformat(),
                        _r2(dur), _r2(soc_s), _r2(soc_e),
                        _r2(energy), _r2(rated), "stopped",
                    ))
            cur_ts += timedelta(hours=1)

        await db.executemany(
            """INSERT OR IGNORE INTO sessions
               (session_id, charger_id, zone_id, id_tag, charger_type, started_at,
                stopped_at, duration_min, soc_start_pct, soc_end_pct, energy_kwh, power_kw, state)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        await db.commit()
        log.info("ocpp backfill done sessions=%d", len(rows))


# ─────────────── Background loop ───────────────
async def run() -> None:
    while True:
        try:
            await _tick(_now())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("ocpp tick failed")
        await asyncio.sleep(TICK_OCPP)


# ─────────────── REST endpoints ───────────────
@router.get("/status/{zone_id}")
async def status_for_zone(zone_id: str) -> dict[str, Any]:
    if zone_id not in ZONES_BY_ID:
        raise HTTPException(status_code=404, detail=f"zone {zone_id} not found")
    chargers = [c for c in CHARGERS.values() if c.zone_id == zone_id]
    return {
        "zone_id": zone_id,
        "node_id": NODE_ID,
        "timestamp": _now().isoformat(),
        "total_chargers": len(chargers),
        "chargers": [
            {
                "charger_id": c.charger_id,
                "charger_type": c.charger_type,
                "rated_kw": _r2(c.rated_kw),
                "connector_id": c.connector_id,
                "status": c.status,
                "session_id": c.session_id,
                "ocpp_version": c.ocpp_version,
                "cumulative_wh": _r2(c.cumulative_wh),
            }
            for c in chargers
        ],
    }


@router.get("/sessions/active/{zone_id}")
async def active_sessions(zone_id: str) -> dict[str, Any]:
    if zone_id not in ZONES_BY_ID:
        raise HTTPException(status_code=404, detail=f"zone {zone_id} not found")
    now = _now()
    active = []
    for s in SESSIONS.values():
        if s.zone_id != zone_id or s.state != "active":
            continue
        ch = CHARGERS.get(s.charger_id)
        elapsed = (now - s.started_at).total_seconds() / 60.0
        active.append({
            "session_id": s.session_id,
            "charger_id": s.charger_id,
            "id_tag": s.id_tag,
            "charger_type": s.charger_type,
            "started_at": s.started_at.isoformat(),
            "duration_min_so_far": _r2(elapsed),
            "duration_planned_min": _r2(s.duration_planned_min),
            "soc_start_pct": _r2(s.soc_start_pct),
            "soc_target_pct": _r2(s.soc_target_pct),
            "energy_delivered_kwh": _r2((ch.cumulative_wh - s.meter_start_wh) / 1000.0) if ch else 0.0,
            "power_kw": _r2(ch.rated_kw) if ch else 0.0,
        })
    return {
        "zone_id": zone_id,
        "node_id": NODE_ID,
        "timestamp": now.isoformat(),
        "active_count": len(active),
        "sessions": active,
    }


@router.get("/sessions/history")
async def sessions_history(zone_id: str = Query(...), hours: int = Query(24, ge=1, le=24 * 7)) -> dict[str, Any]:
    if zone_id not in ZONES_BY_ID:
        raise HTTPException(status_code=404, detail=f"zone {zone_id} not found")
    since = (_now() - timedelta(hours=hours)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM sessions WHERE zone_id=? AND started_at>=? ORDER BY started_at DESC",
            (zone_id, since),
        )
        rows = await cur.fetchall()
    return {
        "zone_id": zone_id,
        "node_id": NODE_ID,
        "timestamp": _now().isoformat(),
        "window_hours": hours,
        "session_count": len(rows),
        "sessions": [dict(r) for r in rows],
    }

"""PostgreSQL client + DDL for backend services (asyncpg pool)."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

import asyncpg

from config import POSTGRES_URL

log = logging.getLogger("gridmind.postgres")

_pool: Optional[asyncpg.Pool] = None
_lock = asyncio.Lock()


DDL = """
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id      TEXT PRIMARY KEY,
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_for_minutes INT NOT NULL,
    payload          JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_schedules_generated ON schedules (generated_at DESC);

CREATE TABLE IF NOT EXISTS schedule_overrides (
    id           BIGSERIAL PRIMARY KEY,
    schedule_id  TEXT,
    zone_id      TEXT NOT NULL,
    operator_id  TEXT NOT NULL,
    power_kw     DOUBLE PRECISION NOT NULL,
    reason       TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_overrides_zone ON schedule_overrides (zone_id, created_at DESC);

CREATE TABLE IF NOT EXISTS zone_recommendations (
    id          BIGSERIAL PRIMARY KEY,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_version TEXT,
    payload     JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_recs_computed ON zone_recommendations (computed_at DESC);

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    service     TEXT NOT NULL,
    action      TEXT NOT NULL,
    actor       TEXT,
    correlation_id TEXT,
    payload     JSONB
);
CREATE INDEX IF NOT EXISTS idx_audit_service_ts ON audit_log (service, ts DESC);
"""


async def connect() -> asyncpg.Pool:
    global _pool
    async with _lock:
        if _pool is None:
            _pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=8, timeout=10)
            async with _pool.acquire() as conn:
                await conn.execute(DDL)
    return _pool


async def close() -> None:
    global _pool
    async with _lock:
        if _pool is not None:
            await _pool.close()
            _pool = None


async def healthy() -> bool:
    if _pool is None:
        return False
    try:
        async with _pool.acquire() as conn:
            return (await conn.fetchval("SELECT 1")) == 1
    except Exception:
        return False


# ─────────────── Inserts ───────────────
async def insert_schedule(schedule_id: str, valid_for_minutes: int, payload: dict[str, Any]) -> None:
    pool = await connect()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO schedules(schedule_id, valid_for_minutes, payload) VALUES($1, $2, $3::jsonb) "
            "ON CONFLICT (schedule_id) DO NOTHING",
            schedule_id, valid_for_minutes, json.dumps(payload, default=str),
        )


async def insert_override(*, schedule_id: Optional[str], zone_id: str, operator_id: str, power_kw: float, reason: str) -> int:
    pool = await connect()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO schedule_overrides(schedule_id, zone_id, operator_id, power_kw, reason) "
            "VALUES($1, $2, $3, $4, $5) RETURNING id",
            schedule_id, zone_id, operator_id, power_kw, reason,
        )


async def insert_recommendations(model_version: str, payload: dict[str, Any]) -> None:
    pool = await connect()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO zone_recommendations(model_version, payload) VALUES($1, $2::jsonb)",
            model_version, json.dumps(payload, default=str),
        )


async def insert_audit(*, service: str, action: str, actor: Optional[str], correlation_id: Optional[str], payload: Optional[dict[str, Any]] = None) -> None:
    pool = await connect()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO audit_log(service, action, actor, correlation_id, payload) "
            "VALUES($1, $2, $3, $4, $5::jsonb)",
            service, action, actor, correlation_id,
            json.dumps(payload or {}, default=str),
        )


# ─────────────── Selects ───────────────
async def latest_schedule() -> Optional[dict[str, Any]]:
    pool = await connect()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT schedule_id, generated_at, valid_for_minutes, payload "
            "FROM schedules ORDER BY generated_at DESC LIMIT 1",
        )
    if not row:
        return None
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return payload


async def latest_recommendations() -> Optional[dict[str, Any]]:
    pool = await connect()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT computed_at, model_version, payload "
            "FROM zone_recommendations ORDER BY computed_at DESC LIMIT 1",
        )
    if not row:
        return None
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return payload

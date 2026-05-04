"""Redis Streams publisher + cross-node hot-cache for GRIDMIND data-nodes.

Each `publish(stream, payload)` call does two things:
1. XADD the JSON payload to the stream (with approximate MAXLEN trim).
2. SET `latest:<stream>` and update an in-process cache so peer nodes
   can read each other's most recent value without round-tripping Redis.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import redis.asyncio as redis

from config import REDIS_URL, STREAM_MAXLEN

log = logging.getLogger("gridmind.redis")

_client: redis.Redis | None = None
_lock = asyncio.Lock()

# In-process latest payload by stream name. Mirrors `latest:<stream>` in Redis.
LATEST: dict[str, dict[str, Any]] = {}

START_TIME = time.time()


async def connect() -> None:
    global _client
    async with _lock:
        if _client is not None:
            return
        _client = redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            health_check_interval=30,
        )
        await _client.ping()
        log.info("redis connected url=%s", REDIS_URL)


async def close() -> None:
    global _client
    async with _lock:
        if _client is None:
            return
        try:
            await _client.aclose()
        finally:
            _client = None


def _json_default(o: Any) -> Any:
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if hasattr(o, "value"):
        return o.value
    return str(o)


async def publish(stream: str, payload: dict[str, Any]) -> str | None:
    """Publish payload. Always updates in-process LATEST; Redis is best-effort."""
    LATEST[stream] = payload
    if _client is None:
        return None
    body = json.dumps(payload, default=_json_default, separators=(",", ":"))
    try:
        msg_id = await _client.xadd(
            stream,
            {"data": body},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
        await _client.set(f"latest:{stream}", body, ex=3600)
        return msg_id
    except Exception:
        log.exception("redis publish failed stream=%s", stream)
        return None


async def get_latest(stream: str) -> dict[str, Any] | None:
    """In-process first; falls back to `latest:<stream>` in Redis."""
    if stream in LATEST:
        return LATEST[stream]
    if _client is None:
        return None
    try:
        body = await _client.get(f"latest:{stream}")
        return json.loads(body) if body else None
    except Exception:
        log.exception("redis get_latest failed stream=%s", stream)
        return None


async def healthy() -> bool:
    if _client is None:
        return False
    try:
        return bool(await _client.ping())
    except Exception:
        return False


def uptime_seconds() -> int:
    return int(time.time() - START_TIME)

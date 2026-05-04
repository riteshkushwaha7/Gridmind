"""Redis Streams consumer + helper for backend services."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Callable, Optional

import redis.asyncio as redis

from config import REDIS_URL

log = logging.getLogger("gridmind.redis")

_client: Optional[redis.Redis] = None
_lock = asyncio.Lock()


async def connect() -> redis.Redis:
    global _client
    async with _lock:
        if _client is None:
            _client = redis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                health_check_interval=30,
            )
            await _client.ping()
    return _client


async def close() -> None:
    global _client
    async with _lock:
        if _client is not None:
            await _client.aclose()
            _client = None


def client() -> redis.Redis:
    if _client is None:
        raise RuntimeError("redis_consumer.connect() not called")
    return _client


async def healthy() -> bool:
    if _client is None:
        return False
    try:
        return bool(await _client.ping())
    except Exception:
        return False


async def get_latest(stream: str) -> Optional[dict[str, Any]]:
    """Fetch latest payload from `latest:<stream>` (set by data-nodes)."""
    c = await connect()
    body = await c.get(f"latest:{stream}")
    return json.loads(body) if body else None


async def cache_get(key: str) -> Optional[dict[str, Any]]:
    c = await connect()
    body = await c.get(key)
    return json.loads(body) if body else None


async def cache_set(key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
    c = await connect()
    await c.set(key, json.dumps(payload, default=str), ex=ttl_seconds)


async def consume(
    streams: list[str],
    *,
    group: str,
    consumer: str,
    handler: Callable[[str, dict[str, Any]], "asyncio.Future | Any"],
    block_ms: int = 5000,
    count: int = 100,
) -> None:
    """Long-running consumer over a Redis Streams consumer group.

    Creates the group on each stream (idempotent) and dispatches each
    decoded payload to `handler(stream_name, payload)`.
    """
    c = await connect()
    for s in streams:
        try:
            await c.xgroup_create(s, group, id="$", mkstream=True)
        except redis.ResponseError:
            pass  # BUSYGROUP — already exists

    streams_arg = {s: ">" for s in streams}
    while True:
        try:
            res = await c.xreadgroup(group, consumer, streams_arg, count=count, block=block_ms)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("xreadgroup failed; backing off")
            await asyncio.sleep(2)
            continue

        for stream_name, msgs in res:
            ack_ids: list[str] = []
            for msg_id, fields in msgs:
                body = fields.get("data") if isinstance(fields, dict) else None
                if not body:
                    ack_ids.append(msg_id)
                    continue
                try:
                    payload = json.loads(body)
                    out = handler(stream_name, payload)
                    if asyncio.iscoroutine(out):
                        await out
                except Exception:
                    log.exception("handler failed stream=%s msg=%s", stream_name, msg_id)
                ack_ids.append(msg_id)
            if ack_ids:
                await c.xack(stream_name, group, *ack_ids)


async def stream_tail(stream: str, count: int = 50) -> list[dict[str, Any]]:
    """Fetch the last `count` payloads from a stream (no consumer group)."""
    c = await connect()
    res = await c.xrevrange(stream, count=count)
    out: list[dict[str, Any]] = []
    for _, fields in res:
        body = fields.get("data") if isinstance(fields, dict) else None
        if body:
            try:
                out.append(json.loads(body))
            except json.JSONDecodeError:
                continue
    out.reverse()
    return out

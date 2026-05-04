"""Async HTTP client with circuit-breaker-style retry for inter-service calls."""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from shared.observability import correlation_id

log = logging.getLogger("gridmind.http")

_TRANSIENT = (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.PoolTimeout)


def _headers(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    h = {"X-Correlation-ID": correlation_id() or ""}
    if extra:
        h.update(extra)
    return h


async def _request(method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    timeout = kwargs.pop("timeout", 5.0)
    headers = _headers(kwargs.pop("headers", None))
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.2, min=0.2, max=2.0),
            retry=retry_if_exception_type(_TRANSIENT),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=timeout) as cli:
                    r = await cli.request(method, url, headers=headers, **kwargs)
                    r.raise_for_status()
                    return r.json()
    except RetryError as e:
        log.error("upstream retries exhausted url=%s err=%s", url, e)
        raise
    raise RuntimeError("unreachable")


async def get(url: str, **kwargs: Any) -> dict[str, Any]:
    return await _request("GET", url, **kwargs)


async def post(url: str, *, json: Optional[dict[str, Any]] = None, **kwargs: Any) -> dict[str, Any]:
    return await _request("POST", url, json=json, **kwargs)

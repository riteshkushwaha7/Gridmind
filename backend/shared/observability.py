"""Cross-cutting concerns: JSON logging, correlation IDs, Prometheus metrics."""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from config import FRONTEND_ORIGIN, LOG_LEVEL

CORRELATION_ID: ContextVar[str | None] = ContextVar("correlation_id", default=None)


# ─────────────── JSON logging ───────────────
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        cid = CORRELATION_ID.get()
        if cid:
            out["correlation_id"] = cid
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(LOG_LEVEL)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# ─────────────── Prometheus metrics ───────────────
REQUEST_COUNT = Counter(
    "gridmind_requests_total",
    "Total HTTP requests",
    ("service", "method", "path", "status"),
)
REQUEST_LATENCY = Histogram(
    "gridmind_request_latency_seconds",
    "Request latency seconds",
    ("service", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.5, 5.0, 10.0),
)


# ─────────────── Middleware + lifecycle ───────────────
def install_observability(app: FastAPI, *, service: str) -> None:
    """Install JSON logging, correlation IDs, CORS, /metrics, and global exc handler."""
    setup_logging()
    log = logging.getLogger(f"gridmind.{service}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in FRONTEND_ORIGIN.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    @app.middleware("http")
    async def _wrap(request: Request, call_next):
        cid = request.headers.get("x-correlation-id") or uuid.uuid4().hex
        token = CORRELATION_ID.set(cid)
        path = request.url.path
        t0 = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as exc:
            log.exception("unhandled error path=%s", path)
            response = JSONResponse(
                status_code=500,
                content={
                    "error": exc.__class__.__name__,
                    "detail": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "correlation_id": cid,
                },
            )
        finally:
            REQUEST_COUNT.labels(service, request.method, path, str(status)).inc()
            REQUEST_LATENCY.labels(service, path).observe(time.perf_counter() - t0)
            CORRELATION_ID.reset(token)
        response.headers["X-Correlation-ID"] = cid
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def correlation_id() -> str | None:
    return CORRELATION_ID.get()


_START = time.time()
def uptime_seconds() -> int:
    return int(time.time() - _START)

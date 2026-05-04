"""GRIDMIND data-nodes — single FastAPI app exposing 6 simulator routers."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import redis_client
from config import DATA_DIR, SERVICE_NAME, SERVICE_PORT
from nodes import ev_session, grid, ocpp, solar, tariff, weather

# ───────────── structured JSON logging ─────────────
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        for k, v in record.__dict__.items():
            if k in ("args", "msg", "levelname", "name", "exc_info", "exc_text",
                     "stack_info", "created", "msecs", "relativeCreated",
                     "levelno", "pathname", "filename", "module", "lineno",
                     "funcName", "thread", "threadName", "processName",
                     "process", "taskName"):
                continue
            try:
                json.dumps(v)
                out[k] = v
            except Exception:
                out[k] = str(v)
        return json.dumps(out, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


log = logging.getLogger("gridmind.main")

NODES = (ocpp, grid, solar, tariff, ev_session, weather)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    os.makedirs(DATA_DIR, exist_ok=True)

    try:
        await redis_client.connect()
    except Exception:
        log.exception("redis unavailable at startup — continuing in degraded mode")

    # Initialise per-node SQLite schemas + in-memory state.
    await asyncio.gather(*(n.init() for n in NODES))

    # Backfill 7 days of synthetic history.
    await asyncio.gather(*(n.backfill() for n in NODES))

    # Launch periodic publishers as background tasks.
    bg: list[asyncio.Task] = [asyncio.create_task(n.run(), name=n.NODE_ID) for n in NODES]
    log.info("data-nodes ready", extra={"nodes": [n.NODE_ID for n in NODES]})

    try:
        yield
    finally:
        for t in bg:
            t.cancel()
        await asyncio.gather(*bg, return_exceptions=True)
        await redis_client.close()


app = FastAPI(
    title="GRIDMIND data-nodes",
    version="1.0.0",
    description="Simulators for OCPP, grid, solar, tariff, EV-session, weather.",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": exc.__class__.__name__,
            "detail": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "node_id": SERVICE_NAME,
        "nodes": [n.NODE_ID for n in NODES],
        "redis_connected": await redis_client.healthy(),
        "uptime_seconds": redis_client.uptime_seconds(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Mount routers.
app.include_router(ocpp.router,       prefix="/ocpp",    tags=["ocpp"])
app.include_router(grid.router,       prefix="/grid",    tags=["grid"])
app.include_router(solar.router,      prefix="/solar",   tags=["solar"])
app.include_router(tariff.router,     prefix="/tariff",  tags=["tariff"])
app.include_router(ev_session.router, prefix="/ev",      tags=["ev"])
app.include_router(weather.router,    prefix="/weather", tags=["weather"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=SERVICE_PORT)

"""APScheduler entrypoint — retrain LSTM every LSTM_RETRAIN_HOURS, then ping
the inference server's /lstm/reload endpoint.

Run as its own container (or as a sidecar to the inference service).
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import LSTM_RETRAIN_HOURS, LSTM_URL
from lstm import train as lstm_train
from shared.observability import setup_logging

log = logging.getLogger("gridmind.lstm.scheduler")


async def _train_then_reload() -> None:
    log.info("scheduled retrain starting")
    try:
        result = await lstm_train.run()
        log.info("retrain complete rmse=%.4f version=%s", result["rmse_overall"], result.get("version"))
    except Exception:
        log.exception("retrain failed")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.post(f"{LSTM_URL}/lstm/reload")
            r.raise_for_status()
            log.info("reload response %s", r.json())
    except Exception:
        log.exception("inference reload failed (will retry next cycle)")


async def main() -> None:
    setup_logging()
    sched = AsyncIOScheduler()
    sched.add_job(
        _train_then_reload,
        IntervalTrigger(hours=LSTM_RETRAIN_HOURS),
        id="lstm_retrain",
        next_run_time=None,
        replace_existing=True,
    )
    sched.start()
    log.info("LSTM scheduler started; cadence=%dh", LSTM_RETRAIN_HOURS)
    # Run an initial training pass on startup so the registry is non-empty.
    await _train_then_reload()
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())

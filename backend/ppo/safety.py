"""Safety filter applied to every PPO action before it reaches the environment
or a real charger.

Two layers:
  1.  Hard cap   : P_final = min(P_AI, P_max_feeder).
  2.  Fallback   : if any zone has feeder_headroom_pct < SAFETY_HEADROOM_FLOOR_PCT,
                   replace the PPO action for that zone with a proportional-fairness
                   allocation across active EVs (80 % of available headroom).

Every override is logged to InfluxDB measurement `safety_events`.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from config import SAFETY_HEADROOM_FLOOR_PCT, ZONES
from shared import influx_client

log = logging.getLogger("gridmind.ppo.safety")


@dataclass
class ZoneSafetyState:
    zone_id: str
    feeder_capacity_kw: float
    feeder_headroom_pct: float
    active_evs: int

    @property
    def headroom_kw(self) -> float:
        return max(0.0, self.feeder_capacity_kw * self.feeder_headroom_pct / 100.0)


@dataclass
class SafetyResult:
    final_kw: np.ndarray            # shape (Z,)
    capped_mask: np.ndarray         # shape (Z,) bool — was hard cap engaged?
    fallback_mask: np.ndarray       # shape (Z,) bool — was fairness fallback used?


def apply(
    *,
    pai_normalized: np.ndarray,            # (Z,) in [0, 1]
    zone_states: list[ZoneSafetyState],
    log_to_influx: bool = True,
) -> SafetyResult:
    assert pai_normalized.shape[0] == len(zone_states)
    z = len(zone_states)
    capped = np.zeros(z, dtype=bool)
    fallback = np.zeros(z, dtype=bool)
    final = np.zeros(z, dtype=np.float32)

    for i, st in enumerate(zone_states):
        p_ai_kw = float(np.clip(pai_normalized[i], 0.0, 1.0)) * st.feeder_capacity_kw
        p_max = st.headroom_kw
        if st.feeder_headroom_pct < SAFETY_HEADROOM_FLOOR_PCT and st.active_evs > 0:
            # Proportional-fairness fallback — share 80 % of headroom across EVs.
            fair = (st.headroom_kw / max(1, st.active_evs)) * 0.8 * st.active_evs
            final_i = min(fair, p_max)
            fallback[i] = True
            capped[i] = p_ai_kw > final_i
        else:
            final_i = min(p_ai_kw, p_max)
            capped[i] = p_ai_kw > p_max
        final[i] = final_i

    if log_to_influx and (capped.any() or fallback.any()):
        asyncio.create_task(_log_overrides(zone_states, pai_normalized, final, capped, fallback))
    return SafetyResult(final_kw=final, capped_mask=capped, fallback_mask=fallback)


async def _log_overrides(
    zone_states: list[ZoneSafetyState],
    pai_norm: np.ndarray,
    final_kw: np.ndarray,
    capped: np.ndarray,
    fallback: np.ndarray,
) -> None:
    now = datetime.now(timezone.utc)
    points = []
    for i, st in enumerate(zone_states):
        if not (capped[i] or fallback[i]):
            continue
        points.append({
            "measurement": "safety_events",
            "tags": {
                "zone_id": st.zone_id,
                "kind": "fallback" if fallback[i] else "cap",
            },
            "fields": {
                "pai_normalized": float(pai_norm[i]),
                "final_kw": float(final_kw[i]),
                "headroom_pct": float(st.feeder_headroom_pct),
                "active_evs": int(st.active_evs),
            },
            "ts": now,
        })
    if points:
        await influx_client.write_points(points)


def state_from_request(zone_payload: list[dict], default_capacity_kw: float = 1500.0) -> list[ZoneSafetyState]:
    """Build zone safety state list aligned to ZONES order."""
    by_id: dict[str, dict] = {p["zone_id"]: p for p in zone_payload}
    out: list[ZoneSafetyState] = []
    for zid in ZONES:
        p = by_id.get(zid, {})
        out.append(ZoneSafetyState(
            zone_id=zid,
            feeder_capacity_kw=float(p.get("feeder_capacity_kw", default_capacity_kw)),
            feeder_headroom_pct=float(p.get("feeder_headroom_pct", 100.0)),
            active_evs=int(p.get("active_evs", 0)),
        ))
    return out

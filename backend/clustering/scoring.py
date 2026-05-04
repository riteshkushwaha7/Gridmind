"""Zone scoring formula:

    Score(z) = α · D(z) + β · G(z) − γ · C(z)

with all components min-max normalised across zones in [0, 1].

D(z) = 0.6 · norm(avg_demand) + 0.4 · norm(growth_rate)
G(z) = 1 − norm(grid_headroom_avg_pct)         # low headroom → high score
C(z) = norm(existing_charger_count)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from config import (
    CHARGER_COST_INR_LAKHS,
    SCORE_ALPHA,
    SCORE_BETA,
    SCORE_GAMMA,
)
from shared.schemas import Action, ChargerType, Priority


@dataclass
class ZoneFeatures:
    zone_id: str
    avg_demand_kwh_daily: float
    demand_growth_rate_pct: float
    peak_demand_kw: float
    demand_variance: float
    grid_headroom_avg_pct: float
    grid_headroom_min_pct: float
    existing_charger_count: int
    charger_utilization_pct: float
    avg_queue_length: float
    ev_adoption_growth_rate: float


def _normalise(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=np.float64)
    lo, hi = float(arr.min()), float(arr.max())
    if hi - lo < 1e-9:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


def score_zones(features: list[ZoneFeatures]) -> list[dict]:
    n = len(features)
    if n == 0:
        return []

    demand_norm = _normalise(f.avg_demand_kwh_daily for f in features)
    growth_norm = _normalise(f.demand_growth_rate_pct for f in features)
    headroom_norm = _normalise(f.grid_headroom_avg_pct for f in features)
    infra_norm = _normalise(f.existing_charger_count for f in features)

    D = 0.6 * demand_norm + 0.4 * growth_norm
    G = 1.0 - headroom_norm
    C = infra_norm
    raw = SCORE_ALPHA * D + SCORE_BETA * G - SCORE_GAMMA * C

    # Re-normalise final score to [0, 1] for stable downstream comparisons.
    rmin, rmax = float(raw.min()), float(raw.max())
    score = (raw - rmin) / (rmax - rmin) if rmax - rmin > 1e-9 else np.zeros_like(raw)

    # Priority bucketing — top 3, middle 4, bottom 3 by sorted score.
    order = np.argsort(-score)
    priorities: list[Priority] = [Priority.LOW] * n
    for rank, idx in enumerate(order):
        if rank < 3:
            priorities[idx] = Priority.HIGH
        elif rank < 7:
            priorities[idx] = Priority.MEDIUM

    out: list[dict] = []
    for i, f in enumerate(features):
        out.append({
            "zone_id": f.zone_id,
            "score": round(float(score[i]), 4),
            "priority": priorities[i],
            "metrics": {
                "avg_demand": round(float(f.avg_demand_kwh_daily), 2),
                "growth_rate": round(float(f.demand_growth_rate_pct), 2),
                "headroom": round(float(f.grid_headroom_avg_pct), 2),
                "existing_chargers": int(f.existing_charger_count),
            },
            "components": {
                "D": round(float(D[i]), 4),
                "G": round(float(G[i]), 4),
                "C": round(float(C[i]), 4),
            },
        })
    return out


def recommend(zone: dict, *, forecast_horizon_days: float = 90.0, avg_kwh_per_charger_day: float = 60.0) -> dict:
    """Decide EXPAND/MONITOR/MAINTAIN + charger spec based on score & metrics."""
    metrics = zone["metrics"]
    growth = max(0.0, metrics["growth_rate"]) / 100.0
    avg_demand = metrics["avg_demand"]
    forecast_extra_kwh = avg_demand * growth * forecast_horizon_days
    chargers_needed = int(math.ceil(forecast_extra_kwh / max(1.0, avg_kwh_per_charger_day)))
    chargers_needed = max(0, min(chargers_needed, 20))

    if zone["priority"] == Priority.HIGH and chargers_needed > 0:
        action = Action.EXPAND
        ctype = ChargerType.DC_Fast_50kW if metrics["headroom"] < 30 else ChargerType.L2_AC_22kW
        reason = f"High score ({zone['score']:.2f}); growth {metrics['growth_rate']:.1f}%/30d; headroom {metrics['headroom']:.0f}%"
    elif zone["priority"] == Priority.MEDIUM:
        action = Action.MONITOR
        ctype = ChargerType.L2_AC_22kW
        chargers_needed = max(0, chargers_needed // 2)
        reason = f"Moderate score ({zone['score']:.2f}); revisit after next replan window"
    else:
        action = Action.MAINTAIN
        ctype = ChargerType.L2_AC_22kW
        chargers_needed = 0
        reason = f"Low score ({zone['score']:.2f}); existing capacity sufficient"

    cost = chargers_needed * CHARGER_COST_INR_LAKHS[ctype.value]
    return {
        "action": action,
        "new_chargers_suggested": chargers_needed,
        "charger_type_suggested": ctype,
        "estimated_cost_inr_lakhs": round(cost, 2),
        "priority_reason": reason,
    }

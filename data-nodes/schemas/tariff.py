from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel


class PricingMode(str, Enum):
    ToU = "ToU"
    RTP = "RTP"
    FLAT = "FLAT"


class Tier(str, Enum):
    OFF_PEAK = "OFF_PEAK"
    MID_PEAK = "MID_PEAK"
    PEAK = "PEAK"
    SUPER_PEAK = "SUPER_PEAK"


class GridStress(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TariffSignal(BaseModel):
    zone_id: str
    node_id: str = "tariff"
    timestamp: datetime
    pricing_mode: PricingMode
    tier: Tier
    rate_inr_per_kwh: float
    next_tier: str
    next_tier_change_minutes: int
    demand_charge_inr_per_kw: float
    tou_schedule: dict[str, Any]
    rtp_premium_pct: float
    ev_incentive_active: bool
    ev_incentive_rate_inr: float
    grid_stress_signal: GridStress

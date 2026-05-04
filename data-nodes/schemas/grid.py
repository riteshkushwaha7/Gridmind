from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class FeederStatus(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CONSTRAINED = "CONSTRAINED"
    OVERLOAD = "OVERLOAD"


class GridSnapshot(BaseModel):
    zone_id: str
    feeder_id: str
    node_id: str = "grid"
    timestamp: datetime
    feeder_capacity_kw: float
    transformer_capacity_kva: float
    transformer_limit_kw: float
    base_load_kw: float
    ev_load_kw: float
    total_load_kw: float
    headroom_kw: float
    headroom_pct: float
    load_factor: float
    power_factor: float
    voltage_pu: float
    frequency_hz: float
    active_evs: int
    feeder_status: FeederStatus
    constraint_flag: bool
    peak_today_kw: float
    demand_response_active: bool

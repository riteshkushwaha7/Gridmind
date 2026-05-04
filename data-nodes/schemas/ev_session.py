from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class EVTypeMix(BaseModel):
    two_wheeler_pct: float
    three_wheeler_pct: float
    four_wheeler_pct: float
    bus_pct: float


class EVAggregate(BaseModel):
    zone_id: str
    node_id: str = "ev_session"
    timestamp: datetime
    active_sessions: int
    queued_evs: int
    available_chargers: int
    total_chargers: int
    utilization_pct: float
    avg_soc_arriving: float
    avg_soc_departing: float
    avg_session_duration_min: float
    avg_energy_per_session_kwh: float
    total_energy_delivered_kwh: float
    demand_kwh_15min: float
    demand_kwh_1h: float
    demand_kwh_24h: float
    ev_types: EVTypeMix
    peak_hour_today: int
    demand_forecast_1h_kwh: float

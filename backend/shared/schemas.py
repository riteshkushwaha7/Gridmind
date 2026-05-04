"""Pydantic v2 schemas shared across services and the gateway."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ─────────────── Common ───────────────
class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: datetime
    correlation_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    uptime_seconds: int
    model_version: Optional[str] = None
    dependencies: dict[str, str] = Field(default_factory=dict)


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# ─────────────── LSTM ───────────────
class ForecastRequest(BaseModel):
    zone_id: str
    horizon_hours: int = Field(default=4, ge=1, le=24)


class ForecastPoint(BaseModel):
    timestamp: datetime
    demand_kwh: float
    confidence_lower: float
    confidence_upper: float


class ForecastResponse(BaseModel):
    zone_id: str
    model_version: str
    generated_at: datetime
    forecast: list[ForecastPoint]
    rmse_last_eval: float
    feature_importance: dict[str, float]


# ─────────────── PPO ───────────────
class ZoneState(BaseModel):
    zone_id: str
    active_evs: int
    avg_soc: float
    feeder_headroom_pct: float
    solar_output_kw: float
    battery_soc: float


class ScheduleRequest(BaseModel):
    zones: list[ZoneState]
    tariff_current: float
    demand_forecast: list[float] = Field(min_length=16, max_length=16)


class ZoneSchedule(BaseModel):
    zone_id: str
    recommended_power_kw: float
    safety_capped: bool
    fallback_active: bool
    charging_cost_inr_per_kwh: float
    estimated_sessions_served: int
    reasoning: str


class ScheduleResponse(BaseModel):
    schedule_id: str
    generated_at: datetime
    valid_for_minutes: int = 15
    schedules: list[ZoneSchedule]
    total_grid_load_kw: float
    peak_reduction_vs_unmanaged_pct: float


class ScheduleOverride(BaseModel):
    zone_id: str
    power_kw: float
    operator_id: str
    reason: str


# ─────────────── Clustering ───────────────
class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Action(str, Enum):
    EXPAND = "EXPAND"
    MONITOR = "MONITOR"
    MAINTAIN = "MAINTAIN"


class ChargerType(str, Enum):
    L2_AC_22kW = "L2_AC_22kW"
    DC_Fast_50kW = "DC_Fast_50kW"


class ZoneRecommendation(BaseModel):
    action: Action
    new_chargers_suggested: int
    charger_type_suggested: ChargerType
    estimated_cost_inr_lakhs: float
    priority_reason: str


class ZoneMetrics(BaseModel):
    avg_demand: float
    growth_rate: float
    headroom: float
    existing_chargers: int


class ZoneRanking(BaseModel):
    zone_id: str
    score: float
    priority: Priority
    cluster_label: int
    is_outlier: bool
    metrics: ZoneMetrics
    recommendation: ZoneRecommendation


class RankingResponse(BaseModel):
    computed_at: datetime
    next_replan: datetime
    zones: list[ZoneRanking]
    silhouette_score: float
    model_version: str


class ReplanResponse(BaseModel):
    job_id: str
    accepted_at: datetime
    status: str = "accepted"


# ─────────────── Dashboard ───────────────
class SystemStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class ZoneSummary(BaseModel):
    zone_id: str
    status: str
    load_pct: float
    active_evs: int
    score: float


class GridTotal(BaseModel):
    total_load_kw: float
    total_capacity_kw: float
    system_headroom_pct: float


class TariffNow(BaseModel):
    tier: str
    rate_inr: float
    next_change_minutes: int


class SolarTotal(BaseModel):
    generation_kw: float
    battery_soc_avg: float
    self_consumption_pct: float


class Alert(BaseModel):
    zone_id: str
    severity: Severity
    message: str
    timestamp: datetime


class DashboardOverview(BaseModel):
    timestamp: datetime
    system_status: SystemStatus
    zones_summary: list[ZoneSummary]
    grid_total: GridTotal
    current_tariff: TariffNow
    solar_total: SolarTotal
    active_sessions_total: int
    peak_reduction_today_pct: float
    cost_savings_today_inr: float
    alerts: list[Alert]

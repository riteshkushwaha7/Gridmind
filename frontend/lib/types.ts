// Types for the GRIDMIND backend gateway responses.
// Mirrors backend/shared/schemas.py 1:1.

export type SystemStatus = "HEALTHY" | "DEGRADED" | "CRITICAL";
export type ZonePriority = "HIGH" | "MEDIUM" | "LOW";
export type TariffTier = "OFF_PEAK" | "MID_PEAK" | "PEAK" | "SUPER_PEAK";
export type FeederStatus = "NORMAL" | "WARNING" | "CONSTRAINED" | "OVERLOAD";
export type AlertSeverity = "INFO" | "WARNING" | "CRITICAL";

// ─────────────── Dashboard ───────────────
export type Alert = {
  zone_id: string;
  severity: AlertSeverity;
  message: string;
  timestamp: string;
};

export type ZoneSummary = {
  zone_id: string;
  status: FeederStatus;
  load_pct: number;
  active_evs: number;
  score: number;
};

export type DashboardOverview = {
  timestamp: string;
  system_status: SystemStatus;
  zones_summary: ZoneSummary[];
  grid_total: {
    total_load_kw: number;
    total_capacity_kw: number;
    system_headroom_pct: number;
  };
  current_tariff: {
    tier: TariffTier;
    rate_inr: number;
    next_change_minutes: number;
  };
  solar_total: {
    generation_kw: number;
    battery_soc_avg: number;
    self_consumption_pct: number;
  };
  active_sessions_total: number;
  peak_reduction_today_pct: number;
  cost_savings_today_inr: number;
  alerts: Alert[];
};

// ─────────────── Forecast ───────────────
export type ForecastPoint = {
  timestamp: string;
  demand_kwh: number;
  confidence_lower: number;
  confidence_upper: number;
};

export type ZoneForecast = {
  zone_id: string;
  model_version: string;
  generated_at: string;
  forecast: ForecastPoint[];
  rmse_last_eval: number;
  feature_importance: Record<string, number>;
};

// ─────────────── Schedule ───────────────
export type ZoneSchedule = {
  zone_id: string;
  recommended_power_kw: number;
  safety_capped: boolean;
  fallback_active: boolean;
  charging_cost_inr_per_kwh: number;
  estimated_sessions_served: number;
  reasoning: string;
};

export type ScheduleResponse = {
  schedule_id: string;
  generated_at: string;
  valid_for_minutes: number;
  schedules: ZoneSchedule[];
  total_grid_load_kw: number;
  peak_reduction_vs_unmanaged_pct: number;
};

// ─────────────── Zone Planning ───────────────
export type ChargerTypeId = "L2_AC_22kW" | "DC_Fast_50kW";

export type ZoneRecommendation = {
  action: "EXPAND" | "MONITOR" | "MAINTAIN";
  new_chargers_suggested: number;
  charger_type_suggested: string;
  estimated_cost_inr_lakhs: number;
  priority_reason: string;
};

export type ZoneRanking = {
  zone_id: string;
  score: number;
  priority: ZonePriority;
  cluster_label: number;
  is_outlier: boolean;
  metrics: {
    avg_demand: number;
    growth_rate: number;
    headroom: number;
    existing_chargers: number;
  };
  recommendation: ZoneRecommendation;
};

export type ZoneRankingResponse = {
  computed_at: string;
  next_replan: string;
  zones: ZoneRanking[];
  silhouette_score: number;
  model_version: string;
};

// ─────────────── Zone Detail ───────────────
export type ZoneDetail = {
  zone_id: string;
  name: string;
  status: FeederStatus;
  feeder_capacity_kw: number;
  demand_history: { timestamp: string; demand_kwh: number }[];
  forecast: ForecastPoint[];
  current_schedule: ZoneSchedule;
  metrics: {
    utilization_pct: number;
    active_evs: number;
    queue_length: number;
    solar_contribution_kw: number;
  };
};

// ─────────────── Health ───────────────
export type SystemHealth = {
  status: string;
  services: Record<string, string>;
};

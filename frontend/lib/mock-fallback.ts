// Empty defaults returned by lib/api.ts when the gateway is unreachable.
// These are NOT mock data — every numeric field is zero and every list is
// empty so the UI renders its EmptyState / Skeleton components rather than
// fake live readings. The contract is: api.ts never throws; downstream
// hooks see well-typed "no data" objects.

import type {
  Alert,
  DashboardOverview,
  ScheduleResponse,
  SystemHealth,
  ZoneDetail,
  ZoneForecast,
  ZoneRankingResponse,
} from "./types";

const NOW = () => new Date().toISOString();

export const MOCK_DASHBOARD: DashboardOverview = {
  timestamp: NOW(),
  system_status: "DEGRADED",
  zones_summary: [],
  grid_total: { total_load_kw: 0, total_capacity_kw: 0, system_headroom_pct: 0 },
  current_tariff: { tier: "MID_PEAK", rate_inr: 0, next_change_minutes: 0 },
  solar_total: { generation_kw: 0, battery_soc_avg: 0, self_consumption_pct: 0 },
  active_sessions_total: 0,
  peak_reduction_today_pct: 0,
  cost_savings_today_inr: 0,
  alerts: [],
};

export function MOCK_FORECAST(zoneId: string, _hours: number): ZoneForecast {
  return {
    zone_id: zoneId,
    model_version: "fallback",
    generated_at: NOW(),
    forecast: [],
    rmse_last_eval: 0,
    feature_importance: {},
  };
}

export const MOCK_FORECAST_ALL: ZoneForecast[] = [];

export const MOCK_SCHEDULE: ScheduleResponse = {
  schedule_id: "fallback",
  generated_at: NOW(),
  valid_for_minutes: 15,
  schedules: [],
  total_grid_load_kw: 0,
  peak_reduction_vs_unmanaged_pct: 0,
};

export const MOCK_ZONE_RANKING: ZoneRankingResponse = {
  computed_at: NOW(),
  next_replan: NOW(),
  zones: [],
  silhouette_score: 0,
  model_version: "fallback",
};

export function MOCK_ZONE_DETAIL(zoneId: string): ZoneDetail {
  return {
    zone_id: zoneId,
    name: zoneId,
    status: "NORMAL",
    feeder_capacity_kw: 0,
    demand_history: [],
    forecast: [],
    current_schedule: {
      zone_id: zoneId,
      recommended_power_kw: 0,
      safety_capped: false,
      fallback_active: false,
      charging_cost_inr_per_kwh: 0,
      estimated_sessions_served: 0,
      reasoning: "Backend unreachable",
    },
    metrics: {
      utilization_pct: 0,
      active_evs: 0,
      queue_length: 0,
      solar_contribution_kw: 0,
    },
  };
}

export const MOCK_ALERTS: Alert[] = [];

export const MOCK_HEALTH: SystemHealth = {
  status: "fallback",
  services: {},
};

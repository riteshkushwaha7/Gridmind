// Bangalore-first scenario data returned by lib/api.ts when the backend is
// intentionally bypassed. Every page reads from these curated mocks so the UI
// mirrors how the system would look with live BESCOM feeds, without needing the
// heavy ML services to run locally. The contract is unchanged: api.ts never
// throws; callers always receive typed payloads.

import type {
  Alert,
  DashboardOverview,
  ForecastPoint,
  ScheduleResponse,
  SystemHealth,
  ZoneDetail,
  ZoneForecast,
  ZoneRanking,
  ZoneRankingResponse,
  ZoneSchedule,
} from "./types";

const clone = <T>(value: T): T =>
  typeof globalThis.structuredClone === "function"
    ? globalThis.structuredClone(value)
    : JSON.parse(JSON.stringify(value));

const base = Date.now();
const iso = (offsetMinutes: number) =>
  new Date(base + offsetMinutes * 60_000).toISOString();

type BangaloreZone = {
  zone_id: string;
  name: string;
  status: ZoneDetail["status"];
  feeder_capacity_kw: number;
  load_pct: number;
  active_evs: number;
  score: number;
  demandProfileKw: number[];
  metrics: ZoneDetail["metrics"];
  schedule: ZoneSchedule;
  ranking: ZoneRanking;
  featureImportance: ZoneForecast["feature_importance"];
};

const BANGALORE_ZONES: BangaloreZone[] = [
  {
    zone_id: "Whitefield",
    name: "Whitefield Tech Park",
    status: "WARNING",
    feeder_capacity_kw: 2900,
    load_pct: 76,
    active_evs: 52,
    score: 0.82,
    demandProfileKw: [
      520, 540, 548, 552, 560, 575, 588, 602, 615, 628, 640, 655, 640, 622, 600,
      584,
    ],
    metrics: {
      utilization_pct: 78,
      active_evs: 52,
      queue_length: 6,
      solar_contribution_kw: 220,
    },
    schedule: {
      zone_id: "Whitefield",
      recommended_power_kw: 540,
      safety_capped: true,
      fallback_active: false,
      charging_cost_inr_per_kwh: 7.25,
      estimated_sessions_served: 38,
      reasoning: "Holding load below 80% feeder headroom",
    },
    ranking: {
      zone_id: "Whitefield",
      score: 0.82,
      priority: "HIGH",
      cluster_label: 0,
      is_outlier: false,
      metrics: {
        avg_demand: 610,
        growth_rate: 5.6,
        headroom: 18,
        existing_chargers: 22,
      },
      recommendation: {
        action: "EXPAND",
        new_chargers_suggested: 4,
        charger_type_suggested: "DC_Fast_50kW",
        estimated_cost_inr_lakhs: 96,
        priority_reason: "Tech corridor load growing 5% MoM; only 18% headroom left",
      },
    },
    featureImportance: {
      tariff: 0.28,
      headroom: 0.2,
      solar: 0.12,
      weather: 0.1,
      sessions: 0.08,
    },
  },
  {
    zone_id: "Koramangala",
    name: "Koramangala",
    status: "NORMAL",
    feeder_capacity_kw: 2100,
    load_pct: 58,
    active_evs: 34,
    score: 0.71,
    demandProfileKw: [
      320, 330, 338, 346, 352, 360, 372, 388, 402, 415, 430, 440, 432, 420, 408,
      392,
    ],
    metrics: {
      utilization_pct: 62,
      active_evs: 34,
      queue_length: 2,
      solar_contribution_kw: 148,
    },
    schedule: {
      zone_id: "Koramangala",
      recommended_power_kw: 360,
      safety_capped: false,
      fallback_active: false,
      charging_cost_inr_per_kwh: 7.25,
      estimated_sessions_served: 24,
      reasoning: "Balancing residential + startup hub evening surge",
    },
    ranking: {
      zone_id: "Koramangala",
      score: 0.71,
      priority: "MEDIUM",
      cluster_label: 1,
      is_outlier: false,
      metrics: {
        avg_demand: 395,
        growth_rate: 3.1,
        headroom: 34,
        existing_chargers: 12,
      },
      recommendation: {
        action: "MAINTAIN",
        new_chargers_suggested: 0,
        charger_type_suggested: "L2_AC_22kW",
        estimated_cost_inr_lakhs: 0,
        priority_reason: "Comfortable headroom; monitor evening peaks",
      },
    },
    featureImportance: {
      tariff: 0.24,
      headroom: 0.18,
      weather: 0.1,
      mobility_events: 0.08,
      solar: 0.07,
    },
  },
  {
    zone_id: "Electronic City",
    name: "Electronic City",
    status: "CONSTRAINED",
    feeder_capacity_kw: 3300,
    load_pct: 84,
    active_evs: 61,
    score: 0.88,
    demandProfileKw: [
      640, 650, 662, 676, 688, 702, 720, 738, 756, 770, 784, 798, 782, 760, 740,
      712,
    ],
    metrics: {
      utilization_pct: 86,
      active_evs: 61,
      queue_length: 9,
      solar_contribution_kw: 250,
    },
    schedule: {
      zone_id: "Electronic City",
      recommended_power_kw: 720,
      safety_capped: true,
      fallback_active: true,
      charging_cost_inr_per_kwh: 7.25,
      estimated_sessions_served: 44,
      reasoning: "PPO output clipped to stay within 85% feeder load",
    },
    ranking: {
      zone_id: "Electronic City",
      score: 0.88,
      priority: "HIGH",
      cluster_label: 0,
      is_outlier: false,
      metrics: {
        avg_demand: 750,
        growth_rate: 6.8,
        headroom: 12,
        existing_chargers: 28,
      },
      recommendation: {
        action: "EXPAND",
        new_chargers_suggested: 6,
        charger_type_suggested: "DC_Fast_50kW",
        estimated_cost_inr_lakhs: 138,
        priority_reason: "Campus commuters & highway spillover saturating feeder",
      },
    },
    featureImportance: {
      headroom: 0.26,
      tariff: 0.21,
      queue: 0.13,
      solar: 0.09,
      weather: 0.07,
    },
  },
  {
    zone_id: "Hebbal",
    name: "Hebbal",
    status: "NORMAL",
    feeder_capacity_kw: 2500,
    load_pct: 49,
    active_evs: 27,
    score: 0.58,
    demandProfileKw: [
      260, 268, 274, 282, 290, 298, 310, 320, 332, 342, 350, 360, 352, 338, 324,
      308,
    ],
    metrics: {
      utilization_pct: 55,
      active_evs: 27,
      queue_length: 1,
      solar_contribution_kw: 132,
    },
    schedule: {
      zone_id: "Hebbal",
      recommended_power_kw: 310,
      safety_capped: false,
      fallback_active: false,
      charging_cost_inr_per_kwh: 7.25,
      estimated_sessions_served: 18,
      reasoning: "Plenty of headroom; keeping reserve for airport corridor",
    },
    ranking: {
      zone_id: "Hebbal",
      score: 0.58,
      priority: "LOW",
      cluster_label: 2,
      is_outlier: false,
      metrics: {
        avg_demand: 320,
        growth_rate: 1.4,
        headroom: 44,
        existing_chargers: 10,
      },
      recommendation: {
        action: "MONITOR",
        new_chargers_suggested: 0,
        charger_type_suggested: "L2_AC_22kW",
        estimated_cost_inr_lakhs: 0,
        priority_reason: "Demand steady; airport expressway buffers load",
      },
    },
    featureImportance: {
      tariff: 0.22,
      tourism: 0.11,
      headroom: 0.18,
      solar: 0.12,
      weather: 0.05,
    },
  },
  {
    zone_id: "Peenya",
    name: "Peenya Industrial",
    status: "WARNING",
    feeder_capacity_kw: 2600,
    load_pct: 69,
    active_evs: 41,
    score: 0.75,
    demandProfileKw: [
      440, 452, 466, 480, 492, 506, 520, 534, 548, 560, 574, 588, 576, 558, 540,
      522,
    ],
    metrics: {
      utilization_pct: 71,
      active_evs: 41,
      queue_length: 4,
      solar_contribution_kw: 205,
    },
    schedule: {
      zone_id: "Peenya",
      recommended_power_kw: 505,
      safety_capped: true,
      fallback_active: false,
      charging_cost_inr_per_kwh: 7.25,
      estimated_sessions_served: 29,
      reasoning: "Industrial feeders close to cap; tapering overnight window",
    },
    ranking: {
      zone_id: "Peenya",
      score: 0.75,
      priority: "MEDIUM",
      cluster_label: 1,
      is_outlier: false,
      metrics: {
        avg_demand: 540,
        growth_rate: 4.1,
        headroom: 24,
        existing_chargers: 16,
      },
      recommendation: {
        action: "EXPAND",
        new_chargers_suggested: 2,
        charger_type_suggested: "DC_Fast_50kW",
        estimated_cost_inr_lakhs: 46,
        priority_reason: "Industrial parks adding fleet depots; pre-empt queues",
      },
    },
    featureImportance: {
      tariff: 0.2,
      headroom: 0.22,
      queue: 0.11,
      solar: 0.09,
      weather: 0.06,
    },
  },
];

const alerts: Alert[] = [
  {
    zone_id: "Electronic City",
    severity: "CRITICAL",
    message: "Feeder 66/11 kV EC-2 fell below 15% headroom for 8 minutes",
    timestamp: iso(-25),
  },
  {
    zone_id: "Whitefield",
    severity: "WARNING",
    message: "PPO capped three connectors at 75 kW to respect tech-park limit",
    timestamp: iso(-18),
  },
  {
    zone_id: "Peenya",
    severity: "INFO",
    message: "Night-shift depot pre-charge brought forward by 30 minutes",
    timestamp: iso(-10),
  },
];

const buildHistory = (series: number[]): ForecastPoint[] =>
  series.map((value, index) => ({
    timestamp: iso(-((series.length - index) * 15)),
    demand_kwh: Math.round(value * 0.85 + 12),
    confidence_lower: 0,
    confidence_upper: 0,
  }));

const buildForecastSeries = (zone: BangaloreZone): ForecastPoint[] =>
  zone.demandProfileKw.map((value, index) => ({
    timestamp: iso((index + 1) * 15),
    demand_kwh: value,
    confidence_lower: Math.round(value * 0.92),
    confidence_upper: Math.round(value * 1.08),
  }));

const zoneForecastMap = new Map<string, ZoneForecast>();
const zoneDetailMap = new Map<string, ZoneDetail>();

BANGALORE_ZONES.forEach((zone) => {
  const forecast = {
    zone_id: zone.zone_id,
    model_version: "blr-sim-2026.05",
    generated_at: iso(0),
    forecast: buildForecastSeries(zone),
    rmse_last_eval: 17.4,
    feature_importance: zone.featureImportance,
  } satisfies ZoneForecast;
  zoneForecastMap.set(zone.zone_id, forecast);

  zoneDetailMap.set(zone.zone_id, {
    zone_id: zone.zone_id,
    name: zone.name,
    status: zone.status,
    feeder_capacity_kw: zone.feeder_capacity_kw,
    demand_history: buildHistory(zone.demandProfileKw).map(({ timestamp, demand_kwh }) => ({
      timestamp,
      demand_kwh,
    })),
    forecast: forecast.forecast,
    current_schedule: zone.schedule,
    metrics: zone.metrics,
  });
});

const totalLoadKw = BANGALORE_ZONES.reduce(
  (sum, zone) => sum + zone.schedule.recommended_power_kw,
  0,
);
const totalCapacityKw = BANGALORE_ZONES.reduce(
  (sum, zone) => sum + zone.feeder_capacity_kw,
  0,
);

export const MOCK_DASHBOARD: DashboardOverview = {
  timestamp: iso(0),
  system_status: "DEGRADED",
  zones_summary: BANGALORE_ZONES.map((zone) => ({
    zone_id: zone.zone_id,
    status: zone.status,
    load_pct: zone.load_pct,
    active_evs: zone.active_evs,
    score: zone.score,
  })),
  grid_total: {
    total_load_kw: totalLoadKw,
    total_capacity_kw: totalCapacityKw,
    system_headroom_pct: Number(
      (100 - (totalLoadKw / totalCapacityKw) * 100).toFixed(1),
    ),
  },
  current_tariff: { tier: "MID_PEAK", rate_inr: 7.25, next_change_minutes: 90 },
  solar_total: {
    generation_kw: BANGALORE_ZONES.reduce(
      (sum, zone) => sum + zone.metrics.solar_contribution_kw,
      0,
    ),
    battery_soc_avg: 64,
    self_consumption_pct: 81,
  },
  active_sessions_total: BANGALORE_ZONES.reduce(
    (sum, zone) => sum + zone.metrics.active_evs,
    0,
  ),
  peak_reduction_today_pct: 18.7,
  cost_savings_today_inr: 182000,
  alerts,
};

export function MOCK_FORECAST(zoneId: string, hours: number): ZoneForecast {
  const series = zoneForecastMap.get(zoneId);
  if (!series) {
    return {
      zone_id: zoneId,
      model_version: "blr-sim-2026.05",
      generated_at: iso(0),
      forecast: [],
      rmse_last_eval: 0,
      feature_importance: {},
    };
  }
  const pointsNeeded = Math.min(
    series.forecast.length,
    Math.max(4, Math.round(hours * 4)),
  );
  return clone({
    ...series,
    forecast: series.forecast.slice(0, pointsNeeded),
  });
}

export const MOCK_FORECAST_ALL: ZoneForecast[] = Array.from(
  zoneForecastMap.values(),
).map(clone);

export const MOCK_SCHEDULE: ScheduleResponse = {
  schedule_id: "blr-grid-virtual",
  generated_at: iso(0),
  valid_for_minutes: 15,
  schedules: BANGALORE_ZONES.map((zone) => zone.schedule),
  total_grid_load_kw: totalLoadKw,
  peak_reduction_vs_unmanaged_pct: 21.4,
};

export const MOCK_ZONE_RANKING: ZoneRankingResponse = {
  computed_at: iso(-30),
  next_replan: iso(60 * 24 * 3),
  zones: BANGALORE_ZONES.map((zone) => zone.ranking),
  silhouette_score: 0.71,
  model_version: "blr-sim-2026.05",
};

export function MOCK_ZONE_DETAIL(zoneId: string): ZoneDetail {
  const detail = zoneDetailMap.get(zoneId);
  if (!detail) {
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
        reasoning: "Mock dataset does not include this zone",
      },
      metrics: {
        utilization_pct: 0,
        active_evs: 0,
        queue_length: 0,
        solar_contribution_kw: 0,
      },
    };
  }
  return clone(detail);
}

export const MOCK_ALERTS: Alert[] = alerts.map(clone);

export const MOCK_HEALTH: SystemHealth = {
  status: "mock-data",
  services: {
    "backend-gateway": "mock-only",
    "backend-lstm": "mock-only",
    "backend-ppo": "mock-only",
    "backend-clustering": "mock-only",
    "data-nodes": "synthetic-stream",
    redis: "inline-cache",
    influxdb: "static-export",
  },
};

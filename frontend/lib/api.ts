// Typed REST client for the GRIDMIND backend gateway.
//
// Contract: every function NEVER throws. On any failure (missing env,
// network error, non-2xx, schema mismatch) it logs `[GRIDMIND API]` and
// returns the matching mock-fallback payload so the UI keeps rendering.

import {
  MOCK_ALERTS,
  MOCK_DASHBOARD,
  MOCK_FORECAST,
  MOCK_FORECAST_ALL,
  MOCK_HEALTH,
  MOCK_SCHEDULE,
  MOCK_ZONE_DETAIL,
  MOCK_ZONE_RANKING,
} from "./mock-fallback";
import type {
  Alert,
  DashboardOverview,
  ScheduleResponse,
  SystemHealth,
  ZoneDetail,
  ZoneForecast,
  ZoneRankingResponse,
} from "./types";

const BASE_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) || "";
const DATA_MODE =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_DATA_MODE) ||
  "mock";
const USE_MOCK = DATA_MODE !== "live";

// NOTE: This build intentionally avoids hitting the backend gateway. When the
// stack is ready for live data, set NEXT_PUBLIC_DATA_MODE=live and re-enable the
// commented fetch blocks below.

function clone<T>(value: T): T {
  if (typeof globalThis.structuredClone === "function") {
    return globalThis.structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
}

function logError(label: string, err: unknown): void {
  // eslint-disable-next-line no-console
  console.warn(`[GRIDMIND API] ${label} →`, err);
}

async function request<T>(
  path: string,
  init: RequestInit | undefined,
  fallback: T,
  label: string,
): Promise<T> {
  if (USE_MOCK || !BASE_URL) {
    if (!BASE_URL) {
      logError(label, "NEXT_PUBLIC_API_URL not set; using fallback");
    }
    return clone(fallback);
  }
  logError(label, "Live gateway disabled; serving mock payload");
  /*
  // When the backend is available, restore the fetch logic below.
  const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer =
    ctrl &&
    setTimeout(() => {
      try {
        ctrl.abort();
      } catch {
        // ignore
      }
    }, DEFAULT_TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      signal: ctrl?.signal,
      cache: "no-store",
    });
    if (!res.ok) {
      logError(label, `HTTP ${res.status} ${res.statusText}`);
      return clone(fallback);
    }
    return (await res.json()) as T;
  } catch (err) {
    logError(label, err);
    return clone(fallback);
  } finally {
    if (timer) clearTimeout(timer);
  }
  */
  return clone(fallback);
}

// ─────────────── Dashboard ───────────────
export function getDashboardOverview(): Promise<DashboardOverview> {
  return request<DashboardOverview>(
    "/dashboard/overview",
    undefined,
    MOCK_DASHBOARD,
    "GET /dashboard/overview",
  );
}

export function getZoneDetail(zoneId: string): Promise<ZoneDetail> {
  return request<ZoneDetail>(
    `/dashboard/zone/${encodeURIComponent(zoneId)}`,
    undefined,
    MOCK_ZONE_DETAIL(zoneId),
    `GET /dashboard/zone/${zoneId}`,
  );
}

export async function getAlerts(): Promise<Alert[]> {
  // The backend returns { timestamp, count, alerts: [...] }; flatten for the hook.
  type AlertsEnvelope = { alerts?: Alert[] } | Alert[];
  const data = await request<AlertsEnvelope>(
    "/dashboard/alerts",
    undefined,
    { alerts: MOCK_ALERTS },
    "GET /dashboard/alerts",
  );
  if (Array.isArray(data)) return data;
  return data.alerts ?? MOCK_ALERTS;
}

// ─────────────── Forecast ───────────────
export function getZoneForecast(
  zoneId: string,
  hours: number,
): Promise<ZoneForecast> {
  return request<ZoneForecast>(
    `/forecast/${encodeURIComponent(zoneId)}?hours=${hours}`,
    undefined,
    MOCK_FORECAST(zoneId, hours),
    `GET /forecast/${zoneId}`,
  );
}

export async function getAllForecast(
  hours: number,
): Promise<ZoneForecast[]> {
  type AllForecastEnvelope = { forecasts?: ZoneForecast[] } | ZoneForecast[];
  const data = await request<AllForecastEnvelope>(
    `/forecast/all?hours=${hours}`,
    undefined,
    { forecasts: MOCK_FORECAST_ALL },
    "GET /forecast/all",
  );
  if (Array.isArray(data)) return data;
  return data.forecasts ?? MOCK_FORECAST_ALL;
}

// ─────────────── Schedule ───────────────
export function getCurrentSchedule(): Promise<ScheduleResponse> {
  return request<ScheduleResponse>(
    "/schedule/current",
    undefined,
    MOCK_SCHEDULE,
    "GET /schedule/current",
  );
}

export async function overrideZoneSchedule(
  zoneId: string,
  powerKw: number,
): Promise<{ success: boolean }> {
  if (USE_MOCK || !BASE_URL) {
    logError(
      "POST /schedule/override",
      USE_MOCK
        ? "mock mode enabled; acknowledging override without backend"
        : "NEXT_PUBLIC_API_URL not set; faking success",
    );
    return { success: true };
  }
  logError("POST /schedule/override", "Live overrides disabled; returning success");
  /*
  try {
    const res = await fetch(`${BASE_URL}/schedule/override`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        zone_id: zoneId,
        power_kw: powerKw,
        operator_id: "ui-operator",
        reason: "Manual override from operator UI",
      }),
    });
    return { success: res.ok };
  } catch (err) {
    logError("POST /schedule/override", err);
    return { success: false };
  }
  */
  return { success: true };
}

// ─────────────── Planning ───────────────
export function getZoneRanking(): Promise<ZoneRankingResponse> {
  return request<ZoneRankingResponse>(
    "/zones/ranking",
    undefined,
    MOCK_ZONE_RANKING,
    "GET /zones/ranking",
  );
}

export async function triggerReplan(): Promise<{ job_id: string }> {
  if (USE_MOCK || !BASE_URL) {
    logError(
      "POST /clustering/replan",
      USE_MOCK
        ? "mock mode enabled; returning simulated job id"
        : "NEXT_PUBLIC_API_URL not set; faking job",
    );
    return { job_id: "mock-job-blr" };
  }
  logError("POST /clustering/replan", "Live replan disabled; returning mock job id");
  /*
  try {
    const res = await fetch(`${BASE_URL}/clustering/replan`, {
      method: "POST",
    });
    if (!res.ok) {
      logError("POST /clustering/replan", `HTTP ${res.status}`);
      return { job_id: "fallback-job" };
    }
    const data = (await res.json()) as { job_id?: string };
    return { job_id: data.job_id ?? "unknown" };
  } catch (err) {
    logError("POST /clustering/replan", err);
    return { job_id: "fallback-job" };
  }
  */
  return { job_id: "mock-job-blr" };
}

// ─────────────── Health ───────────────
export async function getSystemHealth(): Promise<SystemHealth> {
  // Gateway returns { status, dependencies: {...} }; normalise to { status, services }.
  type HealthEnvelope = {
    status?: string;
    dependencies?: Record<string, string>;
    services?: Record<string, string>;
  };
  const data = await request<HealthEnvelope>(
    "/health",
    undefined,
    { status: MOCK_HEALTH.status, services: MOCK_HEALTH.services },
    "GET /health",
  );
  return {
    status: data.status ?? "unknown",
    services: data.services ?? data.dependencies ?? {},
  };
}

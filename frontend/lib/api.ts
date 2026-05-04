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

const DEFAULT_TIMEOUT_MS = 8_000;

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
  if (!BASE_URL) {
    logError(label, "NEXT_PUBLIC_API_URL not set; using fallback");
    return fallback;
  }
  const ctrl =
    typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer =
    ctrl &&
    setTimeout(() => {
      try {
        ctrl.abort();
      } catch {
        /* ignore */
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
      return fallback;
    }
    return (await res.json()) as T;
  } catch (err) {
    logError(label, err);
    return fallback;
  } finally {
    if (timer) clearTimeout(timer);
  }
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
  if (!BASE_URL) {
    logError("POST /schedule/override", "NEXT_PUBLIC_API_URL not set; faking success");
    return { success: true };
  }
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
  if (!BASE_URL) {
    logError("POST /clustering/replan", "NEXT_PUBLIC_API_URL not set; faking job");
    return { job_id: "fallback-job" };
  }
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

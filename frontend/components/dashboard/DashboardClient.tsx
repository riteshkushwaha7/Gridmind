"use client";

import { useMemo } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BatteryCharging,
  CircleAlert,
  Gauge,
  IndianRupee,
  Leaf,
  TrendingDown,
  Users,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useAlerts, useDashboardOverview } from "@/hooks/useDashboard";
import { useAllForecast } from "@/hooks/useForecast";
import {
  axisProps,
  chartPalette,
  gridProps,
  tooltipProps,
} from "@/lib/chart-theme";
import { cn } from "@/lib/cn";
import type { Alert, ZoneSummary } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, Skeleton } from "@/components/ui/Skeleton";
import { Stat } from "@/components/ui/Stat";
import {
  StatusChip,
  feederStatusTone,
  systemStatusTone,
} from "@/components/ui/StatusChip";

// ─────────────── Helpers ───────────────
function formatHM(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function alertTone(severity: Alert["severity"]) {
  if (severity === "CRITICAL") return "danger" as const;
  if (severity === "WARNING") return "warn" as const;
  return "slate" as const;
}

// ─────────────── Sections ───────────────
function HeaderRow() {
  const { data, isLoading } = useDashboardOverview();
  const status = data?.system_status;
  const headroom = data?.grid_total.system_headroom_pct;
  return (
    <PageHeader
      eyebrow="Operations · live"
      title="GRIDMIND control room"
      subtitle={
        isLoading
          ? "Loading live state from the gateway…"
          : `${data?.zones_summary.length ?? 0} BESCOM zones online · ${
              headroom !== undefined
                ? `${headroom.toFixed(1)}% system headroom`
                : "headroom unknown"
            }`
      }
      action={
        status ? (
          <StatusChip tone={systemStatusTone(status)}>{status}</StatusChip>
        ) : null
      }
    />
  );
}

function KpiRow() {
  const { data, isLoading } = useDashboardOverview();

  if (isLoading || !data) {
    return (
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
    );
  }

  const grid = data.grid_total;
  const solar = data.solar_total;
  const tariff = data.current_tariff;
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
      <Stat
        label="Active sessions"
        value={data.active_sessions_total}
        icon={Users}
        tone="lime"
        accent
        caption={`across ${data.zones_summary.length} zones`}
      />
      <Stat
        label="Peak reduction today"
        value={`${data.peak_reduction_today_pct.toFixed(1)}%`}
        icon={TrendingDown}
        tone="ok"
        caption="vs unmanaged baseline"
      />
      <Stat
        label="Cost saved today"
        value={`₹${Math.round(data.cost_savings_today_inr).toLocaleString("en-IN")}`}
        icon={IndianRupee}
        tone="magenta"
        caption="net of tariff differential"
      />
      <Stat
        label="Solar generation"
        value={`${Math.round(solar.generation_kw)}`}
        suffix="kW"
        icon={Leaf}
        tone="ok"
        caption={`battery avg ${solar.battery_soc_avg.toFixed(0)}% SoC`}
      />
      <Stat
        label="Grid load"
        value={`${Math.round(grid.total_load_kw).toLocaleString("en-IN")}`}
        suffix={`/ ${Math.round(grid.total_capacity_kw).toLocaleString("en-IN")} kW`}
        icon={Gauge}
        tone={grid.system_headroom_pct < 15 ? "warn" : "lime"}
        caption={`tariff ₹${tariff.rate_inr.toFixed(2)} · ${tariff.tier
          .replace("_", " ")
          .toLowerCase()}`}
      />
    </div>
  );
}

function ForecastChart() {
  const { data, isLoading } = useAllForecast(4);

  // Aggregate forecast across zones into a single fleet curve.
  const series = useMemo(() => {
    if (!data || data.length === 0) return [];
    const bucket = new Map<
      string,
      { ts: string; demand: number; lower: number; upper: number; n: number }
    >();
    for (const zf of data) {
      for (const p of zf.forecast) {
        const cur = bucket.get(p.timestamp) ?? {
          ts: p.timestamp,
          demand: 0,
          lower: 0,
          upper: 0,
          n: 0,
        };
        cur.demand += p.demand_kwh;
        cur.lower += p.confidence_lower;
        cur.upper += p.confidence_upper;
        cur.n += 1;
        bucket.set(p.timestamp, cur);
      }
    }
    return Array.from(bucket.values())
      .sort((a, b) => a.ts.localeCompare(b.ts))
      .map((row) => ({
        time: formatHM(row.ts),
        demand: Math.round(row.demand),
        lower: Math.round(row.lower),
        upper: Math.round(row.upper),
      }));
  }, [data]);

  return (
    <Card className="flex h-full min-h-[360px] flex-col">
      <CardHeader
        eyebrow="Forecast · 4 h horizon"
        title="Fleet load (LSTM)"
        description="Aggregated 15-minute demand across all zones with 95% confidence band."
        action={
          data && data.length > 0 ? (
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-bm-slate dark:text-blueprint-mist/45">
              v{data[0]?.model_version ?? "—"}
            </span>
          ) : null
        }
      />
      <div className="mt-5 min-h-[260px] flex-1">
        {isLoading ? (
          <Skeleton className="h-full w-full" />
        ) : series.length === 0 ? (
          <EmptyState
            title="No forecast data yet"
            hint="Train the LSTM model: docker compose exec backend-lstm python -m lstm.train"
          />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={series}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id="primaryFill" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor={chartPalette.primary}
                    stopOpacity={0.4}
                  />
                  <stop
                    offset="100%"
                    stopColor={chartPalette.primary}
                    stopOpacity={0.02}
                  />
                </linearGradient>
                <linearGradient id="bandFill" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor={chartPalette.primary}
                    stopOpacity={0.18}
                  />
                  <stop
                    offset="100%"
                    stopColor={chartPalette.primary}
                    stopOpacity={0.02}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="time" {...axisProps} />
              <YAxis {...axisProps} width={56} />
              <Tooltip {...tooltipProps} />
              <Area
                type="monotone"
                dataKey="upper"
                stroke="none"
                fill="url(#bandFill)"
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="lower"
                stroke="none"
                fill="var(--bm-mist)"
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="demand"
                stroke={chartPalette.primary}
                strokeWidth={2}
                fill="url(#primaryFill)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}

function ZoneCard({ z }: { z: ZoneSummary }) {
  const tone = feederStatusTone(z.status);
  const fillColor =
    tone === "danger"
      ? "bg-bm-danger"
      : tone === "warn"
        ? "bg-bm-warn"
        : "bg-bm-lime";
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-bm-slate dark:text-blueprint-mist/45">
            zone
          </p>
          <p className="font-sans text-base font-bold text-blueprint-navy dark:text-blueprint-mist">
            {z.zone_id}
          </p>
        </div>
        <StatusChip tone={tone}>{z.status}</StatusChip>
      </div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-sans text-2xl font-bold tabular-nums text-blueprint-navy dark:text-blueprint-mist">
          {z.load_pct.toFixed(0)}
          <span className="text-sm font-medium text-bm-slate dark:text-blueprint-mist/45">
            %
          </span>
        </span>
        <span className="font-sans text-xs text-bm-slate dark:text-blueprint-mist/55">
          {z.active_evs} EVs · score {z.score.toFixed(2)}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-bm-slate/15 dark:bg-white/10">
        <div
          className={cn("h-full rounded-full", fillColor)}
          style={{ width: `${Math.min(100, z.load_pct)}%` }}
        />
      </div>
    </Card>
  );
}

function ZoneGrid() {
  const { data, isLoading } = useDashboardOverview();
  if (isLoading || !data) {
    return (
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
        {Array.from({ length: 10 }).map((_, i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
    );
  }
  if (data.zones_summary.length === 0) {
    return (
      <EmptyState
        title="No zone data"
        hint="Bring up the data-nodes service: docker compose up -d data-nodes"
      />
    );
  }
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
      {data.zones_summary.map((z) => (
        <ZoneCard key={z.zone_id} z={z} />
      ))}
    </div>
  );
}

function AlertsPanel() {
  const { data, isLoading } = useAlerts();
  return (
    <Card className="flex h-full flex-col">
      <CardHeader
        eyebrow="Live"
        title="Active alerts"
        description="Constraint warnings, queue spillover, and headroom drops from across the fleet."
        action={
          <span className="gm-chip gm-chip-magenta">{data?.length ?? 0}</span>
        }
      />
      <div className="mt-4 flex-1 space-y-2.5 overflow-y-auto pr-1">
        {isLoading ? (
          <>
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </>
        ) : !data || data.length === 0 ? (
          <EmptyState
            title="All clear"
            hint="No constraints, queues, or safety overrides in the last cycle."
          />
        ) : (
          data.map((a, i) => {
            const tone = alertTone(a.severity);
            const Icon =
              a.severity === "CRITICAL"
                ? CircleAlert
                : a.severity === "WARNING"
                  ? AlertTriangle
                  : BatteryCharging;
            return (
              <div
                key={i}
                className="flex items-start gap-3 rounded-card border border-bm-line/50 bg-bm-mist/40 p-3 dark:border-white/10 dark:bg-white/[0.02]"
              >
                <span
                  className={cn(
                    "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-chip",
                    tone === "danger"
                      ? "bg-bm-danger/15 text-bm-danger"
                      : tone === "warn"
                        ? "bg-bm-warn/15 text-bm-warn"
                        : "bg-bm-slate/15 text-bm-slate",
                  )}
                  aria-hidden
                >
                  <Icon className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-sans text-sm font-semibold text-blueprint-navy dark:text-blueprint-mist">
                      {a.zone_id}
                    </span>
                    <StatusChip tone={tone}>{a.severity}</StatusChip>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-bm-slate dark:text-blueprint-mist/65">
                    {a.message}
                  </p>
                  <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-bm-slate/70 dark:text-blueprint-mist/35">
                    {formatHM(a.timestamp)}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </Card>
  );
}

function PeakReductionPill() {
  const { data } = useDashboardOverview();
  const pct = data?.peak_reduction_today_pct ?? 0;
  const positive = pct >= 0;
  const Icon = positive ? ArrowDownRight : ArrowUpRight;
  return (
    <Card className="flex items-center justify-between gap-4">
      <div>
        <p className="gm-eyebrow">Today vs uncontrolled</p>
        <p className="mt-2 flex items-baseline gap-2 font-sans text-3xl font-bold tracking-tight text-blueprint-navy dark:text-blueprint-mist">
          {pct.toFixed(1)}%
          <Icon
            className={cn(
              "h-5 w-5",
              positive ? "text-bm-ok" : "text-bm-danger",
            )}
            aria-hidden
          />
        </p>
        <p className="mt-1 text-xs text-bm-slate dark:text-blueprint-mist/55">
          Peak reduction since 00:00 IST
        </p>
      </div>
      <div className="hidden h-16 w-16 items-center justify-center rounded-card bg-bm-lime/15 ring-1 ring-bm-lime/40 dark:bg-bm-lime/10 sm:flex">
        <Leaf className="h-7 w-7 text-bm-ink dark:text-bm-lime" aria-hidden />
      </div>
    </Card>
  );
}

// ─────────────── Page ───────────────
export function DashboardClient() {
  return (
    <div className="space-y-6 md:space-y-8">
      <HeaderRow />
      <KpiRow />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ForecastChart />
        </div>
        <div className="flex flex-col gap-5">
          <PeakReductionPill />
          <AlertsPanel />
        </div>
      </div>

      <section>
        <div className="mb-4 flex items-end justify-between">
          <div>
            <p className="gm-eyebrow mb-1.5">Network</p>
            <h2 className="font-sans text-xl font-bold tracking-tight text-blueprint-navy dark:text-blueprint-mist">
              Zone health
            </h2>
          </div>
          <p className="hidden text-xs text-bm-slate dark:text-blueprint-mist/55 sm:block">
            Per-feeder load, EV count, and clustering score
          </p>
        </div>
        <ZoneGrid />
      </section>
    </div>
  );
}

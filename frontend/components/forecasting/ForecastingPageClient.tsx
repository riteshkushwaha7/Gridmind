"use client";

import { useMemo, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  Gauge,
  Layers,
  Sparkle,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useDashboardOverview } from "@/hooks/useDashboard";
import { useZoneForecast } from "@/hooks/useForecast";
import {
  axisProps,
  chartPalette,
  gridProps,
  tooltipProps,
} from "@/lib/chart-theme";
import { cn } from "@/lib/cn";
import { Card, CardHeader } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, Skeleton } from "@/components/ui/Skeleton";
import { Stat } from "@/components/ui/Stat";

const HORIZON_OPTIONS = [
  { value: 1, label: "1h" },
  { value: 4, label: "4h" },
  { value: 12, label: "12h" },
  { value: 24, label: "24h" },
];

function formatHM(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function ZoneSelector({
  zones,
  value,
  onChange,
}: {
  zones: { zone_id: string; load_pct: number }[];
  value: string | null;
  onChange: (z: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {zones.map((z) => {
        const active = z.zone_id === value;
        return (
          <button
            key={z.zone_id}
            type="button"
            onClick={() => onChange(z.zone_id)}
            className={cn(
              "gm-focus rounded-chip px-3 py-1.5 font-sans text-xs font-semibold transition-colors",
              active
                ? "bg-bm-ink text-bm-lime ring-1 ring-bm-lime/40 dark:bg-bm-lime/15"
                : "border border-bm-line/60 text-bm-slate hover:bg-bm-mist dark:border-white/10 dark:text-blueprint-mist/65 dark:hover:bg-white/5",
            )}
          >
            {z.zone_id}
            <span className="ml-1.5 font-normal opacity-70">
              {z.load_pct.toFixed(0)}%
            </span>
          </button>
        );
      })}
    </div>
  );
}

function HorizonPicker({
  value,
  onChange,
}: {
  value: number;
  onChange: (h: number) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Forecast horizon"
      className="inline-flex rounded-chip border border-bm-line/60 bg-bm-surface p-0.5 dark:border-white/10 dark:bg-white/5"
    >
      {HORIZON_OPTIONS.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              "gm-focus rounded-chip px-3 py-1 font-sans text-xs font-semibold transition-colors",
              active
                ? "bg-bm-ink text-bm-lime dark:bg-bm-lime dark:text-bm-ink"
                : "text-bm-slate hover:text-blueprint-navy dark:text-blueprint-mist/55",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

export function ForecastingPageClient() {
  const [horizon, setHorizon] = useState(4);
  const { data: overview } = useDashboardOverview();
  const zones = overview?.zones_summary ?? [];
  const [selectedZone, setSelectedZone] = useState<string | null>(null);
  const activeZone =
    selectedZone ?? (zones.length > 0 ? zones[0]!.zone_id : null);

  const { data: forecast, isLoading } = useZoneForecast(activeZone, horizon);

  const chartData = useMemo(() => {
    if (!forecast) return [];
    return forecast.forecast.map((p) => ({
      time: formatHM(p.timestamp),
      demand: Math.round(p.demand_kwh),
      lower: Math.round(p.confidence_lower),
      upper: Math.round(p.confidence_upper),
    }));
  }, [forecast]);

  const peakKw = useMemo(() => {
    if (!forecast || forecast.forecast.length === 0) return 0;
    return Math.max(...forecast.forecast.map((p) => p.demand_kwh));
  }, [forecast]);

  const featureImportance = useMemo(() => {
    if (!forecast?.feature_importance) return [];
    return Object.entries(forecast.feature_importance)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6);
  }, [forecast]);

  return (
    <div className="space-y-6 md:space-y-8">
      <PageHeader
        eyebrow="Forecast · LSTM"
        title="Demand forecasting"
        subtitle="Per-zone 15-minute demand projections from the LSTM service. Pick a zone and a horizon."
        action={<HorizonPicker value={horizon} onChange={setHorizon} />}
      />

      {/* Zone selector */}
      <Card>
        <CardHeader
          eyebrow="Zone"
          title={
            activeZone
              ? `${activeZone} · selected`
              : "No zones available"
          }
          description="Forecasts come from the LSTM service via the gateway. Pick any active zone."
        />
        <div className="mt-4">
          {zones.length === 0 ? (
            <EmptyState
              title="No zones online"
              hint="The data-nodes service hasn't published any zone state yet."
            />
          ) : (
            <ZoneSelector
              zones={zones}
              value={activeZone}
              onChange={setSelectedZone}
            />
          )}
        </div>
      </Card>

      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat
          label="Forecast peak"
          value={`${Math.round(peakKw).toLocaleString("en-IN")}`}
          suffix="kWh"
          icon={Gauge}
          tone="lime"
          accent
          caption={`over next ${horizon} h`}
        />
        <Stat
          label="RMSE (last eval)"
          value={forecast?.rmse_last_eval.toFixed(2) ?? "—"}
          suffix="kWh"
          icon={Activity}
          tone="ok"
          caption="lower is better"
        />
        <Stat
          label="Steps returned"
          value={chartData.length}
          icon={Layers}
          tone="slate"
          caption="15-minute buckets"
        />
        <Stat
          label="Model version"
          value={
            forecast?.model_version === "fallback"
              ? "fallback"
              : `v${forecast?.model_version ?? "—"}`
          }
          icon={Sparkle}
          tone="magenta"
          caption={
            forecast?.model_version === "fallback"
              ? "gateway unreachable — using stub"
              : "MLflow Production stage"
          }
        />
      </div>

      {/* Main chart */}
      <Card className="flex h-full min-h-[420px] flex-col">
        <CardHeader
          eyebrow={`Zone ${activeZone ?? "—"} · LSTM`}
          title={`Demand forecast · ${horizon} h ahead`}
          description="Mean prediction with 95 % confidence band derived from validation residual standard deviation."
          action={
            <a
              href={
                activeZone
                  ? `/dashboard/zone/${activeZone}`
                  : "/dashboard"
              }
              className="gm-btn-ghost text-xs"
            >
              Zone detail <ArrowUpRight className="h-3.5 w-3.5" />
            </a>
          }
        />
        <div className="mt-5 min-h-[320px] flex-1">
          {isLoading || !activeZone ? (
            <Skeleton className="h-full w-full" />
          ) : chartData.length === 0 ? (
            <EmptyState
              title="No forecast points"
              hint="Train the LSTM model: docker compose exec backend-lstm python -m lstm.train"
            />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData}
                margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="fcFill" x1="0" y1="0" x2="0" y2="1">
                    <stop
                      offset="0%"
                      stopColor={chartPalette.primary}
                      stopOpacity={0.45}
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
                  fill="url(#fcFill)"
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="demand"
                  stroke={chartPalette.primary}
                  strokeWidth={0}
                  dot={{ r: 2.5, fill: chartPalette.primary, strokeWidth: 0 }}
                  activeDot={{ r: 4, fill: chartPalette.secondary }}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>

      {/* Feature importance */}
      <Card>
        <CardHeader
          eyebrow="Explainability"
          title="Top features driving this forecast"
          description="Permutation importance scored on the 14 LSTM input features. Higher = more influence on the predicted demand."
          action={<BarChart3 className="h-5 w-5 text-bm-slate" aria-hidden />}
        />
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {featureImportance.length === 0
            ? Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-10" />
              ))
            : featureImportance.map(([name, score]) => {
                const pct = Math.round(score * 100);
                return (
                  <div key={name} className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono text-blueprint-navy dark:text-blueprint-mist">
                        {name}
                      </span>
                      <span className="font-mono tabular-nums text-bm-slate dark:text-blueprint-mist/55">
                        {pct}%
                      </span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-bm-slate/15 dark:bg-white/10">
                      <div
                        className="h-full rounded-full bg-bm-lime"
                        style={{ width: `${Math.min(100, pct)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
        </div>
      </Card>
    </div>
  );
}

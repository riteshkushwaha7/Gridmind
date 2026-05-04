"use client";

import { useMemo, useState } from "react";
import {
  ArrowDownRight,
  Building2,
  Cpu,
  Layers,
  MapPin,
  RefreshCw,
  Sparkles,
  Target,
} from "lucide-react";

import { useReplan, useZoneRanking } from "@/hooks/useZones";
import { cn } from "@/lib/cn";
import type { ZoneRanking } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, Skeleton } from "@/components/ui/Skeleton";
import { Stat } from "@/components/ui/Stat";
import { StatusChip } from "@/components/ui/StatusChip";

const PRIORITY_TONE = {
  HIGH:   "magenta" as const,
  MEDIUM: "warn"    as const,
  LOW:    "slate"   as const,
};

const ACTION_TONE = {
  EXPAND:   "lime"  as const,
  MONITOR:  "warn"  as const,
  MAINTAIN: "slate" as const,
};

function formatRelativeDate(iso: string): string {
  const target = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = target - now;
  const days = Math.round(diffMs / (24 * 60 * 60 * 1000));
  if (days <= 0) return "today";
  if (days === 1) return "tomorrow";
  if (days < 14) return `in ${days} days`;
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  });
}

function ZoneRow({ z, rank }: { z: ZoneRanking; rank: number }) {
  const priorityTone = PRIORITY_TONE[z.priority];
  const actionTone = ACTION_TONE[z.recommendation.action];
  const widthPct = Math.min(100, Math.round(z.score * 100));
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-card bg-bm-ink font-mono text-xs font-bold text-bm-lime"
            aria-hidden
          >
            #{String(rank).padStart(2, "0")}
          </span>
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-bm-slate dark:text-blueprint-mist/45">
              zone
            </p>
            <p className="font-sans text-base font-bold text-blueprint-navy dark:text-blueprint-mist">
              {z.zone_id}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusChip tone={priorityTone}>{z.priority}</StatusChip>
          {z.is_outlier ? (
            <StatusChip tone="warn">outlier</StatusChip>
          ) : null}
        </div>
      </div>

      {/* Score bar */}
      <div>
        <div className="mb-1.5 flex items-baseline justify-between font-sans text-xs">
          <span className="text-bm-slate dark:text-blueprint-mist/55">
            Composite score
          </span>
          <span className="font-mono font-semibold tabular-nums text-blueprint-navy dark:text-blueprint-mist">
            {z.score.toFixed(2)}
          </span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-bm-slate/15 dark:bg-white/10">
          <div
            className={cn(
              "h-full rounded-full",
              priorityTone === "magenta" && "bg-bm-magenta",
              priorityTone === "warn" && "bg-bm-warn",
              priorityTone === "slate" && "bg-bm-slate",
            )}
            style={{ width: `${widthPct}%` }}
          />
        </div>
      </div>

      {/* Metrics grid */}
      <dl className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
        <div>
          <dt className="text-bm-slate dark:text-blueprint-mist/55">Demand</dt>
          <dd className="mt-0.5 font-mono font-semibold tabular-nums text-blueprint-navy dark:text-blueprint-mist">
            {Math.round(z.metrics.avg_demand).toLocaleString("en-IN")} kWh/d
          </dd>
        </div>
        <div>
          <dt className="text-bm-slate dark:text-blueprint-mist/55">
            Growth
          </dt>
          <dd className="mt-0.5 font-mono font-semibold tabular-nums text-blueprint-navy dark:text-blueprint-mist">
            {z.metrics.growth_rate >= 0 ? "+" : ""}
            {z.metrics.growth_rate.toFixed(1)}% / 30d
          </dd>
        </div>
        <div>
          <dt className="text-bm-slate dark:text-blueprint-mist/55">
            Headroom
          </dt>
          <dd className="mt-0.5 font-mono font-semibold tabular-nums text-blueprint-navy dark:text-blueprint-mist">
            {z.metrics.headroom.toFixed(0)}%
          </dd>
        </div>
        <div>
          <dt className="text-bm-slate dark:text-blueprint-mist/55">
            Existing
          </dt>
          <dd className="mt-0.5 font-mono font-semibold tabular-nums text-blueprint-navy dark:text-blueprint-mist">
            {z.metrics.existing_chargers} chargers
          </dd>
        </div>
      </dl>

      {/* Recommendation */}
      <div className="flex flex-col gap-2 rounded-card border border-bm-line/50 bg-bm-mist/40 p-3 dark:border-white/10 dark:bg-white/[0.02]">
        <div className="flex flex-wrap items-center gap-2">
          <StatusChip tone={actionTone}>{z.recommendation.action}</StatusChip>
          {z.recommendation.new_chargers_suggested > 0 ? (
            <span className="gm-chip gm-chip-lime">
              + {z.recommendation.new_chargers_suggested} ×{" "}
              {z.recommendation.charger_type_suggested}
            </span>
          ) : (
            <span className="gm-chip gm-chip-slate">no expansion</span>
          )}
          <span className="gm-chip gm-chip-slate">
            ₹ {z.recommendation.estimated_cost_inr_lakhs.toFixed(1)} L
          </span>
        </div>
        <p className="text-xs leading-relaxed text-bm-slate dark:text-blueprint-mist/65">
          {z.recommendation.priority_reason}
        </p>
      </div>
    </Card>
  );
}

export function PlannerPageClient() {
  const { data, isLoading } = useZoneRanking();
  const replan = useReplan();
  const [filter, setFilter] = useState<"ALL" | "HIGH" | "MEDIUM" | "LOW">(
    "ALL",
  );

  const stats = useMemo(() => {
    if (!data || data.zones.length === 0) {
      return null;
    }
    const high = data.zones.filter((z) => z.priority === "HIGH").length;
    const expand = data.zones.filter(
      (z) => z.recommendation.action === "EXPAND",
    );
    const totalNew = expand.reduce(
      (s, z) => s + z.recommendation.new_chargers_suggested,
      0,
    );
    const totalCost = data.zones.reduce(
      (s, z) => s + z.recommendation.estimated_cost_inr_lakhs,
      0,
    );
    const avgGrowth =
      data.zones.reduce((s, z) => s + z.metrics.growth_rate, 0) /
      data.zones.length;
    return { high, totalNew, totalCost, avgGrowth };
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    if (filter === "ALL") return data.zones;
    return data.zones.filter((z) => z.priority === filter);
  }, [data, filter]);

  return (
    <div className="space-y-6 md:space-y-8">
      <PageHeader
        eyebrow="Planner · K-Means + DBSCAN"
        title="Infrastructure planner"
        subtitle="Where to expand the BESCOM EV charging network next, scored from 30 days of demand, growth, and grid-headroom signals."
        action={
          <button
            type="button"
            disabled={replan.isPending}
            onClick={() => replan.mutate()}
            className="gm-btn-primary"
          >
            <RefreshCw
              className={cn(
                "h-4 w-4",
                replan.isPending && "animate-spin",
              )}
              aria-hidden
            />
            {replan.isPending ? "Recomputing…" : "Recompute now"}
          </button>
        }
      />

      {/* Top stats */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat
          label="High-priority zones"
          value={stats?.high ?? "—"}
          icon={Target}
          tone="magenta"
          accent
          caption={`of ${data?.zones.length ?? 0} ranked`}
        />
        <Stat
          label="Suggested chargers"
          value={stats?.totalNew ?? "—"}
          icon={Building2}
          tone="lime"
          caption="across EXPAND zones"
        />
        <Stat
          label="Indicative capex"
          value={
            stats ? `₹${stats.totalCost.toFixed(1)}` : "—"
          }
          suffix="L"
          icon={Layers}
          tone="ok"
          caption="from charger spec × cost"
        />
        <Stat
          label="Avg demand growth"
          value={stats ? `${stats.avgGrowth.toFixed(1)}%` : "—"}
          icon={ArrowDownRight}
          tone="slate"
          caption="last 30 d, OLS slope"
        />
      </div>

      {/* Methodology + replan info */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            eyebrow="How it scores"
            title="Score(z) = α·D + β·G − γ·C"
            description="α = 0.4 demand, β = 0.3 grid headroom (inverse), γ = 0.3 existing-infra penalty. All components min-max normalised across zones, final score re-normalised to [0, 1]."
            action={<Cpu className="h-5 w-5 text-bm-slate" aria-hidden />}
          />
          <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
            <div className="rounded-card bg-bm-mist/40 p-3 dark:bg-white/[0.02]">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-bm-slate dark:text-blueprint-mist/45">
                D · demand
              </p>
              <p className="mt-1 font-sans text-blueprint-navy dark:text-blueprint-mist">
                0.6 · norm(daily kWh) + 0.4 · norm(growth %)
              </p>
            </div>
            <div className="rounded-card bg-bm-mist/40 p-3 dark:bg-white/[0.02]">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-bm-slate dark:text-blueprint-mist/45">
                G · headroom
              </p>
              <p className="mt-1 font-sans text-blueprint-navy dark:text-blueprint-mist">
                1 − norm(avg headroom %)
              </p>
            </div>
            <div className="rounded-card bg-bm-mist/40 p-3 dark:bg-white/[0.02]">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-bm-slate dark:text-blueprint-mist/45">
                C · existing
              </p>
              <p className="mt-1 font-sans text-blueprint-navy dark:text-blueprint-mist">
                norm(charger count)
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader
            eyebrow="Run metadata"
            title="Last clustering"
            description="Re-runs every 7 days; trigger an immediate recompute with the button above."
            action={<Sparkles className="h-5 w-5 text-bm-slate" aria-hidden />}
          />
          <div className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-bm-slate dark:text-blueprint-mist/55">
                Computed
              </span>
              <span className="font-mono text-blueprint-navy dark:text-blueprint-mist">
                {data ? formatRelativeDate(data.computed_at) : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-bm-slate dark:text-blueprint-mist/55">
                Next replan
              </span>
              <span className="font-mono text-blueprint-navy dark:text-blueprint-mist">
                {data ? formatRelativeDate(data.next_replan) : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-bm-slate dark:text-blueprint-mist/55">
                Silhouette
              </span>
              <span className="font-mono text-blueprint-navy dark:text-blueprint-mist">
                {data?.silhouette_score.toFixed(3) ?? "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-bm-slate dark:text-blueprint-mist/55">
                Model
              </span>
              <span className="font-mono text-blueprint-navy dark:text-blueprint-mist">
                {data?.model_version === "fallback"
                  ? "fallback"
                  : `v${data?.model_version ?? "—"}`}
              </span>
            </div>
          </div>
        </Card>
      </div>

      {/* Filter */}
      <div className="flex flex-wrap items-center gap-2">
        <MapPin
          className="h-4 w-4 text-bm-slate dark:text-blueprint-mist/55"
          aria-hidden
        />
        <p className="gm-eyebrow">Filter by priority</p>
        {(["ALL", "HIGH", "MEDIUM", "LOW"] as const).map((p) => {
          const active = filter === p;
          return (
            <button
              key={p}
              type="button"
              onClick={() => setFilter(p)}
              className={cn(
                "gm-focus rounded-chip px-3 py-1 font-sans text-xs font-semibold transition-colors",
                active
                  ? "bg-bm-ink text-bm-lime dark:bg-bm-lime dark:text-bm-ink"
                  : "border border-bm-line/60 text-bm-slate hover:bg-bm-mist dark:border-white/10 dark:text-blueprint-mist/65 dark:hover:bg-white/5",
              )}
            >
              {p}
            </button>
          );
        })}
      </div>

      {/* Zone list */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-56" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No zones in this filter"
          hint="Try ALL or trigger a recompute."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {filtered.map((z, i) => (
            <ZoneRow key={z.zone_id} z={z} rank={i + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

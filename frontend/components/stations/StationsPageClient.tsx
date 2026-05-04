"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Power,
  ShieldAlert,
  Sliders,
  Zap,
} from "lucide-react";

import { useDashboardOverview } from "@/hooks/useDashboard";
import {
  useCurrentSchedule,
  useOverrideSchedule,
} from "@/hooks/useSchedule";
import { cn } from "@/lib/cn";
import type { ZoneSchedule, ZoneSummary } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, Skeleton } from "@/components/ui/Skeleton";
import { Stat } from "@/components/ui/Stat";
import {
  StatusChip,
  feederStatusTone,
} from "@/components/ui/StatusChip";

type Row = ZoneSchedule & {
  load_pct?: number;
  feeder_status?: ZoneSummary["status"];
  active_evs?: number;
};

function ScheduleCard({
  row,
  onOverride,
  pending,
}: {
  row: Row;
  onOverride: (zoneId: string, powerKw: number) => void;
  pending: boolean;
}) {
  const [delta, setDelta] = useState(0);
  const target = Math.max(0, Math.round(row.recommended_power_kw + delta));
  const safetyTone = row.safety_capped || row.fallback_active ? "warn" : "ok";
  const SafetyIcon = row.fallback_active
    ? ShieldAlert
    : row.safety_capped
      ? AlertTriangle
      : CheckCircle2;

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-card bg-bm-ink text-bm-lime"
            aria-hidden
          >
            <Zap className="h-5 w-5" strokeWidth={2.2} />
          </span>
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-bm-slate dark:text-blueprint-mist/45">
              Zone
            </p>
            <p className="font-sans text-base font-bold text-blueprint-navy dark:text-blueprint-mist">
              {row.zone_id}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          {row.feeder_status ? (
            <StatusChip tone={feederStatusTone(row.feeder_status)}>
              {row.feeder_status}
            </StatusChip>
          ) : null}
          <span
            className={cn(
              "gm-chip",
              safetyTone === "warn" ? "gm-chip-warn" : "gm-chip-ok",
            )}
          >
            <SafetyIcon className="h-3 w-3" />
            {row.fallback_active
              ? "Fallback"
              : row.safety_capped
                ? "Capped"
                : "OK"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 text-xs">
        <div>
          <p className="text-bm-slate dark:text-blueprint-mist/55">
            Recommended
          </p>
          <p className="mt-0.5 font-sans text-xl font-bold tabular-nums text-blueprint-navy dark:text-blueprint-mist">
            {row.recommended_power_kw.toFixed(0)}
            <span className="ml-1 text-sm font-medium text-bm-slate dark:text-blueprint-mist/45">
              kW
            </span>
          </p>
        </div>
        <div>
          <p className="text-bm-slate dark:text-blueprint-mist/55">
            Sessions
          </p>
          <p className="mt-0.5 font-sans text-xl font-bold tabular-nums text-blueprint-navy dark:text-blueprint-mist">
            {row.estimated_sessions_served}
          </p>
        </div>
        <div>
          <p className="text-bm-slate dark:text-blueprint-mist/55">Tariff</p>
          <p className="mt-0.5 font-sans text-xl font-bold tabular-nums text-blueprint-navy dark:text-blueprint-mist">
            ₹{row.charging_cost_inr_per_kwh.toFixed(2)}
          </p>
        </div>
      </div>

      <p className="rounded-card bg-bm-mist/40 p-3 text-xs leading-relaxed text-bm-slate dark:bg-white/[0.02] dark:text-blueprint-mist/65">
        {row.reasoning}
      </p>

      {/* Operator override */}
      <div className="flex flex-col gap-2 border-t border-bm-line/40 pt-3 dark:border-white/10">
        <div className="flex items-center justify-between text-xs">
          <span className="font-mono uppercase tracking-[0.16em] text-bm-slate dark:text-blueprint-mist/55">
            Override
          </span>
          <span className="font-mono tabular-nums text-blueprint-navy dark:text-blueprint-mist">
            {target} kW
            {delta !== 0 ? (
              <span
                className={cn(
                  "ml-1.5",
                  delta > 0 ? "text-bm-warn" : "text-bm-ok",
                )}
              >
                ({delta > 0 ? "+" : ""}
                {delta} kW)
              </span>
            ) : null}
          </span>
        </div>
        <input
          type="range"
          min={-Math.round(row.recommended_power_kw)}
          max={Math.round(row.recommended_power_kw * 0.5) + 5}
          value={delta}
          onChange={(e) => setDelta(Number(e.target.value))}
          className="h-1 w-full appearance-none rounded-full bg-bm-slate/20 accent-bm-lime dark:bg-white/10"
          aria-label={`Override power for zone ${row.zone_id}`}
        />
        <button
          type="button"
          disabled={pending || delta === 0}
          onClick={() => onOverride(row.zone_id, target)}
          className={cn(
            "gm-btn-primary mt-1 w-full justify-center text-xs",
            (pending || delta === 0) &&
              "cursor-not-allowed opacity-50 hover:scale-100",
          )}
        >
          <Power className="h-3.5 w-3.5" />
          {pending
            ? "Sending…"
            : delta === 0
              ? "Adjust to override"
              : "Apply override"}
        </button>
      </div>
    </Card>
  );
}

export function StationsPageClient() {
  const { data: schedule, isLoading: sLoading } = useCurrentSchedule();
  const { data: overview } = useDashboardOverview();
  const override = useOverrideSchedule();
  const [filter, setFilter] = useState<"ALL" | "CAPPED" | "FALLBACK">("ALL");

  const rows = useMemo<Row[]>(() => {
    if (!schedule) return [];
    const overlay = new Map<string, ZoneSummary>();
    for (const z of overview?.zones_summary ?? []) {
      overlay.set(z.zone_id, z);
    }
    return schedule.schedules.map((s) => {
      const o = overlay.get(s.zone_id);
      return {
        ...s,
        load_pct: o?.load_pct,
        feeder_status: o?.status,
        active_evs: o?.active_evs,
      };
    });
  }, [schedule, overview]);

  const filtered = useMemo(() => {
    if (filter === "ALL") return rows;
    if (filter === "CAPPED") return rows.filter((r) => r.safety_capped);
    return rows.filter((r) => r.fallback_active);
  }, [rows, filter]);

  const totals = useMemo(() => {
    if (!schedule) return null;
    const capped = schedule.schedules.filter((s) => s.safety_capped).length;
    const fb = schedule.schedules.filter((s) => s.fallback_active).length;
    return {
      total_kw: schedule.total_grid_load_kw,
      reduction: schedule.peak_reduction_vs_unmanaged_pct,
      capped,
      fallback: fb,
    };
  }, [schedule]);

  return (
    <div className="space-y-6 md:space-y-8">
      <PageHeader
        eyebrow="Live · PPO"
        title="Charger schedule monitor"
        subtitle={
          schedule
            ? `Schedule ${schedule.schedule_id.slice(0, 8)} valid for ${schedule.valid_for_minutes} min · regenerated by the PPO service`
            : "Loading current schedule from the gateway…"
        }
        action={
          schedule ? (
            <span className="hidden font-mono text-[10px] uppercase tracking-[0.16em] text-bm-slate dark:text-blueprint-mist/45 sm:inline">
              Generated{" "}
              {new Date(schedule.generated_at).toLocaleTimeString(undefined, {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          ) : null
        }
      />

      {/* Top stats */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat
          label="Dispatched load"
          value={
            totals
              ? Math.round(totals.total_kw).toLocaleString("en-IN")
              : "—"
          }
          suffix="kW"
          icon={Zap}
          tone="lime"
          accent
          caption={`${overview?.zones_summary.length ?? 10} zones`}
        />
        <Stat
          label="Peak reduction"
          value={totals ? `${totals.reduction.toFixed(1)}%` : "—"}
          icon={Cpu}
          tone="ok"
          caption="vs unmanaged baseline"
        />
        <Stat
          label="Safety caps"
          value={totals?.capped ?? "—"}
          icon={AlertTriangle}
          tone="warn"
          caption="zones throttled by hard cap"
        />
        <Stat
          label="Fallback active"
          value={totals?.fallback ?? "—"}
          icon={ShieldAlert}
          tone="magenta"
          caption="proportional fairness engaged"
        />
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        <Sliders
          className="h-4 w-4 text-bm-slate dark:text-blueprint-mist/55"
          aria-hidden
        />
        <p className="gm-eyebrow">Filter</p>
        {(
          [
            { key: "ALL",      label: "All zones" },
            { key: "CAPPED",   label: "Capped" },
            { key: "FALLBACK", label: "Fallback" },
          ] as const
        ).map((opt) => {
          const active = filter === opt.key;
          return (
            <button
              key={opt.key}
              type="button"
              onClick={() => setFilter(opt.key)}
              className={cn(
                "gm-focus rounded-chip px-3 py-1 font-sans text-xs font-semibold transition-colors",
                active
                  ? "bg-bm-ink text-bm-lime dark:bg-bm-lime dark:text-bm-ink"
                  : "border border-bm-line/60 text-bm-slate hover:bg-bm-mist dark:border-white/10 dark:text-blueprint-mist/65 dark:hover:bg-white/5",
              )}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      {/* Zone schedule cards */}
      {sLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-72" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No zones in this filter"
          hint={
            schedule
              ? "Switch back to ALL to see all schedules."
              : "Train the PPO model: docker compose exec backend-ppo python -m ppo.train"
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((row) => (
            <ScheduleCard
              key={row.zone_id}
              row={row}
              pending={override.isPending}
              onOverride={(zoneId, powerKw) =>
                override.mutate({ zoneId, powerKw })
              }
            />
          ))}
        </div>
      )}

      {/* Override outcome */}
      {override.isSuccess && override.data?.success === false ? (
        <Card className="border-bm-warn/40 bg-bm-warn/5">
          <p className="text-sm text-bm-warn">
            Override request was rejected by the gateway. Check operator
            permissions or the gateway logs.
          </p>
        </Card>
      ) : null}
      {override.isSuccess && override.data?.success === true ? (
        <Card className="border-bm-ok/40 bg-bm-ok/5">
          <p className="text-sm text-bm-ok">
            Override applied. The schedule cache will refresh on the next
            poll.
          </p>
        </Card>
      ) : null}
    </div>
  );
}

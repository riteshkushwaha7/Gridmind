import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Activity, Gauge, PlugZap, Sun, Zap } from "lucide-react";

import { getZoneDetail } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { Stat } from "@/components/ui/Stat";

function formatSlot(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

type ZoneDetailPageProps = { params: { zoneId: string } };

export async function generateMetadata({ params }: ZoneDetailPageProps): Promise<Metadata> {
  const zoneId = decodeURIComponent(params.zoneId);
  return {
    title: `${zoneId} · Zone detail · GRIDMIND`,
    description: `Schedule, metrics, and demand traces for ${zoneId}.`,
  };
}

export default async function ZoneDetailPage({ params }: ZoneDetailPageProps) {
  const zoneId = decodeURIComponent(params.zoneId);
  const zone = await getZoneDetail(zoneId);

  if (!zone || !zone.zone_id) {
    notFound();
  }

  const demandHistory = zone.demand_history.slice(-10).reverse();
  const nextForecast = zone.forecast.slice(0, 10);
  const metrics = zone.metrics;
  const schedule = zone.current_schedule;

  return (
    <div className="space-y-6 md:space-y-8">
      <PageHeader
        eyebrow="Dashboard · Zone detail"
        title={`${zone.name} (${zone.zone_id})`}
        subtitle="Mock telemetry pulled directly from the Bengaluru simulation. Review the operator schedule, demand traces, and guardrails before dispatch."
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Feeder capacity"
          value={zone.feeder_capacity_kw.toLocaleString("en-IN")}
          suffix="kW"
          icon={Gauge}
          caption="Rated at the 66/11 kV substation"
        />
        <Stat
          label="Utilization"
          value={`${metrics.utilization_pct.toFixed(0)}%`}
          icon={Activity}
          tone="ok"
          caption="Current load vs headroom"
        />
        <Stat
          label="Active EVs"
          value={metrics.active_evs.toLocaleString("en-IN")}
          icon={PlugZap}
          tone="slate"
          caption="Charging or queued right now"
        />
        <Stat
          label="Solar contribution"
          value={metrics.solar_contribution_kw.toLocaleString("en-IN")}
          suffix="kW"
          icon={Sun}
          tone="lime"
          caption="Fleet depots + C&I rooftops"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader
            eyebrow="Recommended schedule"
            title={`${schedule.recommended_power_kw.toLocaleString("en-IN")} kW dispatched`}
            description={
              schedule.safety_capped
                ? "PPO output clamped by feeder cap."
                : "Within safe headroom."
            }
          />
          <dl className="mt-4 grid grid-cols-1 gap-3 text-sm">
            <div className="rounded-card bg-white/50 p-3 ring-1 ring-bm-line/40">
              <dt className="font-semibold text-blueprint-navy">Sessions served</dt>
              <dd className="text-bm-slate">
                ~{schedule.estimated_sessions_served} EVs in this window
              </dd>
            </div>
            <div className="rounded-card bg-white/50 p-3 ring-1 ring-bm-line/40">
              <dt className="font-semibold text-blueprint-navy">Tariff exposure</dt>
              <dd className="text-bm-slate">₹{schedule.charging_cost_inr_per_kwh.toFixed(2)} / kWh</dd>
            </div>
            <div className="rounded-card bg-white/50 p-3 ring-1 ring-bm-line/40">
              <dt className="font-semibold text-blueprint-navy">Fallback status</dt>
              <dd className="text-bm-slate">
                {schedule.fallback_active
                  ? "Proportional-fairness fallback is in control."
                  : "PPO plan accepted by operator."}
              </dd>
            </div>
            <div className="rounded-card bg-white/50 p-3 ring-1 ring-bm-line/40">
              <dt className="font-semibold text-blueprint-navy">Reasoning string</dt>
              <dd className="text-bm-slate">{schedule.reasoning}</dd>
            </div>
          </dl>
        </Card>

        <Card>
          <CardHeader
            eyebrow="Forecast"
            title="Next demand buckets"
            description="15-minute predictions from the LSTM service with PPO guardrails applied upstream."
            action={<Zap className="h-4 w-4 text-bm-slate" aria-hidden />}
          />
          <div className="mt-4 divide-y divide-bm-line/30 text-sm">
            {nextForecast.length === 0 ? (
              <p className="py-6 text-center text-bm-slate">
                No forecast points available — run the LSTM simulator.
              </p>
            ) : (
              nextForecast.map((point) => (
                <div key={point.timestamp} className="flex items-center justify-between py-2">
                  <span className="font-mono text-bm-slate">{formatSlot(point.timestamp)}</span>
                  <span className="font-mono text-blueprint-navy">
                    {Math.round(point.demand_kwh).toLocaleString("en-IN")}
                    <span className="ml-1 text-xs text-bm-slate">kWh</span>
                  </span>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader
          eyebrow="Historical"
          title="Recent demand (last 10 points)"
          description="Raw telemetry exported from the mock Bengaluru gateway."
        />
        <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {demandHistory.length === 0 ? (
            <p className="py-4 text-bm-slate">
              No history yet — bring the data-nodes service online.
            </p>
          ) : (
            demandHistory.map((entry) => (
              <div
                key={entry.timestamp}
                className="flex items-center justify-between rounded-card bg-white/60 px-4 py-2 text-sm ring-1 ring-bm-line/30"
              >
                <span className="font-mono text-bm-slate">{formatSlot(entry.timestamp)}</span>
                <span className="font-mono text-blueprint-navy">
                  {Math.round(entry.demand_kwh).toLocaleString("en-IN")}
                  <span className="ml-1 text-xs text-bm-slate">kWh</span>
                </span>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}

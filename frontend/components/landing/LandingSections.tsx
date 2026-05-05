import Link from "next/link";
import {
  Activity,
  Building2,
  Cpu,
  Gauge,
  Layers,
  Leaf,
  Map,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

type Pillar = {
  icon: LucideIcon;
  title: string;
  body: string;
  accent: "lime" | "magenta" | "ok" | "slate";
};

const PILLARS: Pillar[] = [
  {
    icon: Activity,
    title: "LSTM demand forecast",
    body: "PyTorch 2-layer LSTM, 192 × 14 features → 16-step 4 h horizon at 15-minute resolution. Retrains nightly off InfluxDB.",
    accent: "lime",
  },
  {
    icon: Cpu,
    title: "PPO charge scheduler",
    body: "Stable-Baselines3 PPO with hard safety cap and proportional-fairness fallback below 10 % feeder headroom. Online updates every 6 h.",
    accent: "magenta",
  },
  {
    icon: Map,
    title: "Infrastructure planner",
    body: "K-Means + DBSCAN over 30-day rollups; HIGH/MEDIUM/LOW priority and per-zone charger spec with indicative ₹-lakh capex.",
    accent: "ok",
  },
];

type Result = {
  value: string;
  label: string;
  citation: string;
  icon: LucideIcon;
};

const RESULTS: Result[] = [
  {
    value: "20%",
    label: "Peak demand reduction target",
    citation: "DR-LB-AI · Scientific Reports, 2024",
    icon: Gauge,
  },
  {
    value: "10",
    label: "BESCOM zones modelled in the prototype",
    citation: "Synthetic data-nodes simulator",
    icon: Layers,
  },
  {
    value: "54%",
    label: "Grid dependency reduction with solar + storage",
    citation: "Integrated DER literature (representative)",
    icon: Leaf,
  },
  {
    value: "0",
    label: "Safety-constraint violations under PPO + hard-cap fallback",
    citation: "Simulation-backed guardrails",
    icon: ShieldCheck,
  },
];

const ACCENT: Record<Pillar["accent"], string> = {
  lime: "bg-bm-lime/15 text-bm-ink ring-1 ring-bm-lime/40",
  magenta: "bg-bm-magenta/12 text-bm-magenta ring-1 ring-bm-magenta/30",
  ok: "bg-bm-ok/15 text-bm-ok ring-1 ring-bm-ok/30",
  slate: "bg-bm-slate/15 text-bm-slate ring-1 ring-bm-slate/25",
};

export function LandingSections() {
  return (
    <section className="bg-bm-mist text-blueprint-navy">
      <div className="mx-auto w-full max-w-6xl px-6 py-16 md:px-10 md:py-20">
        {/* ───── Pillars ───── */}
        <div className="flex flex-col gap-3">
          <span className="gm-eyebrow inline-flex items-center gap-2">
            <Sparkles className="h-3 w-3" aria-hidden /> What it does
          </span>
          <h2 className="font-sans text-3xl font-bold tracking-tight md:text-4xl">
            Three models, one operator surface.
          </h2>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-5 md:grid-cols-3">
          {PILLARS.map((p) => {
            const Icon = p.icon;
            return (
              <article key={p.title} className="gm-card flex flex-col gap-4">
                <span
                  className={`flex h-11 w-11 items-center justify-center rounded-card ${ACCENT[p.accent]}`}
                  aria-hidden
                >
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="font-sans text-lg font-bold tracking-tight">
                  {p.title}
                </h3>
                <p className="text-sm leading-relaxed text-bm-slate">
                  {p.body}
                </p>
              </article>
            );
          })}
        </div>

        {/* ───── Results ───── */}
        <div className="mt-16 flex flex-col gap-3">
          <span className="gm-eyebrow">Outcomes targeted</span>
          <h2 className="font-sans text-3xl font-bold tracking-tight md:text-4xl">
            Honest numbers — drawn from peer-reviewed work and our simulator.
          </h2>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {RESULTS.map((r) => {
            const Icon = r.icon;
            return (
              <article key={r.label} className="gm-card flex flex-col gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-chip bg-bm-lime/15 text-bm-ink ring-1 ring-bm-lime/40">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <p className="font-sans text-3xl font-bold tabular-nums tracking-tight">
                  {r.value}
                </p>
                <p className="text-sm font-medium text-blueprint-navy">
                  {r.label}
                </p>
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-bm-slate">
                  {r.citation}
                </p>
              </article>
            );
          })}
        </div>

        {/* ───── How it stays safe ───── */}
        <div className="mt-16 grid grid-cols-1 gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2 gm-card">
            <span className="gm-eyebrow inline-flex items-center gap-2">
              <ShieldCheck className="h-3 w-3" aria-hidden /> Safety-first
            </span>
            <h3 className="mt-3 font-sans text-2xl font-bold tracking-tight md:text-3xl">
              Recommendations only. The grid stays in the operator&rsquo;s
              hands.
            </h3>
            <p className="mt-3 text-sm leading-relaxed text-bm-slate">
              GRIDMIND today is advisory. PPO outputs flow through a hard cap
              that ensures{" "}
              <span className="font-mono text-blueprint-navy">
                P_final = min(P_AI, P_max_feeder)
              </span>
              . When feeder headroom drops below the safety floor, a
              proportional-fairness fallback takes over and every override is
              written to InfluxDB as a
              <span className="font-mono text-blueprint-navy"> safety_events </span>
              row. No commands are dispatched to BESCOM infrastructure
              automatically.
            </p>
          </div>
          <div className="gm-card flex flex-col gap-3">
            <span
              className="flex h-9 w-9 items-center justify-center rounded-chip bg-bm-magenta/12 text-bm-magenta ring-1 ring-bm-magenta/30"
              aria-hidden
            >
              <Building2 className="h-4 w-4" />
            </span>
            <p className="font-sans text-lg font-bold">For BESCOM grid teams</p>
            <p className="text-sm text-bm-slate">
              Built around the BESCOM ToU tariff, distribution-feeder
              constraints, and 10 representative Bengaluru zones (residential,
              commercial, highway, mixed) — all reproduced via a curated mock
              dataset so the UI runs anywhere.
            </p>
          </div>
        </div>

        {/* ───── CTA strip ───── */}
        <div className="mt-16 flex flex-col items-start justify-between gap-4 rounded-card border border-bm-lime/40 bg-bm-lime/15 p-6 md:flex-row md:items-center">
          <div>
            <p className="font-sans text-xl font-bold tracking-tight text-blueprint-navy">
              Ready to see it run — sans backend?
            </p>
            <p className="mt-1 text-sm text-bm-slate">
              The operator dashboard loads Bengaluru mock telemetry by default.
              Flip a single env var whenever you wire it to the real gateway.
            </p>
          </div>
          <Link
            href="/dashboard"
            className="gm-btn-primary text-base font-semibold"
          >
            <Zap className="h-4 w-4" />
            Open dashboard
          </Link>
        </div>

        {/* ───── Footer note ───── */}
        <footer className="mt-12 border-t border-bm-line/40 pt-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-bm-slate">
            GRIDMIND · Research prototype · Bengaluru mock dataset
          </p>
          <p className="mt-2 font-sans text-sm text-bm-slate">
            Based on peer-reviewed work — Scientific Reports (Nature) · IEEE
            OCPP studies. Recommendations are advisory; no automated commands
            flow to BESCOM infrastructure today.
          </p>
        </footer>
      </div>
    </section>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Flag,
  Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export const metadata: Metadata = {
  title: "GRIDMIND — Roadmap",
  description:
    "What's shipped, what's next for the BESCOM pilot, and what scales beyond.",
};

type Phase = {
  key: "current" | "next" | "future";
  label: string;
  caption: string;
  status: string;
  accent: "lime" | "magenta" | "slate";
  icon: LucideIcon;
  items: { title: string; body: string }[];
};

const PHASES: Phase[] = [
  {
    key: "current",
    label: "Current",
    caption: "Prototype · shipped",
    status: "Live",
    accent: "lime",
    icon: CheckCircle2,
    items: [
      {
        title: "Synthetic data simulation",
        body:
          "Six FastAPI nodes (OCPP, Grid, Solar, Tariff, EV Analytics, Weather) publish to Redis Streams every 15 min — 30 s for OCPP events.",
      },
      {
        title: "LSTM demand forecast",
        body:
          "PyTorch 2-layer LSTM, 192 × 14 features → 16-step 4 h horizon at 15-min resolution. Retrains nightly.",
      },
      {
        title: "PPO scheduler",
        body:
          "Stable-Baselines3 PPO with hard safety cap and proportional-fairness fallback below 10 % feeder headroom. Online-updates every 6 h.",
      },
      {
        title: "Infrastructure planning",
        body:
          "K-Means + DBSCAN over 30-day rollups; HIGH/MEDIUM/LOW priority and per-zone charger recommendation.",
      },
      {
        title: "BESCOM operator dashboard",
        body:
          "Next.js 14 + TanStack Query; safe-fail data layer with mock fallback so the UI never breaks if the gateway is down.",
      },
    ],
  },
  {
    key: "next",
    label: "Next",
    caption: "Finals · pilot",
    status: "In progress",
    accent: "magenta",
    icon: Clock,
    items: [
      {
        title: "Real BESCOM feeder data",
        body:
          "Replace synthetic grid telemetry with live SCADA / AMI feeds, starting with one Bengaluru sub-division.",
      },
      {
        title: "Pilot deployment, 2–3 zones",
        body:
          "Whitefield, Koramangala, Electronic City. Read-only at first; PPO outputs reviewed by an operator.",
      },
      {
        title: "PPO shadow mode",
        body:
          "Recommendations sent to live chargers but require operator confirmation before dispatch.",
      },
      {
        title: "SMS / email alerts",
        body:
          "Critical feeder warnings, safety overrides, and constraint violations pushed to on-call.",
      },
      {
        title: "Operator authentication",
        body:
          "Role-based access (viewer / operator / admin) with audit trail in PostgreSQL.",
      },
    ],
  },
  {
    key: "future",
    label: "Future",
    caption: "Scale",
    status: "Planned",
    accent: "slate",
    icon: Sparkles,
    items: [
      {
        title: "Vehicle-to-Grid (V2G)",
        body:
          "Bidirectional dispatch in the PPO action space; expand reward to credit grid-export revenue under critical-peak windows.",
      },
      {
        title: "Multi-DISCOM expansion",
        body:
          "Generalise feeder + tariff abstractions for CESC (Mysuru) and TNEB (Tamil Nadu).",
      },
      {
        title: "Two-way charger control",
        body:
          "Bring OCPP 2.0.1 SetChargingProfile / RemoteStop into the dispatch loop; today the system is advisory.",
      },
      {
        title: "Anomaly detection on meters",
        body:
          "Unsupervised drift detection on per-charger meter values to catch faults before they trip a connector.",
      },
      {
        title: "Mobile app for field ops",
        body:
          "Lightweight React Native app for substation crews — alert acknowledgement, charger status, manual override capture.",
      },
    ],
  },
];

const accentClass = {
  lime: {
    chip: "bg-bm-lime/15 text-bm-ink ring-1 ring-bm-lime/40 dark:text-bm-lime",
    bar:  "bg-bm-lime",
    dot:  "bg-bm-lime shadow-[0_0_0_4px_rgba(181,242,58,0.18)]",
    icon: "text-bm-ink dark:text-bm-lime",
    accentText: "text-bm-ink dark:text-bm-lime",
  },
  magenta: {
    chip: "bg-bm-magenta/12 text-bm-magenta ring-1 ring-bm-magenta/35",
    bar:  "bg-bm-magenta",
    dot:  "bg-bm-magenta shadow-[0_0_0_4px_rgba(255,61,138,0.18)]",
    icon: "text-bm-magenta",
    accentText: "text-bm-magenta",
  },
  slate: {
    chip: "bg-bm-slate/15 text-bm-slate ring-1 ring-bm-slate/30",
    bar:  "bg-bm-slate",
    dot:  "bg-bm-slate shadow-[0_0_0_4px_rgba(92,111,102,0.18)]",
    icon: "text-bm-slate",
    accentText: "text-bm-slate",
  },
} as const;

function PhaseHeader({ phase }: { phase: Phase }) {
  const Icon = phase.icon;
  const a = accentClass[phase.accent];
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="gm-eyebrow">{phase.caption}</p>
        <h2 className="mt-2 flex items-center gap-2 font-sans text-2xl font-semibold tracking-tight text-blueprint-navy dark:text-blueprint-mist">
          <Icon className={`h-5 w-5 ${a.icon}`} aria-hidden />
          {phase.label}
        </h2>
      </div>
      <span className={`gm-chip ${a.chip}`}>{phase.status}</span>
    </div>
  );
}

function PhaseColumn({ phase, index }: { phase: Phase; index: number }) {
  const a = accentClass[phase.accent];
  return (
    <section className="gm-card flex h-full flex-col gap-5">
      <PhaseHeader phase={phase} />
      <div className={`h-[3px] w-12 rounded-full ${a.bar}`} aria-hidden />
      <ol className="relative flex flex-1 flex-col gap-3 pl-5">
        <span
          className="absolute left-[5px] top-1.5 bottom-1.5 w-px bg-bm-line dark:bg-white/10"
          aria-hidden
        />
        {phase.items.map((item, i) => (
          <li key={i} className="relative">
            <span
              className={`absolute -left-5 top-1.5 h-2.5 w-2.5 rounded-full ${a.dot}`}
              aria-hidden
            />
            <div className="rounded-card bg-white/40 p-3 ring-1 ring-bm-line/40 transition-colors hover:bg-white dark:bg-white/[0.03] dark:ring-white/10 dark:hover:bg-white/[0.05]">
              <p className="font-sans text-sm font-semibold text-blueprint-navy dark:text-blueprint-mist">
                {item.title}
              </p>
              <p className="mt-1 font-sans text-[13px] leading-relaxed text-bm-slate dark:text-blueprint-mist/65">
                {item.body}
              </p>
            </div>
          </li>
        ))}
      </ol>
      <p className={`mt-auto font-mono text-[10px] uppercase tracking-[0.18em] ${a.accentText}`}>
        {String(index + 1).padStart(2, "0")} / 03
      </p>
    </section>
  );
}

export default function RoadmapPage() {
  return (
    <main className="relative min-h-screen bg-bm-mist text-blueprint-navy dark:bg-bm-ink dark:text-blueprint-mist">
      {/* Decorative grid background — subtle, fades on smaller screens. */}
      <div className="pointer-events-none absolute inset-x-0 top-0 hidden h-[480px] opacity-60 md:block hero-grid-bg" aria-hidden />

      <div className="relative mx-auto w-full max-w-7xl px-5 py-10 md:px-8 md:py-14">
        {/* ───── Header ───── */}
        <header className="mb-12 flex flex-col gap-6">
          <Link
            href="/"
            className="gm-focus inline-flex w-fit items-center gap-2 font-mono text-[11px] uppercase tracking-[0.16em] text-bm-slate transition-colors hover:text-bm-lime dark:text-blueprint-mist/55"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Back
          </Link>

          <div className="flex flex-col gap-3">
            <span className="gm-eyebrow flex items-center gap-2">
              <Flag className="h-3 w-3" aria-hidden /> GRIDMIND · Roadmap
            </span>
            <h1 className="max-w-3xl font-sans text-4xl font-semibold tracking-tight text-blueprint-navy dark:text-blueprint-mist md:text-5xl">
              From research prototype to a{" "}
              <span className="text-bm-ink underline decoration-bm-lime decoration-4 underline-offset-[6px] dark:text-bm-lime dark:decoration-bm-lime/80">
                BESCOM pilot
              </span>
              , then scale.
            </h1>
            <p className="max-w-2xl font-sans text-base text-bm-slate dark:text-blueprint-mist/65">
              GRIDMIND is an AI-driven EV charging optimisation system for
              Bengaluru&rsquo;s distribution grid. Below is an honest view of
              what works today, what we&rsquo;re hardening for the BESCOM
              pilot, and what we&rsquo;re building next.
            </p>
          </div>

          {/* KPI strip — three numbers that anchor the roadmap. */}
          <div className="grid grid-cols-3 gap-4 rounded-card border border-bm-line/30 bg-bm-surface/80 p-5 shadow-card backdrop-blur-sm dark:border-white/10 dark:bg-bm-graphite/80">
            <div>
              <p className="gm-eyebrow">Built</p>
              <p className="mt-1 font-mono text-3xl tabular-nums text-blueprint-navy dark:text-bm-lime">
                5
              </p>
              <p className="mt-1 font-sans text-xs text-bm-slate dark:text-blueprint-mist/55">
                core capabilities shipped
              </p>
            </div>
            <div className="border-l border-bm-line/30 pl-4 dark:border-white/10">
              <p className="gm-eyebrow">In flight</p>
              <p className="mt-1 font-mono text-3xl tabular-nums text-blueprint-navy dark:text-bm-magenta">
                5
              </p>
              <p className="mt-1 font-sans text-xs text-bm-slate dark:text-blueprint-mist/55">
                pilot-readiness items
              </p>
            </div>
            <div className="border-l border-bm-line/30 pl-4 dark:border-white/10">
              <p className="gm-eyebrow">Planned</p>
              <p className="mt-1 font-mono text-3xl tabular-nums text-blueprint-navy dark:text-blueprint-mist">
                5
              </p>
              <p className="mt-1 font-sans text-xs text-bm-slate dark:text-blueprint-mist/55">
                scale-up bets
              </p>
            </div>
          </div>
        </header>

        {/* ───── Kanban: 3 phase columns ───── */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {PHASES.map((phase, i) => (
            <PhaseColumn key={phase.key} phase={phase} index={i} />
          ))}
        </div>

        {/* ───── Footer note ───── */}
        <footer className="mt-12 flex flex-col items-start justify-between gap-4 border-t border-bm-line/40 pt-6 dark:border-white/10 md:flex-row md:items-center">
          <div>
            <p className="font-sans text-sm text-blueprint-navy dark:text-blueprint-mist">
              GRIDMIND is a research prototype. Today&rsquo;s recommendations
              are advisory only — no commands flow to BESCOM infrastructure.
            </p>
            <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.18em] text-bm-slate dark:text-blueprint-mist/45">
              Based on peer-reviewed work · Scientific Reports (Nature) · IEEE OCPP studies
            </p>
          </div>
          <Link
            href="/dashboard"
            className="gm-focus inline-flex items-center gap-2 rounded-chip bg-bm-lime px-4 py-2 font-sans text-sm font-semibold text-bm-ink transition-transform hover:scale-[1.02] hover:bg-bm-lime-soft"
          >
            Open the operator dashboard
            <ArrowUpRight className="h-4 w-4" aria-hidden />
          </Link>
        </footer>
      </div>
    </main>
  );
}

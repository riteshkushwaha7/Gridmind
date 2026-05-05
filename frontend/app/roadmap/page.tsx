import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ArrowUpRight, CheckCircle2, Flag } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export const metadata: Metadata = {
  title: "GRIDMIND — Roadmap",
  description: "Bengaluru mock dataset today, BESCOM pilot tomorrow.",
};

type Phase = {
  key: "current" | "final";
  label: string;
  caption: string;
  status: string;
  accent: "lime" | "magenta";
  icon: LucideIcon;
  items: { title: string; body: string }[];
};

const PHASES: Phase[] = [
  {
    key: "current",
    label: "Current · Bengaluru mock",
    caption: "Prototype · shipping now",
    status: "Live (frontend only)",
    accent: "lime",
    icon: CheckCircle2,
    items: [
      {
        title: "10 curated Bengaluru zones",
        body: "Whitefield, Koramangala, Electronic City and seven more feeders modelled end-to-end with demand, tariff, and charger mix.",
      },
      {
        title: "Full-stack mocks in the repo",
        body: "Six FastAPI data nodes, LSTM, PPO, and clustering services are simulated so the UI works without Docker at all.",
      },
      {
        title: "Operator UX on Next.js 14",
        body: "Dashboard, forecasting, planner, and stations views powered entirely by TanStack Query mocks for instant demos.",
      },
      {
        title: "Safety rails baked in",
        body: "Every schedule shown in the UI already reflects hard feeder caps, PF fallback, and transparent reasoning strings.",
      },
    ],
  },
  {
    key: "final",
    label: "Final · BESCOM pilot",
    caption: "What we're hardening next",
    status: "Next milestone",
    accent: "magenta",
    icon: Flag,
    items: [
      {
        title: "Bridge live SCADA feeds",
        body: "Swap the simulator for the actual 66/11 kV feeder telemetry so the same UI reflects production signals.",
      },
      {
        title: "Operator auth + audit",
        body: "Role-based access with change logs in PostgreSQL before allowing schedule overrides in the control room.",
      },
      {
        title: "Alerting + on-call hooks",
        body: "SMS / mail fan-out for headroom breaches and PPO caps so BESCOM field teams get a heads-up immediately.",
      },
      {
        title: "Shadow-mode PPO",
        body: "Push PPO recommendations alongside live commands, reviewed by an operator before dispatching to chargers.",
      },
    ],
  },
];

const accentClass = {
  lime: {
    chip: "bg-bm-lime/15 text-bm-ink ring-1 ring-bm-lime/40",
    bar: "bg-bm-lime",
    dot: "bg-bm-lime shadow-[0_0_0_4px_rgba(181,242,58,0.18)]",
    icon: "text-bm-ink",
    accentText: "text-bm-ink",
  },
  magenta: {
    chip: "bg-bm-magenta/12 text-bm-magenta ring-1 ring-bm-magenta/35",
    bar: "bg-bm-magenta",
    dot: "bg-bm-magenta shadow-[0_0_0_4px_rgba(255,61,138,0.18)]",
    icon: "text-bm-magenta",
    accentText: "text-bm-magenta",
  },
} as const;

function PhaseHeader({ phase }: { phase: Phase }) {
  const Icon = phase.icon;
  const a = accentClass[phase.accent];
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="gm-eyebrow">{phase.caption}</p>
        <h2 className="mt-2 flex items-center gap-2 font-sans text-2xl font-semibold tracking-tight text-blueprint-navy">
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
          className="absolute left-[5px] top-1.5 bottom-1.5 w-px bg-bm-line"
          aria-hidden
        />
        {phase.items.map((item, i) => (
          <li key={i} className="relative">
            <span
              className={`absolute -left-5 top-1.5 h-2.5 w-2.5 rounded-full ${a.dot}`}
              aria-hidden
            />
            <div className="rounded-card bg-white/40 p-3 ring-1 ring-bm-line/40 transition-colors hover:bg-white">
              <p className="font-sans text-sm font-semibold text-blueprint-navy">
                {item.title}
              </p>
              <p className="mt-1 font-sans text-[13px] leading-relaxed text-bm-slate">
                {item.body}
              </p>
            </div>
          </li>
        ))}
      </ol>
      <p className={`mt-auto font-mono text-[10px] uppercase tracking-[0.18em] ${a.accentText}`}>
        {String(index + 1).padStart(2, "0")} / 02
      </p>
    </section>
  );
}

export default function RoadmapPage() {
  return (
    <main className="relative min-h-screen bg-bm-mist text-blueprint-navy">
      {/* Decorative grid background — subtle, fades on smaller screens. */}
      <div className="pointer-events-none absolute inset-x-0 top-0 hidden h-[480px] opacity-60 md:block hero-grid-bg" aria-hidden />

      <div className="relative mx-auto w-full max-w-7xl px-5 py-10 md:px-8 md:py-14">
        {/* ───── Header ───── */}
        <header className="mb-12 flex flex-col gap-6">
          <Link
            href="/"
            className="gm-focus inline-flex w-fit items-center gap-2 font-mono text-[11px] uppercase tracking-[0.16em] text-bm-slate transition-colors hover:text-bm-lime"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Back
          </Link>

          <div className="flex flex-col gap-3">
            <span className="gm-eyebrow flex items-center gap-2">
              <Flag className="h-3 w-3" aria-hidden /> GRIDMIND · Roadmap
            </span>
            <h1 className="max-w-3xl font-sans text-4xl font-semibold tracking-tight text-blueprint-navy md:text-5xl">
              Bengaluru mock today, BESCOM pilot tomorrow.
            </h1>
            <p className="max-w-2xl font-sans text-base text-bm-slate">
              Everything you see in the operator dashboard is powered by a
              Bengaluru-first mock dataset. This page documents what&rsquo;s
              already shippable in that mode and the concrete work queued up to
              make it production-grade for BESCOM.
            </p>
          </div>

          {/* KPI strip */}
          <div className="grid grid-cols-2 gap-4 rounded-card border border-bm-line/30 bg-bm-surface/80 p-5 shadow-card backdrop-blur-sm">
            <div>
              <p className="gm-eyebrow">Built</p>
              <p className="mt-1 font-mono text-3xl tabular-nums text-blueprint-navy">
                4
              </p>
              <p className="mt-1 font-sans text-xs text-bm-slate">
                mock-first modules live in repo
              </p>
            </div>
            <div className="border-l border-bm-line/30 pl-4">
              <p className="gm-eyebrow">Next up</p>
              <p className="mt-1 font-mono text-3xl tabular-nums text-blueprint-navy">
                4
              </p>
              <p className="mt-1 font-sans text-xs text-bm-slate">
                pilot-hardening tasks
              </p>
            </div>
          </div>
        </header>

        {/* ───── Phases ───── */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {PHASES.map((phase, i) => (
            <PhaseColumn key={phase.key} phase={phase} index={i} />
          ))}
        </div>

        {/* ───── Footer note ───── */}
        <footer className="mt-12 flex flex-col items-start justify-between gap-4 border-t border-bm-line/40 pt-6 md:flex-row md:items-center">
          <div>
            <p className="font-sans text-sm text-blueprint-navy">
              GRIDMIND is a research prototype. Today&rsquo;s recommendations
              are advisory only — no commands flow to BESCOM infrastructure.
            </p>
            <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.18em] text-bm-slate">
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

"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight, Route, Zap } from "lucide-react";

export function LandingHero() {
  return (
    <main className="relative z-10 mx-auto flex w-full max-w-5xl flex-1 flex-col items-start justify-center gap-10 px-6 py-20 md:px-10 md:py-24">
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="flex flex-col gap-6"
      >
        <span className="gm-eyebrow inline-flex items-center gap-2">
          <span
            className="flex h-6 w-6 items-center justify-center rounded-chip bg-bm-lime/15 text-bm-ink ring-1 ring-bm-lime/40 dark:text-bm-lime"
            aria-hidden
          >
            <Zap className="h-3.5 w-3.5" strokeWidth={2.4} />
          </span>
          Research prototype · BESCOM
        </span>

        <h1 className="font-sans text-4xl font-bold leading-[1.05] tracking-tight text-blueprint-navy dark:text-blueprint-mist sm:text-5xl md:text-6xl">
          AI-driven EV charging,
          <br />
          <span className="text-bm-ink underline decoration-bm-lime decoration-[6px] underline-offset-[8px] dark:text-bm-lime dark:decoration-bm-lime/80">
            built for the grid&rsquo;s real constraints.
          </span>
        </h1>

        <p className="max-w-2xl font-sans text-lg leading-relaxed text-bm-slate dark:text-blueprint-mist/70">
          GRIDMIND forecasts feeder load, schedules chargers under live tariff
          and headroom constraints, and ranks where Bengaluru should add the
          next stations. Recommendations are advisory — operators stay in
          control.
        </p>

        <div className="mt-2 flex flex-wrap items-center gap-3">
          <Link
            href="/dashboard"
            className="gm-btn-primary text-base font-semibold"
          >
            Open the operator dashboard
            <ArrowUpRight className="h-4 w-4" />
          </Link>
          <Link
            href="/roadmap"
            className="gm-btn-ghost text-base font-medium"
          >
            <Route className="h-4 w-4" />
            See the roadmap
          </Link>
        </div>
      </motion.div>
    </main>
  );
}

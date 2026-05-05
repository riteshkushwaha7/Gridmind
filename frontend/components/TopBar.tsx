"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Bell } from "lucide-react";
import { useDashboardOverview } from "@/hooks/useDashboard";
import { routeTitles } from "@/lib/routeTitles";
import { StatusChip, systemStatusTone } from "@/components/ui/StatusChip";

function formatClock(d: Date) {
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatDate(d: Date) {
  return d.toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "short",
  });
}

export function TopBar() {
  const pathname = usePathname();
  const title = routeTitles[pathname] ?? "GRIDMIND";
  const [now, setNow] = useState<Date | null>(null);
  const [mounted, setMounted] = useState(false);
  const { data: overview } = useDashboardOverview();

  useEffect(() => {
    setMounted(true);
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);

  const status = overview?.system_status;
  const tariff = overview?.current_tariff;
  const alertCount = overview?.alerts.length ?? 0;

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b border-bm-line/40 bg-white/90 px-5 backdrop-blur-md md:px-8">
      {/* Title + clock */}
      <div className="min-w-0">
        <h1 className="truncate font-sans text-base font-bold tracking-tight text-blueprint-navy md:text-lg">
          {title}
        </h1>
        <p
          className="hidden font-sans text-[11px] text-bm-slate sm:block"
          suppressHydrationWarning
        >
          {mounted && now
            ? `${formatDate(now)} · ${formatClock(now)} IST`
            : "—"}
        </p>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        {/* System status pill */}
        {status ? (
          <StatusChip tone={systemStatusTone(status)}>{status}</StatusChip>
        ) : null}

        {/* Tariff readout */}
        {tariff ? (
          <span className="hidden items-center gap-2 rounded-card border border-bm-line/40 bg-white px-3 py-1.5 font-sans text-xs text-blueprint-navy sm:inline-flex">
            <span className="font-semibold text-blueprint-navy">
              ₹{tariff.rate_inr.toFixed(2)}
            </span>
            <span className="text-bm-slate">
              /kWh · {tariff.tier.replace("_", " ").toLowerCase()} · Bangalore
            </span>
          </span>
        ) : null}

        {/* Alerts bell */}
        <button
          type="button"
          className="gm-focus relative inline-flex h-9 w-9 items-center justify-center rounded-card border border-bm-line/40 bg-white text-blueprint-navy transition-colors hover:bg-bm-mist"
          aria-label={`${alertCount} alerts`}
        >
          <Bell className="h-4 w-4" />
          {alertCount > 0 ? (
            <span className="absolute -right-1 -top-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-bm-magenta px-1 font-mono text-[10px] font-semibold text-white">
              {alertCount}
            </span>
          ) : null}
        </button>

        <span className="hidden text-[11px] uppercase tracking-[0.18em] text-bm-slate md:inline">
          Mock data · Bengaluru city limits
        </span>
      </div>
    </header>
  );
}

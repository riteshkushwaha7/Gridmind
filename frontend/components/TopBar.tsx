"use client";

import { useTheme } from "next-themes";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Bell, Moon, Sun } from "lucide-react";
import { useDashboardOverview } from "@/hooks/useDashboard";
import { routeTitles } from "@/lib/routeTitles";
import { cn } from "@/lib/cn";
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
  const { resolvedTheme, setTheme } = useTheme();
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
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b border-bm-line/60 bg-bm-mist/85 px-5 backdrop-blur-md dark:border-white/10 dark:bg-bm-ink/85 md:px-8">
      {/* Title + clock */}
      <div className="min-w-0">
        <h1 className="truncate font-sans text-base font-bold tracking-tight text-blueprint-navy dark:text-blueprint-mist md:text-lg">
          {title}
        </h1>
        <p
          className="hidden font-sans text-[11px] text-bm-slate dark:text-blueprint-mist/55 sm:block"
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
          <span className="hidden items-center gap-2 rounded-card border border-bm-line/60 bg-bm-surface px-3 py-1.5 font-sans text-xs dark:border-white/10 dark:bg-white/5 sm:inline-flex">
            <span className="font-semibold text-blueprint-navy dark:text-blueprint-mist">
              ₹{tariff.rate_inr.toFixed(2)}
            </span>
            <span className="text-bm-slate dark:text-blueprint-mist/55">
              /kWh · {tariff.tier.replace("_", " ").toLowerCase()}
            </span>
          </span>
        ) : null}

        {/* Alerts bell */}
        <button
          type="button"
          className="gm-focus relative inline-flex h-9 w-9 items-center justify-center rounded-card border border-bm-line/60 bg-bm-surface text-blueprint-navy transition-colors hover:bg-bm-mist dark:border-white/10 dark:bg-white/5 dark:text-blueprint-mist dark:hover:bg-white/10"
          aria-label={`${alertCount} alerts`}
        >
          <Bell className="h-4 w-4" />
          {alertCount > 0 ? (
            <span className="absolute -right-1 -top-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-bm-magenta px-1 font-mono text-[10px] font-semibold text-white">
              {alertCount}
            </span>
          ) : null}
        </button>

        {/* Theme toggle */}
        <button
          type="button"
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
          className={cn(
            "gm-focus inline-flex h-9 w-9 items-center justify-center rounded-card border border-bm-line/60 bg-bm-surface text-blueprint-navy transition-colors hover:bg-bm-mist",
            "dark:border-white/10 dark:bg-white/5 dark:text-blueprint-mist dark:hover:bg-white/10",
          )}
          aria-label="Toggle colour theme"
        >
          {!mounted ? (
            <span className="block h-4 w-4 rounded-sm bg-current opacity-20" />
          ) : resolvedTheme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </button>
      </div>
    </header>
  );
}

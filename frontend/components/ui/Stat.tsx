import { cn } from "@/lib/cn";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Card } from "./Card";

export type Tone = "lime" | "magenta" | "ok" | "warn" | "danger" | "slate";

const toneAccent: Record<Tone, string> = {
  lime:    "text-bm-ink dark:text-bm-lime",
  magenta: "text-bm-magenta",
  ok:      "text-bm-ok",
  warn:    "text-bm-warn",
  danger:  "text-bm-danger",
  slate:   "text-bm-slate",
};

const toneRing: Record<Tone, string> = {
  lime:    "ring-bm-lime/30",
  magenta: "ring-bm-magenta/30",
  ok:      "ring-bm-ok/30",
  warn:    "ring-bm-warn/30",
  danger:  "ring-bm-danger/30",
  slate:   "ring-bm-slate/25",
};

/**
 * KPI card. Big number, label, optional icon and trend caption.
 */
export function Stat({
  label,
  value,
  suffix,
  icon: Icon,
  tone = "lime",
  caption,
  accent = false,
  className,
}: {
  label: string;
  value: ReactNode;
  suffix?: ReactNode;
  icon?: LucideIcon;
  tone?: Tone;
  caption?: ReactNode;
  accent?: boolean;
  className?: string;
}) {
  return (
    <Card accent={accent} className={cn("flex flex-col gap-3", className)}>
      <div className="flex items-start justify-between gap-3">
        <p className="gm-eyebrow">{label}</p>
        {Icon ? (
          <span
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-chip ring-1",
              toneRing[tone],
              toneAccent[tone],
            )}
            aria-hidden
          >
            <Icon className="h-4 w-4" />
          </span>
        ) : null}
      </div>
      <p className="flex items-baseline gap-2">
        <span className="gm-stat-num">{value}</span>
        {suffix ? <span className="gm-stat-suffix">{suffix}</span> : null}
      </p>
      {caption ? (
        <p className="font-sans text-xs text-bm-slate dark:text-blueprint-mist/55">
          {caption}
        </p>
      ) : null}
    </Card>
  );
}

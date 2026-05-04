import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

export type ChipTone = "ok" | "warn" | "danger" | "lime" | "magenta" | "slate";

const variants: Record<ChipTone, string> = {
  ok:      "gm-chip-ok",
  warn:    "gm-chip-warn",
  danger:  "gm-chip-danger",
  lime:    "gm-chip-lime",
  magenta: "gm-chip-magenta",
  slate:   "gm-chip-slate",
};

/** Status chip — one of the canonical tones. */
export function StatusChip({
  tone = "slate",
  children,
  className,
}: {
  tone?: ChipTone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("gm-chip", variants[tone], className)}>{children}</span>
  );
}

/**
 * Map a backend feeder status string to a chip tone.
 */
export function feederStatusTone(
  status: string | undefined,
): ChipTone {
  switch (status) {
    case "NORMAL":
      return "ok";
    case "WARNING":
      return "warn";
    case "CONSTRAINED":
      return "warn";
    case "OVERLOAD":
      return "danger";
    default:
      return "slate";
  }
}

/**
 * Map a system status to a chip tone.
 */
export function systemStatusTone(
  status: string | undefined,
): ChipTone {
  switch (status) {
    case "HEALTHY":
      return "ok";
    case "DEGRADED":
      return "warn";
    case "CRITICAL":
      return "danger";
    default:
      return "slate";
  }
}

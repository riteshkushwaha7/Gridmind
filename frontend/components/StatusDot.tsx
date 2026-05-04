import { cn } from "@/lib/cn";

type StatusTone = "green" | "amber" | "red";

const tones: Record<StatusTone, { ring: string; fill: string }> = {
  green: {
    ring: "bg-[#0D9488]/35",
    fill: "bg-[#0D9488]",
  },
  amber: {
    ring: "bg-[#F59E0B]/35",
    fill: "bg-[#F59E0B]",
  },
  red: {
    ring: "bg-red-500/35",
    fill: "bg-red-400",
  },
};

export function StatusDot({
  color,
  className,
  label,
}: {
  color: StatusTone;
  className?: string;
  /** Visually hidden label for screen readers */
  label?: string;
}) {
  const t = tones[color];
  return (
    <span
      className={cn("relative inline-flex h-2 w-2 shrink-0", className)}
      role="img"
      aria-label={label ?? `${color} status`}
    >
      <span
        className={cn(
          "absolute inline-flex h-full w-full animate-ping rounded-full opacity-60",
          t.fill,
        )}
      />
      <span
        className={cn(
          "relative inline-flex h-2 w-2 rounded-full",
          t.ring,
          "p-0.5",
        )}
      >
        <span className={cn("h-full w-full rounded-full", t.fill)} />
      </span>
    </span>
  );
}

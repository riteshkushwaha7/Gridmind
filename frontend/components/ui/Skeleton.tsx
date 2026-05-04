import { cn } from "@/lib/cn";

/**
 * Loading placeholder. Used while a useQuery hook is fetching.
 * Lands as a soft pulsing block on the page so the layout doesn't shift.
 */
export function Skeleton({
  className,
}: {
  className?: string;
}) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-card bg-bm-slate/10 dark:bg-white/5",
        className,
      )}
    />
  );
}

/** Inline empty-state copy when a hook has no data. */
export function EmptyState({
  title,
  hint,
  className,
}: {
  title: string;
  hint?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-start gap-1 rounded-card border border-dashed border-bm-line/60 bg-bm-mist/40 p-5 text-sm dark:border-white/10 dark:bg-white/[0.02]",
        className,
      )}
    >
      <p className="font-sans font-semibold text-blueprint-navy dark:text-blueprint-mist">
        {title}
      </p>
      {hint ? (
        <p className="text-bm-slate dark:text-blueprint-mist/55">{hint}</p>
      ) : null}
    </div>
  );
}

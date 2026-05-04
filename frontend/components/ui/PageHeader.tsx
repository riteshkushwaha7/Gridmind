import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

/**
 * Standard page header — eyebrow, title, optional subtitle and action area.
 * Used at the top of every operator page so the typography is identical.
 */
export function PageHeader({
  eyebrow,
  title,
  subtitle,
  action,
  className,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        "mb-6 flex flex-col gap-4 md:mb-8 md:flex-row md:items-end md:justify-between",
        className,
      )}
    >
      <div className="min-w-0">
        {eyebrow ? <p className="gm-eyebrow mb-2">{eyebrow}</p> : null}
        <h1 className="font-sans text-2xl font-bold tracking-tight text-blueprint-navy dark:text-blueprint-mist md:text-3xl">
          {title}
        </h1>
        {subtitle ? (
          <p className="mt-1.5 max-w-2xl text-sm text-bm-slate dark:text-blueprint-mist/55">
            {subtitle}
          </p>
        ) : null}
      </div>
      {action ? <div className="flex items-center gap-2">{action}</div> : null}
    </header>
  );
}

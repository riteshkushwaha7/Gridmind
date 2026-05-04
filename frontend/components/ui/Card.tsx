import { cn } from "@/lib/cn";
import type { HTMLAttributes, ReactNode } from "react";

type CardProps = HTMLAttributes<HTMLDivElement> & { accent?: boolean };

/**
 * Standard surface used by every page. The `gm-card` class encapsulates the
 * border, radius, padding (p-5) and shadow tokens defined in globals.css —
 * change them there to retheme the whole app.
 */
export function Card({ className, accent = false, ...props }: CardProps) {
  return (
    <div
      {...props}
      className={cn(accent ? "gm-card-accent" : "gm-card", className)}
    />
  );
}

export function CardHeader({
  eyebrow,
  title,
  action,
  description,
  className,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  action?: ReactNode;
  description?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-4", className)}>
      <div className="min-w-0">
        {eyebrow ? <p className="gm-eyebrow mb-1.5">{eyebrow}</p> : null}
        <h3 className="font-sans text-base font-semibold tracking-tight text-blueprint-navy dark:text-blueprint-mist">
          {title}
        </h3>
        {description ? (
          <p className="mt-1 text-sm text-bm-slate dark:text-blueprint-mist/55">
            {description}
          </p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

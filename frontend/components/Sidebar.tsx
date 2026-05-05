"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Compass,
  LayoutDashboard,
  MapPin,
  Route,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

type NavItem = { href: string; label: string; icon: LucideIcon; end?: boolean };

const TOP: NavItem[] = [
  { href: "/dashboard",   label: "Dashboard",  icon: LayoutDashboard },
  { href: "/stations",    label: "Stations",   icon: Zap },
  { href: "/forecasting", label: "Forecasting", icon: Activity },
  { href: "/planner",     label: "Planner",    icon: MapPin },
];

const BOTTOM: NavItem[] = [
  { href: "/roadmap", label: "Roadmap", icon: Route },
  { href: "/",        label: "Landing", icon: Compass, end: true },
];

function isActive(pathname: string, href: string, end?: boolean) {
  if (end) return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavLink({
  item,
  active,
}: {
  item: NavItem;
  active: boolean;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      title={item.label}
      className={cn(
        "group/nav relative flex h-11 items-center gap-3 overflow-hidden rounded-card px-3 font-sans text-sm transition-colors",
        active
          ? "bg-bm-lime/20 text-bm-ink"
          : "text-bm-slate hover:bg-bm-mist hover:text-blueprint-navy",
      )}
    >
      {active ? (
        <span
          className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-bm-lime"
          aria-hidden
        />
      ) : null}
      <Icon className="h-5 w-5 shrink-0" strokeWidth={active ? 2.2 : 1.8} />
      <span className="hidden truncate font-medium group-hover/sidebar:inline">
        {item.label}
      </span>
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "group/sidebar fixed left-0 top-0 z-40 hidden h-screen w-16 flex-col border-r border-bm-line/30 bg-white text-blueprint-navy md:flex",
        "transition-[width] duration-200 ease-out hover:w-[228px]",
      )}
      aria-label="Primary"
    >
      {/* Logo */}
      <Link
        href="/"
        className="flex h-16 shrink-0 items-center gap-3 px-4 text-bm-ink"
      >
        <span
          className="flex h-9 w-9 items-center justify-center rounded-card bg-bm-lime/20 ring-1 ring-bm-lime/40"
          aria-hidden
        >
          <Zap className="h-5 w-5" strokeWidth={2.4} />
        </span>
        <div className="hidden flex-col leading-tight group-hover/sidebar:flex">
          <span className="font-sans text-sm font-bold tracking-wide text-blueprint-navy">
            GRIDMIND
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-bm-slate">
            BESCOM · operator
          </span>
        </div>
      </Link>

      <nav className="flex flex-1 flex-col gap-1 px-2 pt-2">
        {TOP.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            active={isActive(pathname, item.href, item.end)}
          />
        ))}
      </nav>

      <div className="flex flex-col gap-1 px-2 pb-4">
        <span
          className="mx-3 mb-2 hidden font-mono text-[10px] uppercase tracking-[0.18em] text-bm-slate/70 group-hover/sidebar:block"
          aria-hidden
        >
          More
        </span>
        {BOTTOM.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            active={isActive(pathname, item.href, item.end)}
          />
        ))}
      </div>
    </aside>
  );
}

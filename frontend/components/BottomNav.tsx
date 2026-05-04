"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, LayoutDashboard, MapPin, Route, Zap } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

type NavItem = { href: string; label: string; icon: LucideIcon };

const items: NavItem[] = [
  { href: "/dashboard",   label: "Grid",     icon: LayoutDashboard },
  { href: "/stations",    label: "Stations", icon: Zap },
  { href: "/forecasting", label: "Forecast", icon: Activity },
  { href: "/planner",     label: "Planner",  icon: MapPin },
  { href: "/roadmap",     label: "Roadmap",  icon: Route },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 flex border-t border-white/5 bg-bm-ink/95 backdrop-blur-md md:hidden"
      aria-label="Primary"
    >
      {items.map(({ href, label, icon: Icon }) => {
        const active =
          pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex min-h-[52px] flex-1 flex-col items-center justify-center gap-0.5 px-1 py-1.5 transition-colors",
              active ? "text-bm-lime" : "text-white/55 hover:text-white",
            )}
          >
            <Icon className="h-5 w-5 shrink-0" strokeWidth={active ? 2.2 : 1.8} />
            <span className="font-sans text-[10px] font-medium leading-none">
              {label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}

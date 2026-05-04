"use client";

import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";

export function OperatorFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-bm-mist text-blueprint-navy dark:bg-bm-ink dark:text-blueprint-mist">
      <Sidebar />
      <div className="flex min-h-0 flex-1 flex-col md:pl-16">
        <TopBar />
        <main className="flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}

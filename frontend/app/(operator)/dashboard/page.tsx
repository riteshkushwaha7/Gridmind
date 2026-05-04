import type { Metadata } from "next";
import { DashboardClient } from "@/components/dashboard/DashboardClient";

export const metadata: Metadata = {
  title: "Operations Dashboard · GRIDMIND",
  description:
    "Live fleet KPIs, network load, AI agent status, and tariff context for GRIDMIND operators.",
};

export default function DashboardPage() {
  return <DashboardClient />;
}
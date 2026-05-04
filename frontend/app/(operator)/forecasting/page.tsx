import type { Metadata } from "next";
import { ForecastingPageClient } from "@/components/forecasting/ForecastingPageClient";

export const metadata: Metadata = {
  title: "Demand Forecasting · GRIDMIND",
  description:
    "BESCOM Part A: 15-minute demand forecasting, schedule advisor, and zone-level Bengaluru signals.",
};

export default function ForecastingPage() {
  return <ForecastingPageClient />;
}
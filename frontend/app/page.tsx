import type { Metadata } from "next";
import { LandingHero } from "@/components/LandingHero";
import { LandingSections } from "@/components/landing/LandingSections";

export const metadata: Metadata = {
  title: "GRIDMIND — AI-Driven EV Charging Optimization",
  description:
    "Research prototype for BESCOM: demand forecasting, PPO scheduling, and infrastructure siting for smart EV charging.",
};

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <div className="relative flex flex-col hero-grid-bg">
        <div className="pointer-events-none absolute inset-0 bg-bm-mist/55" aria-hidden />
        <LandingHero />
      </div>
      <LandingSections />
    </div>
  );
}

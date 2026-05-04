import type { Metadata } from "next";
import { PlannerPageClient } from "@/components/planner/PlannerPageClient";

export const metadata: Metadata = {
  title: "Infrastructure Planner · GRIDMIND",
  description:
    "BESCOM Part B: K-means demand clustering and grid-constrained charging station siting recommendations for Bengaluru zones.",
};

export default function PlannerPage() {
  return <PlannerPageClient />;
}

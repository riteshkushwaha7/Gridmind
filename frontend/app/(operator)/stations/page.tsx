import type { Metadata } from "next";
import { StationsPageClient } from "@/components/stations/StationsPageClient";

export const metadata: Metadata = {
  title: "Station Monitor · GRIDMIND",
  description:
    "OCPP-aligned station list, connector detail, and tariff view for each site in the GRIDMIND fleet.",
};

export default function StationsPage() {
  return <StationsPageClient />;
}
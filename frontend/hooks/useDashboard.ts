"use client";

import { useQuery } from "@tanstack/react-query";

import { getAlerts, getDashboardOverview, getZoneDetail } from "@/lib/api";

export function useDashboardOverview() {
  return useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: getDashboardOverview,
    staleTime: 15_000,
    refetchInterval: 15_000,
  });
}

export function useZoneDetail(zoneId: string | null | undefined) {
  return useQuery({
    queryKey: ["dashboard", "zone", zoneId],
    queryFn: () => getZoneDetail(zoneId as string),
    enabled: Boolean(zoneId),
    staleTime: 15_000,
  });
}

export function useAlerts() {
  return useQuery({
    queryKey: ["dashboard", "alerts"],
    queryFn: getAlerts,
    staleTime: 5_000,
    refetchInterval: 5_000,
  });
}

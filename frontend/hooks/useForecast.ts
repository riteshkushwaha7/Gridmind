"use client";

import { useQuery } from "@tanstack/react-query";

import { getAllForecast, getZoneForecast } from "@/lib/api";

export function useZoneForecast(
  zoneId: string | null | undefined,
  hours: number,
) {
  return useQuery({
    queryKey: ["forecast", "zone", zoneId, hours],
    queryFn: () => getZoneForecast(zoneId as string, hours),
    enabled: Boolean(zoneId),
    staleTime: 300_000,
  });
}

export function useAllForecast(hours: number) {
  return useQuery({
    queryKey: ["forecast", "all", hours],
    queryFn: () => getAllForecast(hours),
    staleTime: 300_000,
  });
}

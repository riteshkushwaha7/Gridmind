"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getCurrentSchedule, overrideZoneSchedule } from "@/lib/api";

export function useCurrentSchedule() {
  return useQuery({
    queryKey: ["schedule", "current"],
    queryFn: getCurrentSchedule,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}

export function useOverrideSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ zoneId, powerKw }: { zoneId: string; powerKw: number }) =>
      overrideZoneSchedule(zoneId, powerKw),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedule", "current"] });
    },
  });
}

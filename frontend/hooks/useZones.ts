"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getZoneRanking, triggerReplan } from "@/lib/api";

export function useZoneRanking() {
  return useQuery({
    queryKey: ["zones", "ranking"],
    queryFn: getZoneRanking,
    staleTime: 3_600_000,
  });
}

export function useReplan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: triggerReplan,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["zones", "ranking"] });
    },
  });
}

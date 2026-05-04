"use client";

import { create } from "zustand";

import type { SystemStatus } from "@/lib/types";

export type TimeRange = "1h" | "4h" | "12h" | "24h";

type GridmindStore = {
  selectedZoneId: string | null;
  setSelectedZoneId: (id: string | null) => void;
  timeRange: TimeRange;
  setTimeRange: (range: TimeRange) => void;
  alertCount: number;
  setAlertCount: (count: number) => void;
  systemStatus: SystemStatus;
  setSystemStatus: (status: SystemStatus) => void;
  isBackendConnected: boolean;
  setIsBackendConnected: (v: boolean) => void;
};

export const useGridmindStore = create<GridmindStore>((set) => ({
  selectedZoneId: null,
  setSelectedZoneId: (id) => set({ selectedZoneId: id }),

  timeRange: "4h",
  setTimeRange: (range) => set({ timeRange: range }),

  alertCount: 0,
  setAlertCount: (count) => set({ alertCount: count }),

  systemStatus: "HEALTHY",
  setSystemStatus: (status) => set({ systemStatus: status }),

  isBackendConnected: false,
  setIsBackendConnected: (v) => set({ isBackendConnected: v }),
}));

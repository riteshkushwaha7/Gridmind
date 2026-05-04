"""Gymnasium environment for the PPO charge-scheduling agent.

Episode = 96 steps (24h × 15-min). Each step:
  1. Action a ∈ [0, 1]^Z is normalised charging power per zone.
  2. Safety filter projects onto feasible set (P_final = min(P_AI, P_max)).
  3. Reward = -(α·cost + β·peak_norm) + γ·energy_norm.

State is bootstrapped from a synthetic generator so PPO can train without a
live data plane. In production the state factory can be swapped out (see
`build_synthetic_state_fn`) for one that pulls live values from Redis.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Callable, Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from config import (
    LSTM_HORIZON,
    PPO_ACTION_DIM,
    PPO_EPISODE_LEN,
    PPO_OBS_DIM,
    PPO_REWARD_ALPHA,
    PPO_REWARD_BETA,
    PPO_REWARD_GAMMA,
    ZONES,
)
from ppo.safety import ZoneSafetyState, apply as safety_apply

NUM_ZONES = len(ZONES)
DEFAULT_CAPACITY_KW = np.array(
    [900, 1100, 800, 1800, 2000, 1700, 600, 650, 600, 1300], dtype=np.float32
)


@dataclass
class Snapshot:
    forecast_16: np.ndarray            # (16,)
    tariff_inr: float
    feeder_headroom_pct: np.ndarray    # (Z,)
    active_evs: np.ndarray             # (Z,) int
    avg_soc: np.ndarray                # (Z,)
    battery_soc: np.ndarray            # (Z,)
    solar_output_kw: np.ndarray        # (Z,)
    hour: int                          # 0..23
    is_weekend: bool


StateFn = Callable[[int], Snapshot]   # step → Snapshot


def _peak_for_hour(h: int, weekend: bool) -> float:
    base = 0.4 + 0.5 * math.exp(-((h - 19) ** 2) / 8)   # evening peak
    if not weekend:
        base += 0.2 * math.exp(-((h - 9) ** 2) / 6)     # morning shoulder
    return base


def build_synthetic_state_fn(seed: int = 0) -> StateFn:
    rng = random.Random(seed)
    npr = np.random.default_rng(seed)

    def fn(step: int) -> Snapshot:
        hour = (step // 4) % 24
        is_we = (step // 96) % 7 >= 5
        peak = _peak_for_hour(hour, is_we)
        forecast = np.array([
            DEFAULT_CAPACITY_KW.mean() * peak * (0.95 + 0.1 * npr.random())
            for _ in range(LSTM_HORIZON)
        ], dtype=np.float32)
        tariff = float(np.interp(hour, [0, 6, 17, 21, 23], [4.5, 7.0, 9.5, 11.0, 4.5]))
        headroom = np.clip(60 - 50 * peak + npr.normal(0, 8, NUM_ZONES), 5, 100).astype(np.float32)
        evs = np.clip((peak * 25 + npr.normal(0, 4, NUM_ZONES)).astype(int), 0, 50)
        soc = np.clip(npr.uniform(20, 60, NUM_ZONES), 5, 95).astype(np.float32)
        batt = np.clip(50 + npr.normal(0, 15, NUM_ZONES), 5, 95).astype(np.float32)
        solar_peak = max(0.0, math.sin(max(0, (hour - 6) / 12) * math.pi))
        solar = (solar_peak * 0.6 * DEFAULT_CAPACITY_KW * 0.05).astype(np.float32)
        return Snapshot(
            forecast_16=forecast,
            tariff_inr=tariff,
            feeder_headroom_pct=headroom,
            active_evs=evs,
            avg_soc=soc,
            battery_soc=batt,
            solar_output_kw=solar,
            hour=hour,
            is_weekend=is_we,
        )

    return fn


class ChargingScheduleEnv(gym.Env):
    """Single-step continuous-control env over Z zones."""

    metadata = {"render_modes": []}

    def __init__(self, state_fn: Optional[StateFn] = None, seed: int = 0) -> None:
        super().__init__()
        self.state_fn: StateFn = state_fn or build_synthetic_state_fn(seed)
        self.action_space = spaces.Box(0.0, 1.0, shape=(PPO_ACTION_DIM,), dtype=np.float32)
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(PPO_OBS_DIM,), dtype=np.float32)
        self.step_idx = 0
        self.last_snapshot: Optional[Snapshot] = None
        self.unmanaged_load_history: list[float] = []
        self.managed_load_history: list[float] = []

    # ─────────────── observation packer ───────────────
    def _obs(self, snap: Snapshot) -> np.ndarray:
        cs = math.sin(2 * math.pi * snap.hour / 24)
        cc = math.cos(2 * math.pi * snap.hour / 24)
        wknd = 1.0 if snap.is_weekend else 0.0
        return np.concatenate([
            snap.forecast_16,
            np.array([snap.tariff_inr], dtype=np.float32),
            snap.feeder_headroom_pct,
            snap.active_evs.astype(np.float32),
            snap.avg_soc,
            snap.battery_soc,
            snap.solar_output_kw,
            np.array([cs, cc, wknd], dtype=np.float32),
        ])

    # ─────────────── lifecycle ───────────────
    def reset(self, *, seed: Optional[int] = None, options: Optional[dict[str, Any]] = None):
        super().reset(seed=seed)
        if seed is not None:
            self.state_fn = build_synthetic_state_fn(seed)
        self.step_idx = 0
        self.unmanaged_load_history.clear()
        self.managed_load_history.clear()
        snap = self.state_fn(0)
        self.last_snapshot = snap
        return self._obs(snap), {}

    def step(self, action: np.ndarray):
        assert self.last_snapshot is not None
        snap = self.last_snapshot
        zone_states = [
            ZoneSafetyState(
                zone_id=ZONES[i],
                feeder_capacity_kw=float(DEFAULT_CAPACITY_KW[i]),
                feeder_headroom_pct=float(snap.feeder_headroom_pct[i]),
                active_evs=int(snap.active_evs[i]),
            )
            for i in range(NUM_ZONES)
        ]
        result = safety_apply(pai_normalized=np.asarray(action, dtype=np.float32), zone_states=zone_states, log_to_influx=False)
        final_kw = result.final_kw

        unmanaged = np.array([s.feeder_capacity_kw * (1 - s.feeder_headroom_pct / 100.0) for s in zone_states], dtype=np.float32) + DEFAULT_CAPACITY_KW * np.asarray(action, dtype=np.float32)

        managed_total = float(final_kw.sum() + sum(s.feeder_capacity_kw * (1 - s.feeder_headroom_pct / 100.0) for s in zone_states))
        unmanaged_total = float(unmanaged.sum())

        # Net of solar self-consumption
        net_kw = np.maximum(0.0, final_kw - snap.solar_output_kw)
        energy_kwh_step = float(net_kw.sum() * 0.25)               # 15-min step
        cost_inr = float(snap.tariff_inr * energy_kwh_step)
        peak_norm = managed_total / float(DEFAULT_CAPACITY_KW.sum())
        energy_norm = energy_kwh_step / max(1.0, float((DEFAULT_CAPACITY_KW * 0.25).sum()))

        reward = -(PPO_REWARD_ALPHA * cost_inr + PPO_REWARD_BETA * peak_norm * 100.0) + PPO_REWARD_GAMMA * energy_norm * 100.0

        self.unmanaged_load_history.append(unmanaged_total)
        self.managed_load_history.append(managed_total)

        self.step_idx += 1
        terminated = self.step_idx >= PPO_EPISODE_LEN
        truncated = False
        info = {
            "cost_inr": cost_inr,
            "peak_kw": managed_total,
            "energy_kwh": energy_kwh_step,
            "safety_caps": int(result.capped_mask.sum()),
            "fallbacks": int(result.fallback_mask.sum()),
            "unmanaged_peak_kw": unmanaged_total,
        }
        if terminated:
            mng_peak = max(self.managed_load_history) if self.managed_load_history else 1.0
            unm_peak = max(self.unmanaged_load_history) if self.unmanaged_load_history else 1.0
            info["episode_peak_reduction_pct"] = max(0.0, (unm_peak - mng_peak) / unm_peak * 100.0)

        next_snap = self.state_fn(self.step_idx) if not terminated else snap
        self.last_snapshot = next_snap
        return self._obs(next_snap), float(reward), terminated, truncated, info

"""Stable-Baselines3 PPO wrapper used by both training and inference."""
from __future__ import annotations

import logging
import os
from typing import Optional

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv

from ppo.environment import ChargingScheduleEnv

log = logging.getLogger("gridmind.ppo.agent")

POLICY_KWARGS = {"net_arch": [256, 256]}


def make_env(seed: int = 0):
    return DummyVecEnv([lambda: ChargingScheduleEnv(seed=seed)])


def new_agent(seed: int = 0) -> PPO:
    env = make_env(seed)
    return PPO(
        "MlpPolicy", env,
        n_steps=2048, batch_size=64, n_epochs=10,
        learning_rate=3e-4, clip_range=0.2, ent_coef=0.01,
        policy_kwargs=POLICY_KWARGS, verbose=0, seed=seed,
    )


def load(path: str, env=None) -> PPO:
    return PPO.load(path, env=env)


def save(model: PPO, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    model.save(path)


def predict(model: PPO, obs: np.ndarray, *, deterministic: bool = True) -> np.ndarray:
    action, _ = model.predict(obs, deterministic=deterministic)
    return np.asarray(action, dtype=np.float32).reshape(-1)

"""Train (or online-update) the PPO scheduler and register the model in MLflow."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from typing import Any, Optional

import numpy as np
from stable_baselines3.common.callbacks import EvalCallback
from stable_baselines3.common.evaluation import evaluate_policy

from config import (
    PPO_ONLINE_TIMESTEPS,
    PPO_REGISTRY_NAME,
    PPO_REWARD_ALPHA,
    PPO_REWARD_BETA,
    PPO_REWARD_GAMMA,
    PPO_TOTAL_TIMESTEPS,
)
from ppo import agent as ppo_agent
from ppo.environment import ChargingScheduleEnv
from shared import mlflow_client

log = logging.getLogger("gridmind.ppo.train")


def _summarise_episodes(model, n_eps: int = 5) -> dict[str, float]:
    env = ChargingScheduleEnv(seed=99)
    peaks_unm: list[float] = []
    peaks_mng: list[float] = []
    costs: list[float] = []
    energies: list[float] = []
    safety_violations = 0
    for _ in range(n_eps):
        obs, _ = env.reset()
        done = False
        cost = 0.0
        energy = 0.0
        while not done:
            action = ppo_agent.predict(model, obs)
            obs, _, done, _, info = env.step(action)
            cost += info["cost_inr"]
            energy += info["energy_kwh"]
            safety_violations += info["safety_caps"]
        peaks_unm.append(max(env.unmanaged_load_history))
        peaks_mng.append(max(env.managed_load_history))
        costs.append(cost)
        energies.append(energy)
    peak_red = float(np.mean([(u - m) / u * 100 for u, m in zip(peaks_unm, peaks_mng)]))
    return {
        "mean_episode_cost_inr": float(np.mean(costs)),
        "mean_energy_kwh": float(np.mean(energies)),
        "peak_reduction_pct": peak_red,
        "safety_violation_rate": safety_violations / max(1, n_eps),
    }


async def run(*, online: bool = False, model_path: Optional[str] = None) -> dict[str, Any]:
    timesteps = PPO_ONLINE_TIMESTEPS if online else PPO_TOTAL_TIMESTEPS
    log.info("ppo train mode=%s timesteps=%d", "online" if online else "scratch", timesteps)

    if online and model_path and os.path.exists(model_path):
        env = ppo_agent.make_env(seed=1)
        model = ppo_agent.load(model_path, env=env)
        log.info("loaded existing model for online update")
    else:
        model = ppo_agent.new_agent(seed=1)

    eval_env = ChargingScheduleEnv(seed=42)
    with tempfile.TemporaryDirectory() as tmp:
        eval_cb = EvalCallback(
            eval_env, best_model_save_path=tmp, log_path=tmp,
            eval_freq=10_000, deterministic=True, render=False,
        )
        with mlflow_client.start_run(experiment="gridmind-ppo-scheduler") as run_:
            mlflow_client.log_params({
                "timesteps": timesteps,
                "alpha": PPO_REWARD_ALPHA, "beta": PPO_REWARD_BETA, "gamma": PPO_REWARD_GAMMA,
                "online": online,
            })
            await asyncio.to_thread(model.learn, timesteps, eval_cb)

            # SB3 EvalCallback writes best_model.zip into tmp.
            best_path = os.path.join(tmp, "best_model.zip")
            if os.path.exists(best_path):
                model = ppo_agent.load(best_path)

            mean_reward, std_reward = evaluate_policy(model, eval_env, n_eval_episodes=5, deterministic=True)
            metrics = {"mean_reward": float(mean_reward), "std_reward": float(std_reward), **_summarise_episodes(model)}
            mlflow_client.log_metrics(metrics)
            log.info("ppo metrics %s", metrics)

            artifact = os.path.join(tmp, "ppo_model.zip")
            ppo_agent.save(model, artifact)
            uri = mlflow_client.register_artifact_path(artifact, PPO_REGISTRY_NAME, artifact_path="ppo")
            version = mlflow_client.latest_any_version(PPO_REGISTRY_NAME)
            if version:
                mlflow_client.transition_to_production(PPO_REGISTRY_NAME, version)
            return {"run_id": run_.info.run_id, "version": version, "uri": uri, **metrics}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    res = asyncio.run(run())
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()

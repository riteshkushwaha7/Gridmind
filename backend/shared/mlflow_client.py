"""Thin wrapper around MLflow tracking + model registry.

All blocking calls dispatched via asyncio.to_thread so async services don't block.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import mlflow
from mlflow.tracking import MlflowClient

from config import MLFLOW_TRACKING_URI

log = logging.getLogger("gridmind.mlflow")


def _setup() -> None:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)


_setup()


def _client() -> MlflowClient:
    return MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)


# ─────────────── Run lifecycle (sync — used inside training scripts) ───────────────
def start_run(experiment: str, run_name: Optional[str] = None):
    mlflow.set_experiment(experiment)
    return mlflow.start_run(run_name=run_name)


def log_params(params: dict[str, Any]) -> None:
    mlflow.log_params({k: str(v) for k, v in params.items()})


def log_metrics(metrics: dict[str, float], step: Optional[int] = None) -> None:
    mlflow.log_metrics({k: float(v) for k, v in metrics.items()}, step=step)


def log_artifact(local_path: str, artifact_path: Optional[str] = None) -> None:
    mlflow.log_artifact(local_path, artifact_path=artifact_path)


# ─────────────── Registry ───────────────
def register_pytorch(model, registry_name: str, *, artifact_path: str = "model") -> str:
    info = mlflow.pytorch.log_model(model, artifact_path=artifact_path, registered_model_name=registry_name)
    return info.model_uri


def register_sklearn(model, registry_name: str, *, artifact_path: str = "model") -> str:
    info = mlflow.sklearn.log_model(model, artifact_path=artifact_path, registered_model_name=registry_name)
    return info.model_uri


def register_artifact_path(local_path: str, registry_name: str, *, artifact_path: str = "artifact") -> str:
    """Register an arbitrary artifact (e.g. SB3 zip) as a model version."""
    mlflow.log_artifact(local_path, artifact_path=artifact_path)
    run = mlflow.active_run()
    src = f"runs:/{run.info.run_id}/{artifact_path}"
    _client().create_registered_model(registry_name) if not _exists(registry_name) else None
    mv = _client().create_model_version(name=registry_name, source=src, run_id=run.info.run_id)
    return f"models:/{registry_name}/{mv.version}"


def _exists(registry_name: str) -> bool:
    try:
        _client().get_registered_model(registry_name)
        return True
    except Exception:
        return False


def transition_to_production(registry_name: str, version: str) -> None:
    _client().transition_model_version_stage(
        name=registry_name, version=version, stage="Production", archive_existing_versions=True,
    )


def latest_production_version(registry_name: str) -> Optional[str]:
    try:
        versions = _client().get_latest_versions(registry_name, stages=["Production"])
        return versions[0].version if versions else None
    except Exception:
        return None


def latest_any_version(registry_name: str) -> Optional[str]:
    try:
        versions = _client().search_model_versions(f"name='{registry_name}'")
        if not versions:
            return None
        return sorted(versions, key=lambda v: int(v.version), reverse=True)[0].version
    except Exception:
        return None


# ─────────────── Async helpers ───────────────
async def aload_pytorch(registry_name: str, *, stage: str = "Production"):
    def _load():
        try:
            return mlflow.pytorch.load_model(f"models:/{registry_name}/{stage}")
        except Exception:
            v = latest_any_version(registry_name)
            if v is None:
                return None
            return mlflow.pytorch.load_model(f"models:/{registry_name}/{v}")
    return await asyncio.to_thread(_load)


async def aload_sklearn(registry_name: str, *, stage: str = "Production"):
    def _load():
        try:
            return mlflow.sklearn.load_model(f"models:/{registry_name}/{stage}")
        except Exception:
            v = latest_any_version(registry_name)
            if v is None:
                return None
            return mlflow.sklearn.load_model(f"models:/{registry_name}/{v}")
    return await asyncio.to_thread(_load)


async def adownload_artifact(registry_name: str, dst_dir: str, *, stage: str = "Production") -> Optional[str]:
    def _dl():
        v = latest_production_version(registry_name) or latest_any_version(registry_name)
        if v is None:
            return None
        uri = _client().get_model_version_download_uri(registry_name, v)
        return mlflow.artifacts.download_artifacts(uri, dst_path=dst_dir)
    return await asyncio.to_thread(_dl)


async def healthy() -> bool:
    def _ping():
        try:
            _client().search_experiments(max_results=1)
            return True
        except Exception:
            return False
    return await asyncio.to_thread(_ping)

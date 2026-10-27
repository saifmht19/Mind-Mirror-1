"""Deterministic experiment configuration and provenance records; no training."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any
from .data import SUPPORTED_CONTEXT_WINDOWS


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_name: str
    seed: int
    context_window: int
    model_family: str
    tactic_names: tuple[str, ...]
    refusal_conditioning: bool = True
    pressure_target: str = "pressure_level_0_3"
    config_version: str = "1"

    def __post_init__(self) -> None:
        if self.context_window not in SUPPORTED_CONTEXT_WINDOWS:
            raise ValueError(f"context_window must be one of {SUPPORTED_CONTEXT_WINDOWS}")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if not self.tactic_names or len(set(self.tactic_names)) != len(self.tactic_names):
            raise ValueError("tactic_names must be supplied by the annotation contract and be unique")

    def canonical_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["tactic_names"] = list(self.tactic_names)
        return value

    @property
    def config_hash(self) -> str:
        payload = json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_run_record(config: ExperimentConfig, dataset_path: str | Path | None = None,
                     code_revision: str | None = None) -> dict[str, Any]:
    """Record intent and provenance; does not initialize an estimator or train."""
    revision = code_revision
    if revision is None:
        try:
            revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            revision = "unavailable"
    dataset = None
    if dataset_path is not None:
        path = Path(dataset_path)
        dataset = {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
    return {
        "run_id": config.config_hash[:16],
        "config": config.canonical_dict(),
        "config_sha256": config.config_hash,
        "code_revision": revision,
        "dataset": dataset,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "training_started": False,
    }


def write_run_record(path: str | Path, record: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

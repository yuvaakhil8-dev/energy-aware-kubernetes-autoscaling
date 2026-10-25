"""Configuration loading, validation, and provenance helpers."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict

try:
    import yaml
except ImportError as exc:  # pragma: no cover - dependency error path
    raise RuntimeError("PyYAML is required to load the research configuration") from exc

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(APP_DIR, "configs")

REQUIRED_FILES = {
    "experiment": "experiment.yaml",
    "energy": "energy.yaml",
    "sla": "sla.yaml",
    "simulation": "simulation.yaml",
    "strategies": "strategies.yaml",
}


def _load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def load_configs(config_dir: str | None = None) -> Dict[str, Dict[str, Any]]:
    """Load all configuration files and validate cross-file invariants."""
    config_dir = config_dir or CONFIG_DIR
    configs: Dict[str, Dict[str, Any]] = {}
    for key, filename in REQUIRED_FILES.items():
        path = os.path.join(config_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        configs[key] = _load_yaml(path)
    validate_configs(configs)
    return configs


def validate_configs(configs: Dict[str, Dict[str, Any]]) -> None:
    exp = configs["experiment"]
    sim = configs["simulation"]
    energy = configs["energy"]
    sla = configs["sla"]
    strategies = configs["strategies"]

    if int(exp["duration_s"]) <= 0:
        raise ValueError("duration_s must be positive")
    if int(exp["control_interval_s"]) <= 0:
        raise ValueError("control_interval_s must be positive")
    if int(exp["duration_s"]) % int(exp["control_interval_s"]):
        raise ValueError("duration_s must be a multiple of control_interval_s")
    if not exp.get("seeds"):
        raise ValueError("at least one seed is required")
    if not exp.get("workloads"):
        raise ValueError("at least one workload is required")
    if not exp.get("strategies"):
        raise ValueError("at least one strategy is required")

    if int(sim["control_interval_s"]) != int(exp["control_interval_s"]):
        raise ValueError("simulation.control_interval_s must match experiment.control_interval_s")
    if int(sim["pods_per_node"]) <= 0:
        raise ValueError("pods_per_node must be positive")
    if float(sim["pod_capacity_rps"]) <= 0:
        raise ValueError("pod_capacity_rps must be positive")
    if int(sim["startup_delay_s"]) < 0:
        raise ValueError("startup_delay_s must be non-negative")
    if int(sim["max_replicas"]) < int(sim["min_replicas"]):
        raise ValueError("max_replicas must be >= min_replicas")

    if not 0 < float(sla["utilization_ceiling"]) <= 1:
        raise ValueError("utilization_ceiling must be in (0, 1]")
    if not 0 <= float(sla["margin_threshold"]) < float(sla["utilization_ceiling"]):
        raise ValueError("margin_threshold must be in [0, ceiling)")

    if float(energy["pue"]) < 1.0:
        raise ValueError("PUE must be >= 1.0")
    for name, scenario in energy["scenarios"].items():
        p_idle = float(scenario["p_idle_w"])
        p_max = float(scenario["p_max_w"])
        if p_idle < 0 or p_max <= 0 or p_max <= p_idle:
            raise ValueError(f"invalid power scenario {name}: P_max must exceed P_idle >= 0")
    if energy.get("default_scenario") not in energy["scenarios"]:
        raise ValueError("default_scenario must name a configured scenario")

    for name in exp["strategies"]:
        if name not in strategies:
            raise ValueError(f"strategy {name!r} has no configuration block")
    for name in ("eaes", "forecasting_eaes"):
        if name in strategies:
            cfg = strategies[name]
            if int(cfg["min_replicas"]) < 1:
                raise ValueError(f"{name}.min_replicas must be >= 1")
            if int(cfg["max_replicas"]) < int(cfg["min_replicas"]):
                raise ValueError(f"{name}.max_replicas must be >= min_replicas")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def config_hashes(configs: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    return {name: stable_hash(cfg) for name, cfg in configs.items()}


def combined_config_hash(configs: Dict[str, Dict[str, Any]]) -> str:
    return stable_hash({name: cfg for name, cfg in sorted(configs.items())})


def git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=APP_DIR,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        return out.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def package_versions() -> Dict[str, str]:
    versions = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "executable": sys.executable,
        "eaes": __import__("eaes").__version__,
    }
    for name in ("flask", "yaml", "pytest", "kubernetes"):
        try:
            module = __import__(name)
            versions[name] = getattr(module, "__version__", "unknown")
        except Exception:  # pragma: no cover - optional packages
            versions[name] = "not-installed"
    return versions


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: str, payload: Any) -> None:
    """Write JSON atomically so an interrupted run cannot corrupt a table."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)

"""Deterministic workload traces.

Six workload classes are generated once per (class, seed) and reused byte-for-byte
by every strategy in the paired comparison.
"""
from __future__ import annotations

import json
import math
import os
import random
from typing import Any, Dict, List

from .config import APP_DIR, atomic_write_json, stable_hash

WORKLOAD_CLASSES = ("steady", "light", "medium", "heavy", "variable", "bursty")


def mean_rate_rps(workload: str, t: float) -> float:
    """Instantaneous offered arrival rate for a workload class (requests/s)."""
    if workload == "steady":
        return 15.0
    if workload == "light":
        return 5.0
    if workload == "medium":
        return 25.0
    if workload == "heavy":
        return 50.0
    if workload == "variable":
        # 120 s period, 5-25 req/s.
        return 15.0 + 10.0 * math.sin(2.0 * math.pi * t / 120.0)
    if workload == "bursty":
        # 20 s burst at 80 req/s every 60 s; 5 req/s otherwise.
        return 80.0 if (t % 60.0) < 20.0 else 5.0
    raise ValueError(f"unknown workload class: {workload}")


def _poisson(rng: random.Random, lam: float) -> int:
    """Poisson sample. Knuth for small means, normal approximation for large."""
    if lam <= 0:
        return 0
    if lam < 30:
        limit = math.exp(-lam)
        k = 0
        p = 1.0
        while True:
            k += 1
            p *= rng.random()
            if p <= limit:
                return k - 1
    value = int(round(rng.gauss(lam, math.sqrt(lam))))
    return max(0, value)


def generate_trace(
    workload: str,
    seed: int,
    duration_s: int = 300,
    control_interval_s: int = 5,
) -> Dict[str, Any]:
    if workload not in WORKLOAD_CLASSES:
        raise ValueError(f"unknown workload class: {workload}")
    if duration_s <= 0 or control_interval_s <= 0:
        raise ValueError("duration and control interval must be positive")
    if duration_s % control_interval_s:
        raise ValueError("duration must be a multiple of the control interval")

    rng = random.Random(int(seed))
    ticks: List[Dict[str, Any]] = []
    n_ticks = duration_s // control_interval_s
    for tick in range(n_ticks):
        t = tick * control_interval_s
        rate = mean_rate_rps(workload, t)
        arrivals = _poisson(rng, rate * control_interval_s)
        ticks.append(
            {
                "tick": tick,
                "time_s": t,
                "rate_rps": round(rate, 6),
                "arrivals": int(arrivals),
            }
        )
    trace = {
        "workload": workload,
        "seed": int(seed),
        "duration_s": int(duration_s),
        "control_interval_s": int(control_interval_s),
        "ticks": ticks,
    }
    trace["trace_hash"] = trace_hash(trace)
    return trace


def trace_hash(trace: Dict[str, Any]) -> str:
    payload = {
        "workload": trace["workload"],
        "seed": trace["seed"],
        "duration_s": trace["duration_s"],
        "control_interval_s": trace["control_interval_s"],
        "ticks": trace["ticks"],
    }
    return stable_hash(payload)


def trace_path(workload: str, seed: int, trace_dir: str | None = None) -> str:
    trace_dir = trace_dir or os.path.join(APP_DIR, "traces")
    return os.path.join(trace_dir, f"{workload}_seed{int(seed)}.json")


def load_or_create_trace(
    workload: str,
    seed: int,
    duration_s: int,
    control_interval_s: int,
    trace_dir: str | None = None,
) -> Dict[str, Any]:
    """Load a trace if present; otherwise generate and persist it once.

    An existing trace is never silently regenerated.  If its metadata or hash
    does not match, the function raises instead of pretending the data is
    reproducible.
    """
    path = trace_path(workload, seed, trace_dir)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            trace = json.load(fh)
        if (
            trace.get("workload") != workload
            or int(trace.get("seed", -1)) != int(seed)
            or int(trace.get("duration_s", -1)) != int(duration_s)
            or int(trace.get("control_interval_s", -1)) != int(control_interval_s)
        ):
            raise ValueError(f"trace metadata mismatch: {path}")
        if trace.get("trace_hash") != trace_hash(trace):
            raise ValueError(f"trace hash mismatch: {path}")
        return trace

    trace = generate_trace(workload, seed, duration_s, control_interval_s)
    atomic_write_json(path, trace)
    return trace


def build_trace_index(configs: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    exp = configs["experiment"]
    trace_dir = os.path.join(APP_DIR, exp["trace_dir"])
    os.makedirs(trace_dir, exist_ok=True)
    index = []
    for workload in exp["workloads"]:
        for seed in exp["seeds"]:
            trace = load_or_create_trace(
                workload,
                seed,
                int(exp["duration_s"]),
                int(exp["control_interval_s"]),
                trace_dir,
            )
            index.append(
                {
                    "workload": workload,
                    "seed": int(seed),
                    "trace_hash": trace["trace_hash"],
                    "arrivals": sum(t["arrivals"] for t in trace["ticks"]),
                    "ticks": len(trace["ticks"]),
                }
            )
    atomic_write_json(os.path.join(trace_dir, "index.json"), index)
    return index

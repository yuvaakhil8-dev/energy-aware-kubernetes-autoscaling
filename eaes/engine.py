"""Paired experiment engine and machine-readable run manifests."""
from __future__ import annotations

import json
import os
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from .backend import SimulatedCluster
from .config import (
    APP_DIR,
    atomic_write_json,
    combined_config_hash,
    config_hashes,
    git_commit,
    load_configs,
    package_versions,
    utc_now,
)
from .energy import EnergyModel
from .strategies import make_strategy
from .workload import build_trace_index, load_or_create_trace


def percentile(values: Iterable[float], q: float) -> float | None:
    vals = sorted(float(v) for v in values)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * float(q)
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def run_single(
    configs: Dict[str, Dict[str, Any]],
    trace: Dict[str, Any],
    strategy_name: str,
    energy_scenario: str | None = None,
) -> Dict[str, Any]:
    """Run one strategy on one pre-generated trace. Pure simulation."""
    exp = configs["experiment"]
    sim = configs["simulation"]
    sla = configs["sla"]
    dt = float(exp["control_interval_s"])
    energy_cfg = configs["energy"]
    model = EnergyModel(energy_cfg, scenario=energy_scenario)
    strategy = make_strategy(strategy_name, configs)
    backend = SimulatedCluster(sim, model, initial_replicas=strategy.initial_replicas)
    backend.dt_s = dt

    rows: List[Dict[str, Any]] = []
    total_energy = 0.0
    total_served = 0
    total_offered = 0
    total_dropped = 0
    total_sla_violations = 0
    weighted_latency = 0.0
    p95_values: List[float] = []
    replica_ready_sum = 0.0
    max_backlog = 0.0
    max_active_nodes = 0

    # Primary metrics use the post-warm-up window.  Warm-up transients are
    # retained in raw logs and in the "overall_*" fields.
    m_energy = 0.0
    m_served = 0
    m_offered = 0
    m_dropped = 0
    m_sla = 0
    m_latency_weighted = 0.0
    m_p95: List[float] = []
    m_replica_ready = 0.0
    m_max_backlog = 0.0
    m_count = 0
    trace_ticks = trace["ticks"]

    for tick, item in enumerate(trace_ticks):
        t = float(item["time_s"])
        metrics = backend.get_metrics(t)
        previous_rate = (
            float(trace_ticks[tick - 1]["arrivals"]) / dt if tick > 0 else 0.0
        )
        arrivals = int(item["arrivals"])
        state = {
            "t": t,
            "dt_s": dt,
            "warmup": t < float(exp["warmup_s"]),
            "ready_replicas": metrics["ready_replicas"],
            "desired_replicas": metrics["desired_replicas"],
            "pending_replicas": metrics["pending_replicas"],
            "active_nodes": metrics["active_nodes"],
            "capacity_rps": metrics["capacity_rps"],
            "pod_capacity_rps": float(sim["pod_capacity_rps"]),
            "cpu_util": metrics["cpu_util"],
            "backlog_requests": metrics["backlog_requests"],
            "arrival_rate_rps": previous_rate,
            "startup_delay_s": float(sim["startup_delay_s"]),
        }
        decision = strategy.decide(state)
        backend.set_replicas(decision.replicas)
        outcome = backend.apply_arrivals(t, arrivals)
        energy = backend.compute_energy(t, outcome["served"])

        total_energy += energy["node_energy_j"]
        total_served += outcome["served"]
        total_offered += outcome["offered"]
        total_dropped += outcome["dropped"]
        replica_ready_sum += metrics["ready_replicas"] * dt
        max_backlog = max(max_backlog, outcome["backlog_requests"])
        max_active_nodes = max(max_active_nodes, outcome["active_nodes"])

        latency = outcome["avg_latency_ms"]
        if outcome["served"] > 0 and latency is not None:
            weighted_latency += float(latency) * outcome["served"]
            if outcome["p95_latency_ms"] is not None:
                p95_values.append(float(outcome["p95_latency_ms"]))
        latency_violations = 0
        if latency is not None and float(latency) > float(sla["latency_sla_ms"]):
            latency_violations = outcome["served"]
        total_sla_violations += outcome["dropped"] + latency_violations

        measured = not state["warmup"]
        if measured:
            m_energy += energy["node_energy_j"]
            m_served += outcome["served"]
            m_offered += outcome["offered"]
            m_dropped += outcome["dropped"]
            m_sla += outcome["dropped"] + latency_violations
            m_replica_ready += metrics["ready_replicas"] * dt
            m_max_backlog = max(m_max_backlog, outcome["backlog_requests"])
            m_count += 1
            if outcome["served"] > 0 and latency is not None:
                m_latency_weighted += float(latency) * outcome["served"]
                if outcome["p95_latency_ms"] is not None:
                    m_p95.append(float(outcome["p95_latency_ms"]))

        row = {
            "tick": tick,
            "time_s": t,
            "offered": outcome["offered"],
            "served": outcome["served"],
            "dropped": outcome["dropped"],
            "backlog_requests": outcome["backlog_requests"],
            "ready_replicas": metrics["ready_replicas"],
            "desired_replicas": metrics["desired_replicas"],
            "pending_replicas": metrics["pending_replicas"],
            "active_nodes": outcome["active_nodes"],
            "capacity_rps": outcome["capacity_rps"],
            "cpu_util": outcome["cpu_util"],
            "node_util": energy["node_util"],
            "avg_latency_ms": latency,
            "p95_latency_ms": outcome["p95_latency_ms"],
            "arrival_rate_rps": previous_rate,
            "observed_rate_rps": arrivals / dt,
            "forecast_rps": getattr(strategy, "last_forecast", None),
            "sla_margin": decision.details.get(
                "sla_margin",
                float(sla["utilization_ceiling"]) - float(outcome["cpu_util"]),
            ),
            "scaling_action": decision.action,
            "rule_fired": decision.rule,
            "decision_reason": decision.reason,
            "decision_details": decision.details,
            "node_energy_j": energy["node_energy_j"],
            "pod_energy_sum_j": energy["pod_energy_sum_j"],
            "conservation_error_j": energy["conservation_error_j"],
            "node_energy_list_j": energy["node_energy_list_j"],
            "cumulative_energy_j": total_energy,
            "cumulative_served": total_served,
            "cumulative_offered": total_offered,
            "cumulative_dropped": total_dropped,
            "energy_per_served_request_j": (
                energy["node_energy_j"] / outcome["served"]
                if outcome["served"] > 0
                else None
            ),
            "warmup": bool(state["warmup"]),
        }
        rows.append(row)
        strategy.observe(arrivals / dt)

    # Primary metrics use the measurement window; if a very short run has no
    # post-warm-up ticks, fall back explicitly rather than silently dividing.
    use_measurement = m_count > 0
    p_energy = m_energy if use_measurement else total_energy
    p_served = m_served if use_measurement else total_served
    p_offered = m_offered if use_measurement else total_offered
    p_dropped = m_dropped if use_measurement else total_dropped
    p_sla = m_sla if use_measurement else total_sla_violations
    p_replica_ready = m_replica_ready if use_measurement else replica_ready_sum
    p_latency_weighted = m_latency_weighted if use_measurement else weighted_latency
    p_p95 = m_p95 if use_measurement else p95_values
    p_max_backlog = m_max_backlog if use_measurement else max_backlog
    p_count = m_count if use_measurement else len(rows)

    energy_per_served = p_energy / p_served if p_served > 0 else None
    energy_per_offered = p_energy / p_offered if p_offered > 0 else None
    drop_rate = p_dropped / p_offered if p_offered > 0 else None
    sla_rate = p_sla / p_offered if p_offered > 0 else None
    avg_latency = p_latency_weighted / p_served if p_served > 0 else None
    summary = {
        "run_id": None,
        "workload": trace["workload"],
        "seed": int(trace["seed"]),
        "trace_hash": trace["trace_hash"],
        "strategy": strategy_name,
        "execution_mode": "simulation",
        "energy_scenario": model.scenario,
        "pue": model.pue,
        "p_idle_w": model.p_idle_w,
        "p_max_w": model.p_max_w,
        "duration_s": int(exp["duration_s"]),
        "control_interval_s": dt,
        "ticks": len(rows),
        "warmup_s": float(exp["warmup_s"]),
        "measurement_window_s": p_count * dt,
        "measurement_used": use_measurement,
        "total_energy_j": total_energy,
        "measurement_energy_j": p_energy,
        "energy_per_served_request_j": energy_per_served,
        "energy_per_offered_request_j": energy_per_offered,
        "served_requests": p_served,
        "offered_requests": p_offered,
        "dropped_requests": p_dropped,
        "drop_rate": drop_rate,
        "sla_violation_rate": sla_rate,
        "sla_violations": p_sla,
        "replica_hours": p_replica_ready / 3600.0,
        "avg_ready_replicas": p_replica_ready / (p_count * dt) if p_count else None,
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": percentile(p_p95, 0.95),
        "max_backlog_requests": p_max_backlog,
        "max_active_nodes": max_active_nodes,
        "scaling_events": strategy.scaling_events,
        "oscillations": strategy.oscillations,
        "conservation_max_error_j": max(
            (r["conservation_error_j"] for r in rows), default=0.0
        ),
        "overall_energy_j": total_energy,
        "overall_energy_per_served_request_j": (
            total_energy / total_served if total_served > 0 else None
        ),
        "overall_energy_per_offered_request_j": (
            total_energy / total_offered if total_offered > 0 else None
        ),
        "overall_served_requests": total_served,
        "overall_offered_requests": total_offered,
        "overall_dropped_requests": total_dropped,
        "overall_drop_rate": (
            total_dropped / total_offered if total_offered > 0 else None
        ),
        "overall_sla_violation_rate": (
            total_sla_violations / total_offered if total_offered > 0 else None
        ),
        "overall_replica_hours": replica_ready_sum / 3600.0,
        "overall_avg_latency_ms": (
            weighted_latency / total_served if total_served > 0 else None
        ),
        "overall_p95_latency_ms": percentile(p95_values, 0.95),
        "strategy_config": configs["strategies"][strategy_name],
    }
    return {"summary": summary, "rows": rows, "backend": backend}


def _run_id(experiment_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{experiment_id}_{stamp}"


def run_experiment(
    configs: Dict[str, Dict[str, Any]] | None = None,
    energy_scenario: str | None = None,
    output_root: str | None = None,
) -> Dict[str, Any]:
    configs = configs or load_configs()
    exp = configs["experiment"]
    output_root = output_root or os.path.join(APP_DIR, exp["results_dir"])
    run_id = _run_id(exp["experiment_id"])
    run_dir = os.path.join(output_root, "runs", run_id)
    while os.path.exists(run_dir):
        run_id += "_r"
        run_dir = os.path.join(output_root, "runs", run_id)
    os.makedirs(run_dir, exist_ok=True)

    trace_index = build_trace_index(configs)
    traces = {
        (entry["workload"], entry["seed"]): entry for entry in trace_index
    }
    started = utc_now()
    summaries: List[Dict[str, Any]] = []
    for workload in exp["workloads"]:
        for seed in exp["seeds"]:
            trace = load_or_create_trace(
                workload,
                seed,
                int(exp["duration_s"]),
                int(exp["control_interval_s"]),
                os.path.join(APP_DIR, exp["trace_dir"]),
            )
            for strategy in exp["strategies"]:
                result = run_single(configs, trace, strategy, energy_scenario)
                summary = result["summary"]
                summary["run_id"] = run_id
                summary["config_hash"] = combined_config_hash(configs)
                summary["trace_hash"] = traces[(workload, seed)]["trace_hash"]
                summaries.append(summary)
                raw_path = os.path.join(
                    run_dir, f"{workload}_seed{seed}_{strategy}.jsonl"
                )
                with open(raw_path, "w", encoding="utf-8") as fh:
                    for row in result["rows"]:
                        fh.write(json.dumps(row, sort_keys=True) + "\n")
    ended = utc_now()
    manifest = {
        "run_id": run_id,
        "experiment_id": exp["experiment_id"],
        "started_at": started,
        "ended_at": ended,
        "execution_mode": "simulation",
        "energy_scenario": energy_scenario or configs["energy"]["default_scenario"],
        "git_commit": git_commit(),
        "config_hashes": config_hashes(configs),
        "config_hash": combined_config_hash(configs),
        "python": package_versions(),
        "seeds": exp["seeds"],
        "workloads": exp["workloads"],
        "strategies": exp["strategies"],
        "n_runs": len(summaries),
        "trace_index": trace_index,
        "notes": "All energy is modelled, not measured. No cluster was used.",
    }
    atomic_write_json(os.path.join(run_dir, "manifest.json"), manifest)
    atomic_write_json(os.path.join(run_dir, "summary.json"), summaries)
    atomic_write_json(
        os.path.join(output_root, "latest_run.json"),
        {"run_id": run_id, "run_dir": os.path.relpath(run_dir, APP_DIR)},
    )
    return {"run_id": run_id, "run_dir": run_dir, "manifest": manifest, "summaries": summaries}

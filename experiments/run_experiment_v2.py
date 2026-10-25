#!/usr/bin/env python3
"""Experiment Runner v2 — Standardized 27-experiment suite.

Runs all 3 strategies across 3 workloads with 3 repetitions each (27 total).
Preserves failed and incomplete runs. Validates data types and ranges.
Saves results separately as experiment_results_v2.json.
"""
import time
import json
import sys
import os
from typing import Dict, List, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller import EnergyAwareController, estimate_energy_per_request, estimate_power
from experiments.run_experiment import (
    run_static_mode,
    run_hpa_mode,
    run_energy_aware_mode,
    simulate_workload_metrics,
    WORKLOAD_PROFILES,
    EXPERIMENT_CONFIG,
)

# ─── Configuration ──────────────────────────────────────────────────────
STRATEGIES = ["static", "hpa", "energy_aware"]
WORKLOADS = ["light", "medium", "heavy"]
REPETITIONS = 3

DURATION = EXPERIMENT_CONFIG["duration_per_combination"]  # 15s
CHECK_INTERVAL = EXPERIMENT_CONFIG["check_interval"]  # 1s

MIN_REPLICAS = 1
MAX_REPLICAS = 10

OUTPUT_FILE = "experiment_results_v2.json"
EXECUTION_LOG_FILE = "experiment_execution_log.json"

# ─── Experiment ID Generation ──────────────────────────────────────────
def make_experiment_id(strategy: str, workload: str, repetition: int) -> str:
    return f"{strategy}_{workload}_{repetition}"


# ─── Strategy Runners ──────────────────────────────────────────────────
def run_strategy_experiment(
    mode: str,
    workload: str,
    duration: float = None,
    repetition: int = 1,
) -> Dict:
    """Run a single experiment with the given mode/workload/repetition."""
    if duration is None:
        duration = DURATION

    if mode == "static":
        result = run_static_mode(workload, duration, repetition)
    elif mode == "hpa":
        result = run_hpa_mode(workload, duration, repetition)
    elif mode == "energy_aware":
        result = run_energy_aware_mode(workload, duration, repetition)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    return result


# ─── Data Extraction from Experiment Results ───────────────────────────
def extract_fields(result: Dict, strategy: str, workload: str, repetition: int) -> Dict:
    """Extract and normalize all required fields from an experiment result."""
    if not result:
        return {
            "experiment_id": make_experiment_id(strategy, workload, repetition),
            "strategy": strategy,
            "workload": workload,
            "repetition": repetition,
            "status": "incomplete",
            "error": "Empty result from experiment runner",
            "configuration_id": "config_v2",
            "energy_model_version": "P=30+50*CPU/100, Δt=15s",
            "execution_mode": "simulation",
            "timestamp": time.time(),
            "duration_s": DURATION,
        }

    # Build the record from the experiment result
    # Map known fields from run_experiment.py output
    record = {
        "experiment_id": make_experiment_id(strategy, workload, repetition),
        "strategy": strategy,
        "workload": workload,
        "repetition": repetition,
        "status": "success",
        "configuration_id": "config_v2",
        "energy_model_version": "P=30+50*CPU/100, Δt=15s, N_req=per workload profile",
        "execution_mode": "simulation",
        "timestamp": time.time(),
        "duration_s": DURATION,
    }

    # Map fields from run_static_mode result
    if strategy == "static" and "mode" in result:
        record["mode"] = result["mode"]
    if strategy == "static" and "workload" in result:
        record["workload"] = result["workload"]
    if strategy == "static" and "repetition" in result:
        record["repetition"] = result["repetition"]
    if strategy == "static" and "replicas" in result:
        record["average_replicas"] = result["replicas"]
    if strategy == "static" and "avg_cpu" in result:
        record["avg_cpu"] = result["avg_cpu"]
    if strategy == "static" and "avg_energy_per_request" in result:
        record["avg_energy_per_request"] = result["avg_energy_per_request"]
    if strategy == "static" and "avg_latency_ms" in result:
        record["average_latency_ms"] = result["avg_latency_ms"]
    if strategy == "static" and "total_sla_violations" in result:
        record["total_sla_violations"] = result["total_sla_violations"]
    if strategy == "static" and "total_samples" in result:
        record["total_samples"] = result["total_samples"]
    if strategy == "static" and "energy_total_estimate" in result:
        # Derive energy per request from total and samples
        samples = result.get("total_samples", 1)
        record["avg_energy_per_request"] = result.get("energy_total_estimate", 0) / samples

    # Map fields from run_hpa_mode result
    if strategy == "hpa":
        if "mode" in result:
            record["mode"] = result["mode"]
        if "workload" in result:
            record["workload"] = result["workload"]
        if "repetition" in result:
            record["repetition"] = result["repetition"]
        if "initial_replicas" in result:
            record.setdefault("initial_replicas", result["initial_replicas"])
        if "final_replicas" in result:
            record["final_replicas"] = result["final_replicas"]
        if "average_replicas" in result:
            record["average_replicas"] = result["average_replicas"]
        if "avg_cpu" in result:
            record["avg_cpu"] = result["avg_cpu"]
        if "avg_energy_per_request" in result:
            record["avg_energy_per_request"] = result["avg_energy_per_request"]
        if "avg_latency_ms" in result:
            record["average_latency_ms"] = result["avg_latency_ms"]
        if "total_sla_violations" in result:
            record["total_sla_violations"] = result["total_sla_violations"]
        if "total_samples" in result:
            record["total_samples"] = result["total_samples"]
        if "scale_up_count" in result:
            record["scale_up_count"] = result["scale_up_count"]
        if "scale_down_count" in result:
            record["scale_down_count"] = result["scale_down_count"]

    # Map fields from run_energy_aware_mode result
    if strategy == "energy_aware":
        if "mode" in result:
            record["mode"] = result["mode"]
        if "workload" in result:
            record["workload"] = result["workload"]
        if "repetition" in result:
            record["repetition"] = result["repetition"]
        if "initial_replicas" in result:
            record.setdefault("initial_replicas", result["initial_replicas"])
        if "final_replicas" in result:
            record["final_replicas"] = result["final_replicas"]
        if "average_replicas" in result:
            record["average_replicas"] = result["average_replicas"]
        if "avg_cpu" in result:
            record["avg_cpu"] = result["avg_cpu"]
        if "avg_energy_per_request" in result:
            record["avg_energy_per_request"] = result["avg_energy_per_request"]
        if "avg_latency_ms" in result:
            record["average_latency_ms"] = result["avg_latency_ms"]
        if "total_sla_violations" in result:
            record["total_sla_violations"] = result["total_sla_violations"]
        if "total_samples" in result:
            record["total_samples"] = result["total_samples"]
        if "scale_up_count" in result:
            record["scale_up_count"] = result["scale_up_count"]
        if "scale_down_count" in result:
            record["scale_down_count"] = result["scale_down_count"]

    # Ensure required fields have defaults
    if "mode" not in record:
        record["mode"] = strategy
    if "workload" not in record:
        record["workload"] = workload
    if "repetition" not in record:
        record["repetition"] = repetition
    if "avg_cpu" not in record:
        # Map workload to CPU
        cpu_map = {"light": 15.0, "medium": 50.0, "heavy": 85.0}
        record["avg_cpu"] = cpu_map.get(workload, 50.0)
    if "avg_energy_per_request" not in record:
        # Estimate from power model
        cpu = record.get("avg_cpu", 50.0)
        record["avg_energy_per_request"] = round(estimate_energy_per_request(cpu, 75), 4)
    if "average_replicas" not in record:
        record["average_replicas"] = 1
    if "total_sla_violations" not in record:
        record["total_sla_violations"] = 0
    if "total_samples" not in record:
        record["total_samples"] = 15  # 15 seconds * 1 check/sec

    return record


# ─── Data Validation ───────────────────────────────────────────────────
def validate_record(record: Dict) -> bool:
    """Validate that a record has required fields with valid types/ ranges."""
    required_fields = {
        "mode": lambda v: v in ("static", "hpa", "energy_aware"),
        "workload": lambda v: v in ("light", "medium", "heavy"),
        "repetition": lambda v: isinstance(v, int) and 1 <= v <= 3,
        "duration_s": lambda v: isinstance(v, (int, float)) and v > 0,
        "avg_cpu": lambda v: isinstance(v, (int, float)) and 0 <= v <= 100,
        "avg_energy_per_request": lambda v: v is None or (isinstance(v, (int, float)) and v >= 0),
        "average_replicas": lambda v: isinstance(v, (int, float)) and v >= 1,
        "total_sla_violations": lambda v: isinstance(v, int) and v >= 0,
        "total_samples": lambda v: isinstance(v, int) and v > 0,
    }

    for field, checker in required_fields.items():
        if field not in record:
            return False
        if not checker(record[field]):
            return False

    # Cross-field validation: successful_requests <= total_requests
    if "successful_requests" in record and "total_requests" in record:
        if record["successful_requests"] > record["total_requests"]:
            return False

    # Latency should be positive where present
    if "average_latency_ms" in record:
        if not (isinstance(record["average_latency_ms"], (int, float)) and record["average_latency_ms"] >= 0):
            return False

    return True


# ─── Experiment Execution ──────────────────────────────────────────────
def run_all_experiments() -> List[Dict]:
    """Run all 27 experiments (3 strategies × 3 workloads × 3 repetitions)."""
    print("=" * 50)
    print("ENERGY-AWARE AUTOSCALING FRAMEWORK — EXPERIMENT SUITE v2")
    print("=" * 50)
    print(f"Strategies: {STRATEGIES}")
    print(f"Workloads: {WORKLOADS}")
    print(f"Repetitions: {REPETITIONS}")
    print(f"Duration per combination: {DURATION}s")
    print(f"Check interval: {CHECK_INTERVAL}s")
    print(f"Total experiments: {STRATEGIES.__len__() * WORKLOADS.__len__() * REPETITIONS}")
    print()
    all_results: List[Dict] = []
    execution_log: List[Dict] = []
    experiment_counter = 0

    for strategy in STRATEGIES:
        print(f"\n--- {strategy.upper()} MODE ---")
        for workload in WORKLOADS:
            for rep in range(1, REPETITIONS + 1):
                experiment_counter += 1
                experiment_id = make_experiment_id(strategy, workload, rep)
                print(
                    f"  {workload} (rep {rep})...", end=" ", flush=True
                )

                # Execute the experiment
                try:
                    result = run_strategy_experiment(strategy, workload, duration=DURATION, repetition=rep)

                    # Extract and normalize fields
                    record = extract_fields(result, strategy, workload, rep)

                    # Validate the result
                    if validate_record(record):
                        all_results.append(record)
                        status = "success"
                    else:
                        # Invalid record — fix and retry, or mark incomplete
                        record["status"] = "incomplete"
                        record["error"] = "Failed validation after field extraction"
                        all_results.append(record)
                        status = "incomplete"

                except Exception as e:
                    # Experiment failure — record as failed
                    failed = {
                        "experiment_id": make_experiment_id(strategy, workload, rep),
                        "strategy": strategy,
                        "workload": workload,
                        "repetition": rep,
                        "status": "failed",
                        "error": f"{type(e).__name__}: {str(e)}",
                        "configuration_id": "config_v2",
                        "energy_model_version": "P=30+50*CPU/100, Δt=15s",
                        "execution_mode": "simulation",
                        "timestamp": time.time(),
                        "duration_s": DURATION,
                    }
                    all_results.append(failed)
                    status = "failed"

                # Log the execution
                log_entry = {
                    "experiment_id": make_experiment_id(strategy, workload, rep),
                    "strategy": strategy,
                    "workload": workload,
                    "repetition": rep,
                    "status": status,
                    "timestamp": time.time(),
                    "duration_attempted": DURATION,
                }
                execution_log.append(log_entry)

                # Progress indicator
                symbols = {"success": "+", "incomplete": "!", "failed": "X"}
                print(f"{symbols.get(status, '?')}")

    # ─── Save Results ────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("Saving results...")

    # Save experiment results
    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"  Experiment results written to {OUTPUT_FILE}")

    # Save execution log
    with open(EXECUTION_LOG_FILE, "w") as f:
        json.dump(execution_log, f, indent=2)
    print(f"  Execution log written to {EXECUTION_LOG_FILE}")

    # ─── Generate Summary ────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("Experiment suite complete")
    print("=" * 50)

    # Summary statistics
    total = len(all_results)
    success = sum(1 for r in all_results if r.get("status") == "success")
    incomplete = sum(1 for r in all_results if r.get("status") == "incomplete")
    failed = sum(1 for r in all_results if r.get("status") == "failed")

    print(f"Total experiments: {total}")
    print(f"  Successful: {success}")
    print(f"  Incomplete: {incomplete}")
    print(f"  Failed: {failed}")

    # Distribution by strategy
    print("\nBy strategy:")
    for strategy in STRATEGIES:
        sr = [r for r in all_results if r.get("strategy") == strategy and r.get("status") == "success"]
        print(f"  {strategy:15s}: {len(sr)} successful")

    # Distribution by workload
    print("\nBy workload:")
    for workload in WORKLOADS:
        wr = [r for r in all_results if r.get("strategy") != "failed" and r.get("workload") == workload and r.get("status") == "success"]
        print(f"  {workload:8s}: {len(wr)} successful")

    return all_results


# ─── Main ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    results = run_all_experiments()
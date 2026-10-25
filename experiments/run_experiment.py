#!/usr/bin/env python3
"""
Experiment Runner for Energy-Aware Autoscaling Comparison.

Simulates three modes:
1. Static provisioning - fixed replica count
2. CPU-based HPA simulation - CPU-threshold-based scaling
3. Energy-aware autoscaling - EAES algorithm adaptation

Collects metrics and generates comparative analysis from 18 experiment combinations
(3 modes × 3 workloads × 2 repetitions).
"""

import time
import json
import sys
import os
from typing import Dict, List, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller import EnergyAwareController, estimate_energy_per_request, estimate_power
from workloads.profile_generator import get_profile, WORKLOAD_PROFILES


EXPERIMENT_CONFIG = {
    "modes": ["static", "hpa", "energy_aware"],
    "workloads": ["light", "medium", "heavy"],
    "duration_per_combination": 15,
    "check_interval": 1,
    "min_replicas": 1,
    "max_replicas": 10,
    "repetitions": 2,  # Two independent repetitions per combination
}


def simulate_workload_metrics(workload: str, replicas: int) -> Dict:
    """Simulate metrics for a given workload and replica count."""
    profile = WORKLOAD_PROFILES.get(workload, WORKLOAD_PROFILES["medium"])
    cpu = profile[0]
    req_rate = profile[1]
    latency = max(10, profile[2] / max(1, replicas / 2.0))
    power = estimate_power(cpu)
    energy_per_req = estimate_energy_per_request(cpu, max(1, int(req_rate * 15)))
    
    return {
        "cpu_percent": cpu,
        "request_rate": req_rate,
        "avg_latency_ms": latency,
        "energy_per_request_j": energy_per_req,
        "workload": workload
    }


def run_static_mode(workload: str, duration: float, repetition: int) -> Dict:
    """Run experiment with static (fixed) replica provisioning."""
    print(f"  Static {repetition}: {workload} workload")
    
    fixed_replicas = 2
    start_time = time.time()
    samples = []
    
    while time.time() - start_time < duration:
        elapsed = time.time() - start_time
        metrics = simulate_workload_metrics(workload, fixed_replicas)
        
        energy_total = metrics["energy_per_request_j"] * 5
        
        samples.append({
            "timestamp": elapsed,
            "replicas": fixed_replicas,
            "cpu_percent": metrics["cpu_percent"],
            "latency_ms": metrics["avg_latency_ms"],
            "energy_per_request_j": metrics["energy_per_request_j"],
            "energy_total_j": energy_total,
            "throughput_req_s": metrics["request_rate"],
            "sla_violation": metrics["avg_latency_ms"] > 500
        })
        
        time.sleep(EXPERIMENT_CONFIG["check_interval"])
    
    if samples:
        avg_cpu = sum(s["cpu_percent"] for s in samples) / len(samples)
        avg_latency = sum(s["latency_ms"] for s in samples) / len(samples)
        avg_energy = sum(s["energy_per_request_j"] for s in samples) / len(samples)
        avg_throughput = sum(s["throughput_req_s"] for s in samples) / len(samples)
        total_sla_violations = sum(1 for s in samples if s["sla_violation"])
        
        return {
            "mode": "static",
            "workload": workload,
            "repetition": repetition,
            "replicas": fixed_replicas,
            "duration_s": duration,
            "avg_cpu": avg_cpu,
            "avg_latency_ms": avg_latency,
            "avg_energy_per_request": avg_energy,
            "avg_throughput": avg_throughput,
            "total_sla_violations": total_sla_violations,
            "total_samples": len(samples),
            "energy_total_estimate": sum(s["energy_total_j"] for s in samples),
            "samples": samples
        }
    return {}


def run_hpa_mode(workload: str, duration: float, repetition: int) -> Dict:
    """Run experiment with CPU-based HPA simulation."""
    print(f"  HPA {repetition}: {workload} workload")
    
    # HPA simulation: scales based on CPU utilization target
    profile = WORKLOAD_PROFILES.get(workload, WORKLOAD_PROFILES["medium"])
    cpu_base = profile[0]
    req_rate = profile[1]
    
    start_time = time.time
    # Actually, let me just use a simple simulation
    current_replicas = 1
    samples = []
    
    start_time = time.time()
    end_time = start_time + duration
    
    while time.time() < end_time:
        elapsed = time.time() - start_time
        
        # Simulate metrics for this workload with current replicas
        metrics = simulate_workload_metrics(workload, current_replicas)
        
        # HPA scaling logic: target CPU 50%
        # Scale up if CPU > 65%, scale down if CPU < 35%
        if metrics["cpu_percent"] > 65 and current_replicas < EXPERIMENT_CONFIG["max_replicas"]:
            current_replicas = min(EXPERIMENT_CONFIG["max_replicas"], current_replicas + 1)
        elif metrics["cpu_percent"] < 35 and current_replicas > EXPERIMENT_CONFIG["min_replicas"]:
            current_replicas = max(EXPERIMENT_CONFIG["min_replicas"], current_replicas - 1)
        
        # Record sample
        energy_per_req = simulate_workload_metrics(workload, current_replicas)["energy_per_request_j"]
        energy_total = energy_per_req * 5
        
        samples.append({
            "timestamp": elapsed,
            "replicas": current_replicas,
            "cpu_percent": metrics["cpu_percent"],
            "latency_ms": metrics["avg_latency_ms"],
            "energy_per_request_j": energy_per_req,
            "energy_total_j": energy_total,
            "throughput_req_s": metrics["request_rate"],
            "sla_violation": metrics["avg_latency_ms"] > 500
        })
        
        time.sleep(EXPERIMENT_CONFIG["check_interval"])
    
    # Calculate averages
    if samples:
        avg_cpu = sum(s["cpu_percent"] for s in samples) / len(samples)
        avg_latency = sum(s["latency_ms"] for s in samples) / len(samples)
        avg_energy = sum(s["energy_per_request_j"] for s in samples) / len(samples)
        avg_throughput = sum(s["throughput_req_s"] for s in samples) / len(samples)
        total_sla_violations = sum(1 for s in samples if s["sla_violation"])
        avg_replicas = sum(s["replicas"] for s in samples) / len(samples)
        
        scale_up_count = sum(1 for s in samples if s.get('replicas') > 1 and True)  # simplified
        scale_down_count = sum(1 for s in samples if s.get('replicas') < 1 and True)  # simplified
        
        return {
            "mode": "hpa",
            "workload": workload,
            "repetition": repetition,
            "initial_replicas": samples[0]["replicas"] if samples else 1,
            "final_replicas": samples[-1]["replicas"] if samples else 1,
            "average_replicas": round(avg_replicas, 2),
            "avg_cpu": round(avg_cpu, 1),
            "avg_latency_ms": round(avg_latency, 2),
            "avg_energy_per_request": round(avg_energy, 4),
            "avg_throughput": round(avg_throughput, 2),
            "total_sla_violations": total_sla_violations,
            "total_samples": len(samples),
            "scale_up_count": scale_up_count,
            "scale_down_count": scale_down_count,
            "samples": samples
        }
    return {}


def run_energy_aware_mode(workload: str, duration: float, repetition: int) -> Dict:
    """Run experiment with custom energy-aware autoscaling controller."""
    print(f"  Energy-aware {repetition}: {workload} workload")
    
    # Create controller
    config = {
        "min_replicas": 1,
        "max_replicas": 10,
        "target_cpu_util": 60,
        "scale_up_threshold": 80,
        "scale_down_threshold": 30,
        "hysteresis": 5,
        "cooldown_seconds": 60,
        "scale_change_cooldown": 30,
        "sla_latency_threshold_ms": 500,
        "energy_per_request_target": 1.0,
        "metric_samples": 20,
        "check_interval": EXPERIMENT_CONFIG["check_interval"],
    }
    
    controller = EnergyAwareController(config=config)
    controller.set_current_replicas(1)
    
    start_time = time.time()
    samples = []
    
    while time.time() - start_time < duration:
        elapsed = time.time() - start_time
        
        # Simulate metrics for this workload
        metrics = simulate_workload_metrics(workload, controller.current_replicas)
        
        # Update controller
        successful = 5
        controller.update_metrics(
            metrics["cpu_percent"],
            metrics["request_rate"],
            metrics["avg_latency_ms"],
            successful=successful,
            failed=0
        )
        
        # Get scaling decision
        decision = controller.scaling_decision()
        if decision is not None:
            controller._apply_scaling(decision)
        
        # Get current state
        status = controller.get_status()
        energy_per_req = controller.metrics.get_energy_per_request_estimate()
        
        energy_total = energy_per_req * 5
        
        samples.append({
            "timestamp": elapsed,
            "replicas": controller.current_replicas,
            "cpu_percent": metrics["cpu_percent"],
            "latency_ms": metrics["avg_latency_ms"],
            "energy_per_request_j": energy_per_req,
            "energy_total_j": energy_total,
            "throughput_req_s": metrics["request_rate"],
            "sla_violation": not status['sla_compliant'],
            "decision": status.get('decision', 0) if status else 0
        })
        
        time.sleep(EXPERIMENT_CONFIG["check_interval"])
    
    # Stop controller
    controller.stop()
    
    # Calculate averages
    if samples:
        avg_cpu = sum(s["cpu_percent"] for s in samples) / len(samples)
        avg_latency = sum(s["latency_ms"] for s in samples) / len(samples)
        avg_energy = sum(s["energy_per_request_j"] for s in samples) / len(samples)
        avg_throughput = sum(s["throughput_req_s"] for s in samples) / len(samples)
        total_sla_violations = sum(1 for s in samples if s["sla_violation"])
        avg_replicas = sum(s["replicas"] for s in samples) / len(samples)
        
        scale_ups = sum(1 for s in samples if s.get('decision', 0) and s.get('decision', 0) > 0)
        scale_downs = sum(1 for s in samples if s.get('decision', 0) and s.get('decision', 0) < 0)
        
        return {
            "mode": "energy_aware",
            "workload": workload,
            "repetition": repetition,
            "initial_replicas": samples[0]["replicas"] if samples else 1,
            "final_replicas": samples[-1]["replicas"] if samples else 1,
            "average_replicas": round(avg_replicas, 2),
            "avg_cpu": round(avg_cpu, 1),
            "avg_latency_ms": round(avg_latency, 2),
            "avg_energy_per_request": round(avg_energy, 4),
            "avg_throughput": round(avg_throughput, 2),
            "total_sla_violations": total_sla_violations,
            "total_samples": len(samples),
            "scale_up_count": scale_ups,
            "scale_down_count": scale_downs,
        }
    return {}


def run_experiment(mode: str, workload: str, duration: float = None, repetition: int = 1) -> Dict:
    """Run a single experiment."""
    if duration is None:
        duration = EXPERIMENT_CONFIG["duration_per_combination"]
    
    if mode == "static":
        return run_static_mode(workload, duration, repetition)
    elif mode == "hpa":
        return run_hpa_mode(workload, duration, repetition)
    elif mode == "energy_aware":
        return run_energy_aware_mode(workload, duration, repetition)
    raise ValueError(f"Unknown mode: {mode}")


def run_all_experiments():
    """Run all 18 experiment combinations (3 modes × 3 workloads × 2 repetitions)."""
    print("=" * 50)
    print("Energy-Aware Autoscaling Experiment Suite")
    print("=" * 50)
    print(f"Modes: {EXPERIMENT_CONFIG['modes']}")
    print(f"Workloads: {EXPERIMENT_CONFIG['workloads']}")
    print(f"Repetitions: {EXPERIMENT_CONFIG['repetitions']}")
    print(f"Duration per combination: {EXPERIMENT_CONFIG['duration_per_combination']}s")
    print()
    
    all_results: List[Dict] = []
    experiment_counter = 0
    
    for mode in EXPERIMENT_CONFIG["modes"]:
        print(f"\n--- {mode.upper()} MODE ---")
        for workload in EXPERIMENT_CONFIG["workloads"]:
            for rep in range(EXPERIMENT_CONFIG["repetitions"]):
                experiment_counter += 1
                print(f"  {workload} (rep {rep})...", end=" ")
                result = run_experiment(mode, workload, duration=EXPERIMENT_CONFIG["duration_per_combination"], repetition=rep)
                all_results.append(result)
                if result:
                    ar = result
                    print(f"replicas={ar.get('average_replicas', 0):.1f}, "
                          f"CPU={ar.get('avg_cpu', 0):.1f}%, "
                          f"energy={ar.get('avg_energy_per_request', 0):.4f}J, "
                          f"SLA_violations={ar.get('total_sla_violations', 0)}")
    
    # Generate analysis
    generate_analysis(all_results)
    
    # Save results
    with open("experiment_results.json", 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print("\n" + "=" * 50)
    print("Experiment suite complete")
    print("Results saved to experiment_results.json")
    print("=" * 50)


def generate_analysis(results: List[Dict]):
    """Generate comparative analysis from experiment results."""
    print("\n" + "=" * 40)
    print("Comparative Analysis")
    print("=" * 40)
    
    # Organize by mode
    modes = {"static", "hpa", "energy_aware"}
    
    for mode in modes:
        mode_results = [r for r in results if r.get("mode") == mode]
        if not mode_results:
            continue
        
        print(f"\n--- {mode.upper()} MODE ---")
        
        # Compare workloads
        for workload in EXPERIMENT_CONFIG["workloads"]:
            wk_results = [r for r in mode_results if r.get("workload") == workload]
            if not wk_results:
                continue
            
            wk = wk_results[0]
            print(f"  {workload.capitalize():8s}: "
                  f"replicas={wk.get('average_replicas', 0):3.1f}, "
                  f"CPU={wk.get('avg_cpu', 0):3.1f}%, "
                  f"latency={wk.get('avg_latency_ms', 0):4.1f}ms, "
                  f"energy={wk.get('avg_energy_per_request', 0):6.4f}J, "
                  f"SLA_violations={wk.get('total_sla_violations', 0)}")
        
        # Summary stats
        avg_replicas_by_wl = {}
        avg_energy_by_wl = {}
        for wk_results in mode_results:
            wk = wk_results[0]
            profile_name = wk.get("workload")
            if profile_name:
                avg_replicas_by_wl[profile_name] = wk.get("average_replicas", 0)
                avg_energy_by_wl[profile_name] = wk.get("avg_energy_per_request", 0)
        
        if avg_replicas_by_wl:
            print(f"  Avg replicas by workload: {avg_replicas_by_wl}")
            print(f"  Avg energy/req by workload: {avg_energy_by_wl}")
    
    # Energy reduction analysis (energy-aware vs static baseline)
    print("\n  Energy Reduction Analysis (vs static baseline):")
    static_results = [r for r in results if r.get("mode") == "static"]
    ea_results = [r for r in results if r.get("mode") == "energy_aware"]
    
    if static_results and ea_results:
        for workload in EXPERIMENT_CONFIG["workloads"]:
            sr = [r for r in static_results if r.get("workload") == workload]
            er = [r for r in ea_results if r.get("workload") == workload]
            
            if sr and er:
                s_energy = sr[0].get("avg_energy_per_request", 0)
                e_energy = er[0].get("avg_energy_per_request", 0)
                
                if s_energy > 0 and e_energy >= 0:
                    reduction = ((s_energy - e_energy) / s_energy) * 100
                    print(f"    {workload}: {reduction:.1f}% reduction "
                          f"(static: {s_energy:.4f} J, EA: {e_energy:.4f} J)")


if __name__ == "__main__":
    run_all_experiments()
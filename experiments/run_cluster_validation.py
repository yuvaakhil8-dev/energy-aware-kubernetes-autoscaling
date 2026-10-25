#!/usr/bin/env python3
"""Validation of the real Kubernetes/HPA environment.

This is *not* the paired simulation and it is not a power measurement.  It
records real replica counts, request outcomes, and measured node CPU, then
applies the documented power model to that CPU.  Results are labelled
``kubernetes_validation`` and are reported separately from the simulation.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from eaes.config import atomic_write_json, git_commit, load_configs
from eaes.energy import EnergyModel

OUT_DIR = os.path.join(APP_DIR, "results", "cluster_validation")
HPA_PATH = os.path.join(APP_DIR, "kubernetes", "hpa.yaml")


def kubectl(args: List[str], check: bool = True, timeout: float = 60.0) -> str:
    proc = subprocess.run(
        ["kubectl"] + args, capture_output=True, text=True, timeout=timeout, check=False
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            "kubectl failed: " + " ".join(["kubectl"] + args) + "\n" + (proc.stderr or proc.stdout)
        )
    return proc.stdout.strip()


def deployment_state(namespace: str, deployment: str) -> Dict[str, int]:
    raw = kubectl(["get", "deployment", deployment, "-n", namespace, "-o", "json"])
    payload = json.loads(raw)
    status = payload.get("status", {})
    return {
        "spec": int(payload.get("spec", {}).get("replicas", 0) or 0),
        "ready": int(status.get("readyReplicas", 0) or 0),
        "available": int(status.get("availableReplicas", 0) or 0),
    }


def wait_ready(namespace: str, deployment: str, expected: int, timeout: float = 120.0) -> bool:
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        state = deployment_state(namespace, deployment)
        if state["ready"] >= expected:
            return True
        time.sleep(2)
    return False


def parse_percent(value: str) -> float | None:
    text = (value or "").strip().rstrip("%")
    try:
        return float(text)
    except ValueError:
        return None


def parse_millicores(value: str) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("m"):
            return float(text[:-1])
        if text.endswith("n"):
            return float(text[:-1]) / 1_000_000.0
        return float(text) * 1000.0
    except ValueError:
        return None


def top_node(namespace: str | None = None) -> tuple[float | None, int]:
    raw = kubectl(["top", "nodes", "--no-headers"], check=False, timeout=20.0)
    percentages = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            value = parse_percent(parts[2])
            if value is not None:
                percentages.append(value)
    node_raw = kubectl(["get", "nodes", "--no-headers"], check=False, timeout=20.0)
    nodes = len([line for line in node_raw.splitlines() if line.strip()])
    return (statistics.mean(percentages) if percentages else None), nodes


def top_pods(namespace: str, selector: str) -> float | None:
    raw = kubectl(
        ["top", "pods", "-n", namespace, "-l", selector, "--no-headers"],
        check=False,
        timeout=20.0,
    )
    values = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            value = parse_millicores(parts[1])
            if value is not None:
                values.append(value)
    return sum(values) if values else None


def fetch(url: str, timeout: float = 10.0) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            response.read()
            ok = 200 <= int(response.status) < 300
            status = int(response.status)
            error = None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        ok = False
        status = None
        error = str(exc)
    return {
        "ok": ok,
        "status": status,
        "latency_ms": (time.perf_counter() - started) * 1000.0,
        "error": error,
    }


class Sampler(threading.Thread):
    def __init__(self, namespace: str, deployment: str, selector: str, interval: float = 5.0):
        super().__init__(daemon=True)
        self.namespace = namespace
        self.deployment = deployment
        self.selector = selector
        self.interval = interval
        self.stop_event = threading.Event()
        self.samples: List[Dict[str, Any]] = []

    def run(self) -> None:
        started = time.time()
        while not self.stop_event.is_set():
            try:
                state = deployment_state(self.namespace, self.deployment)
            except Exception:
                state = {"spec": 0, "ready": 0, "available": 0}
            try:
                node_cpu, nodes = top_node(self.namespace)
            except Exception:
                node_cpu, nodes = None, 0
            try:
                pod_cpu = top_pods(self.namespace, self.selector)
            except Exception:
                pod_cpu = None
            self.samples.append(
                {
                    "elapsed_s": time.time() - started,
                    "replicas_spec": state["spec"],
                    "replicas_ready": state["ready"],
                    "replicas_available": state["available"],
                    "node_cpu_percent": node_cpu,
                    "pod_cpu_millicores": pod_cpu,
                    "node_count": nodes,
                }
            )
            self.stop_event.wait(self.interval)

    def stop(self) -> None:
        self.stop_event.set()
        self.join(timeout=30)


def reset_mode(mode: str, namespace: str, deployment: str, replicas: int) -> Dict[str, Any]:
    kubectl(["delete", "hpa", "energy-aware-hpa", "-n", namespace, "--ignore-not-found"])
    kubectl(["scale", "deployment", deployment, "-n", namespace, f"--replicas={replicas}"])
    ready = wait_ready(namespace, deployment, replicas, timeout=120)
    if not ready:
        raise RuntimeError(f"deployment did not reach {replicas} ready replicas")
    if mode == "hpa":
        kubectl(["apply", "-f", HPA_PATH, "-n", namespace])
        # Give the HPA controller and metrics-server a chance to observe the pod.
        time.sleep(20)
    return deployment_state(namespace, deployment)


def run_repetition(
    mode: str,
    repetition: int,
    duration: float,
    rate: float,
    namespace: str,
    deployment: str,
    selector: str,
    service_url: str,
    seed: int,
    energy_model: EnergyModel,
) -> Dict[str, Any]:
    initial = 1 if mode == "hpa" else 3
    before = reset_mode(mode, namespace, deployment, initial)
    sampler = Sampler(namespace, deployment, selector, interval=5.0)
    sampler.start()
    rng = random.Random(seed)
    url = service_url.rstrip("/") + "/cpu/intensive"
    requests: List[Dict[str, Any]] = []
    started = time.monotonic()
    deadline = started + duration
    next_arrival = started
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=64) as pool:
        futures = []
        while True:
            next_arrival += rng.expovariate(rate) if rate > 0 else duration + 1
            if next_arrival > deadline:
                break
            delay = next_arrival - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            offset = time.monotonic() - started
            futures.append((offset, pool.submit(fetch, url)))
        for offset, future in futures:
            outcome = future.result()
            requests.append(
                {
                    "offset_s": offset,
                    "ok": outcome["ok"],
                    "status": outcome["status"],
                    "latency_ms": outcome["latency_ms"],
                    "error": outcome["error"],
                }
            )
    elapsed = time.monotonic() - started
    sampler.stop()
    after = deployment_state(namespace, deployment)
    served = [r for r in requests if r["ok"]]
    latencies = [float(r["latency_ms"]) for r in served]
    latencies.sort()

    def percentile(values: List[float], q: float) -> float | None:
        if not values:
            return None
        pos = (len(values) - 1) * q
        lo = int(pos)
        hi = min(lo + 1, len(values) - 1)
        return values[lo] * (1 - (pos - lo)) + values[hi] * (pos - lo)

    # Modelled energy: apply the documented node power curve to measured node CPU.
    energy_j = None
    node_cpu_values = [s["node_cpu_percent"] for s in sampler.samples if s["node_cpu_percent"] is not None]
    if node_cpu_values and len(sampler.samples) >= 2:
        energy_j = 0.0
        for i in range(len(sampler.samples) - 1):
            current = sampler.samples[i]
            nxt = sampler.samples[i + 1]
            dt = max(0.0, float(nxt["elapsed_s"]) - float(current["elapsed_s"]))
            cpu = current["node_cpu_percent"]
            nodes = max(1, int(current["node_count"] or 1))
            if cpu is not None and dt > 0:
                util = max(0.0, min(1.0, float(cpu) / 100.0))
                energy_j += nodes * energy_model.node_energy_j(util, dt)

    replicas = [s["replicas_ready"] for s in sampler.samples]
    result = {
        "execution_mode": "kubernetes_validation",
        "mode": mode,
        "repetition": repetition,
        "seed": seed,
        "namespace": namespace,
        "deployment": deployment,
        "service_url": service_url,
        "target_rate_rps": rate,
        "duration_s": elapsed,
        "initial_state": before,
        "final_state": after,
        "offered_requests": len(requests),
        "served_requests": len(served),
        "failed_requests": len(requests) - len(served),
        "drop_rate": (len(requests) - len(served)) / len(requests) if requests else None,
        "throughput_rps": len(served) / elapsed if elapsed > 0 else None,
        "avg_latency_ms": statistics.mean(latencies) if latencies else None,
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "p99_latency_ms": percentile(latencies, 0.99),
        "avg_ready_replicas": statistics.mean(replicas) if replicas else None,
        "max_ready_replicas": max(replicas) if replicas else None,
        "avg_node_cpu_percent": statistics.mean(node_cpu_values) if node_cpu_values else None,
        "max_node_cpu_percent": max(node_cpu_values) if node_cpu_values else None,
        "modelled_energy_j": energy_j,
        "modelled_energy_per_served_request_j": (energy_j / len(served)) if energy_j is not None and served else None,
        "samples": sampler.samples,
        "notes": [
            "Replica counts and request outcomes are real Kubernetes observations.",
            "Energy is modelled from measured node CPU, not measured power.",
            "This run is not part of the paired simulation experiment.",
        ],
    }
    return {"summary": result, "requests": requests}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--rate", type=float, default=20.0)
    parser.add_argument("--namespace", default="energy-aware-dev")
    parser.add_argument("--deployment", default="energy-aware-app")
    parser.add_argument("--selector", default="app=energy-aware-app")
    parser.add_argument("--service-url", default="http://127.0.0.1:5001")
    parser.add_argument("--scenario", default="nominal")
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    configs = load_configs()
    model = EnergyModel(configs["energy"], scenario=args.scenario)
    started_at = datetime.now(timezone.utc).isoformat()
    summaries = []
    for mode in ("static", "hpa"):
        for repetition in range(1, args.repetitions + 1):
            seed = 1000 + repetition + (0 if mode == "static" else 100)
            print(f"[{mode} rep {repetition}] resetting and running {args.duration:.0f}s ...", flush=True)
            result = run_repetition(
                mode,
                repetition,
                args.duration,
                args.rate,
                args.namespace,
                args.deployment,
                args.selector,
                args.service_url,
                seed,
                model,
            )
            summary = result["summary"]
            summaries.append(summary)
            json_path = os.path.join(OUT_DIR, f"{mode}_rep{repetition}.json")
            atomic_write_json(json_path, summary)
            with open(os.path.join(OUT_DIR, f"{mode}_rep{repetition}_requests.jsonl"), "w", encoding="utf-8") as fh:
                for row in result["requests"]:
                    fh.write(json.dumps(row, sort_keys=True) + "\n")
            print(
                f"  served={summary['served_requests']}/{summary['offered_requests']} "
                f"p95={summary['p95_latency_ms']} ms "
                f"avg_replicas={summary['avg_ready_replicas']} "
                f"max_replicas={summary['max_ready_replicas']} "
                f"node_cpu={summary['avg_node_cpu_percent']}%"
            )

    manifest = {
        "execution_mode": "kubernetes_validation",
        "started_at": started_at,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "namespace": args.namespace,
        "deployment": args.deployment,
        "service_url": args.service_url,
        "repetitions": args.repetitions,
        "duration_s": args.duration,
        "target_rate_rps": args.rate,
        "energy_scenario": model.scenario,
        "pue": model.pue,
        "node": kubectl(["get", "nodes", "-o", "wide"], check=False),
        "kubectl_version": kubectl(["version", "--client"], check=False),
        "minikube_version": subprocess.run(
            ["minikube", "version"], capture_output=True, text=True, check=False
        ).stdout.strip(),
        "docker_version": subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip(),
        "notes": [
            "This is a real Minikube/Docker cluster validation, not the paired simulation.",
            "The native Kubernetes HPA controls the hpa mode; the static mode has HPA deleted.",
            "Replica counts and request outcomes are real; energy is modelled from measured node CPU.",
        ],
    }
    atomic_write_json(os.path.join(OUT_DIR, "manifest.json"), manifest)
    atomic_write_json(os.path.join(OUT_DIR, "summary.json"), summaries)

    # CSV summary.
    fields = [
        "mode", "repetition", "seed", "offered_requests", "served_requests",
        "failed_requests", "drop_rate", "throughput_rps", "avg_latency_ms",
        "p95_latency_ms", "p99_latency_ms", "avg_ready_replicas",
        "max_ready_replicas", "avg_node_cpu_percent", "max_node_cpu_percent",
        "modelled_energy_j", "modelled_energy_per_served_request_j",
    ]
    with open(os.path.join(OUT_DIR, "summary.csv"), "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summaries)

    def fmt(v: Any, digits: int = 4) -> str:
        if v is None:
            return "null"
        if isinstance(v, float):
            return f"{v:.{digits}f}"
        return str(v)

    lines = [
        "# Cluster Validation (real Minikube, separate from simulation)",
        "",
        f"Git commit: `{manifest['git_commit']}`  ",
        f"Cluster: `{args.namespace}` / `{args.deployment}`  ",
        f"Target load: {args.rate} req/s for {args.duration:.0f} s per repetition; {args.repetitions} repetitions per mode.  ",
        f"Execution mode: **{manifest['execution_mode']}**  ",
        "",
        "> Replica counts and request outcomes are real Kubernetes observations. "
        "Energy is **modelled** by applying the documented node power curve to "
        "measured node CPU; it is not a physical power measurement.",
        "",
        "## Results",
        "",
        "| Mode | Rep | Served | Offered | Drop | Throughput | p50 ms | p95 ms | p99 ms | Avg repl | Max repl | Avg node CPU | Modelled J/req |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        lines.append(
            f"| {s['mode']} | {s['repetition']} | {s['served_requests']} | "
            f"{s['offered_requests']} | {fmt(s['drop_rate'])} | {fmt(s['throughput_rps'], 2)} | "
            f"{fmt(s['p50_latency_ms'], 1)} | {fmt(s['p95_latency_ms'], 1)} | "
            f"{fmt(s['p99_latency_ms'], 1)} | {fmt(s['avg_ready_replicas'], 2)} | "
            f"{fmt(s['max_ready_replicas'], 0)} | {fmt(s['avg_node_cpu_percent'], 1)} | "
            f"{fmt(s['modelled_energy_per_served_request_j'], 2)} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- Native HPA scaling and static-replica scaling were both exercised against the same Flask service.",
        "- These values validate that the cluster, metrics-server, service, and HPA are operational.",
        "- They do not validate the simulation's energy rankings; the simulation has 10 paired seeds and a fixed workload trace.",
        "- No claim of measured energy is made.",
        "",
        "## Exact environment",
        "",
        "```",
        manifest["node"],
        "```",
        "",
        "## Limitations",
        "",
        "- Single-node Minikube on Docker Desktop; not a multi-node production cluster.",
        "- Flask development server is used inside the container, not a production WSGI server.",
        "- Node CPU includes cluster/system overhead and is not per-pod power.",
        "- The load generator is external HTTP traffic, not the simulated arrivals.",
        "",
    ]
    with open(os.path.join(OUT_DIR, "CLUSTER_VALIDATION.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

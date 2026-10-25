"""Cluster backend abstraction and the discrete-time simulated cluster.

The controller talks only to this interface.  ``SimulatedCluster`` is used for
the confirmatory paired experiment.  ``KubernetesCluster`` is a separate,
explicitly labelled validation backend that shells out to a verified ``kubectl``
context; it never silently substitutes simulated data for a deployment.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from .energy import EnergyModel


class ClusterBackend(ABC):
    @abstractmethod
    def get_replicas(self) -> int:
        ...

    @abstractmethod
    def set_replicas(self, n: int) -> None:
        ...

    @abstractmethod
    def get_metrics(self, t: float) -> Dict[str, Any]:
        ...

    @abstractmethod
    def apply_arrivals(self, t: float, requests: int) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_served_and_dropped(self) -> Dict[str, int]:
        ...


class SimulatedCluster(ClusterBackend):
    """Fixed-capacity nodes, per-pod capacity, startup delay, bounded backlog.

    The simulation deliberately makes capacity depend on ready replicas.  A
    controller that adds replicas during a burst pays a startup delay before
    the new capacity exists; excess arrivals wait in a bounded queue and are
    dropped when the queue overflows.
    """

    def __init__(
        self,
        simulation_config: Dict[str, Any],
        energy_model: EnergyModel,
        initial_replicas: int | None = None,
    ):
        self.cfg = simulation_config
        self.energy = energy_model
        self.pods_per_node = int(simulation_config["pods_per_node"])
        self.pod_capacity_rps = float(simulation_config["pod_capacity_rps"])
        self.startup_delay_s = int(simulation_config["startup_delay_s"])
        self.max_replicas = int(simulation_config["max_replicas"])
        self.base_latency_ms = float(simulation_config["base_latency_ms"])
        self.max_queue_factor = float(simulation_config["max_queue_factor"])
        self.dt_s = 1.0  # replaced by the engine before the first tick

        initial = int(
            simulation_config.get("initial_replicas", 1)
            if initial_replicas is None
            else initial_replicas
        )
        self.ready = max(0, min(initial, self.max_replicas))
        self.desired = self.ready
        self.pending: List[Dict[str, float]] = []
        self.now = 0.0
        self.backlog = 0.0
        self.cum_served = 0
        self.cum_dropped = 0
        self.cum_offered = 0
        self.latencies: List[float] = []
        self.last_metrics: Dict[str, Any] = {
            "cpu_util": 0.0,
            "served": 0,
            "dropped": 0,
            "avg_latency_ms": None,
            "p95_latency_ms": None,
        }
        self._last_active_nodes = self._active_nodes()
        self._new_nodes_this_tick = 0

    # -- helpers ---------------------------------------------------------
    def _active_nodes(self) -> int:
        return int(math.ceil(self.ready / self.pods_per_node)) if self.ready > 0 else 0

    def _update_ready(self, t: float) -> None:
        self.now = max(self.now, float(t))
        remaining: List[Dict[str, float]] = []
        activated = 0
        for item in self.pending:
            if item["ready_at"] <= self.now + 1e-9:
                self.ready += int(item["count"])
                activated += int(item["count"])
            else:
                remaining.append(item)
        self.pending = remaining
        current_nodes = self._active_nodes()
        if current_nodes > self._last_active_nodes:
            self._new_nodes_this_tick += current_nodes - self._last_active_nodes
        self._last_active_nodes = current_nodes

    def _total_requested(self) -> int:
        return self.ready + sum(int(p["count"]) for p in self.pending)

    # -- interface -------------------------------------------------------
    def get_replicas(self) -> int:
        return self.ready

    def set_replicas(self, n: int) -> None:
        n = max(0, min(int(n), self.max_replicas))
        total = self._total_requested()
        if n == total:
            self.desired = n
            return
        if n > total:
            self.pending.append(
                {
                    "ready_at": self.now + self.startup_delay_s,
                    "count": n - total,
                }
            )
        else:
            to_remove = total - n
            for item in reversed(self.pending):
                if to_remove <= 0:
                    break
                take = min(int(item["count"]), to_remove)
                item["count"] -= take
                to_remove -= take
            self.pending = [p for p in self.pending if int(p["count"]) > 0]
            if to_remove > 0:
                self.ready = max(0, self.ready - to_remove)
        self.desired = n

    def get_metrics(self, t: float) -> Dict[str, Any]:
        self._new_nodes_this_tick = 0
        self._update_ready(t)
        active = self._active_nodes()
        capacity_rps = self.ready * self.pod_capacity_rps
        return {
            "t": float(t),
            "ready_replicas": self.ready,
            "desired_replicas": self.desired,
            "pending_replicas": sum(int(p["count"]) for p in self.pending),
            "active_nodes": active,
            "capacity_rps": capacity_rps,
            "backlog_requests": self.backlog,
            "cpu_util": float(self.last_metrics["cpu_util"]),
            "last_served": int(self.last_metrics["served"]),
            "last_dropped": int(self.last_metrics["dropped"]),
            "last_latency_ms": self.last_metrics["avg_latency_ms"],
        }

    def apply_arrivals(self, t: float, requests: int) -> Dict[str, Any]:
        if requests < 0:
            raise ValueError("requests must be non-negative")
        self._update_ready(t)
        requests = int(requests)
        capacity_rps = self.ready * self.pod_capacity_rps
        capacity_requests = capacity_rps * self.dt_s
        backlog_before = self.backlog
        if capacity_requests <= 0:
            served = 0
            dropped = int(requests + backlog_before)
            self.backlog = 0.0
            avg_latency = None
            p95_latency = None
        else:
            total = backlog_before + requests
            served = int(min(total, capacity_requests))
            backlog_after = total - served
            max_queue = self.max_queue_factor * capacity_requests
            if backlog_after > max_queue:
                dropped = int(math.ceil(backlog_after - max_queue))
                backlog_after = max_queue
            else:
                dropped = 0
            self.backlog = float(backlog_after)
            # Mean queue wait before service; served requests are a mixture,
            # so this is a conservative average.  p95 is an analytic estimate.
            wait_s = (backlog_before / capacity_rps) if capacity_rps > 0 else 0.0
            avg_latency = self.base_latency_ms + wait_s * 1000.0
            p95_latency = self.base_latency_ms + wait_s * 1000.0 * 3.0
        cpu_util = (served / capacity_requests) if capacity_requests > 0 else 0.0
        cpu_util = max(0.0, min(1.0, cpu_util))
        self.cum_offered += int(requests)
        self.cum_served += int(served)
        self.cum_dropped += int(dropped)
        if avg_latency is not None:
            self.latencies.append(float(avg_latency))
        self.last_metrics = {
            "cpu_util": cpu_util,
            "served": int(served),
            "dropped": int(dropped),
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
        }
        return {
            "offered": int(requests),
            "served": int(served),
            "dropped": int(dropped),
            "backlog_requests": self.backlog,
            "capacity_rps": capacity_rps,
            "capacity_requests": capacity_requests,
            "cpu_util": cpu_util,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "active_nodes": self._active_nodes(),
        }

    def get_served_and_dropped(self) -> Dict[str, int]:
        return {
            "offered": self.cum_offered,
            "served": self.cum_served,
            "dropped": self.cum_dropped,
        }

    def compute_energy(self, t: float, served: int) -> Dict[str, Any]:
        """Compute modelled node energy and attribute it to occupied pods."""
        self._update_ready(t)
        active = self._active_nodes()
        if active == 0 or self.ready == 0:
            self._new_nodes_this_tick = 0
            return {
                "node_energy_j": 0.0,
                "pod_energy_sum_j": 0.0,
                "conservation_error_j": 0.0,
                "active_nodes": 0,
                "node_util": 0.0,
                "node_energy_list_j": [],
                "pod_energy_list_j": [],
                "node_pod_counts": [],
            }
        full_node_capacity = self.pods_per_node * self.pod_capacity_rps * self.dt_s
        total_node_energy = 0.0
        pod_energy_all: List[float] = []
        node_energy_list: List[float] = []
        node_utils: List[float] = []
        node_pod_counts: List[int] = []
        startup_nodes = min(self._new_nodes_this_tick, active)
        for i in range(active):
            n_pods = min(self.pods_per_node, self.ready - i * self.pods_per_node)
            node_pod_counts.append(n_pods)
            node_served = (float(served) * n_pods / self.ready) if self.ready else 0.0
            node_util = node_served / full_node_capacity if full_node_capacity > 0 else 0.0
            node_util = max(0.0, min(1.0, node_util))
            node_utils.append(node_util)
            components = self.energy.node_components_j(node_util, self.dt_s)
            startup = self.energy.startup_energy_j if i >= active - startup_nodes else 0.0
            total = components["total_j"] + startup
            node_energy_list.append(total)
            total_node_energy += total
            per_pod_served = node_served / n_pods if n_pods else 0.0
            pod_energies = self.energy.attribute_pod_energy(
                components,
                [per_pod_served] * n_pods,
                startup_energy_j=startup,
            )
            pod_energy_all.extend(pod_energies)
        self._new_nodes_this_tick = 0
        pod_sum = sum(pod_energy_all)
        return {
            "node_energy_j": total_node_energy,
            "pod_energy_sum_j": pod_sum,
            "conservation_error_j": abs(total_node_energy - pod_sum),
            "active_nodes": active,
            "node_util": sum(node_utils) / len(node_utils) if node_utils else 0.0,
            "node_energy_list_j": node_energy_list,
            "pod_energy_list_j": pod_energy_all,
            "node_pod_counts": node_pod_counts,
        }


def parse_cpu_millicores(value: str) -> float:
    """Parse ``kubectl top`` CPU strings such as ``12m`` or ``1``."""
    text = (value or "").strip()
    if not text:
        return 0.0
    if text.endswith("m"):
        return float(text[:-1])
    if text.endswith("n"):
        return float(text[:-1]) / 1_000_000.0
    if text.endswith("u"):
        return float(text[:-1]) / 1_000.0
    return float(text) * 1000.0


class KubernetesCluster(ClusterBackend):
    """Validation-only backend that talks to a verified kubectl context.

    It is not used for the paired confirmatory experiment.  Replica readings and
    request outcomes are real; any energy derived from CPU is still a model
    estimate and must be labelled as such.
    """

    execution_mode = "kubernetes_validation"

    def __init__(
        self,
        namespace: str = "energy-aware-dev",
        deployment: str = "energy-aware-app",
        service_url: str | None = None,
        kubectl: str | None = None,
        pod_capacity_rps: float = 10.0,
        cpu_request_millicores: float = 100.0,
        label_selector: str = "app=energy-aware-app",
        request_timeout_s: float = 10.0,
    ):
        self.namespace = namespace
        self.deployment = deployment
        self.service_url = service_url.rstrip("/") if service_url else None
        self.kubectl = kubectl or os.environ.get("KUBECTL", "kubectl")
        if shutil.which(self.kubectl) is None:
            raise RuntimeError(
                f"kubectl executable not found: {self.kubectl!r}. "
                "Install/configure kubectl before using KubernetesCluster."
            )
        self.pod_capacity_rps = float(pod_capacity_rps)
        self.cpu_request_millicores = float(cpu_request_millicores)
        self.label_selector = label_selector
        self.request_timeout_s = float(request_timeout_s)
        self.cum_offered = 0
        self.cum_served = 0
        self.cum_dropped = 0
        self.last_metrics: Dict[str, Any] = {
            "cpu_util": None,
            "served": 0,
            "dropped": 0,
            "avg_latency_ms": None,
            "p95_latency_ms": None,
        }

    # -- kubectl helpers -------------------------------------------------
    def _run(self, args: List[str], timeout: float = 30.0) -> str:
        command = [self.kubectl] + args
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"kubectl failed to execute: {exc}") from exc
        if proc.returncode != 0:
            raise RuntimeError(
                "kubectl command failed: "
                + " ".join(command)
                + "\n"
                + (proc.stderr or proc.stdout)
            )
        return proc.stdout.strip()

    def _deployment_json(self) -> Dict[str, Any]:
        raw = self._run(
            ["get", "deployment", self.deployment, "-n", self.namespace, "-o", "json"]
        )
        return json.loads(raw)

    def _pod_cpu_millicores(self) -> float | None:
        try:
            raw = self._run(
                [
                    "top",
                    "pods",
                    "-n",
                    self.namespace,
                    "-l",
                    self.label_selector,
                    "--no-headers",
                ],
                timeout=20.0,
            )
        except RuntimeError:
            return None
        total = 0.0
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                total += parse_cpu_millicores(parts[1])
        return total

    def _node_count(self) -> int:
        try:
            raw = self._run(["get", "nodes", "--no-headers"], timeout=20.0)
        except RuntimeError:
            return 0
        return len([line for line in raw.splitlines() if line.strip()])

    # -- interface -------------------------------------------------------
    def get_replicas(self) -> int:
        raw = self._run(
            [
                "get",
                "deployment",
                self.deployment,
                "-n",
                self.namespace,
                "-o",
                "jsonpath={.status.readyReplicas}",
            ],
            timeout=20.0,
        )
        return int(raw) if raw.strip() else 0

    def set_replicas(self, n: int) -> None:
        n = max(0, int(n))
        self._run(
            [
                "scale",
                "deployment",
                self.deployment,
                "-n",
                self.namespace,
                f"--replicas={n}",
            ],
            timeout=30.0,
        )

    def get_metrics(self, t: float) -> Dict[str, Any]:
        payload = self._deployment_json()
        spec_replicas = int(payload.get("spec", {}).get("replicas", 0) or 0)
        status = payload.get("status", {})
        ready = int(status.get("readyReplicas", 0) or 0)
        pod_cpu = self._pod_cpu_millicores()
        cpu_util = None
        if pod_cpu is not None and ready > 0 and self.cpu_request_millicores > 0:
            cpu_util = pod_cpu / (ready * self.cpu_request_millicores)
            cpu_util = max(0.0, min(1.0, cpu_util))
        return {
            "t": float(t),
            "ready_replicas": ready,
            "desired_replicas": spec_replicas,
            "pending_replicas": max(0, spec_replicas - ready),
            "active_nodes": self._node_count(),
            "capacity_rps": ready * self.pod_capacity_rps,
            "backlog_requests": 0.0,
            "cpu_util": cpu_util,
            "last_served": int(self.last_metrics["served"]),
            "last_dropped": int(self.last_metrics["dropped"]),
            "last_latency_ms": self.last_metrics["avg_latency_ms"],
            "pod_cpu_millicores": pod_cpu,
        }

    def apply_arrivals(self, t: float, requests: int) -> Dict[str, Any]:
        if self.service_url is None:
            raise RuntimeError("service_url is required to send validation traffic")
        requests = int(requests)
        if requests < 0:
            raise ValueError("requests must be non-negative")
        url = self.service_url + "/cpu/intensive"

        def one_request() -> float | None:
            started = time.perf_counter()
            try:
                with urllib.request.urlopen(url, timeout=self.request_timeout_s) as response:
                    response.read()
                    ok = 200 <= int(response.status) < 300
            except (urllib.error.URLError, TimeoutError, OSError):
                ok = False
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return elapsed_ms if ok else None

        with ThreadPoolExecutor(max_workers=min(32, max(1, requests))) as pool:
            outcomes = list(pool.map(lambda _: one_request(), range(requests)))
        latencies = [x for x in outcomes if x is not None]
        served = len(latencies)
        dropped = requests - served
        avg_latency = sum(latencies) / len(latencies) if latencies else None
        p95_latency = None
        if latencies:
            ordered = sorted(latencies)
            p95_latency = ordered[min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))]
        self.cum_offered += requests
        self.cum_served += served
        self.cum_dropped += dropped
        self.last_metrics = {
            "cpu_util": self.last_metrics["cpu_util"],
            "served": served,
            "dropped": dropped,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
        }
        return {
            "offered": requests,
            "served": served,
            "dropped": dropped,
            "backlog_requests": 0.0,
            "capacity_rps": 0.0,
            "capacity_requests": None,
            "cpu_util": self.last_metrics["cpu_util"],
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "active_nodes": 0,
        }

    def get_served_and_dropped(self) -> Dict[str, int]:
        return {
            "offered": self.cum_offered,
            "served": self.cum_served,
            "dropped": self.cum_dropped,
        }

"""Cluster backend abstraction and the discrete-time simulated cluster.

The controller talks only to this interface.  The Kubernetes implementation is
an explicit stub; no cluster result can be produced by importing it.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
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


class KubernetesCluster(ClusterBackend):
    """Explicit stub for the cluster backend.

    A real implementation is attempted only in Phase 7 after WSL2, Docker,
    kubectl, and a cluster are independently verified.  Construction always
    fails so that a caller cannot accidentally present simulated data as a
    deployment.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        raise NotImplementedError(
            "KubernetesCluster is a stub. No verified cluster is configured; "
            "use SimulatedCluster for simulation and see LIMITATIONS.md."
        )

    def get_replicas(self) -> int:  # pragma: no cover
        raise NotImplementedError

    def set_replicas(self, n: int) -> None:  # pragma: no cover
        raise NotImplementedError

    def get_metrics(self, t: float) -> Dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def apply_arrivals(self, t: float, requests: int) -> Dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def get_served_and_dropped(self) -> Dict[str, int]:  # pragma: no cover
        raise NotImplementedError

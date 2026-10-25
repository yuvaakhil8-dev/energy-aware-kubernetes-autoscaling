"""Backend abstraction and simulated-cluster behaviour tests."""
import copy

import pytest

from eaes.backend import ClusterBackend, KubernetesCluster, SimulatedCluster, parse_cpu_millicores
from eaes.config import load_configs
from eaes.energy import EnergyModel, conservation_error


def _backend(initial=1, startup=10):
    configs = load_configs()
    sim = copy.deepcopy(configs["simulation"])
    sim["startup_delay_s"] = startup
    backend = SimulatedCluster(sim, EnergyModel(configs["energy"]), initial_replicas=initial)
    backend.dt_s = float(sim["control_interval_s"])
    return backend


def test_backend_implements_interface():
    backend = _backend()
    assert isinstance(backend, ClusterBackend)


def test_kubernetes_backend_requires_kubectl():
    with pytest.raises(RuntimeError):
        KubernetesCluster(kubectl="definitely-not-a-real-kubectl-binary")


def test_parse_cpu_millicores():
    assert parse_cpu_millicores("12m") == 12.0
    assert parse_cpu_millicores("1") == 1000.0
    assert parse_cpu_millicores("") == 0.0


def test_scale_up_is_delayed():
    backend = _backend(initial=1)
    assert backend.get_metrics(0)["ready_replicas"] == 1
    backend.set_replicas(3)
    assert backend.get_metrics(0)["pending_replicas"] == 2
    assert backend.get_metrics(5)["ready_replicas"] == 1
    metrics = backend.get_metrics(10)
    assert metrics["ready_replicas"] == 3
    assert metrics["pending_replicas"] == 0


def test_scale_down_is_immediate():
    backend = _backend(initial=3)
    assert backend.get_metrics(0)["ready_replicas"] == 3
    backend.set_replicas(1)
    assert backend.get_metrics(0)["ready_replicas"] == 1


def test_capacity_and_drop_accounting():
    backend = _backend(initial=1)
    out = backend.apply_arrivals(0, 300)
    assert out["capacity_requests"] == 50
    assert out["served"] == 50
    assert out["dropped"] == 150
    assert out["backlog_requests"] == 100
    totals = backend.get_served_and_dropped()
    assert totals == {"offered": 300, "served": 50, "dropped": 150}


def test_zero_replicas_drops_everything_and_uses_no_energy():
    backend = _backend(initial=1)
    backend.set_replicas(0)
    out = backend.apply_arrivals(0, 12)
    assert out["served"] == 0
    assert out["dropped"] == 12
    energy = backend.compute_energy(0, 0)
    assert energy["node_energy_j"] == 0
    assert energy["active_nodes"] == 0


def test_scaling_changes_served_requests():
    one = _backend(initial=1)
    three = _backend(initial=3)
    out1 = one.apply_arrivals(0, 200)
    out3 = three.apply_arrivals(0, 200)
    assert out3["served"] > out1["served"]


def test_energy_is_conserved_per_tick():
    backend = _backend(initial=3)
    out = backend.apply_arrivals(0, 100)
    energy = backend.compute_energy(0, out["served"])
    assert energy["conservation_error_j"] < 1e-9
    assert conservation_error(energy["node_energy_j"], energy["pod_energy_list_j"]) < 1e-9
    assert len(energy["pod_energy_list_j"]) == 3
    assert energy["node_energy_j"] > 0


def test_backlog_latency_rises():
    backend = _backend(initial=1)
    first = backend.apply_arrivals(0, 100)
    second = backend.apply_arrivals(5, 50)
    assert first["avg_latency_ms"] is not None
    assert second["avg_latency_ms"] > first["avg_latency_ms"]
    assert second["p95_latency_ms"] >= second["avg_latency_ms"]


def test_invalid_arrivals_rejected():
    backend = _backend()
    with pytest.raises(ValueError):
        backend.apply_arrivals(0, -1)

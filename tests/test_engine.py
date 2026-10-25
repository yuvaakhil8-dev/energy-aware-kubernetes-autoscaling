"""Experiment engine: pairing, determinism, conservation, and edge cases."""
import copy

from eaes.config import load_configs
from eaes.engine import run_single
from eaes.workload import generate_trace

import pytest


def _run(strategy, trace=None, configs=None):
    configs = configs or load_configs()
    trace = trace or generate_trace("medium", 1, 300, 5)
    return run_single(configs, trace, strategy)


def test_same_trace_and_strategy_are_reproducible():
    trace = generate_trace("variable", 2, 120, 5)
    a = _run("eaes", trace)
    b = _run("eaes", trace)
    assert a["summary"] == b["summary"]
    assert a["rows"] == b["rows"]


def test_all_strategies_use_the_same_trace_hash():
    trace = generate_trace("heavy", 3, 120, 5)
    hashes = {
        _run(name, trace)["summary"]["trace_hash"]
        for name in ("static", "cpu_threshold", "hpa_formula", "eaes", "forecasting_eaes")
    }
    assert hashes == {trace["trace_hash"]}


def test_energy_is_conserved_in_every_tick():
    result = _run("eaes")
    assert result["summary"]["conservation_max_error_j"] < 1e-6
    for row in result["rows"]:
        assert row["conservation_error_j"] < 1e-6
        assert row["node_energy_j"] >= 0
        assert row["pod_energy_sum_j"] == pytest.approx(row["node_energy_j"], abs=1e-6)


def test_zero_requests_return_null_energy_per_request():
    configs = load_configs()
    trace = {
        "workload": "zero",
        "seed": 1,
        "duration_s": 300,
        "control_interval_s": 5,
        "ticks": [
            {"tick": i, "time_s": i * 5, "rate_rps": 0.0, "arrivals": 0}
            for i in range(60)
        ],
    }
    trace["trace_hash"] = "zero-trace"
    result = run_single(configs, trace, "static")
    summary = result["summary"]
    assert summary["served_requests"] == 0
    assert summary["offered_requests"] == 0
    assert summary["energy_per_served_request_j"] is None
    assert summary["energy_per_offered_request_j"] is None
    assert summary["total_energy_j"] > 0  # idle energy of active nodes


def test_eaes_serves_more_than_static_under_heavy_load():
    trace = generate_trace("heavy", 4, 300, 5)
    static = _run("static", trace)["summary"]
    eaes = _run("eaes", trace)["summary"]
    assert static["drop_rate"] > eaes["drop_rate"]
    assert eaes["served_requests"] > static["served_requests"]


def test_summary_provenance_fields():
    summary = _run("hpa_formula")["summary"]
    for key in (
        "trace_hash",
        "strategy",
        "seed",
        "execution_mode",
        "energy_scenario",
        "pue",
        "replica_hours",
        "drop_rate",
        "sla_violation_rate",
        "scaling_events",
        "oscillations",
    ):
        assert key in summary
    assert summary["execution_mode"] == "simulation"
    assert summary["energy_scenario"] == "nominal"

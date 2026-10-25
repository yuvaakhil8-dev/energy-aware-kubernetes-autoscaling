"""Workload generation, trace reuse, and configuration provenance tests."""
import copy
import json
import os

import pytest

from eaes.config import combined_config_hash, config_hashes, load_configs, stable_hash
from eaes.workload import (
    WORKLOAD_CLASSES,
    generate_trace,
    load_or_create_trace,
    mean_rate_rps,
    trace_hash,
)


def test_all_workload_classes_generate_valid_traces():
    for workload in WORKLOAD_CLASSES:
        trace = generate_trace(workload, seed=7, duration_s=60, control_interval_s=5)
        assert trace["workload"] == workload
        assert len(trace["ticks"]) == 12
        assert all(t["arrivals"] >= 0 for t in trace["ticks"])
        assert trace["trace_hash"] == trace_hash(trace)


def test_trace_generation_is_deterministic():
    a = generate_trace("heavy", 3, 60, 5)
    b = generate_trace("heavy", 3, 60, 5)
    c = generate_trace("heavy", 4, 60, 5)
    assert a["trace_hash"] == b["trace_hash"]
    assert a["ticks"] == b["ticks"]
    assert a["trace_hash"] != c["trace_hash"]


def test_workload_rate_shapes():
    assert mean_rate_rps("light", 0) < mean_rate_rps("heavy", 0)
    assert mean_rate_rps("steady", 0) == mean_rate_rps("steady", 120)
    assert mean_rate_rps("bursty", 0) > mean_rate_rps("bursty", 30)
    assert mean_rate_rps("variable", 0) != mean_rate_rps("variable", 60)


def test_trace_reuse_and_hash_validation(tmp_path):
    path_dir = str(tmp_path)
    first = load_or_create_trace("medium", 5, 60, 5, path_dir)
    path = os.path.join(path_dir, "medium_seed5.json")
    assert os.path.exists(path)
    mtime = os.path.getmtime(path)
    second = load_or_create_trace("medium", 5, 60, 5, path_dir)
    assert first["trace_hash"] == second["trace_hash"]
    assert os.path.getmtime(path) == mtime

    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    payload["ticks"][0]["arrivals"] += 1
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    with pytest.raises(ValueError):
        load_or_create_trace("medium", 5, 60, 5, path_dir)


def test_config_hashes_are_stable_and_sensitive():
    configs = load_configs()
    assert config_hashes(configs) == config_hashes(copy.deepcopy(configs))
    before = combined_config_hash(configs)
    changed = copy.deepcopy(configs)
    changed["strategies"]["static"]["replicas"] += 1
    assert combined_config_hash(changed) != before
    assert stable_hash({"b": 2, "a": 1}) == stable_hash({"a": 1, "b": 2})


def test_config_rejects_bad_energy_scenario():
    configs = load_configs()
    bad = copy.deepcopy(configs)
    bad["energy"]["scenarios"]["nominal"]["p_max_w"] = 10
    from eaes.config import validate_configs

    with pytest.raises(ValueError):
        validate_configs(bad)

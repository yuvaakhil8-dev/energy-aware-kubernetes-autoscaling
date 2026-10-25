"""Unit tests for all five strategies and their decision rules."""
import copy

import pytest

from eaes.config import load_configs
from eaes.strategies import (
    CPUThresholdStrategy,
    EAESStrategy,
    ForecastingEAESStrategy,
    HPAFormulaStrategy,
    StaticStrategy,
    make_strategy,
)


def _configs():
    return load_configs()


def _state(**overrides):
    state = {
        "t": 100.0,
        "dt_s": 5.0,
        "warmup": False,
        "ready_replicas": 3,
        "desired_replicas": 3,
        "pending_replicas": 0,
        "active_nodes": 1,
        "capacity_rps": 30.0,
        "pod_capacity_rps": 10.0,
        "cpu_util": 0.5,
        "backlog_requests": 0.0,
        "arrival_rate_rps": 15.0,
        "startup_delay_s": 10.0,
    }
    state.update(overrides)
    return state


def test_static_is_fixed():
    strategy = make_strategy("static", _configs())
    assert isinstance(strategy, StaticStrategy)
    decision = strategy.decide(_state())
    assert decision.replicas == 3
    assert decision.action == "hold"
    assert decision.rule == "static_fixed_replicas"


def test_cpu_threshold_scales_up_and_down():
    strategy = make_strategy("cpu_threshold", _configs())
    up = strategy.decide(_state(t=100, cpu_util=0.9, desired_replicas=3))
    assert up.action == "up"
    assert up.replicas == 4
    hold = strategy.decide(_state(t=105, cpu_util=0.9, desired_replicas=4))
    assert hold.action == "hold"
    assert hold.rule == "up_cooldown"
    down_strategy = make_strategy("cpu_threshold", _configs())
    down = down_strategy.decide(_state(t=100, cpu_util=0.1, desired_replicas=3))
    assert down.action == "down"
    assert down.replicas == 2


def test_cpu_threshold_hysteresis_and_warmup():
    strategy = make_strategy("cpu_threshold", _configs())
    assert strategy.decide(_state(cpu_util=0.28, desired_replicas=3)).action == "hold"
    warm = strategy.decide(
        _state(t=10, cpu_util=0.1, desired_replicas=3, warmup=True)
    )
    assert warm.action == "hold"
    assert warm.rule == "warmup_no_scaledown"


def test_hpa_formula_scale_up_and_tolerance():
    strategy = make_strategy("hpa_formula", _configs())
    up = strategy.decide(_state(t=0, cpu_util=0.8, desired_replicas=3))
    assert up.action == "up"
    assert up.replicas == 5  # ceil(3 * 0.8 / 0.5)
    hold = strategy.decide(_state(t=5, cpu_util=0.52, desired_replicas=5))
    assert hold.action == "hold"
    assert hold.rule == "hpa_formula_within_tolerance"


def test_hpa_formula_scale_down_stabilization():
    strategy = make_strategy("hpa_formula", _configs())
    first = strategy.decide(_state(t=0, cpu_util=0.2, desired_replicas=3))
    assert first.action == "hold"
    still = strategy.decide(_state(t=299, cpu_util=0.2, desired_replicas=3))
    assert still.action == "hold"
    down = strategy.decide(_state(t=300, cpu_util=0.2, desired_replicas=3))
    assert down.action == "down"
    assert down.replicas == 2


def test_hpa_formula_metric_unavailable():
    strategy = make_strategy("hpa_formula", _configs())
    decision = strategy.decide(_state(cpu_util=None, capacity_rps=0, desired_replicas=3))
    assert decision.action == "up"
    assert decision.rule == "metric_unavailable_scale_up"


def test_eaes_scales_up_to_restore_margin():
    strategy = make_strategy("eaes", _configs())
    decision = strategy.decide(
        _state(t=100, cpu_util=1.0, desired_replicas=3, arrival_rate_rps=50)
    )
    assert decision.action == "up"
    assert decision.replicas == 8  # ceil(50 / (10 * 0.7))
    assert decision.rule == "sla_margin_below_threshold"
    assert decision.details["sla_margin"] < 0.1


def test_eaes_scales_down_only_when_safe_and_stable():
    strategy = make_strategy("eaes", _configs())
    # First safe observation starts the stabilization clock.
    first = strategy.decide(_state(t=100, cpu_util=0.2, desired_replicas=3, ready_replicas=3, arrival_rate_rps=5))
    assert first.action == "hold"
    early = strategy.decide(_state(t=120, cpu_util=0.2, desired_replicas=3, ready_replicas=3, arrival_rate_rps=5))
    assert early.rule == "stabilization"
    down = strategy.decide(_state(t=200, cpu_util=0.2, desired_replicas=3, ready_replicas=3, arrival_rate_rps=5))
    assert down.action == "down"
    assert down.replicas == 2


def test_eaes_warmup_and_minimum():
    strategy = make_strategy("eaes", _configs())
    warm = strategy.decide(_state(warmup=True, cpu_util=0.1, desired_replicas=3, arrival_rate_rps=5))
    assert warm.rule == "warmup_no_scaledown"
    minimum = strategy.decide(_state(desired_replicas=1, ready_replicas=1, cpu_util=0.1, arrival_rate_rps=1))
    assert minimum.rule == "min_replicas"


def test_eaes_never_scales_down_with_backlog():
    strategy = make_strategy("eaes", _configs())
    strategy.decide(_state(t=100, cpu_util=0.2, desired_replicas=3, arrival_rate_rps=5))
    decision = strategy.decide(
        _state(t=300, cpu_util=0.2, desired_replicas=3, arrival_rate_rps=5, backlog_requests=50)
    )
    assert decision.rule == "backlog_present"


def test_eaes_respects_max_replicas():
    strategy = make_strategy("eaes", _configs())
    decision = strategy.decide(
        _state(t=100, cpu_util=1.0, desired_replicas=10, ready_replicas=10, arrival_rate_rps=100)
    )
    assert decision.action == "hold"
    assert decision.rule == "max_replicas_reached"


def test_forecasting_eaes_uses_observation():
    strategy = make_strategy("forecasting_eaes", _configs())
    assert isinstance(strategy, ForecastingEAESStrategy)
    for _ in range(5):
        strategy.observe(50.0)
    decision = strategy.decide(
        _state(t=100, cpu_util=0.5, desired_replicas=3, arrival_rate_rps=0.0)
    )
    assert decision.details["demand_rps"] > 0
    assert decision.action == "up"


def test_all_decisions_are_serializable():
    for name in ("static", "cpu_threshold", "hpa_formula", "eaes", "forecasting_eaes"):
        decision = make_strategy(name, _configs()).decide(_state())
        payload = decision.to_dict()
        assert set(payload) == {"replicas", "action", "rule", "reason", "details"}
        assert isinstance(payload["replicas"], int)

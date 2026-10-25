"""Energy model and controller unit tests."""
import pytest

import controller as c


# ---------------------------------------------------------------------------
# Energy model
# ---------------------------------------------------------------------------
def test_power_at_idle_and_max():
    assert c.estimate_power(0) == pytest.approx(30.0)
    assert c.estimate_power(100) == pytest.approx(80.0)
    assert c.estimate_power(50) == pytest.approx(55.0)


def test_power_is_monotonic():
    values = [c.estimate_power(p) for p in range(0, 101, 10)]
    assert values == sorted(values)


def test_energy_per_request_units():
    # P(50 %) = 55 W, 15 s -> 825 J over 100 requests -> 8.25 J/req
    assert c.estimate_energy_per_request(50, 100, 15) == pytest.approx(8.25)


def test_energy_per_request_rejects_zero_requests():
    with pytest.raises(ValueError):
        c.estimate_energy_per_request(50, 0, 15)
    with pytest.raises(ValueError):
        c.estimate_energy_per_request(50, -1, 15)


def test_energy_scales_inversely_with_requests():
    single = c.estimate_energy_per_request(60, 10, 15)
    double = c.estimate_energy_per_request(60, 20, 15)
    assert double == pytest.approx(single / 2)


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------
def make_controller(**overrides):
    cfg = dict(c.DEFAULT_CONFIG)
    cfg.update(overrides)
    ctrl = c.EnergyAwareController(config=cfg)
    ctrl.start_monitoring()
    return ctrl


def feed(ctrl, cpu, latency=50.0, request_rate=5.0, successful=100):
    ctrl.update_metrics(cpu, request_rate, latency, successful, 0)


def test_replica_limits_enforced():
    ctrl = make_controller(min_replicas=1, max_replicas=10, cooldown_seconds=0,
                           scale_change_cooldown=0)
    ctrl.set_current_replicas(1)
    # Force a scale-up request many times; must never exceed max_replicas.
    for _ in range(40):
        for _ in range(3):
            feed(ctrl, cpu=95)
        ctrl.scaling_decision()
        ctrl.last_scale_time = 0
    status = ctrl.get_status()
    assert status['current_replicas'] <= 10
    assert status['current_replicas'] >= 1


def test_low_cpu_scales_down_but_not_below_minimum():
    ctrl = make_controller(min_replicas=2, max_replicas=10, cooldown_seconds=0,
                           scale_change_cooldown=0)
    ctrl.set_current_replicas(5)
    for _ in range(10):
        for _ in range(3):
            feed(ctrl, cpu=10)
        ctrl.scaling_decision()
        ctrl.last_scale_time = 0
    assert ctrl.get_status()['current_replicas'] >= 2


def test_sla_violation_forces_scale_up():
    ctrl = make_controller(min_replicas=1, max_replicas=10, cooldown_seconds=0,
                           scale_change_cooldown=0)
    ctrl.set_current_replicas(2)
    feed(ctrl, cpu=40, latency=900)  # above 500 ms threshold
    decision = ctrl.scaling_decision()
    assert decision is not None and decision > 0


def test_cooldown_blocks_repeated_scaling():
    ctrl = make_controller(min_replicas=1, max_replicas=10,
                           cooldown_seconds=60, scale_change_cooldown=30)
    ctrl.set_current_replicas(3)
    for _ in range(3):
        feed(ctrl, cpu=95)
    first = ctrl.scaling_decision()
    assert first is not None and first > 0
    # Immediately asking again must respect the cooldown.
    for _ in range(3):
        feed(ctrl, cpu=95)
    assert ctrl.scaling_decision() is None


def test_status_shape():
    ctrl = make_controller()
    status = ctrl.get_status()
    for key in ('current_replicas', 'target_replicas', 'mode'):
        assert key in status


def test_set_current_replicas_clamps():
    ctrl = make_controller(min_replicas=1, max_replicas=10)
    ctrl.set_current_replicas(999)
    assert ctrl.get_status()['current_replicas'] <= 10
    ctrl.set_current_replicas(-5)
    assert ctrl.get_status()['current_replicas'] >= 1

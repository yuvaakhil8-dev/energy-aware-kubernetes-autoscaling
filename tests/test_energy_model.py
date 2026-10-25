"""Node-level energy model, attribution, and edge-case tests."""
import copy
import math

import pytest

from eaes.config import load_configs
from eaes.energy import EnergyModel, EnergyModelError, conservation_error, scenario_names


def _model(scenario="nominal", pue=None):
    return EnergyModel(load_configs()["energy"], scenario=scenario, pue=pue)


def test_endpoint_power():
    model = _model("nominal")
    assert model.node_power_w(0.0) == model.p_idle_w
    assert model.node_power_w(1.0) == model.p_max_w
    assert model.node_power_w(0.5) == pytest.approx((model.p_idle_w + model.p_max_w) / 2)


def test_pue_and_dt():
    model = _model("nominal", pue=1.5)
    assert model.node_energy_j(0.0, 10) == pytest.approx(model.p_idle_w * 10 * 1.5)
    assert model.node_energy_j(1.0, 10) == pytest.approx(model.p_max_w * 10 * 1.5)


def test_invalid_utilization_and_dt():
    model = _model()
    for value in (-0.01, 1.01, float("nan"), float("inf")):
        with pytest.raises(EnergyModelError):
            model.node_power_w(value)
    with pytest.raises(EnergyModelError):
        model.node_energy_j(0.5, 0)


def test_attribution_conserves_node_energy():
    model = _model()
    components = model.node_components_j(0.6, 5.0)
    pods = model.attribute_pod_energy(components, [30, 20, 10], startup_energy_j=7.0)
    assert conservation_error(components["total_j"] + 7.0, pods) < 1e-9
    assert len(pods) == 3
    assert pods[0] >= pods[1] >= pods[2]  # CPU-use share


def test_zero_served_pods_split_idle_equally():
    model = _model()
    components = model.node_components_j(0.0, 5.0)
    pods = model.attribute_pod_energy(components, [0, 0, 0])
    assert conservation_error(components["total_j"], pods) < 1e-9
    assert pods[0] == pytest.approx(pods[2])


def test_zero_pods_has_no_attribution():
    assert _model().attribute_pod_energy({"idle_j": 1, "dynamic_j": 0, "total_j": 1}, []) == []


def test_zero_request_denominators_return_null():
    model = _model()
    result = model.per_request(500.0, served=0, offered=0)
    assert result["energy_per_served_request_j"] is None
    assert result["energy_per_offered_request_j"] is None
    result = model.per_request(500.0, served=0, offered=10)
    assert result["energy_per_served_request_j"] is None
    assert result["energy_per_offered_request_j"] == 50.0


def test_scenarios_change_power():
    low = _model("low")
    high = _model("high")
    assert high.node_power_w(0.5) > low.node_power_w(0.5)
    assert set(scenario_names(load_configs()["energy"])) == {"low", "nominal", "high"}


def test_invalid_scenario_and_pue():
    with pytest.raises(EnergyModelError):
        _model("does-not-exist")
    with pytest.raises(EnergyModelError):
        _model(pue=0.9)


def test_power_model_is_monotonic():
    model = _model()
    values = [model.node_power_w(i / 10) for i in range(11)]
    assert all(values[i] <= values[i + 1] for i in range(10))
    assert math.isclose(values[-1] - values[0], model.p_max_w - model.p_idle_w)

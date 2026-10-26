"""Tests for extension-only controllers and generated extension evidence."""
import json
import os

import pytest

from eaes.config import load_configs
from eaes.forecast import evaluate_forecast
from eaes.strategies import OracleStrategy

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(APP_DIR, "results", "extension")


def _json(name):
    with open(os.path.join(EXT, name), encoding="utf-8") as fh:
        return json.load(fh)


def test_oracle_uses_true_future_peak_and_respects_bounds():
    configs = load_configs()
    cfg = dict(configs["strategies"]["eaes"])
    oracle = OracleStrategy(cfg, configs["simulation"], configs["sla"])
    state = {
        "arrival_rate_rps": 3.0,
        "future_arrival_rates_rps": [5.0, 25.0, 9.0],
    }
    assert oracle.forecast_rate(state) == 25.0

    decision = oracle.decide(
        {
            "t": 100.0,
            "desired_replicas": 2,
            "ready_replicas": 2,
            "pending_replicas": 0,
            "pod_capacity_rps": 10.0,
            "dt_s": 5.0,
            "cpu_util": 0.2,
            "observed_rate_rps": 3.0,
            "arrival_rate_rps": 3.0,
            "future_arrival_rates_rps": [80.0, 80.0],
        }
    )
    assert 1 <= decision.replicas <= int(configs["simulation"]["max_replicas"])


def test_extension_manifests_are_labeled_and_keep_confirmatory_run_visible():
    for name in ("oracle/manifest.json", "startup_sweep/manifest.json", "seed30/manifest.json"):
        manifest = _json(name)
        assert manifest["label"] == "exploratory_extension"
        assert manifest["confirmatory_run_unchanged"] == "v3_paired_20261025T220942Z"
        assert manifest["execution_mode"] == "simulation"
        assert manifest["git_tracked_dirty"] is False
    seed30 = _json("seed30/manifest.json")
    assert seed30["seeds"] == list(range(11, 31))
    assert seed30["combined_with_confirmatory_seeds"] == list(range(1, 11))


def test_forecast_mape_excludes_zero_and_near_zero_actuals():
    rates = [10.0, 10.0, 10.0, 10.0, 0.0, 0.0, 10.0, 10.0]
    result = evaluate_forecast(
        rates,
        method="ewma",
        cfg={"alpha": 0.3},
        horizon_steps=1,
        eval_fraction=0.5,
        mape_min_actual=0.5,
    )
    assert result["n"] > 0
    assert result["zero_actuals"] > 0
    assert result["mape_excluded"] == result["zero_actuals"]
    assert result["mape_n"] == result["n"] - result["mape_excluded"]


def test_energy_sensitivity_recomputes_nominal_exactly():
    manifest = _json("energy_sensitivity/manifest.json")
    assert manifest["n_runs"] == 3600
    assert manifest["nominal_recompute_max_rel_error"] == 0.0
    assert manifest["confirmatory_run_unchanged"] == "v3_paired_20261025T220942Z"


def test_hpa_replay_manifest_reports_scope_and_limitations():
    manifest = _json("hpa_replay/manifest.json")
    assert manifest["n_transitions"] == 30
    assert manifest["agreement_rate_spec"] == 1.0
    assert manifest["predicted_replica_changes"] == 0
    assert manifest["observed_replica_changes_between_samples"] == 0
    assert any("initial 1->4 transition is not observed" in item for item in manifest["limitations"])


def test_extension_summaries_have_expected_design():
    oracle = json.load(open(os.path.join(EXT, "oracle", "summary.json"), encoding="utf-8"))
    startup = json.load(open(os.path.join(EXT, "startup_sweep", "summary.json"), encoding="utf-8"))
    seed30 = json.load(open(os.path.join(EXT, "seed30", "summary.json"), encoding="utf-8"))
    assert len(oracle) == 6 * 6 * 10
    assert {r["strategy"] for r in oracle} == {
        "static", "cpu_threshold", "hpa_formula", "eaes", "forecasting_eaes", "oracle"
    }
    assert len(startup) == 6 * 2 * 3 * 10
    assert {r["startup_delay_s"] for r in startup} == {5, 10, 20}
    assert len(seed30) == 6 * 5 * 20
    assert all(r["strategy"] != "oracle" for r in seed30)


@pytest.mark.parametrize("path", [
    "oracle/ORACLE.md",
    "startup_sweep/STARTUP_SWEEP.md",
    "seed30/RESULTS_30SEED.md",
    "energy_sensitivity/ENERGY_SENSITIVITY.md",
    "energy_vs_drop/README.md",
    "hpa_replay/HPA_REPLAY.md",
])
def test_extension_reports_exist_and_are_labeled(path):
    with open(os.path.join(EXT, path), encoding="utf-8") as fh:
        text = fh.read().lower()
    assert text.strip()
    assert "extension" in text

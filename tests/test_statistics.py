"""Statistical analysis tests on small known datasets."""
import math

import pytest

from analysis.analyze import (
    _bootstrap_ci,
    _chi2_sf_df4,
    _ranks,
    cliffs_delta,
    friedman_test,
    holm_adjust,
    wilcoxon_signed_rank,
)


def test_average_ranks_with_ties():
    assert _ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]


def test_bootstrap_ci_is_deterministic_and_brackets_mean():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    a = _bootstrap_ci(values, seed=7, resamples=500)
    b = _bootstrap_ci(values, seed=7, resamples=500)
    assert a == b
    assert a[0] <= 3.0 <= a[1]


def test_wilcoxon_all_positive_differences():
    result = wilcoxon_signed_rank([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert result["n"] == 10
    assert result["p_value"] is not None
    assert 0 <= result["p_value"] <= 1


def test_wilcoxon_small_sample_not_testable():
    result = wilcoxon_signed_rank([1, 2, 3])
    assert result["note"] == "not_testable"
    assert result["p_value"] is None


def test_holm_adjustment():
    adjusted = holm_adjust([0.01, 0.04, 0.03, None])
    assert adjusted[3] is None
    assert adjusted[0] == pytest.approx(0.03)
    assert adjusted[2] == pytest.approx(0.06)
    assert adjusted[1] == pytest.approx(0.06)


def test_cliffs_delta_extremes():
    assert cliffs_delta([2, 3, 4], [1, 2, 3]) == pytest.approx(5 / 9)
    assert cliffs_delta([1, 2, 3], [2, 3, 4]) == pytest.approx(-5 / 9)
    assert cliffs_delta([1, 2, 3], [1, 2, 3]) == 0.0
    assert cliffs_delta([4, 5, 6], [1, 2, 3]) == 1.0
    assert cliffs_delta([1, 2, 3], [4, 5, 6]) == -1.0


def test_chi_square_df4_exact_values():
    assert _chi2_sf_df4(0) == 1.0
    assert _chi2_sf_df4(1) == pytest.approx(math.exp(-0.5) * 1.5)
    assert _chi2_sf_df4(10) < 0.05


def test_friedman_toy_dataset():
    strategies = ["static", "cpu_threshold", "hpa_formula", "eaes", "forecasting_eaes"]
    rows = []
    for seed in range(1, 6):
        for i, strategy in enumerate(strategies):
            rows.append(
                {
                    "workload": "toy",
                    "seed": seed,
                    "strategy": strategy,
                    "energy_per_served_request_j": float(i + 1),
                    "sla_violation_rate": 0.0,
                    "replica_hours": float(i + 1),
                    "drop_rate": 0.0,
                }
            )
    result = friedman_test(rows, "toy", "energy_per_served_request_j", strategies)
    assert result["n_blocks"] == 5
    assert result["Q"] is not None
    assert result["p_value"] is not None
    assert result["Q"] > 0
    assert result["rank_sums"]["static"] == 5.0


def test_friedman_handles_incomplete_blocks():
    strategies = ["static", "eaes"]
    rows = [
        {"workload": "toy", "seed": 1, "strategy": "static", "energy_per_served_request_j": 1.0},
        {"workload": "toy", "seed": 1, "strategy": "eaes", "energy_per_served_request_j": 2.0},
    ]
    result = friedman_test(rows, "toy", "energy_per_served_request_j", strategies)
    assert result["note"] == "not_testable"

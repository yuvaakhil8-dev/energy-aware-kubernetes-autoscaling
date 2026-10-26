"""Headline table contract tests.

These tests never write into the committed results directory.  They exercise
the pure aggregation functions with synthetic run-level summaries.
"""
import copy

from analysis.make_headline_table import (
    BASELINES,
    METRICS,
    STRATEGIES,
    bootstrap_median_ci,
    descriptive_rows,
    paired_rows,
)


def _summaries():
    rows = []
    for seed in (1, 2, 3):
        for strategy in STRATEGIES:
            rows.append(
                {
                    "workload": "steady",
                    "strategy": strategy,
                    "seed": seed,
                    "energy_per_served_request_j": 10.0 + seed + STRATEGIES.index(strategy),
                    "energy_per_offered_request_j": 12.0 + seed,
                    "drop_rate": 0.01 * seed,
                    "sla_violation_rate": 0.005 * seed,
                    "replica_hours": 0.2 + 0.01 * seed,
                    "p95_latency_ms": 20.0 + seed,
                    "scaling_events": float(seed),
                    "oscillations": float(seed - 1),
                }
            )
    return rows


def test_descriptive_covers_every_workload_strategy_metric():
    rows = descriptive_rows(_summaries(), ["steady"])
    assert len(rows) == len(STRATEGIES) * len(METRICS)
    for row in rows:
        assert row["n"] == 3
        assert row["missing"] == 0
        assert row["ci_low"] <= row["mean"] <= row["ci_high"]
        assert row["median_ci_low"] <= row["median"] <= row["median_ci_high"]


def test_missing_metric_is_not_replaced():
    data = _summaries()
    for row in data:
        if row["strategy"] == "static":
            row["energy_per_served_request_j"] = None
    rows = descriptive_rows(data, ["steady"])
    static_energy = [
        r for r in rows if r["strategy"] == "static" and r["metric"] == "energy_per_served_request_j"
    ][0]
    assert static_energy["n"] == 0
    assert static_energy["mean"] is None
    assert static_energy["ci_low"] is None


def test_paired_rows_pair_by_seed_and_cover_both_baselines():
    rows = paired_rows(_summaries(), ["steady"])
    assert any(r["baseline"] == "cpu_threshold" for r in rows)
    assert any(r["baseline"] == "hpa_formula" for r in rows)
    eaes = [
        r
        for r in rows
        if r["strategy"] == "eaes"
        and r["baseline"] == "hpa_formula"
        and r["metric"] == "energy_per_served_request_j"
    ][0]
    assert eaes["n_pairs"] == 3
    # EAES is one place after HPA in STRATEGIES, so its synthetic energy is +1 J.
    assert eaes["median_diff"] == 1.0
    # Cliff's delta is the unpaired all-pairs effect size, so it is positive
    # here but not necessarily 1.0.
    assert eaes["cliffs_delta"] > 0
    assert eaes["ci_low"] <= eaes["median_diff"] <= eaes["ci_high"]


def test_median_bootstrap_is_deterministic():
    values = [1.0, 2.0, 3.0, 4.0, 100.0]
    a = bootstrap_median_ci(values, seed=7)
    b = bootstrap_median_ci(values, seed=7)
    assert a == b
    assert a[0] <= 3.0 <= a[1]


def test_expected_baseline_set_is_explicit():
    assert BASELINES == ["cpu_threshold", "hpa_formula", "eaes"]

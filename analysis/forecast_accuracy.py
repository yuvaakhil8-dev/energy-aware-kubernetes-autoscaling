#!/usr/bin/env python3
"""Held-out forecast accuracy and its decision relevance.

Forecast accuracy is measured on the final 50% of each recorded trace with a
two-step (10 s) horizon.  MAPE excludes zero and near-zero actuals explicitly;
the excluded count is reported rather than hidden.  Accuracy alone is not
evidence that a controller is better, so the final section joins the forecast
evaluation to the confirmatory forecasting-EAES comparison.
"""
from __future__ import annotations

import csv
import json
import math
import os
import statistics
import sys
from typing import Any, Dict, Iterable, List, Sequence

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from analysis.make_headline_table import _latest_run, bootstrap_median_ci
from analysis.analyze import _bootstrap_ci, _stable_seed
from eaes.config import load_configs
from eaes.forecast import evaluate_forecast
from eaes.workload import load_or_create_trace

OUT_DIR = os.path.join(APP_DIR, "results", "tables")
MAPE_MIN_ACTUAL = 0.5  # req/s; smaller actuals are counted, not divided by


def _write_csv(path: str, rows: Sequence[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write("")
        return
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _mean_ci(values: Sequence[float], seed: int):
    return _bootstrap_ci(values, seed=seed)


def collect() -> List[Dict[str, Any]]:
    configs = load_configs()
    exp = configs["experiment"]
    rows: List[Dict[str, Any]] = []
    for workload in exp["workloads"]:
        for seed in exp["seeds"]:
            trace = load_or_create_trace(
                workload, int(seed), int(exp["duration_s"]), int(exp["control_interval_s"]),
                os.path.join(APP_DIR, exp["trace_dir"]),
            )
            rates = [t["arrivals"] / float(exp["control_interval_s"]) for t in trace["ticks"]]
            for method, cfg in (("ewma", {"alpha": 0.3}), ("holt", {"alpha": 0.5, "beta": 0.3})):
                result = evaluate_forecast(
                    rates,
                    method=method,
                    cfg=cfg,
                    horizon_steps=2,
                    eval_fraction=float(exp["forecast_eval_fraction"]),
                    mape_min_actual=MAPE_MIN_ACTUAL,
                )
                rows.append(
                    {
                        "workload": workload,
                        "seed": int(seed),
                        "method": method,
                        "horizon_steps": int(result["horizon_steps"]),
                        "n": result["n"],
                        "mae": result["mae"],
                        "mape_pct": result["mape_pct"],
                        "mape_n": result["mape_n"],
                        "mape_excluded": result["mape_excluded"],
                        "zero_actuals": result["zero_actuals"],
                        "mape_min_actual": result["mape_min_actual"],
                    }
                )
    return rows


def summarise(rows: Sequence[Dict[str, Any]], workloads: Sequence[str]) -> List[Dict[str, Any]]:
    out = []
    for workload in workloads:
        for method in ("ewma", "holt"):
            subset = [r for r in rows if r["workload"] == workload and r["method"] == method]
            mae_values = [float(r["mae"]) for r in subset if isinstance(r["mae"], (int, float))]
            mape_values = [float(r["mape_pct"]) for r in subset if isinstance(r["mape_pct"], (int, float))]
            mae_lo, mae_hi = _mean_ci(mae_values, seed=_stable_seed(workload, method, "mae"))
            mape_lo, mape_hi = _mean_ci(mape_values, seed=_stable_seed(workload, method, "mape"))
            mae_med_lo, mae_med_hi = bootstrap_median_ci(
                mae_values, seed=_stable_seed(workload, method, "mae_med"), resamples=2000
            )
            out.append(
                {
                    "workload": workload,
                    "method": method,
                    "n_seeds": len(subset),
                    "n_observations": sum(int(r["n"]) for r in subset),
                    "mae_mean": statistics.mean(mae_values) if mae_values else None,
                    "mae_median": statistics.median(mae_values) if mae_values else None,
                    "mae_ci_low": mae_lo,
                    "mae_ci_high": mae_hi,
                    "mae_median_ci_low": mae_med_lo,
                    "mae_median_ci_high": mae_med_hi,
                    "mape_mean": statistics.mean(mape_values) if mape_values else None,
                    "mape_median": statistics.median(mape_values) if mape_values else None,
                    "mape_ci_low": mape_lo,
                    "mape_ci_high": mape_hi,
                    "mape_n": sum(int(r["mape_n"]) for r in subset),
                    "mape_excluded": sum(int(r["mape_excluded"]) for r in subset),
                    "zero_actuals": sum(int(r["zero_actuals"]) for r in subset),
                }
            )
    return out


def decision_relevance() -> List[Dict[str, Any]]:
    run_dir = _latest_run()
    with open(os.path.join(run_dir, "summary.json"), encoding="utf-8") as fh:
        summaries = json.load(fh)
    out = []
    for workload in sorted({r["workload"] for r in summaries}):
        def mean(strategy, metric):
            vals = [r[metric] for r in summaries if r["workload"] == workload and r["strategy"] == strategy and isinstance(r.get(metric), (int, float))]
            return statistics.mean(vals) if vals else None
        out.append(
            {
                "workload": workload,
                "eaes_energy_per_served_j": mean("eaes", "energy_per_served_request_j"),
                "forecast_energy_per_served_j": mean("forecasting_eaes", "energy_per_served_request_j"),
                "eaes_sla_violation_rate": mean("eaes", "sla_violation_rate"),
                "forecast_sla_violation_rate": mean("forecasting_eaes", "sla_violation_rate"),
                "eaes_replica_hours": mean("eaes", "replica_hours"),
                "forecast_replica_hours": mean("forecasting_eaes", "replica_hours"),
            }
        )
    return out


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> int:
    configs = load_configs()
    exp = configs["experiment"]
    rows = collect()
    summary = summarise(rows, exp["workloads"])
    relevance = decision_relevance()
    _write_csv(os.path.join(OUT_DIR, "forecast_accuracy.csv"), rows)
    _write_csv(os.path.join(OUT_DIR, "forecast_accuracy_summary.csv"), summary)
    _write_csv(os.path.join(OUT_DIR, "forecast_decision_relevance.csv"), relevance)

    lines = [
        "# Forecast accuracy (held-out)",
        "",
        "Evaluation window: final 50% of each trace, two-step (10 s) horizon, online update. "
        f"MAPE excludes actual rates below {MAPE_MIN_ACTUAL} req/s and every zero actual; "
        "the excluded count is shown. This is a held-out segment, not a rolling-origin retraining study.",
        "",
        "| Workload | Method | Seeds | Held-out points | MAE mean [95% CI] | MAE median [95% CI] | MAPE mean % [95% CI] | MAPE points | Excluded | Zero actuals |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in summary:
        lines.append(
            f"| {row['workload']} | {row['method']} | {row['n_seeds']} | {row['n_observations']} | "
            f"{_fmt(row['mae_mean'])} [{_fmt(row['mae_ci_low'])}, {_fmt(row['mae_ci_high'])}] | "
            f"{_fmt(row['mae_median'])} [{_fmt(row['mae_median_ci_low'])}, {_fmt(row['mae_median_ci_high'])}] | "
            f"{_fmt(row['mape_mean'])} [{_fmt(row['mape_ci_low'])}, {_fmt(row['mape_ci_high'])}] | "
            f"{row['mape_n']} | {row['mape_excluded']} | {row['zero_actuals']} |"
        )
    lines += [
        "",
        "## What the forecast errors mean for control",
        "",
        "Lower MAE/MAPE is a necessary but not sufficient condition for better autoscaling. "
        "The table below joins the confirmatory forecasting-EAES comparison to show whether the "
        "forecast changed energy, SLA violations, and provisioning. These are run-level means over "
        "the ten confirmatory seeds; they are not causal estimates.",
        "",
        "| Workload | EAES E/served | Forecast E/served | EAES SLA | Forecast SLA | EAES repl-h | Forecast repl-h |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in relevance:
        lines.append(
            f"| {row['workload']} | {_fmt(row['eaes_energy_per_served_j'])} | "
            f"{_fmt(row['forecast_energy_per_served_j'])} | "
            f"{_fmt(row['eaes_sla_violation_rate'])} | {_fmt(row['forecast_sla_violation_rate'])} | "
            f"{_fmt(row['eaes_replica_hours'])} | {_fmt(row['forecast_replica_hours'])} |"
        )
    lines += [
        "",
        "Interpretation guardrails:",
        "",
        "- Holt and EWMA are deliberately small forecasters, not tuned production models.",
        "- A forecast error on a smooth trace can be small while the resulting scaling decision is unchanged.",
        "- On bursty traces, a two-step horizon can be too short to pre-provision a 10 s startup delay; "
        "the startup-delay sweep in `results/extension/startup_sweep/` tests this directly.",
        "- Forecasting did not remove bursty SLA violations in the confirmatory run. Accuracy alone does not "
        "make the forecasting controller universally superior.",
        "",
    ]
    with open(os.path.join(OUT_DIR, "forecast_accuracy.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"forecast rows: {len(rows)}; summary rows: {len(summary)}")
    print(f"wrote {os.path.join(OUT_DIR, 'forecast_accuracy.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

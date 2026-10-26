#!/usr/bin/env python3
"""Run the explicitly labelled extensions.

Outputs are written only below ``results/extension/``.  The confirmatory run
``v3_paired_20261025T220942Z`` and its derived tables are never modified.

Extensions:
  * perfect-foresight oracle upper bound;
  * startup-delay sweep for reactive and forecasting EAES;
  * seeds 11-30 for all six workloads and all five confirmatory strategies.

The 30-seed extension is a new sample, not a replacement for the 10-seed
confirmatory analysis.
"""
from __future__ import annotations

import copy
import csv
import json
import math
import os
import statistics
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence, Tuple

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import yaml

from analysis.make_headline_table import descriptive_rows, paired_rows
from eaes.config import (
    atomic_write_json,
    combined_config_hash,
    config_hashes,
    git_commit,
    git_tracked_dirty,
    load_configs,
    package_versions,
    utc_now,
)
from eaes.engine import run_single
from eaes.workload import load_or_create_trace

EXT_ROOT = os.path.join(APP_DIR, "results", "extension")
CONFIRMATORY_SUMMARY = os.path.join(
    APP_DIR, "results", "runs", "v3_paired_20261025T220942Z", "summary.json"
)


def _extension_configs() -> Dict[str, Dict[str, Any]]:
    configs = load_configs()
    with open(os.path.join(APP_DIR, "configs", "extensions.yaml"), encoding="utf-8") as fh:
        extra = yaml.safe_load(fh)
    configs["strategies"]["oracle"] = extra["oracle"]
    return configs


def _write_csv(path: str, rows: Sequence[Dict[str, Any]], fields: Sequence[str] | None = None) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write("")
        return
    fieldnames = list(fields) if fields else list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _mean(values: Iterable[float]) -> float | None:
    vals = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))]
    return statistics.mean(vals) if vals else None


def _median(values: Iterable[float]) -> float | None:
    vals = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))]
    return statistics.median(vals) if vals else None


def run_matrix(
    configs: Dict[str, Dict[str, Any]],
    workloads: Sequence[str],
    seeds: Sequence[int],
    strategies: Sequence[str],
    trace_dir: str,
    energy_scenario: str | None = None,
) -> List[Dict[str, Any]]:
    exp = configs["experiment"]
    dt = int(exp["control_interval_s"])
    out: List[Dict[str, Any]] = []
    for workload in workloads:
        for seed in seeds:
            trace = load_or_create_trace(
                workload, int(seed), int(exp["duration_s"]), dt,
                os.path.join(APP_DIR, trace_dir),
            )
            for strategy in strategies:
                summary = run_single(configs, trace, strategy, energy_scenario)["summary"]
                summary["extension"] = True
                out.append(summary)
    return out


def _manifest(name: str, configs, seeds, strategies, notes) -> Dict[str, Any]:
    return {
        "extension": name,
        "label": "exploratory_extension",
        "confirmatory_run_unchanged": "v3_paired_20261025T220942Z",
        "started_at": utc_now(),
        "execution_mode": "simulation",
        "energy_scenario": configs["energy"]["default_scenario"],
        "git_commit": git_commit(),
        "git_tracked_dirty": git_tracked_dirty(),
        "config_hashes": config_hashes(configs),
        "config_hash": combined_config_hash(configs),
        "seeds": list(seeds),
        "strategies": list(strategies),
        "python": package_versions(),
        "notes": notes,
    }


def _summary_fields() -> Sequence[str]:
    return [
        "workload", "seed", "strategy", "energy_per_served_request_j",
        "energy_per_offered_request_j", "drop_rate", "sla_violation_rate",
        "replica_hours", "avg_ready_replicas", "p95_latency_ms",
        "scaling_events", "oscillations", "served_requests", "offered_requests",
        "measurement_energy_j", "trace_hash",
    ]


def _compact(summary: Dict[str, Any]) -> Dict[str, Any]:
    row = {key: summary.get(key) for key in _summary_fields()}
    row["extension"] = True
    return row


def run_oracle() -> Dict[str, Any]:
    out_dir = os.path.join(EXT_ROOT, "oracle")
    os.makedirs(out_dir, exist_ok=True)
    configs = _extension_configs()
    exp = configs["experiment"]
    strategies = ["static", "cpu_threshold", "hpa_formula", "eaes", "forecasting_eaes", "oracle"]
    summaries = run_matrix(configs, exp["workloads"], exp["seeds"], strategies, exp["trace_dir"])
    manifest = _manifest(
        "oracle", configs, exp["seeds"], strategies,
        "Perfect-foresight upper bound. Not a deployable controller and not part of the confirmatory comparison.",
    )
    manifest["n_runs"] = len(summaries)
    atomic_write_json(os.path.join(out_dir, "summary.json"), summaries)
    atomic_write_json(os.path.join(out_dir, "manifest.json"), manifest)
    _write_csv(os.path.join(out_dir, "summary.csv"), [_compact(s) for s in summaries])

    lines = [
        "# Oracle upper bound (extension)", "",
        f"Run at `{manifest['started_at']}`; git `{manifest['git_commit']}`; "
        f"tracked dirty `{str(manifest['git_tracked_dirty']).lower()}`.", "",
        "The oracle reads the true future arrival trace over the startup-delay horizon. "
        "It uses the same simulation, energy model, replica bounds (1-10), and SLA margin. "
        "It is an **information upper bound**, not a deployable autoscaler, and it is not "
        "part of the confirmatory five-strategy comparison.", "",
        "All energy is modelled, not measured.", "",
        "| Workload | Strategy | E/served J | E/offered J | Drop | SLA | Replica-h | P95 ms |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for workload in exp["workloads"]:
        for strategy in strategies:
            subset = [s for s in summaries if s["workload"] == workload and s["strategy"] == strategy]
            def m(metric):
                value = _mean([s.get(metric) for s in subset])
                return "n/a" if value is None else f"{value:.4f}"
            lines.append(
                f"| {workload} | {strategy} | {m('energy_per_served_request_j')} | "
                f"{m('energy_per_offered_request_j')} | {m('drop_rate')} | "
                f"{m('sla_violation_rate')} | {m('replica_hours')} | {m('p95_latency_ms')} |"
            )
    lines += ["", "## Interpretation", "",
              "The oracle is useful as a bound on what better workload information could buy. "
              "It is not evidence that any online controller can achieve the same result. "
              "Its extra scaling activity and energy cost are reported rather than hidden.", ""]
    with open(os.path.join(out_dir, "ORACLE.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return {"name": "oracle", "n_runs": len(summaries), "dir": out_dir}


def run_startup_sweep() -> Dict[str, Any]:
    out_dir = os.path.join(EXT_ROOT, "startup_sweep")
    os.makedirs(out_dir, exist_ok=True)
    base = load_configs()
    exp = base["experiment"]
    delays = [5, 10, 20]
    strategies = ["eaes", "forecasting_eaes"]
    rows: List[Dict[str, Any]] = []
    for delay in delays:
        configs = copy.deepcopy(base)
        configs["simulation"]["startup_delay_s"] = int(delay)
        summaries = run_matrix(configs, exp["workloads"], exp["seeds"], strategies, exp["trace_dir"])
        for summary in summaries:
            summary["startup_delay_s"] = int(delay)
            rows.append(summary)
    manifest = _manifest(
        "startup_sweep", base, exp["seeds"], strategies,
        "Startup-delay sweep at 5, 10, and 20 s. Extension only.",
    )
    manifest["startup_delays_s"] = delays
    manifest["n_runs"] = len(rows)
    atomic_write_json(os.path.join(out_dir, "summary.json"), rows)
    atomic_write_json(os.path.join(out_dir, "manifest.json"), manifest)
    _write_csv(os.path.join(out_dir, "summary.csv"), rows)

    lines = [
        "# Startup-delay sweep (extension)", "",
        f"Startup delays: {', '.join(str(d) for d in delays)} s. "
        "Every run uses the same traces, seeds, replica bounds, and energy model.", "",
        "| Delay s | Workload | EAES E/served | Forecast E/served | EAES drop | Forecast drop | EAES SLA | Forecast SLA | Forecast - EAES SLA |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for delay in delays:
        for workload in exp["workloads"]:
            def mean_for(strategy, metric):
                subset = [r for r in rows if r["startup_delay_s"] == delay and r["workload"] == workload and r["strategy"] == strategy]
                return _mean([r.get(metric) for r in subset])
            e_es = mean_for("eaes", "energy_per_served_request_j")
            f_es = mean_for("forecasting_eaes", "energy_per_served_request_j")
            e_drop = mean_for("eaes", "drop_rate")
            f_drop = mean_for("forecasting_eaes", "drop_rate")
            e_sla = mean_for("eaes", "sla_violation_rate")
            f_sla = mean_for("forecasting_eaes", "sla_violation_rate")
            def fmt(v):
                return "n/a" if v is None else f"{v:.4f}"
            delta = None if e_sla is None or f_sla is None else f_sla - e_sla
            lines.append(
                f"| {delay} | {workload} | {fmt(e_es)} | {fmt(f_es)} | {fmt(e_drop)} | "
                f"{fmt(f_drop)} | {fmt(e_sla)} | {fmt(f_sla)} | {fmt(delta)} |"
            )
    lines += ["", "## Where forecasting changes the outcome", ""]
    for delay in delays:
        for workload in exp["workloads"]:
            def mean_for(strategy, metric):
                subset = [r for r in rows if r["startup_delay_s"] == delay and r["workload"] == workload and r["strategy"] == strategy]
                return _mean([r.get(metric) for r in subset])
            e_sla = mean_for("eaes", "sla_violation_rate")
            f_sla = mean_for("forecasting_eaes", "sla_violation_rate")
            e_es = mean_for("eaes", "energy_per_served_request_j")
            f_es = mean_for("forecasting_eaes", "energy_per_served_request_j")
            if None in (e_sla, f_sla, e_es, f_es):
                continue
            if abs(f_sla - e_sla) > 1e-12 or abs(f_es - e_es) > 1e-9:
                verdict = "improves SLA" if f_sla < e_sla else ("worsens SLA" if f_sla > e_sla else "same SLA")
                lines.append(
                    f"- {delay} s / {workload}: forecasting {verdict}; energy per served changes "
                    f"from {e_es:.4f} to {f_es:.4f} J."
                )
    lines.append("")
    with open(os.path.join(out_dir, "STARTUP_SWEEP.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return {"name": "startup_sweep", "n_runs": len(rows), "dir": out_dir}


def run_seed30() -> Dict[str, Any]:
    out_dir = os.path.join(EXT_ROOT, "seed30")
    os.makedirs(out_dir, exist_ok=True)
    configs = load_configs()
    configs["experiment"]["seeds"] = list(range(11, 31))
    configs["experiment"]["trace_dir"] = os.path.join("traces", "extension_seed30")
    exp = configs["experiment"]
    summaries = run_matrix(
        configs, exp["workloads"], exp["seeds"], exp["strategies"], exp["trace_dir"]
    )
    manifest = _manifest(
        "seed30", configs, exp["seeds"], exp["strategies"],
        "Seeds 11-30, all six workloads and five confirmatory strategies. Extension only; "
        "combined with the confirmatory seeds 1-10 this gives 30 seeds.",
    )
    manifest["n_runs"] = len(summaries)
    manifest["combined_with_confirmatory_seeds"] = list(range(1, 11))
    atomic_write_json(os.path.join(out_dir, "summary.json"), summaries)
    atomic_write_json(os.path.join(out_dir, "manifest.json"), manifest)
    _write_csv(os.path.join(out_dir, "summary.csv"), [_compact(s) for s in summaries])

    # Analysis of this extension only.
    fake_manifest = {
        "run_id": "v3_extension_seed30",
        "workloads": exp["workloads"],
        "seeds": exp["seeds"],
        "strategies": exp["strategies"],
        "execution_mode": "simulation",
        "energy_scenario": configs["energy"]["default_scenario"],
        "git_commit": manifest["git_commit"],
        "git_tracked_dirty": manifest["git_tracked_dirty"],
    }
    desc = descriptive_rows(summaries, exp["workloads"])
    paired = paired_rows(summaries, exp["workloads"])
    _write_csv(os.path.join(out_dir, "descriptive.csv"), desc)
    _write_csv(os.path.join(out_dir, "paired.csv"), paired)

    lines = [
        "# 30-seed extension (seeds 11-30)", "",
        "This is an **extension**, not the confirmatory result. It uses seeds 11-30 with "
        "the same six workloads and five strategies. Combined with the confirmatory "
        "seeds 1-10, the project has 30 independent traces per workload.", "",
        "| Workload | Strategy | E/served J mean [95% CI] | Drop mean | SLA mean | Replica-h mean |",
        "|---|---|---|---|---|---|",
    ]
    for workload in exp["workloads"]:
        for strategy in exp["strategies"]:
            subset = [s for s in summaries if s["workload"] == workload and s["strategy"] == strategy]
            def mean_ci(metric):
                vals = [float(s[metric]) for s in subset if isinstance(s.get(metric), (int, float))]
                if not vals:
                    return "n/a", None
                mean = statistics.mean(vals)
                if len(vals) < 2:
                    return f"{mean:.4f}", mean
                import random
                rng = random.Random(12345)
                means = []
                for _ in range(2000):
                    means.append(sum(vals[rng.randrange(len(vals))] for _ in range(len(vals))) / len(vals))
                means.sort()
                return f"{mean:.4f} [{means[int(.025*(len(means)-1))]:.4f}, {means[int(.975*(len(means)-1))]:.4f}]", mean
            es, _ = mean_ci("energy_per_served_request_j")
            drop, _ = mean_ci("drop_rate")
            sla, _ = mean_ci("sla_violation_rate")
            rh, _ = mean_ci("replica_hours")
            lines.append(f"| {workload} | {strategy} | {es} | {drop} | {sla} | {rh} |")
    lines += ["", "## Paired EAES comparisons (extension)", "",
              "| Workload | Baseline | E/served median diff [95% CI] | Holm p |",
              "|---|---|---|---|"]
    for workload in exp["workloads"]:
        for baseline in ("cpu_threshold", "hpa_formula"):
            row = [
                p for p in paired
                if p["workload"] == workload and p["strategy"] == "eaes"
                and p["baseline"] == baseline
                and p["metric"] == "energy_per_served_request_j"
            ][0]
            ci = "n/a" if row.get("median_diff") is None else (
                f"{row['median_diff']:.4f} [{row['ci_low']:.4f}, {row['ci_high']:.4f}]"
            )
            p = "not testable" if row.get("p_holm") is None else f"{row['p_holm']:.4g}"
            lines.append(f"| {workload} | {baseline} | {ci} | {p} |")
    lines += ["", "The 30-seed extension is reported separately so it cannot be mistaken for the "
              "pre-specified 10-seed confirmatory analysis. Directional agreement is discussed in "
              "`docs/EXTENSIONS.md`.", ""]
    with open(os.path.join(out_dir, "RESULTS_30SEED.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return {"name": "seed30", "n_runs": len(summaries), "dir": out_dir}


def main() -> int:
    os.makedirs(EXT_ROOT, exist_ok=True)
    results = [run_oracle(), run_startup_sweep(), run_seed30()]
    for result in results:
        print(f"{result['name']}: {result['n_runs']} runs -> {result['dir']}")
    summary = {
        "extensions": results,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "confirmatory_run": "v3_paired_20261025T220942Z",
        "note": "Extensions are exploratory and never replace the confirmatory results.",
    }
    atomic_write_json(os.path.join(EXT_ROOT, "manifest.json"), summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

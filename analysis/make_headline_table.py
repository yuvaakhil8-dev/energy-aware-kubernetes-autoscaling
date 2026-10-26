#!/usr/bin/env python3
"""Generate the headline tables and RESULTS.md from the confirmatory run.

Design rules enforced here:

* The experimental unit is a run (one workload, one seed, one strategy).
* Ticks are never treated as independent observations.
* Seeds are paired within a workload.
* A missing or zero-denominator metric stays missing; it is not replaced.
* Energy per served request is always reported beside energy per offered
  request and the drop rate.

All tables are written from the summary.json of the confirmatory run.  The raw
JSONL logs are checked for presence, but this script does not re-derive metrics
from ticks.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import random
import statistics
import sys
from typing import Any, Dict, Iterable, List, Sequence, Tuple

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from analysis.analyze import (  # noqa: E402
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    _fmt,
    _load_run,
    _stable_seed,
    cliffs_delta,
    holm_adjust,
    wilcoxon_signed_rank,
)

STRATEGIES = ["static", "cpu_threshold", "hpa_formula", "eaes", "forecasting_eaes"]
BASELINES = ["cpu_threshold", "hpa_formula", "eaes"]
METRICS: List[Tuple[str, str]] = [
    ("energy_per_served_request_j", "Estimated energy / served request (J)"),
    ("energy_per_offered_request_j", "Estimated energy / offered request (J)"),
    ("drop_rate", "Request drop rate"),
    ("sla_violation_rate", "SLA violation rate"),
    ("replica_hours", "Replica-hours"),
    ("p95_latency_ms", "P95 latency (ms)"),
    ("scaling_events", "Scaling events"),
    ("oscillations", "Oscillation count"),
]
PRIMARY = {
    "energy_per_served_request_j",
    "energy_per_offered_request_j",
    "drop_rate",
    "sla_violation_rate",
}


def _latest_run() -> str:
    pointer = os.path.join(APP_DIR, "results", "latest_run.json")
    if os.path.exists(pointer):
        with open(pointer, encoding="utf-8") as fh:
            payload = json.load(fh)
        candidate = os.path.join(APP_DIR, payload["run_dir"])
        if os.path.isdir(candidate):
            return candidate
    runs = sorted(glob.glob(os.path.join(APP_DIR, "results", "runs", "*")))
    if not runs:
        raise FileNotFoundError("no experiment run found; run python -m experiments.run_v3")
    return runs[-1]


def bootstrap_median_ci(
    values: Sequence[float],
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> Tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return float(values[0]), float(values[0])
    rng = random.Random(seed)
    n = len(values)
    medians = []
    for _ in range(resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(statistics.median(sample))
    medians.sort()
    return medians[int(0.025 * (len(medians) - 1))], medians[int(0.975 * (len(medians) - 1))]


def _values(summaries: Sequence[Dict[str, Any]], workload: str, strategy: str, metric: str) -> List[float]:
    values = []
    for row in summaries:
        if row.get("workload") != workload or row.get("strategy") != strategy:
            continue
        value = row.get(metric)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            values.append(float(value))
    return values


def descriptive_rows(summaries: Sequence[Dict[str, Any]], workloads: Sequence[str]) -> List[Dict[str, Any]]:
    rows = []
    for workload in workloads:
        for strategy in STRATEGIES:
            for metric, label in METRICS:
                values = _values(summaries, workload, strategy, metric)
                if not values:
                    rows.append(
                        {
                            "workload": workload,
                            "strategy": strategy,
                            "metric": metric,
                            "label": label,
                            "n": 0,
                            "missing": len([r for r in summaries if r.get("workload") == workload and r.get("strategy") == strategy]),
                            "mean": None,
                            "median": None,
                            "sd": None,
                            "ci_low": None,
                            "ci_high": None,
                            "median_ci_low": None,
                            "median_ci_high": None,
                        }
                    )
                    continue
                mean_lo, mean_hi = _mean_ci(values, _stable_seed(workload, strategy, metric, "mean"))
                med_lo, med_hi = bootstrap_median_ci(values, _stable_seed(workload, strategy, metric, "median"))
                rows.append(
                    {
                        "workload": workload,
                        "strategy": strategy,
                        "metric": metric,
                        "label": label,
                        "n": len(values),
                        "missing": len([r for r in summaries if r.get("workload") == workload and r.get("strategy") == strategy]) - len(values),
                        "mean": statistics.mean(values),
                        "median": statistics.median(values),
                        "sd": statistics.stdev(values) if len(values) > 1 else 0.0,
                        "ci_low": mean_lo,
                        "ci_high": mean_hi,
                        "median_ci_low": med_lo,
                        "median_ci_high": med_hi,
                    }
                )
    return rows


def _mean_ci(values: Sequence[float], seed: int) -> Tuple[float | None, float | None]:
    from analysis.analyze import _bootstrap_ci

    return _bootstrap_ci(values, seed=seed)


def paired_rows(summaries: Sequence[Dict[str, Any]], workloads: Sequence[str]) -> List[Dict[str, Any]]:
    by_key = {(r["workload"], r["strategy"], int(r["seed"])): r for r in summaries}
    out: List[Dict[str, Any]] = []
    for workload in workloads:
        seeds = sorted({int(r["seed"]) for r in summaries if r.get("workload") == workload})
        for baseline in BASELINES:
            if baseline == "eaes":
                comparisons = ["forecasting_eaes"]
            else:
                comparisons = [s for s in STRATEGIES if s != baseline]
            for strategy in comparisons:
                for metric, label in METRICS:
                    diffs: List[float] = []
                    a_vals: List[float] = []
                    b_vals: List[float] = []
                    for seed in seeds:
                        a = by_key.get((workload, strategy, seed))
                        b = by_key.get((workload, baseline, seed))
                        if not a or not b:
                            continue
                        av = a.get(metric)
                        bv = b.get(metric)
                        if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
                            if math.isfinite(float(av)) and math.isfinite(float(bv)):
                                a_vals.append(float(av))
                                b_vals.append(float(bv))
                                diffs.append(float(av) - float(bv))
                    if not diffs:
                        out.append(
                            {
                                "workload": workload,
                                "strategy": strategy,
                                "baseline": baseline,
                                "metric": metric,
                                "label": label,
                                "n_pairs": 0,
                                "median_diff": None,
                                "mean_diff": None,
                                "ci_low": None,
                                "ci_high": None,
                                "p_value": None,
                                "p_holm": None,
                                "cliffs_delta": None,
                                "note": "no_pairs",
                            }
                        )
                        continue
                    rec = {
                        "workload": workload,
                        "strategy": strategy,
                        "baseline": baseline,
                        "metric": metric,
                        "label": label,
                        "n_pairs": len(diffs),
                        "median_diff": statistics.median(diffs),
                        "mean_diff": statistics.mean(diffs),
                        "ci_low": None,
                        "ci_high": None,
                        "p_value": None,
                        "p_holm": None,
                        "cliffs_delta": cliffs_delta(a_vals, b_vals),
                        "note": "ok",
                    }
                    # Bootstrap the median paired difference, the headline effect.
                    rec["ci_low"], rec["ci_high"] = bootstrap_median_ci(
                        diffs, _stable_seed(workload, strategy, baseline, metric)
                    )
                    test = wilcoxon_signed_rank(diffs)
                    rec["p_value"] = test["p_value"]
                    rec["wilcoxon_stat"] = test["statistic"]
                    rec["test_note"] = test["note"]
                    out.append(rec)
    # Holm within each workload x baseline family, over every comparison in it.
    groups: Dict[Tuple[str, str], List[int]] = {}
    for i, row in enumerate(out):
        groups.setdefault((row["workload"], row["baseline"]), []).append(i)
    for indices in groups.values():
        adjusted = holm_adjust([out[i]["p_value"] for i in indices])
        for i, p_adj in zip(indices, adjusted):
            out[i]["p_holm"] = p_adj
    return out


def _write_csv(path: str, rows: Sequence[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write("")
        return
    fieldnames: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _mean_cell(row: Dict[str, Any] | None) -> str:
    if not row or row.get("mean") is None:
        return "n/a"
    return f"{_fmt(row['mean'])} [{_fmt(row['ci_low'])}, {_fmt(row['ci_high'])}]"


def _median_cell(row: Dict[str, Any] | None) -> str:
    if not row or row.get("median") is None:
        return "n/a"
    if row.get("median_ci_low") is None:
        return f"{_fmt(row['median'])}"
    return f"{_fmt(row['median'])} [{_fmt(row['median_ci_low'])}, {_fmt(row['median_ci_high'])}]"


def _paired_cell(row: Dict[str, Any] | None) -> str:
    if not row or row.get("median_diff") is None:
        return "n/a"
    return f"{_fmt(row['median_diff'])} [{_fmt(row['ci_low'])}, {_fmt(row['ci_high'])}]"


def _p_cell(row: Dict[str, Any] | None) -> str:
    if not row or row.get("p_holm") is None:
        return "not testable"
    return f"{row['p_holm']:.4g}"


def _index(rows: Iterable[Dict[str, Any]], key_fields: Sequence[str]) -> Dict[Tuple[Any, ...], Dict[str, Any]]:
    return {tuple(row.get(f) for f in key_fields): row for row in rows}


def build_markdown(
    manifest: Dict[str, Any],
    summaries: Sequence[Dict[str, Any]],
    descriptive: Sequence[Dict[str, Any]],
    paired: Sequence[Dict[str, Any]],
) -> str:
    workloads = manifest["workloads"]
    run_id = manifest["run_id"]
    desc = _index(descriptive, ("workload", "strategy", "metric"))
    pair = _index(paired, ("workload", "strategy", "baseline", "metric"))
    lines: List[str] = []
    lines.append("# Results")
    lines.append("")
    lines.append("Generated by `python -m analysis.make_headline_table` from the confirmatory run. "
                 "Do not edit this file by hand.")
    lines.append("")
    lines.append(f"- Run: `{run_id}`")
    lines.append(f"- Execution mode: **{manifest['execution_mode']}**")
    lines.append(f"- Energy scenario: **{manifest['energy_scenario']}**")
    lines.append(f"- Run git commit: `{manifest['git_commit']}`")
    lines.append(f"- Tracked tree dirty at run: `{str(manifest['git_tracked_dirty']).lower()}`")
    lines.append(f"- Design: {len(workloads)} workloads x {len(manifest['seeds'])} seeds x {len(manifest['strategies'])} strategies = {len(summaries)} paired runs")
    lines.append(f"- Duration: 300 simulated seconds per run, 5 s control interval, 30 s warm-up excluded")
    lines.append(f"- Statistics: {BOOTSTRAP_RESAMPLES:,}-resample bootstrap, paired by seed, Holm correction")
    lines.append("")
    lines.append("> **Energy is estimated, not measured.** Every energy value is produced by the documented "
                 "node-level power model. No power meter or Kepler measurement exists for these runs. "
                 "The real-cluster section is separate and its energy is also modelled.")
    lines.append("")
    lines.append("## How to read the headline tables")
    lines.append("")
    lines.append("The experimental unit is one run (workload, seed, strategy). Tick-level observations are "
                 "aggregated inside a run first; ticks are not treated as independent samples. Missing values "
                 "(including energy per served request when zero requests were served) are reported as `n/a` "
                 "and are never replaced with an artificial denominator. Energy per served request is always "
                 "shown next to energy per offered request and the drop rate, because a controller can look "
                 "efficient merely by serving less traffic.")
    lines.append("")
    lines.append("Confidence intervals are percentile bootstrap intervals over runs. Paired differences are "
                 "strategy minus baseline; a negative difference is favourable only for metrics where lower is "
                 "better (all metrics in this table). The Wilcoxon signed-rank test uses independent seeds as "
                 "blocks and is Holm-adjusted within each workload x baseline family.")
    lines.append("")

    for metric, label in METRICS:
        lines.append(f"### {label}")
        lines.append("")
        lines.append("| Workload | Strategy | n | Mean [95% CI] | Median [95% CI] | Missing |")
        lines.append("|---|---|---|---|---|---|")
        for workload in workloads:
            for strategy in STRATEGIES:
                row = desc.get((workload, strategy, metric))
                lines.append(
                    f"| {workload} | {strategy} | {row['n'] if row else 0} | {_mean_cell(row)} | "
                    f"{_median_cell(row)} | {row['missing'] if row else 'n/a'} |"
                )
        lines.append("")

    lines.append("## Paired comparisons")
    lines.append("")
    lines.append("Cell values are the **median paired difference [95% bootstrap CI]** with the "
                 "**Holm-adjusted Wilcoxon p-value**. Strategy minus baseline; negative favours the strategy. "
                 "The complete machine-readable table, including Cliff's delta and every strategy, is "
                 "`results/tables/paired_headline.csv`.")
    lines.append("")
    for baseline, baseline_label in (("cpu_threshold", "CPU threshold"), ("hpa_formula", "HPA formula")):
        lines.append(f"### EAES vs {baseline_label}")
        lines.append("")
        lines.append("| Workload | Metric | Median diff [95% CI] | Holm p | Cliff's d |")
        lines.append("|---|---|---|---|---|")
        for workload in workloads:
            for metric, label in METRICS:
                row = pair.get((workload, "eaes", baseline, metric))
                lines.append(
                    f"| {workload} | {label} | {_paired_cell(row)} | {_p_cell(row)} | "
                    f"{_fmt(row.get('cliffs_delta')) if row and row.get('cliffs_delta') is not None else 'n/a'} |"
                )
        lines.append("")

    lines.append("### Forecasting EAES vs reactive EAES")
    lines.append("")
    lines.append("| Workload | Metric | Median diff [95% CI] | Holm p | Cliff's d |")
    lines.append("|---|---|---|---|---|")
    for workload in workloads:
        for metric, label in METRICS:
            row = pair.get((workload, "forecasting_eaes", "eaes", metric))
            lines.append(
                f"| {workload} | {label} | {_paired_cell(row)} | {_p_cell(row)} | "
                f"{_fmt(row.get('cliffs_delta')) if row and row.get('cliffs_delta') is not None else 'n/a'} |"
            )
    lines.append("")

    # Findings constructed only from the generated tables.
    lines.append("## Findings supported by these tables")
    lines.append("")
    findings: List[str] = []
    for workload in workloads:
        e = pair.get((workload, "eaes", "hpa_formula", "energy_per_served_request_j"))
        if e and e.get("median_diff") is not None:
            direction = "lower" if e["median_diff"] < 0 else ("higher" if e["median_diff"] > 0 else "equal")
            sig = "Holm-significant" if e.get("p_holm") is not None and e["p_holm"] < 0.05 else "not Holm-significant"
            findings.append(
                f"{workload}: EAES estimated energy per served request is {direction} than the HPA formula "
                f"(median paired difference {_fmt(e['median_diff'])} J, 95% CI {_fmt(e['ci_low'])} to "
                f"{_fmt(e['ci_high'])}; {sig})."
            )
    for workload in workloads:
        s = desc.get((workload, "static", "drop_rate"))
        if s and s.get("mean") is not None and s["mean"] > 0.01:
            findings.append(
                f"{workload}: static replicas drop {s['mean'] * 100:.2f}% of offered requests "
                f"(95% CI {s['ci_low'] * 100:.2f}% to {s['ci_high'] * 100:.2f}%). Its low energy per "
                f"served request must be read against this loss."
            )
    for workload in workloads:
        e = desc.get((workload, "eaes", "sla_violation_rate"))
        h = desc.get((workload, "hpa_formula", "sla_violation_rate"))
        if e and h and e.get("mean") is not None and h.get("mean") is not None and e["mean"] > 0:
            findings.append(
                f"{workload}: reactive EAES has an SLA violation rate of {e['mean']:.4f} versus "
                f"{h['mean']:.4f} for the HPA formula; the controller's internal safety margin is not a "
                f"guarantee of zero outcome violations."
            )
    for workload in workloads:
        f = desc.get((workload, "forecasting_eaes", "sla_violation_rate"))
        e = desc.get((workload, "eaes", "sla_violation_rate"))
        if f and e and f.get("mean") is not None and e.get("mean") is not None:
            if f["mean"] < e["mean"]:
                findings.append(
                    f"{workload}: forecasting reduces the mean SLA violation rate from {e['mean']:.4f} "
                    f"to {f['mean']:.4f}, at a mean energy cost of "
                    f"{_fmt(desc[(workload, 'forecasting_eaes', 'energy_per_served_request_j')]['mean'])} J "
                    f"per served request versus "
                    f"{_fmt(desc[(workload, 'eaes', 'energy_per_served_request_j')]['mean'])} J."
                )
    if findings:
        lines.extend(f"- {item}" for item in findings)
    else:
        lines.append("- No findings could be derived from the available tables.")
    lines.append("")
    lines.append("## Forecast accuracy")
    lines.append("")
    lines.append("Held-out Holt and EWMA accuracy is in `results/tables/forecast_accuracy.md`. "
                 "Forecasting is an input to the forecasting EAES controller, not evidence that the "
                 "controller is universally better; see the paired table above and `docs/EXTENSIONS.md`.")
    lines.append("")
    lines.append("## Energy sensitivity")
    lines.append("")
    lines.append("Low, nominal, and high power configurations plus PUE 1.0-1.6 are in "
                 "`results/extension/energy_sensitivity/ENERGY_SENSITIVITY.md`. The nominal recomputation "
                 "is checked against the confirmatory energy in the same document.")
    lines.append("")
    lines.append("## Extensions (not confirmatory)")
    lines.append("")
    lines.append("Oracle upper bound, startup-delay sweep, 30-seed extension, HPA replay, and clean-checkout "
                 "reproduction are labelled extensions under `results/extension/` and summarised in "
                 "`docs/EXTENSIONS.md`. They never replace the confirmatory tables above.")
    lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    lines.append("- Simulation results do not establish production behaviour.")
    lines.append("- The `hpa_formula` baseline is a simulated replica formula, not the native Kubernetes HPA controller.")
    lines.append("- `cpu_threshold` is the legacy 80/30 rule, not HPA.")
    lines.append("- The static strategy's apparent efficiency can be an artefact of unmet demand.")
    lines.append("- Statistical significance is a property of this simulated design, not a deployment guarantee.")
    lines.append("")
    return "\n".join(lines)


def generate(run_dir: str | None = None) -> Dict[str, Any]:
    run_dir = run_dir or _latest_run()
    manifest, summaries = _load_run(run_dir)
    workloads = manifest["workloads"]
    tables_dir = os.path.join(APP_DIR, "results", "tables")
    os.makedirs(tables_dir, exist_ok=True)

    descriptive = descriptive_rows(summaries, workloads)
    paired = paired_rows(summaries, workloads)
    _write_csv(os.path.join(tables_dir, "headline.csv"), descriptive)
    _write_csv(os.path.join(tables_dir, "paired_headline.csv"), paired)

    # Headline markdown: descriptive table + compact paired tables.
    md: List[str] = ["# Headline results", ""]
    md.append(f"Run `{manifest['run_id']}`; energy is modelled, not measured.")
    md.append("")
    desc = _index(descriptive, ("workload", "strategy", "metric"))
    for workload in workloads:
        md.append(f"## {workload}")
        md.append("")
        md.append("| Strategy | E/served J | E/offered J | Drop | SLA | Replica-h | P95 ms | Scales | Osc. |")
        md.append("|---|---|---|---|---|---|---|---|---|")
        for strategy in STRATEGIES:
            cells = []
            for metric, _ in METRICS:
                row = desc.get((workload, strategy, metric))
                if metric in ("drop_rate", "sla_violation_rate"):
                    cells.append(f"{row['mean']:.4f}" if row and row.get("mean") is not None else "n/a")
                elif metric == "replica_hours":
                    cells.append(f"{row['mean']:.3f}" if row and row.get("mean") is not None else "n/a")
                elif metric in ("scaling_events", "oscillations"):
                    cells.append(f"{row['mean']:.1f}" if row and row.get("mean") is not None else "n/a")
                else:
                    cells.append(f"{row['mean']:.4f}" if row and row.get("mean") is not None else "n/a")
            md.append(f"| {strategy} | " + " | ".join(cells) + " |")
        md.append("")
    md.append("Full uncertainty intervals and paired tests: `results/RESULTS.md`, "
              "`results/tables/headline.csv`, `results/tables/paired_headline.csv`.")
    with open(os.path.join(tables_dir, "headline.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")

    results_md = build_markdown(manifest, summaries, descriptive, paired)
    with open(os.path.join(APP_DIR, "results", "RESULTS.md"), "w", encoding="utf-8") as fh:
        fh.write(results_md)

    return {
        "run_id": manifest["run_id"],
        "run_dir": run_dir,
        "n_summaries": len(summaries),
        "headline_rows": len(descriptive),
        "paired_rows": len(paired),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", default=None)
    args = parser.parse_args()
    result = generate(args.run_dir)
    print(f"headline generated from run: {result['run_id']}")
    print(f"run dir: {result['run_dir']}")
    print(f"headline rows: {result['headline_rows']}; paired rows: {result['paired_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

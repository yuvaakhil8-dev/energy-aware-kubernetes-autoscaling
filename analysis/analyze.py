#!/usr/bin/env python3
"""Statistical analysis of the paired v3 simulation.

The analysis is deliberately dependency-light (stdlib only) so that the tables
can be regenerated on the target Windows/Python installation.  All tables are
derived from the run's summary and raw tick logs; nothing is hand-edited.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence, Tuple

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from eaes.config import atomic_write_json, git_commit, load_configs
from eaes.workload import load_or_create_trace
from eaes.forecast import evaluate_forecast

STRATEGIES = ["static", "cpu_threshold", "hpa_formula", "eaes", "forecasting_eaes"]
METRICS = [
    ("energy_per_served_request_j", "lower", "E/served (J)"),
    ("sla_violation_rate", "lower", "SLA violation rate"),
    ("replica_hours", "lower", "Replica-hours"),
    ("drop_rate", "lower", "Drop rate"),
    ("energy_per_offered_request_j", "lower", "E/offered (J)"),
    ("p95_latency_ms", "lower", "P95 latency (ms)"),
    ("scaling_events", "lower", "Scaling events"),
    ("oscillations", "lower", "Oscillations"),
]
PRIMARY = {
    "energy_per_served_request_j",
    "sla_violation_rate",
    "replica_hours",
    "drop_rate",
}
ALPHA = 0.05
BOOTSTRAP_SEED = 12345
BOOTSTRAP_RESAMPLES = 5000
NEMENYI_Q05 = {2: 1.960, 3: 2.343, 4: 2.569, 5: 2.728, 6: 2.850, 7: 2.949, 8: 3.031}


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


def _load_run(run_dir: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    with open(os.path.join(run_dir, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    with open(os.path.join(run_dir, "summary.json"), encoding="utf-8") as fh:
        summaries = json.load(fh)
    return manifest, summaries


def _values(summaries: Sequence[Dict[str, Any]], workload: str, strategy: str, metric: str) -> List[float]:
    out = []
    for row in summaries:
        if row["workload"] == workload and row["strategy"] == strategy:
            value = row.get(metric)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                out.append(float(value))
    return out


def _stable_seed(*parts: Any) -> int:
    payload = "|".join(str(p) for p in parts).encode("utf-8")
    return BOOTSTRAP_SEED + int(hashlib.sha256(payload).hexdigest()[:8], 16) % 100000


def _bootstrap_ci(values: Sequence[float], seed: int = BOOTSTRAP_SEED, resamples: int = BOOTSTRAP_RESAMPLES) -> Tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return float(values[0]), float(values[0])
    rng = random.Random(seed)
    means = []
    n = len(values)
    for _ in range(resamples):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[int(0.025 * (len(means) - 1))]
    hi = means[int(0.975 * (len(means) - 1))]
    return lo, hi


def _ranks(values: Sequence[float]) -> List[float]:
    """Average ranks (1 = smallest)."""
    sorted_pairs = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(sorted_pairs):
        j = i
        while j + 1 < len(sorted_pairs) and sorted_pairs[j + 1][1] == sorted_pairs[i][1]:
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[sorted_pairs[k][0]] = avg
        i = j + 1
    return ranks


def _tie_term(values: Sequence[float]) -> float:
    counts: Dict[float, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return sum(c ** 3 - c for c in counts.values() if c > 1)


def wilcoxon_signed_rank(diffs: Sequence[float]) -> Dict[str, Any]:
    nonzero = [d for d in diffs if abs(d) > 1e-12]
    n = len(nonzero)
    if n < 5:
        return {"n": n, "statistic": None, "p_value": None, "note": "not_testable"}
    ranks = _ranks([abs(d) for d in nonzero])
    w_plus = sum(r for r, d in zip(ranks, nonzero) if d > 0)
    mean = n * (n + 1) / 4.0
    var = n * (n + 1) * (2 * n + 1) / 24.0 - _tie_term([abs(d) for d in nonzero]) / 48.0
    if var <= 0:
        return {"n": n, "statistic": w_plus, "p_value": 1.0, "note": "zero_variance"}
    z = (w_plus - mean) / math.sqrt(var)
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return {"n": n, "statistic": w_plus, "z": z, "p_value": min(1.0, p), "note": "normal_approx"}


def cliffs_delta(x: Sequence[float], y: Sequence[float]) -> float | None:
    if not x or not y:
        return None
    gt = sum(1 for a in x for b in y if a > b)
    lt = sum(1 for a in x for b in y if a < b)
    return (gt - lt) / (len(x) * len(y))


def holm_adjust(p_values: Sequence[float | None]) -> List[float | None]:
    indexed = [(i, p) for i, p in enumerate(p_values) if p is not None]
    indexed.sort(key=lambda x: x[1])
    m = len(indexed)
    adjusted: List[float | None] = [None] * len(p_values)
    running = 0.0
    for rank, (idx, p) in enumerate(indexed):
        value = min(1.0, p * (m - rank))
        running = max(running, value)
        adjusted[idx] = running
    return adjusted


def _chi2_sf_df4(x: float) -> float:
    """Survival function for chi-square with 4 degrees of freedom (exact)."""
    if x <= 0:
        return 1.0
    return math.exp(-x / 2.0) * (1.0 + x / 2.0)


def friedman_test(rows: Sequence[Dict[str, Any]], workload: str, metric: str, strategies: Sequence[str]) -> Dict[str, Any]:
    # Build seed x strategy matrix, keeping complete blocks only.
    by_seed: Dict[int, Dict[str, float]] = defaultdict(dict)
    for row in rows:
        if row["workload"] != workload:
            continue
        value = row.get(metric)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            by_seed[int(row["seed"])][row["strategy"]] = float(value)
    blocks = [d for d in by_seed.values() if all(s in d for s in strategies)]
    n = len(blocks)
    k = len(strategies)
    if n < 2 or k < 3:
        return {"workload": workload, "metric": metric, "n_blocks": n, "k": k, "Q": None, "p_value": None, "note": "not_testable"}
    rank_sums = {s: 0.0 for s in strategies}
    tie_sum = 0.0
    for block in blocks:
        vals = [block[s] for s in strategies]
        ranks = _ranks(vals)
        tie_sum += _tie_term(vals)
        for s, r in zip(strategies, ranks):
            rank_sums[s] += r
    q = 12.0 / (n * k * (k + 1)) * sum(v ** 2 for v in rank_sums.values()) - 3 * n * (k + 1)
    correction = 1.0 - tie_sum / (n * (k ** 3 - k)) if n and k > 1 else 1.0
    if correction > 0:
        q = q / correction
    p = _chi2_sf_df4(q) if k == 5 else None
    return {
        "workload": workload,
        "metric": metric,
        "n_blocks": n,
        "k": k,
        "Q": q,
        "p_value": p,
        "note": "chi_square_df4" if k == 5 else "df_not_4",
        "rank_sums": rank_sums,
    }


def nemenyi(rows: Sequence[Dict[str, Any]], workload: str, metric: str, strategies: Sequence[str]) -> List[Dict[str, Any]]:
    fried = friedman_test(rows, workload, metric, strategies)
    if fried.get("Q") is None:
        return []
    n = fried["n_blocks"]
    k = len(strategies)
    q_alpha = NEMENYI_Q05.get(k)
    if q_alpha is None:
        return []
    cd = q_alpha * math.sqrt(k * (k + 1) / (6.0 * n))
    avg_ranks = {s: fried["rank_sums"][s] / n for s in strategies}
    out = []
    for i, a in enumerate(strategies):
        for b in strategies[i + 1:]:
            diff = abs(avg_ranks[a] - avg_ranks[b])
            out.append(
                {
                    "workload": workload,
                    "metric": metric,
                    "strategy_a": a,
                    "strategy_b": b,
                    "mean_rank_a": avg_ranks[a],
                    "mean_rank_b": avg_ranks[b],
                    "rank_diff": diff,
                    "critical_difference": cd,
                    "significant": diff > cd,
                }
            )
    return out


def _descriptive(rows: Sequence[Dict[str, Any]], workloads: Sequence[str]) -> List[Dict[str, Any]]:
    out = []
    for workload in workloads:
        for strategy in STRATEGIES:
            for metric, direction, label in METRICS:
                vals = _values(rows, workload, strategy, metric)
                if not vals:
                    continue
                lo, hi = _bootstrap_ci(vals, seed=_stable_seed(workload, strategy, metric))
                out.append(
                    {
                        "workload": workload,
                        "strategy": strategy,
                        "metric": metric,
                        "label": label,
                        "direction": direction,
                        "n": len(vals),
                        "mean": statistics.mean(vals),
                        "median": statistics.median(vals),
                        "sd": statistics.stdev(vals) if len(vals) > 1 else 0.0,
                        "ci_low": lo,
                        "ci_high": hi,
                    }
                )
    return out


def _paired(rows: Sequence[Dict[str, Any]], workloads: Sequence[str]) -> List[Dict[str, Any]]:
    by_seed: Dict[Tuple[str, str, int], Dict[str, Any]] = {}
    for row in rows:
        by_seed[(row["workload"], row["strategy"], int(row["seed"]))] = row
    out = []
    for workload in workloads:
        for baseline in ("cpu_threshold", "hpa_formula"):
            for strategy in ("eaes", "forecasting_eaes"):
                for metric, direction, label in METRICS:
                    diffs = []
                    a_vals = []
                    b_vals = []
                    for seed in sorted({int(r["seed"]) for r in rows if r["workload"] == workload}):
                        a = by_seed.get((workload, strategy, seed))
                        b = by_seed.get((workload, baseline, seed))
                        if not a or not b:
                            continue
                        av = a.get(metric)
                        bv = b.get(metric)
                        if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
                            a_vals.append(float(av))
                            b_vals.append(float(bv))
                            diffs.append(float(av) - float(bv))
                    if not diffs:
                        continue
                    lo, hi = _bootstrap_ci(diffs, seed=_stable_seed(workload, strategy, baseline, metric))
                    test = wilcoxon_signed_rank(diffs)
                    out.append(
                        {
                            "workload": workload,
                            "metric": metric,
                            "label": label,
                            "strategy": strategy,
                            "baseline": baseline,
                            "n_pairs": len(diffs),
                            "mean_diff": statistics.mean(diffs),
                            "median_diff": statistics.median(diffs),
                            "ci_low": lo,
                            "ci_high": hi,
                            "wilcoxon_stat": test["statistic"],
                            "p_value": test["p_value"],
                            "test_note": test["note"],
                            "cliffs_delta": cliffs_delta(a_vals, b_vals),
                            "primary": metric in PRIMARY,
                        }
                    )
    # Holm within each workload x baseline family (pre-specified).
    groups: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for i, row in enumerate(out):
        groups[(row["workload"], row["baseline"])].append(i)
    for _, indices in groups.items():
        adjusted = holm_adjust([out[i]["p_value"] for i in indices])
        for i, p_adj in zip(indices, adjusted):
            out[i]["p_holm"] = p_adj
    return out


def _forecast_tables(configs: Dict[str, Dict[str, Any]], workloads: Sequence[str], seeds: Sequence[int]) -> List[Dict[str, Any]]:
    exp = configs["experiment"]
    rows = []
    for workload in workloads:
        for seed in seeds:
            trace = load_or_create_trace(
                workload, seed, int(exp["duration_s"]), int(exp["control_interval_s"]),
                os.path.join(APP_DIR, exp["trace_dir"]),
            )
            rates = [t["arrivals"] / float(exp["control_interval_s"]) for t in trace["ticks"]]
            for method, cfg in (("ewma", {"alpha": 0.3}), ("holt", {"alpha": 0.5, "beta": 0.3})):
                result = evaluate_forecast(
                    rates, method=method, cfg=cfg, horizon_steps=2,
                    eval_fraction=float(exp["forecast_eval_fraction"]),
                )
                rows.append(
                    {
                        "workload": workload,
                        "seed": seed,
                        "method": method,
                        "horizon_steps": result["horizon_steps"],
                        "n": result["n"],
                        "mae": result["mae"],
                        "mape_pct": result["mape_pct"],
                    }
                )
    return rows


def _sensitivity(run_dir: str, configs: Dict[str, Dict[str, Any]], summaries: Sequence[Dict[str, Any]], workloads: Sequence[str]) -> Tuple[List[Dict[str, Any]], float]:
    """Recompute energy under power/PUE scenarios from raw tick data."""
    sim = configs["simulation"]
    dt = float(configs["experiment"]["control_interval_s"])
    pods_per_node = int(sim["pods_per_node"])
    pod_cap = float(sim["pod_capacity_rps"])
    energy_cfg = configs["energy"]
    scenarios = energy_cfg["scenarios"]
    pue_values = [float(x) for x in energy_cfg.get("pue_sensitivity", [energy_cfg["pue"]])]
    by_key = {(s["workload"], s["strategy"], int(s["seed"])): s for s in summaries}
    rows = []
    nominal_error = 0.0
    for workload in workloads:
        for strategy in STRATEGIES:
            per_scenario: Dict[Tuple[str, float], Dict[str, float]] = defaultdict(lambda: {"energy": 0.0, "served": 0.0, "offered": 0.0, "seeds": 0.0})
            for seed in sorted({int(s["seed"]) for s in summaries if s["workload"] == workload}):
                raw_path = os.path.join(run_dir, f"{workload}_seed{seed}_{strategy}.jsonl")
                if not os.path.exists(raw_path):
                    continue
                seed_energy = defaultdict(float)
                seed_served = 0.0
                seed_offered = 0.0
                with open(raw_path, encoding="utf-8") as fh:
                    for line in fh:
                        row = json.loads(line)
                        if row.get("warmup"):
                            continue
                        ready = int(row.get("ready_replicas_after", row["ready_replicas"]))
                        served = float(row["served"])
                        offered = float(row["offered"])
                        active = int(row["active_nodes"])
                        if ready > 0 and active > 0:
                            for i in range(active):
                                n_pods = min(pods_per_node, ready - i * pods_per_node)
                                node_served = served * n_pods / ready
                                util = max(0.0, min(1.0, node_served / (pods_per_node * pod_cap * dt)))
                                for scenario_name, spec in scenarios.items():
                                    p_idle = float(spec["p_idle_w"])
                                    p_max = float(spec["p_max_w"])
                                    e = (p_idle + (p_max - p_idle) * util) * dt
                                    for pue in pue_values:
                                        seed_energy[(scenario_name, pue)] += e * pue
                        seed_served += served
                        seed_offered += offered
                # Nominal comparison against recorded energy.
                nominal_spec = scenarios[energy_cfg["default_scenario"]]
                nominal_pue = float(energy_cfg["pue"])
                rec = by_key.get((workload, strategy, seed))
                if rec and rec.get("measurement_energy_j", 0) > 0:
                    err = abs(seed_energy[(energy_cfg["default_scenario"], nominal_pue)] - rec["measurement_energy_j"]) / rec["measurement_energy_j"]
                    nominal_error = max(nominal_error, err)
                for key, total in seed_energy.items():
                    per_scenario[key]["energy"] += total
                    per_scenario[key]["served"] += seed_served
                    per_scenario[key]["offered"] += seed_offered
                    per_scenario[key]["seeds"] += 1
            for (scenario_name, pue), agg in per_scenario.items():
                rows.append(
                    {
                        "scenario": scenario_name,
                        "pue": pue,
                        "workload": workload,
                        "strategy": strategy,
                        "n_seeds": int(agg["seeds"]),
                        "total_energy_j": agg["energy"],
                        "served_requests": agg["served"],
                        "offered_requests": agg["offered"],
                        "energy_per_served_j": (agg["energy"] / agg["served"]) if agg["served"] > 0 else None,
                        "energy_per_offered_j": (agg["energy"] / agg["offered"]) if agg["offered"] > 0 else None,
                    }
                )
    return rows, nominal_error


def _write_csv(path: str, rows: Sequence[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write("")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _md_table(rows: Sequence[Dict[str, Any]], columns: Sequence[Tuple[str, str]]) -> str:
    lines = ["| " + " | ".join(label for _, label in columns) + " |",
             "|" + "|".join("---" for _ in columns) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(row.get(key)) for key, _ in columns) + " |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", default=None)
    args = parser.parse_args()
    run_dir = args.run_dir or _latest_run()
    manifest, summaries = _load_run(run_dir)
    configs = load_configs()
    workloads = manifest["workloads"]
    seeds = manifest["seeds"]
    tables = os.path.join(APP_DIR, "results", "tables")
    os.makedirs(tables, exist_ok=True)

    descriptive = _descriptive(summaries, workloads)
    _write_csv(os.path.join(tables, "descriptive.csv"), descriptive)

    paired = _paired(summaries, workloads)
    _write_csv(os.path.join(tables, "paired.csv"), paired)

    friedman = []
    nemenyi_rows = []
    for workload in workloads:
        for metric, _, _ in METRICS:
            friedman.append(friedman_test(summaries, workload, metric, STRATEGIES))
            nemenyi_rows.extend(nemenyi(summaries, workload, metric, STRATEGIES))
    _write_csv(os.path.join(tables, "friedman.csv"), friedman)
    _write_csv(os.path.join(tables, "nemenyi.csv"), nemenyi_rows)

    forecast_rows = _forecast_tables(configs, workloads, seeds)
    _write_csv(os.path.join(tables, "forecasting.csv"), forecast_rows)

    sensitivity, nominal_error = _sensitivity(run_dir, configs, summaries, workloads)
    _write_csv(os.path.join(tables, "sensitivity.csv"), sensitivity)

    # Markdown summary tables.
    primary_desc = [r for r in descriptive if r["metric"] in PRIMARY]
    with open(os.path.join(tables, "descriptive.md"), "w", encoding="utf-8") as fh:
        fh.write("# Descriptive statistics\n\n")
        fh.write(_md_table(
            [dict(r, mean_ci=f"{_fmt(r['mean'])} [{_fmt(r['ci_low'])}, {_fmt(r['ci_high'])}]") for r in primary_desc],
            [("workload", "Workload"), ("strategy", "Strategy"), ("metric", "Metric"),
             ("n", "n"), ("mean_ci", "Mean [95% CI]"), ("median", "Median")],
        ))
        fh.write("\n")
    with open(os.path.join(tables, "paired.md"), "w", encoding="utf-8") as fh:
        fh.write("# Paired comparisons vs CPU threshold and HPA formula\n\n")
        fh.write("Differences are strategy minus baseline; negative favours the strategy for all listed metrics.\n\n")
        fh.write(_md_table(
            [dict(r, mean_ci=f"{_fmt(r['mean_diff'])} [{_fmt(r['ci_low'])}, {_fmt(r['ci_high'])}]") for r in paired if r["primary"]],
            [("workload", "Workload"), ("strategy", "Strategy"), ("baseline", "Baseline"),
             ("metric", "Metric"), ("n_pairs", "n"), ("mean_ci", "Mean diff [95% CI]"),
             ("p_value", "p"), ("p_holm", "Holm p"), ("cliffs_delta", "Cliff's d")],
        ))
        fh.write("\n")

    # Machine-readable analysis manifest.
    analysis_manifest = {
        "run_id": manifest["run_id"],
        "run_dir": os.path.relpath(run_dir, APP_DIR),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "n_summaries": len(summaries),
        "n_seeds": len(seeds),
        "workloads": workloads,
        "strategies": STRATEGIES,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "alpha": ALPHA,
        "nominal_energy_recompute_max_rel_error": nominal_error,
        "notes": [
            "All energy is modelled, not measured.",
            "Significance describes the simulation only.",
            "Energy per served request is null when no requests were served.",
        ],
    }
    atomic_write_json(os.path.join(APP_DIR, "results", "analysis_manifest.json"), analysis_manifest)

    # The headline report has a single authoritative generator.  Calling it
    # here keeps `python -m analysis.analyze` from silently overwriting the
    # polished RESULTS.md with an older format.
    from analysis.make_headline_table import generate as generate_headline
    headline = generate_headline(run_dir)

    print(f"analyzed run: {manifest['run_id']}")
    print(f"tables: {tables}")
    print(f"nominal recomputation max rel error: {nominal_error:.3e}")
    print(f"paired rows: {len(paired)}; friedman rows: {len(friedman)}; sensitivity rows: {len(sensitivity)}")
    print(f"headline rows: {headline['headline_rows']}; paired headline rows: {headline['paired_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

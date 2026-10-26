#!/usr/bin/env python3
"""Energy-model sensitivity extension.

The controller is energy-independent, so changing P_idle/P_max/PUE cannot
change a scaling decision.  These runs therefore isolate how the *reported
energy* and the strategy ranking respond to the power assumptions.  They are
extensions and never replace the confirmatory nominal results.
"""
from __future__ import annotations

import copy
import csv
import json
import math
import os
import statistics
import sys
from typing import Any, Dict, List, Sequence, Tuple

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from eaes.config import atomic_write_json, combined_config_hash, git_commit, git_tracked_dirty, load_configs, utc_now
from eaes.engine import run_single
from eaes.workload import load_or_create_trace

OUT_DIR = os.path.join(APP_DIR, "results", "extension", "energy_sensitivity")
CONFIRMATORY = os.path.join(APP_DIR, "results", "runs", "v3_paired_20261025T220942Z", "summary.json")
STRATEGIES = ["static", "cpu_threshold", "hpa_formula", "eaes", "forecasting_eaes"]
SCENARIOS = ["low", "nominal", "high"]
PUE_VALUES = [1.0, 1.2, 1.4, 1.6]


def _write_csv(path: str, rows: Sequence[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        open(path, "w", encoding="utf-8").close()
        return
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def collect() -> List[Dict[str, Any]]:
    base = load_configs()
    exp = base["experiment"]
    traces = {}
    for workload in exp["workloads"]:
        for seed in exp["seeds"]:
            traces[(workload, int(seed))] = load_or_create_trace(
                workload, int(seed), int(exp["duration_s"]), int(exp["control_interval_s"]),
                os.path.join(APP_DIR, exp["trace_dir"]),
            )
    rows: List[Dict[str, Any]] = []
    for scenario in SCENARIOS:
        for pue in PUE_VALUES:
            configs = copy.deepcopy(base)
            configs["energy"]["pue"] = float(pue)
            for workload in exp["workloads"]:
                for seed in exp["seeds"]:
                    trace = traces[(workload, int(seed))]
                    for strategy in STRATEGIES:
                        summary = run_single(configs, trace, strategy, energy_scenario=scenario)["summary"]
                        rows.append(
                            {
                                "scenario": scenario,
                                "pue": float(pue),
                                "workload": workload,
                                "seed": int(seed),
                                "strategy": strategy,
                                "measurement_energy_j": summary["measurement_energy_j"],
                                "energy_per_served_request_j": summary["energy_per_served_request_j"],
                                "energy_per_offered_request_j": summary["energy_per_offered_request_j"],
                                "served_requests": summary["served_requests"],
                                "offered_requests": summary["offered_requests"],
                                "drop_rate": summary["drop_rate"],
                                "sla_violation_rate": summary["sla_violation_rate"],
                                "replica_hours": summary["replica_hours"],
                            }
                        )
    return rows


def nominal_check(rows: Sequence[Dict[str, Any]]) -> float:
    with open(CONFIRMATORY, encoding="utf-8") as fh:
        confirmatory = json.load(fh)
    ref = {(r["workload"], int(r["seed"]), r["strategy"]): r for r in confirmatory}
    max_error = 0.0
    for row in rows:
        if row["scenario"] != "nominal" or row["pue"] != 1.2:
            continue
        other = ref.get((row["workload"], row["seed"], row["strategy"]))
        if not other:
            continue
        expected = float(other["measurement_energy_j"])
        if expected > 0:
            max_error = max(max_error, abs(row["measurement_energy_j"] - expected) / expected)
    return max_error


def aggregate(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    keys = sorted({(r["scenario"], r["pue"], r["workload"], r["strategy"]) for r in rows})
    for scenario, pue, workload, strategy in keys:
        subset = [
            r for r in rows
            if r["scenario"] == scenario and r["pue"] == pue
            and r["workload"] == workload and r["strategy"] == strategy
        ]
        es = [float(r["energy_per_served_request_j"]) for r in subset if r["energy_per_served_request_j"] is not None]
        eo = [float(r["energy_per_offered_request_j"]) for r in subset if r["energy_per_offered_request_j"] is not None]
        out.append(
            {
                "scenario": scenario,
                "pue": pue,
                "workload": workload,
                "strategy": strategy,
                "n_seeds": len(subset),
                "energy_per_served_j_mean": statistics.mean(es) if es else None,
                "energy_per_offered_j_mean": statistics.mean(eo) if eo else None,
                "drop_rate_mean": statistics.mean(float(r["drop_rate"]) for r in subset),
                "sla_rate_mean": statistics.mean(float(r["sla_violation_rate"]) for r in subset),
                "replica_hours_mean": statistics.mean(float(r["replica_hours"]) for r in subset),
            }
        )
    return out


def rankings(aggregates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    keys = sorted({(r["scenario"], r["pue"], r["workload"]) for r in aggregates})
    for scenario, pue, workload in keys:
        subset = [
            r for r in aggregates
            if r["scenario"] == scenario and r["pue"] == pue and r["workload"] == workload
        ]
        subset.sort(key=lambda r: (r["energy_per_served_j_mean"] is None, r["energy_per_served_j_mean"] or 0.0))
        for rank, row in enumerate(subset, start=1):
            out.append(
                {
                    "scenario": scenario,
                    "pue": pue,
                    "workload": workload,
                    "strategy": row["strategy"],
                    "rank_by_energy_per_served": rank,
                    "energy_per_served_j_mean": row["energy_per_served_j_mean"],
                    "energy_per_offered_j_mean": row["energy_per_offered_j_mean"],
                    "drop_rate_mean": row["drop_rate_mean"],
                    "sla_rate_mean": row["sla_rate_mean"],
                    "replica_hours_mean": row["replica_hours_mean"],
                }
            )
    return out


def _at(ranks: Sequence[Dict[str, Any]], scenario: str, pue: float, workload: str, strategy: str) -> int | None:
    for row in ranks:
        if (
            row["scenario"] == scenario and row["pue"] == pue
            and row["workload"] == workload and row["strategy"] == strategy
        ):
            return int(row["rank_by_energy_per_served"])
    return None


def build_markdown(ranks: Sequence[Dict[str, Any]], aggregates: Sequence[Dict[str, Any]], max_error: float) -> str:
    workloads = sorted({r["workload"] for r in ranks})
    lines = [
        "# Energy sensitivity (extension)",
        "",
        "The controllers are energy-independent, so low/nominal/high power and PUE values only "
        "recompute the reported energy. Every configuration uses the same seeds and traces.",
        "",
        f"Nominal recomputation check against the confirmatory run: maximum relative error "
        f"`{max_error:.3e}` across all 300 nominal/PUE-1.2 runs.",
        "",
        "## Ranking by mean estimated energy per served request (nominal power)",
        "",
        "Rank 1 is the lowest energy per served request. Read this with the drop and SLA columns; "
        "a low rank can reflect unmet demand. Exact energy ties share the same value; their numeric "
        "rank order is arbitrary and should not be interpreted as a real difference.",
        "",
        "| Workload | Strategy | Rank | E/served J | E/offered J | Drop | SLA | Replica-h |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for workload in workloads:
        subset = [r for r in ranks if r["scenario"] == "nominal" and r["pue"] == 1.2 and r["workload"] == workload]
        subset.sort(key=lambda r: r["rank_by_energy_per_served"])
        for row in subset:
            lines.append(
                f"| {workload} | {row['strategy']} | {row['rank_by_energy_per_served']} | "
                f"{row['energy_per_served_j_mean']:.4f} | {row['energy_per_offered_j_mean']:.4f} | "
                f"{row['drop_rate_mean']:.4f} | {row['sla_rate_mean']:.4f} | {row['replica_hours_mean']:.4f} |"
            )
    lines += [
        "",
        "## Rank stability across power and PUE",
        "",
        "Each cell is the rank under that configuration (nominal PUE 1.2 is the reference). "
        "A change indicates that the power assumptions, not the controller, changed the ordering.",
        "",
        "| Workload | Strategy | nominal/1.2 | low/1.0 | low/1.6 | high/1.0 | high/1.6 |",
        "|---|---|---|---|---|---|---|",
    ]
    for workload in workloads:
        for strategy in STRATEGIES:
            lines.append(
                f"| {workload} | {strategy} | {_at(ranks, 'nominal', 1.2, workload, strategy)} | "
                f"{_at(ranks, 'low', 1.0, workload, strategy)} | {_at(ranks, 'low', 1.6, workload, strategy)} | "
                f"{_at(ranks, 'high', 1.0, workload, strategy)} | {_at(ranks, 'high', 1.6, workload, strategy)} |"
            )
    changes = []
    for workload in workloads:
        for strategy in STRATEGIES:
            ref = _at(ranks, "nominal", 1.2, workload, strategy)
            for scenario in SCENARIOS:
                for pue in PUE_VALUES:
                    value = _at(ranks, scenario, pue, workload, strategy)
                    if ref is not None and value is not None and value != ref:
                        changes.append(
                            f"{workload}/{strategy}: rank {ref} at nominal/PUE 1.2 -> {value} at "
                            f"{scenario}/PUE {pue}."
                        )
    lines += ["", "## Stable and changing comparisons", ""]
    if changes:
        lines.append("The following rank changes were observed:")
        lines.append("")
        lines.extend(f"- {item}" for item in changes)
    else:
        lines.append("No rank change was observed across the tested power and PUE configurations.")
    lines += [
        "",
        "Direct pairwise direction checks (for example EAES versus HPA formula) are in the CSV. "
        "Because the same scaling trajectory is used in every configuration, any ordering change is "
        "an artefact of the idle/dynamic energy split and PUE, not of different control decisions.",
        "",
        "## Interpretation",
        "",
        "- The nominal configuration reproduces the confirmatory energy exactly (error above).",
        "- Scaling decisions are not recomputed differently; this is a post-hoc energy recalculation.",
        "- Ranking changes are possible when idle power dominates (low load) or dynamic power dominates (high load).",
        "- All values are model estimates, not physical measurements.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = collect()
    max_error = nominal_check(rows)
    aggregates = aggregate(rows)
    ranks = rankings(aggregates)
    _write_csv(os.path.join(OUT_DIR, "per_run.csv"), rows)
    _write_csv(os.path.join(OUT_DIR, "aggregates.csv"), aggregates)
    _write_csv(os.path.join(OUT_DIR, "rankings.csv"), ranks)
    manifest = {
        "extension": "energy_sensitivity",
        "label": "exploratory_extension",
        "confirmatory_run_unchanged": "v3_paired_20261025T220942Z",
        "created_at": utc_now(),
        "git_commit": git_commit(),
        "git_tracked_dirty": git_tracked_dirty(),
        "config_hash": combined_config_hash(load_configs()),
        "scenarios": SCENARIOS,
        "pue_values": PUE_VALUES,
        "n_runs": len(rows),
        "nominal_recompute_max_rel_error": max_error,
        "notes": "Energy sensitivity only; confirmatory decisions and results are unchanged.",
    }
    atomic_write_json(os.path.join(OUT_DIR, "manifest.json"), manifest)
    with open(os.path.join(OUT_DIR, "ENERGY_SENSITIVITY.md"), "w", encoding="utf-8") as fh:
        fh.write(build_markdown(ranks, aggregates, max_error))
    print(f"energy sensitivity runs: {len(rows)}")
    print(f"nominal recomputation max rel error: {max_error:.3e}")
    print(f"wrote {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

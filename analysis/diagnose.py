#!/usr/bin/env python3
"""EAES diagnostic from raw per-tick logs.

This script intentionally looks for explanations that could favour *or* harm
EAES: denominator changes, provisioning, startup delay, cooldown, and energy
attribution.  It never adjusts the data.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence, Tuple

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from eaes.config import atomic_write_json, git_commit, load_configs
from analysis.analyze import (
    STRATEGIES,
    _bootstrap_ci,
    _load_run,
    _latest_run,
    _values,
)

PRIMARY_STRATEGIES = ["static", "cpu_threshold", "hpa_formula", "eaes", "forecasting_eaes"]


def _raw_rows(run_dir: str, workload: str, seed: int, strategy: str) -> List[Dict[str, Any]]:
    path = os.path.join(run_dir, f"{workload}_seed{seed}_{strategy}.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def _raw_stats(
    rows: Sequence[Dict[str, Any]],
    target_util: float = 0.7,
    dt: float = 5.0,
    latency_sla_ms: float = 500.0,
) -> Dict[str, Any]:
    measured = [r for r in rows if not r.get("warmup")]
    energy = sum(float(r["node_energy_j"]) for r in measured)
    pod_energy = sum(float(r["pod_energy_sum_j"]) for r in measured)
    served = sum(int(r["served"]) for r in measured)
    offered = sum(int(r["offered"]) for r in measured)
    dropped = sum(int(r["dropped"]) for r in measured)
    sla_violations = 0
    for r in measured:
        latency = r.get("avg_latency_ms")
        sla_violations += int(r["dropped"])
        if latency is not None and float(latency) > latency_sla_ms:
            sla_violations += int(r["served"])
    replica_sum = sum(int(r["ready_replicas_after"]) for r in measured) * dt
    rules = Counter(r.get("rule_fired", "") for r in rows)
    actions = Counter(r.get("scaling_action", "") for r in rows)
    max_pending = max((int(r.get("pending_replicas", 0)) for r in rows), default=0)
    max_ready = max((int(r.get("ready_replicas_after", r["ready_replicas"])) for r in rows), default=0)
    max_active = max((int(r.get("active_nodes", 0)) for r in rows), default=0)
    max_backlog = max((float(r.get("backlog_requests", 0)) for r in rows), default=0.0)
    conservation = max((float(r.get("conservation_error_j", 0)) for r in rows), default=0.0)
    overprovision = []
    for r in measured:
        details = r.get("decision_details") or {}
        demand = details.get("demand_rps")
        cap = 10.0
        if demand is not None and float(demand) > 0:
            required = math.ceil(float(demand) / (cap * target_util))
            overprovision.append(int(r.get("ready_replicas_after", r["ready_replicas"])) - required)
    return {
        "ticks": len(rows),
        "measured_ticks": len(measured),
        "energy_j": energy,
        "pod_energy_j": pod_energy,
        "served": served,
        "offered": offered,
        "dropped": dropped,
        "sla_violations": sla_violations,
        "energy_per_served_j": energy / served if served else None,
        "energy_per_offered_j": energy / offered if offered else None,
        "served_fraction": served / offered if offered else None,
        "drop_rate": dropped / offered if offered else None,
        "sla_violation_rate": sla_violations / offered if offered else None,
        "replica_hours": replica_sum / 3600.0,
        "avg_ready": replica_sum / (len(measured) * dt) if measured else None,
        "max_ready": max_ready,
        "max_pending": max_pending,
        "max_active_nodes": max_active,
        "max_backlog": max_backlog,
        "conservation_max_error_j": conservation,
        "actions": dict(actions),
        "rules": dict(rules),
        "cooldown_holds": sum(v for k, v in rules.items() if "cooldown" in k or "stabilization" in k or "dwell" in k),
        "overprovision_mean": statistics.mean(overprovision) if overprovision else None,
        "overprovision_max": max(overprovision) if overprovision else None,
    }


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _table(rows: Sequence[Dict[str, Any]], cols: Sequence[Tuple[str, str]]) -> str:
    out = ["| " + " | ".join(label for _, label in cols) + " |",
           "|" + "|".join("---" for _ in cols) + "|"]
    for row in rows:
        out.append("| " + " | ".join(_fmt(row.get(key)) for key, _ in cols) + " |")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", default=None)
    args = parser.parse_args()
    run_dir = args.run_dir or _latest_run()
    manifest, summaries = _load_run(run_dir)
    configs = load_configs()
    workloads = manifest["workloads"]
    seeds = manifest["seeds"]
    target_util = float(configs["sla"]["utilization_ceiling"]) - float(configs["sla"]["margin_threshold"])
    dt = float(configs["experiment"]["control_interval_s"])

    # Aggregated per workload/strategy raw statistics.
    agg: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for workload in workloads:
        for strategy in PRIMARY_STRATEGIES:
            for seed in seeds:
                rows = _raw_rows(run_dir, workload, seed, strategy)
                if rows:
                    agg[(workload, strategy)].append(_raw_stats(rows, target_util, dt, float(configs["sla"]["latency_sla_ms"])))

    metric_rows = []
    for workload in workloads:
        for strategy in PRIMARY_STRATEGIES:
            stats = agg[(workload, strategy)]
            if not stats:
                continue
            metric_rows.append(
                {
                    "workload": workload,
                    "strategy": strategy,
                    "energy_per_served_j": statistics.mean(s["energy_per_served_j"] for s in stats),
                    "energy_per_offered_j": statistics.mean(s["energy_per_offered_j"] for s in stats),
                    "drop_rate": statistics.mean(s["drop_rate"] for s in stats),
                    "sla_rate": statistics.mean(s["sla_violation_rate"] for s in stats),
                    "served_fraction": statistics.mean(s["served_fraction"] for s in stats),
                    "replica_hours": statistics.mean(s["replica_hours"] for s in stats),
                    "max_ready": statistics.mean(s["max_ready"] for s in stats),
                    "max_pending": statistics.mean(s["max_pending"] for s in stats),
                    "cooldown_holds": statistics.mean(s["cooldown_holds"] for s in stats),
                }
            )

    # Paired EAES-HPA decomposition per workload/seed.
    paired_rows = []
    for workload in workloads:
        for seed in seeds:
            eaes_rows = _raw_rows(run_dir, workload, seed, "eaes")
            hpa_rows = _raw_rows(run_dir, workload, seed, "hpa_formula")
            if not eaes_rows or not hpa_rows:
                continue
            e = _raw_stats(eaes_rows, target_util, dt, float(configs["sla"]["latency_sla_ms"]))
            h = _raw_stats(hpa_rows, target_util, dt, float(configs["sla"]["latency_sla_ms"]))
            paired_rows.append(
                {
                    "workload": workload,
                    "seed": seed,
                    "e_es": e["energy_per_served_j"],
                    "h_es": h["energy_per_served_j"],
                    "e_eo": e["energy_per_offered_j"],
                    "h_eo": h["energy_per_offered_j"],
                    "e_total": e["energy_j"],
                    "h_total": h["energy_j"],
                    "e_served": e["served"],
                    "h_served": h["served"],
                    "e_offered": e["offered"],
                    "h_offered": h["offered"],
                    "e_rh": e["replica_hours"],
                    "h_rh": h["replica_hours"],
                    "e_drop": e["drop_rate"],
                    "h_drop": h["drop_rate"],
                    "e_sla": e["sla_violation_rate"],
                    "h_sla": h["sla_violation_rate"],
                    "e_max_pending": e["max_pending"],
                    "h_max_pending": h["max_pending"],
                }
            )

    # Forecasting ablation, paired by workload/seed.
    forecast_comparison = []
    for workload in workloads:
        rows = []
        for seed in seeds:
            e_rows = _raw_rows(run_dir, workload, seed, "eaes")
            f_rows = _raw_rows(run_dir, workload, seed, "forecasting_eaes")
            if not e_rows or not f_rows:
                continue
            e = _raw_stats(e_rows, target_util, dt, float(configs["sla"]["latency_sla_ms"]))
            f = _raw_stats(f_rows, target_util, dt, float(configs["sla"]["latency_sla_ms"]))
            rows.append({"e": e, "f": f})
        if not rows:
            continue
        forecast_comparison.append(
            {
                "workload": workload,
                "n_seeds": len(rows),
                "e_es": statistics.mean(r["e"]["energy_per_served_j"] for r in rows),
                "f_es": statistics.mean(r["f"]["energy_per_served_j"] for r in rows),
                "es_ratio": statistics.mean(r["f"]["energy_per_served_j"] for r in rows)
                / statistics.mean(r["e"]["energy_per_served_j"] for r in rows),
                "e_sla": statistics.mean(r["e"]["sla_violation_rate"] for r in rows),
                "f_sla": statistics.mean(r["f"]["sla_violation_rate"] for r in rows),
                "e_rh": statistics.mean(r["e"]["replica_hours"] for r in rows),
                "f_rh": statistics.mean(r["f"]["replica_hours"] for r in rows),
            }
        )

    # Aggregate comparisons.
    comparisons = []
    for workload in workloads:
        rows = [r for r in paired_rows if r["workload"] == workload]
        if not rows:
            continue
        mean = lambda key: statistics.mean(float(r[key]) for r in rows if r.get(key) is not None)
        e_es, h_es = mean("e_es"), mean("h_es")
        e_eo, h_eo = mean("e_eo"), mean("h_eo")
        e_rh, h_rh = mean("e_rh"), mean("h_rh")
        es_worse = sum(1 for r in rows if r["e_es"] is not None and r["h_es"] is not None and r["e_es"] > r["h_es"])
        eo_worse = sum(1 for r in rows if r["e_eo"] is not None and r["h_eo"] is not None and r["e_eo"] > r["h_eo"])
        total_higher = sum(1 for r in rows if r["e_total"] > r["h_total"])
        served_higher = sum(1 for r in rows if r["e_served"] > r["h_served"])
        comparisons.append(
            {
                "workload": workload,
                "n_seeds": len(rows),
                "e_es": e_es,
                "h_es": h_es,
                "es_ratio": e_es / h_es if h_es else None,
                "e_eo": e_eo,
                "h_eo": h_eo,
                "eo_ratio": e_eo / h_eo if h_eo else None,
                "e_rh": e_rh,
                "h_rh": h_rh,
                "rh_ratio": e_rh / h_rh if h_rh else None,
                "e_drop": mean("e_drop"),
                "h_drop": mean("h_drop"),
                "e_sla": mean("e_sla"),
                "h_sla": mean("h_sla"),
                "seeds_es_worse": es_worse,
                "seeds_eo_worse": eo_worse,
                "seeds_total_energy_higher": total_higher,
                "seeds_served_higher": served_higher,
            }
        )

    # Rule and startup diagnostics.
    rule_rows = []
    for workload in workloads:
        for strategy in ("eaes", "hpa_formula", "cpu_threshold"):
            stats = agg[(workload, strategy)]
            if not stats:
                continue
            merged_rules: Counter = Counter()
            for s in stats:
                merged_rules.update(s["rules"])
            rule_rows.append(
                {
                    "workload": workload,
                    "strategy": strategy,
                    "cooldown_or_stab_holds": statistics.mean(s["cooldown_holds"] for s in stats),
                    "max_pending": statistics.mean(s["max_pending"] for s in stats),
                    "max_ready": statistics.mean(s["max_ready"] for s in stats),
                    "max_active_nodes": statistics.mean(s["max_active_nodes"] for s in stats),
                    "overprovision_mean": statistics.mean(
                        s["overprovision_mean"] for s in stats if s["overprovision_mean"] is not None
                    ) if any(s["overprovision_mean"] is not None for s in stats) else None,
                    "conservation_max_error": max(s["conservation_max_error_j"] for s in stats),
                    "top_rules": "; ".join(f"{k}={v}" for k, v in merged_rules.most_common(4)),
                }
            )

    # Findings, written from computed values.
    findings = []
    for c in comparisons:
        if c["es_ratio"] is None:
            continue
        direction = "higher" if c["es_ratio"] > 1 else "lower"
        denom = "not explained by the denominator"
        if c["es_ratio"] > 1 and c["eo_ratio"] is not None and c["eo_ratio"] <= 1:
            denom = "the served-versus-offered denominator changes the sign"
        findings.append(
            f"{c['workload']}: EAES energy per served request is {direction} than HPA formula "
            f"({c['e_es']:.3f} vs {c['h_es']:.3f} J, ratio {c['es_ratio']:.3f}); "
            f"energy per offered request ratio is {c['eo_ratio']:.3f}; {denom}. "
            f"EAES serves {c['seeds_served_higher']}/{c['n_seeds']} seeds more requests, "
            f"has {c['e_drop']:.4f} vs {c['h_drop']:.4f} drop rate and "
            f"{c['e_sla']:.4f} vs {c['h_sla']:.4f} SLA violation rate, and uses "
            f"{c['rh_ratio']:.3f}x the replica-hours."
        )

    report = {
        "run_id": manifest["run_id"],
        "git_commit": git_commit(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "energy_is_modelled": True,
        "comparisons": comparisons,
        "forecast_comparison": forecast_comparison,
        "metric_rows": metric_rows,
        "rule_rows": rule_rows,
        "findings": findings,
        "nominal_conservation_max_error_j": max(
            (r["conservation_max_error"] for r in rule_rows), default=0.0
        ),
    }
    atomic_write_json(os.path.join(APP_DIR, "results", "diagnostic.json"), report)

    lines = [
        "# EAES Diagnostic (generated from raw tick logs)",
        "",
        f"Run: `{manifest['run_id']}`  ",
        f"Git commit: `{git_commit()}`  ",
        f"Execution mode: **{manifest['execution_mode']}**  ",
        "",
        "> All energy is modelled, not measured. The diagnostic looks for evidence "
        "that could favour or harm EAES and does not adjust any result.",
        "",
        "## 1. EAES vs HPA formula decomposition",
        "",
        _table(
            comparisons,
            [("workload", "Workload"), ("e_es", "EAES E/served"), ("h_es", "HPA E/served"),
             ("es_ratio", "Ratio"), ("e_eo", "EAES E/offered"), ("h_eo", "HPA E/offered"),
             ("eo_ratio", "Ratio"), ("e_rh", "EAES repl-h"), ("h_rh", "HPA repl-h"),
             ("rh_ratio", "Ratio"), ("e_drop", "EAES drop"), ("h_drop", "HPA drop"),
             ("e_sla", "EAES SLA"), ("h_sla", "HPA SLA")],
        ),
        "",
        "## 2. Denominator and throughput check",
        "",
        _table(
            comparisons,
            [("workload", "Workload"), ("seeds_served_higher", "Seeds EAES serves more"),
             ("n_seeds", "Seeds"), ("seeds_es_worse", "Seeds E/served worse"),
             ("seeds_eo_worse", "Seeds E/offered worse"),
             ("seeds_total_energy_higher", "Seeds total energy higher")],
        ),
        "",
        "## 3. Forecasting ablation (forecasting EAES vs reactive EAES)",
        "",
        _table(
            forecast_comparison,
            [("workload", "Workload"), ("n_seeds", "Seeds"),
             ("e_es", "EAES E/served"), ("f_es", "Forecast E/served"),
             ("es_ratio", "Ratio"), ("e_sla", "EAES SLA"), ("f_sla", "Forecast SLA"),
             ("e_rh", "EAES repl-h"), ("f_rh", "Forecast repl-h")],
        ),
        "",
        "## 4. Strategy metrics (mean over seeds, raw recomputation)",
        "",
        _table(
            metric_rows,
            [("workload", "Workload"), ("strategy", "Strategy"),
             ("energy_per_served_j", "E/served"), ("energy_per_offered_j", "E/offered"),
             ("drop_rate", "Drop"), ("sla_rate", "SLA"), ("served_fraction", "Served/offered"),
             ("replica_hours", "Replica-hours"), ("max_ready", "Max ready"),
             ("max_pending", "Max pending"), ("cooldown_holds", "Cooldown/stab holds")],
        ),
        "",
        "## 5. Startup, overprovisioning, and control-rule activity",
        "",
        _table(
            rule_rows,
            [("workload", "Workload"), ("strategy", "Strategy"),
             ("max_pending", "Max pending"), ("max_ready", "Max ready"),
             ("max_active_nodes", "Max nodes"), ("overprovision_mean", "Mean overprovision"),
             ("cooldown_or_stab_holds", "Cooldown/stab holds"),
             ("conservation_max_error", "Conservation err"), ("top_rules", "Top rules")],
        ),
        "",
        "## 6. Findings",
        "",
    ]
    for f in findings:
        lines.append(f"- {f}")
    lines += [
        "",
        "## 7. Interpretation",
        "",
        "- A lower energy per served request can be an artefact of serving fewer requests; the offered-request column is the denominator check.",
        "- Replica-hours expose provisioning cost that per-request energy can hide.",
        "- Pending replicas and cooldown/stabilization holds show whether startup delay or conservative control caused the trajectory.",
        "- Node energy and pod-attributed energy are conserved within the reported error; pod attribution does not create energy.",
        "- These are simulation findings, not cluster measurements.",
        "",
    ]
    with open(os.path.join(APP_DIR, "results", "EAES_DIAGNOSTIC.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"diagnostic run: {manifest['run_id']}")
    print(f"comparisons: {len(comparisons)}; rule rows: {len(rule_rows)}")
    print(f"conservation max error: {report['nominal_conservation_max_error_j']:.3e}")
    for f in findings:
        print("-", f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

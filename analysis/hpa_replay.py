#!/usr/bin/env python3
"""Replay recorded native-HPA metric samples through the offline HPA formula.

This is a validation of the *simulated formula*, not a new cluster experiment.
Only recorded samples are used; no metric or replica value is invented.  The
sampler starts after the native HPA has already reached four replicas, so the
initial 1 -> 4 transition is not observed and cannot be replayed.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys
from typing import Any, Dict, List, Sequence

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from eaes.config import atomic_write_json, load_configs, utc_now
from eaes.strategies import HPAFormulaStrategy

CLUSTER_DIR = os.path.join(APP_DIR, "results", "cluster_validation")
OUT_DIR = os.path.join(APP_DIR, "results", "extension", "hpa_replay")
CPU_REQUEST_MILLICORES = 100.0


def _write_csv(path: str, rows: Sequence[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        open(path, "w", encoding="utf-8").close()
        return
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def replay_file(path: str, configs: Dict[str, Any]) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    samples = payload.get("samples") or []
    strategy = HPAFormulaStrategy(
        configs["strategies"]["hpa_formula"], configs["simulation"], configs["sla"]
    )
    rows: List[Dict[str, Any]] = []
    for i in range(len(samples) - 1):
        sample = samples[i]
        nxt = samples[i + 1]
        ready = int(sample.get("replicas_ready") or 0)
        spec = int(sample.get("replicas_spec") or 0)
        pod_cpu = sample.get("pod_cpu_millicores")
        cpu_util = None
        if pod_cpu is not None and ready > 0 and CPU_REQUEST_MILLICORES > 0:
            cpu_util = max(0.0, min(1.0, float(pod_cpu) / (ready * CPU_REQUEST_MILLICORES)))
        state = {
            "t": float(sample.get("elapsed_s") or 0.0),
            "dt_s": 5.0,
            "warmup": False,
            "ready_replicas": ready,
            "desired_replicas": spec,
            "pending_replicas": max(0, spec - ready),
            "active_nodes": int(sample.get("node_count") or 0),
            "capacity_rps": ready * float(configs["simulation"]["pod_capacity_rps"]),
            "pod_capacity_rps": float(configs["simulation"]["pod_capacity_rps"]),
            "cpu_util": cpu_util,
            "backlog_requests": 0.0,
            "arrival_rate_rps": 0.0,
            "future_arrival_rates_rps": [],
            "startup_delay_s": float(configs["simulation"]["startup_delay_s"]),
        }
        decision = strategy.decide(state)
        observed_spec = int(nxt.get("replicas_spec") or 0)
        observed_ready = int(nxt.get("replicas_ready") or 0)
        rows.append(
            {
                "repetition": int(payload.get("repetition", 0)),
                "sample_index": i,
                "elapsed_s": float(sample.get("elapsed_s") or 0.0),
                "ready_replicas": ready,
                "spec_replicas": spec,
                "pod_cpu_millicores": pod_cpu,
                "cpu_util_fraction": cpu_util,
                "predicted_replicas": decision.replicas,
                "observed_next_spec": observed_spec,
                "observed_next_ready": observed_ready,
                "agreement_spec": int(decision.replicas == observed_spec),
                "agreement_ready": int(decision.replicas == observed_ready),
                "action": decision.action,
                "rule": decision.rule,
                "reason": decision.reason,
            }
        )
    return rows


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    configs = load_configs()
    paths = sorted(glob.glob(os.path.join(CLUSTER_DIR, "hpa_rep*.json")))
    if not paths:
        raise SystemExit("no hpa_rep*.json files found; run the cluster validation first")
    rows: List[Dict[str, Any]] = []
    for path in paths:
        rows.extend(replay_file(path, configs))
    _write_csv(os.path.join(OUT_DIR, "replay.csv"), rows)
    mismatches = [r for r in rows if not r["agreement_spec"]]
    _write_csv(os.path.join(OUT_DIR, "mismatches.csv"), mismatches)
    agreement = (sum(r["agreement_spec"] for r in rows) / len(rows)) if rows else None
    observed_changes = sum(
        1 for a, b in zip(rows, rows[1:])
        if a["repetition"] == b["repetition"] and a["spec_replicas"] != b["spec_replicas"]
    )
    predicted_changes = sum(1 for r in rows if r["predicted_replicas"] != r["spec_replicas"])
    manifest = {
        "extension": "hpa_replay",
        "label": "validation_extension",
        "created_at": utc_now(),
        "source_files": [os.path.basename(p) for p in paths],
        "n_transitions": len(rows),
        "agreement_rate_spec": agreement,
        "predicted_replica_changes": predicted_changes,
        "observed_replica_changes_between_samples": observed_changes,
        "limitations": [
            "The sampler starts after the native HPA has reached 4 replicas; the initial 1->4 transition is not observed.",
            "Samples are roughly 5.7 s apart, not exactly the 5 s simulation interval.",
            "The HPA formula is replayed with recorded pod CPU divided by the 100m CPU request; no metric is imputed.",
            "This validates the offline formula against steady-state decisions, not the cluster HPA controller end-to-end.",
        ],
    }
    atomic_write_json(os.path.join(OUT_DIR, "manifest.json"), manifest)
    lines = [
        "# Native-HPA replay (extension)",
        "",
        "Recorded native-HPA pod CPU and replica samples from the Minikube validation were replayed "
        "through the offline `hpa_formula` strategy. No metric series or replica trajectory was invented.",
        "",
        f"- Recorded files: {', '.join(os.path.basename(p) for p in paths)}",
        f"- Comparable sample transitions: **{len(rows)}**",
        f"- Predicted desired replicas agree with the next recorded spec: **{agreement * 100:.2f}%**",
        f"- Predicted replica changes: **{predicted_changes}**; observed changes between samples: **{observed_changes}**",
        "",
        "## What can and cannot be compared",
        "",
        "The native HPA had already scaled from one to four replicas before the sampler's first "
        "observation. The scale-up latency of that transition is therefore missing, and this replay "
        "does not claim to validate it. The replay compares steady-state desired counts, not the "
        "full controller loop. The samples are about 5.7 s apart while the simulation uses 5 s; the "
        "formula is evaluated on the recorded timestamps.",
        "",
        "## Mismatches",
        "",
    ]
    if mismatches:
        lines.append("| Rep | Sample | t s | CPU util | Predicted | Observed next spec | Rule |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in mismatches:
            lines.append(
                f"| {row['repetition']} | {row['sample_index']} | {row['elapsed_s']:.1f} | "
                f"{row['cpu_util_fraction']:.4f} | {row['predicted_replicas']} | "
                f"{row['observed_next_spec']} | {row['rule']} |"
            )
    else:
        lines.append("No mismatch occurred in the recorded sample window.")
    lines += [
        "",
        "## Interpretation",
        "",
        "High agreement here is weak evidence: the recorded window is short, load is steady, and the "
        "native HPA is already at a stable count. It does not establish that the simulated formula "
        "matches native HPA under bursts or cold starts. Those observations are missing.",
        "",
    ]
    with open(os.path.join(OUT_DIR, "HPA_REPLAY.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"transitions: {len(rows)}; agreement: {agreement:.4f}; mismatches: {len(mismatches)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

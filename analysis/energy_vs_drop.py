#!/usr/bin/env python3
"""Energy-versus-drop Pareto plots (extension).

Each workload gets a self-contained SVG so no plotting dependency is needed.
The x axis is estimated energy per *offered* request; the y axis is the request
drop rate.  Using the offered denominator avoids rewarding a strategy simply for
serving less traffic.
"""
from __future__ import annotations

import csv
import json
import os
import statistics
import sys
from typing import Any, Dict, List, Sequence, Tuple

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

RUN_DIR = os.path.join(APP_DIR, "results", "runs", "v3_paired_20261025T220942Z")
OUT_DIR = os.path.join(APP_DIR, "results", "extension", "energy_vs_drop")
STRATEGIES = ["static", "cpu_threshold", "hpa_formula", "eaes", "forecasting_eaes"]
LABELS = {
    "static": "Static",
    "cpu_threshold": "CPU threshold",
    "hpa_formula": "HPA formula",
    "eaes": "EAES",
    "forecasting_eaes": "Forecasting EAES",
}
COLORS = {
    "static": "#f3b44b",
    "cpu_threshold": "#c084fc",
    "hpa_formula": "#5aa9ff",
    "eaes": "#47d7ac",
    "forecasting_eaes": "#ff8a95",
}


def load_means() -> List[Dict[str, Any]]:
    with open(os.path.join(RUN_DIR, "summary.json"), encoding="utf-8") as fh:
        summaries = json.load(fh)
    workloads = sorted({r["workload"] for r in summaries})
    out = []
    for workload in workloads:
        for strategy in STRATEGIES:
            subset = [r for r in summaries if r["workload"] == workload and r["strategy"] == strategy]
            energy = [float(r["energy_per_offered_request_j"]) for r in subset if r["energy_per_offered_request_j"] is not None]
            drop = [float(r["drop_rate"]) for r in subset if r["drop_rate"] is not None]
            out.append(
                {
                    "workload": workload,
                    "strategy": strategy,
                    "strategy_label": LABELS[strategy],
                    "energy_per_offered_j": statistics.mean(energy) if energy else None,
                    "drop_rate": statistics.mean(drop) if drop else None,
                    "n_seeds": len(subset),
                }
            )
    return out


def pareto(rows: Sequence[Dict[str, Any]]) -> List[str]:
    frontier = []
    for row in rows:
        if row["energy_per_offered_j"] is None or row["drop_rate"] is None:
            continue
        dominated = False
        for other in rows:
            if other is row or other["energy_per_offered_j"] is None or other["drop_rate"] is None:
                continue
            if (
                other["energy_per_offered_j"] <= row["energy_per_offered_j"]
                and other["drop_rate"] <= row["drop_rate"]
                and (
                    other["energy_per_offered_j"] < row["energy_per_offered_j"]
                    or other["drop_rate"] < row["drop_rate"]
                )
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(row["strategy"])
    return frontier


def _scale(value: float, lo: float, hi: float, a: float, b: float) -> float:
    if hi <= lo:
        return (a + b) / 2.0
    return a + (value - lo) / (hi - lo) * (b - a)


def svg_for(workload: str, rows: Sequence[Dict[str, Any]], frontier: Sequence[str]) -> str:
    width, height = 920, 540
    left, right, top, bottom = 88, 40, 64, 70
    xs = [r["energy_per_offered_j"] for r in rows if r["energy_per_offered_j"] is not None]
    ys = [r["drop_rate"] for r in rows if r["drop_rate"] is not None]
    x_lo, x_hi = 0.0, max(xs) * 1.12 if xs else 1.0
    y_lo, y_hi = 0.0, max(0.02, max(ys) * 1.12) if ys else 1.0
    plot_w = width - left - right
    plot_h = height - top - bottom

    def px(x):
        return _scale(x, x_lo, x_hi, left, left + plot_w)

    def py(y):
        return _scale(y, y_lo, y_hi, top + plot_h, top)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{workload}: estimated energy versus drop rate</title>',
        f'<desc id="desc">Pareto comparison of five autoscaling strategies. Energy is modelled, not measured.</desc>',
        '<rect width="100%" height="100%" fill="#0b1220"/>',
        f'<text x="{left}" y="30" fill="#e7edf7" font-family="Segoe UI, Arial" font-size="19" font-weight="700">{workload}: estimated energy vs request drop</text>',
        f'<text x="{left}" y="48" fill="#9fb0c9" font-family="Segoe UI, Arial" font-size="12">Mean of 10 seeds. Energy is modelled, not measured. Lower-left is better.</text>',
    ]
    # Grid and x ticks.
    for i in range(6):
        frac = i / 5.0
        x = left + frac * plot_w
        value = x_lo + frac * (x_hi - x_lo)
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top+plot_h}" stroke="#263650" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{top+plot_h+20}" fill="#9fb0c9" font-family="Consolas, monospace" font-size="11" text-anchor="middle">{value:.1f}</text>')
    for i in range(6):
        frac = i / 5.0
        y = top + plot_h - frac * plot_h
        value = y_lo + frac * (y_hi - y_lo)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" stroke="#263650" stroke-width="1"/>')
        parts.append(f'<text x="{left-10}" y="{y+4:.1f}" fill="#9fb0c9" font-family="Consolas, monospace" font-size="11" text-anchor="end">{value*100:.1f}%</text>')
    # Axes.
    parts.append(f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="#9fb0c9" stroke-width="1.2"/>')
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#9fb0c9" stroke-width="1.2"/>')
    parts.append(f'<text x="{left+plot_w/2:.1f}" y="{height-24}" fill="#c9d7ec" font-family="Segoe UI, Arial" font-size="13" text-anchor="middle">Estimated energy per offered request (J)</text>')
    parts.append(f'<text x="22" y="{top+plot_h/2:.1f}" fill="#c9d7ec" font-family="Segoe UI, Arial" font-size="13" text-anchor="middle" transform="rotate(-90 22 {top+plot_h/2:.1f})">Request drop rate</text>')

    # Pareto frontier line.
    if frontier:
        points = sorted(
            [r for r in rows if r["strategy"] in frontier],
            key=lambda r: r["energy_per_offered_j"],
        )
        coords = " ".join(f"{px(r['energy_per_offered_j']):.1f},{py(r['drop_rate']):.1f}" for r in points)
        parts.append(f'<polyline points="{coords}" fill="none" stroke="#47d7ac" stroke-width="2" stroke-dasharray="6 5" opacity="0.75"/>')

    for row in rows:
        if row["energy_per_offered_j"] is None or row["drop_rate"] is None:
            continue
        x, y = px(row["energy_per_offered_j"]), py(row["drop_rate"])
        color = COLORS[row["strategy"]]
        is_frontier = row["strategy"] in frontier
        radius = 8 if is_frontier else 6
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}" stroke="#0b1220" stroke-width="2"/>')
        if is_frontier:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius+4}" fill="none" stroke="{color}" stroke-width="1.2" opacity="0.8"/>')
        label = f"{row['strategy_label']}"
        anchor = "start" if x < left + plot_w * 0.72 else "end"
        dx = 12 if anchor == "start" else -12
        parts.append(f'<text x="{x+dx:.1f}" y="{y+4:.1f}" fill="#e7edf7" font-family="Segoe UI, Arial" font-size="11" text-anchor="{anchor}">{label}</text>')

    # Legend.
    lx, ly = left, height - 52
    for i, strategy in enumerate(STRATEGIES):
        x = lx + i * 165
        parts.append(f'<circle cx="{x}" cy="{ly}" r="5" fill="{COLORS[strategy]}"/>')
        parts.append(f'<text x="{x+10}" y="{ly+4}" fill="#c9d7ec" font-family="Segoe UI, Arial" font-size="11">{LABELS[strategy]}</text>')
    parts.append(f'<text x="{left}" y="{height-12}" fill="#9fb0c9" font-family="Segoe UI, Arial" font-size="11">Ringed points and the dashed line form the Pareto frontier (minimum energy and drop).</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    means = load_means()
    workloads = sorted({r["workload"] for r in means})
    pareto_rows = []
    for workload in workloads:
        rows = [r for r in means if r["workload"] == workload]
        frontier = pareto(rows)
        for row in rows:
            pareto_rows.append(dict(row, pareto_frontier=row["strategy"] in frontier))
        with open(os.path.join(OUT_DIR, f"{workload}.svg"), "w", encoding="utf-8") as fh:
            fh.write(svg_for(workload, rows, frontier))
    with open(os.path.join(OUT_DIR, "pareto.csv"), "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(pareto_rows[0].keys()))
        writer.writeheader()
        writer.writerows(pareto_rows)
    lines = [
        "# Energy-versus-drop Pareto plots (extension)",
        "",
        "One SVG per workload. The x axis is **estimated** energy per offered request; the y axis is "
        "the request drop rate. A strategy that serves less traffic cannot look efficient merely "
        "because its denominator is smaller. Ringed points and the dashed line are the Pareto frontier.",
        "",
        "| Workload | Pareto-frontier strategies |",
        "|---|---|",
    ]
    for workload in workloads:
        frontier = [r["strategy"] for r in pareto_rows if r["workload"] == workload and r["pareto_frontier"]]
        lines.append(f"| {workload} | {', '.join(frontier) if frontier else 'none'} |")
    lines += [
        "",
        "Generated from the confirmatory 10-seed summary (300 runs). Energy is modelled, not measured.",
        "",
    ]
    with open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {len(workloads)} Pareto SVGs to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

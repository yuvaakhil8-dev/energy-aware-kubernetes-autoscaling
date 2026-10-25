#!/usr/bin/env python3
"""Run the paired v3 simulation experiment.

Examples:
    python -m experiments.run_v3
    python -m experiments.run_v3 --quick
    python -m experiments.run_v3 --scenario low
"""
from __future__ import annotations

import argparse
import copy
import os
import sys

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from eaes.config import load_configs
from eaes.engine import run_experiment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="use one seed only")
    parser.add_argument("--seeds", type=int, default=None, help="override seed count")
    parser.add_argument("--scenario", default=None, help="energy scenario")
    parser.add_argument("--output", default=None, help="output root")
    args = parser.parse_args()

    configs = load_configs()
    if args.quick:
        configs = copy.deepcopy(configs)
        configs["experiment"]["seeds"] = [1]
    elif args.seeds:
        configs = copy.deepcopy(configs)
        configs["experiment"]["seeds"] = list(range(1, args.seeds + 1))

    result = run_experiment(configs, energy_scenario=args.scenario, output_root=args.output)
    print(f"run_id: {result['run_id']}")
    print(f"run_dir: {result['run_dir']}")
    print(f"runs: {len(result['summaries'])}")
    print("strategy                 workload     E/served    drop    SLA   repl-h")
    for s in result["summaries"]:
        e = s["energy_per_served_request_j"]
        print(
            f"{s['strategy']:24s} {s['workload']:10s} "
            f"{(f'{e:9.3f}' if e is not None else '     null')} "
            f"{s['drop_rate']:7.4f} {s['sla_violation_rate']:7.4f} "
            f"{s['replica_hours']:8.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

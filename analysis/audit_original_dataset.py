#!/usr/bin/env python3
"""Audit of the original 27-record dataset (read-only).

This script does not modify either dataset. It reports:
- record counts and factorial coverage
- whether repetitions within a cell are identical
- presence of seeds / raw samples
- field availability
- the energy values per cell

Run: python analysis/audit_original_dataset.py
"""
import hashlib
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V2 = os.path.join(ROOT, "experiment_results_v2.json")
LEGACY = os.path.join(ROOT, "experiment_results.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    print("=" * 78)
    print("ORIGINAL DATASET AUDIT (read-only)")
    print("=" * 78)
    for path in (V2, LEGACY):
        if not os.path.exists(path):
            print(f"MISSING: {path}")
            continue
        data = load(path)
        print(f"\nFILE: {os.path.basename(path)}")
        print(f"SHA-256: {sha256(path)}")
        print(f"RECORDS: {len(data)}")
        print(f"KEYS: {sorted(data[0].keys())}")

    if not os.path.exists(V2):
        return
    data = load(V2)
    cells = defaultdict(list)
    for r in data:
        cells[(r.get("strategy"), r.get("workload"))].append(r)

    print("\nFACTORIAL CELLS")
    identical_cells = 0
    for key, rows in sorted(cells.items()):
        payloads = []
        for r in rows:
            kept = {
                k: v
                for k, v in r.items()
                if k not in {"experiment_id", "repetition", "timestamp"}
            }
            payloads.append(json.dumps(kept, sort_keys=True))
        identical = len(set(payloads)) == 1
        identical_cells += int(identical)
        print(
            f"  {key[0]:14s} {key[1]:7s} n={len(rows)} "
            f"identical={identical} "
            f"Ereq={[r.get('avg_energy_per_request') for r in rows]}"
        )

    print("\nSUMMARY")
    print(f"  cells: {len(cells)}")
    print(f"  cells with identical repetitions: {identical_cells}/{len(cells)}")
    print(f"  records with seed field: {sum('seed' in r for r in data)}/{len(data)}")
    print(f"  records with raw samples: {sum('samples' in r for r in data)}/{len(data)}")
    print(f"  strategies: {dict(Counter(r.get('strategy') for r in data))}")
    print(f"  workloads: {dict(Counter(r.get('workload') for r in data))}")
    print(f"  execution modes: {dict(Counter(r.get('execution_mode') for r in data))}")
    print(
        "  energy denominators are not recorded per record; "
        "see experiments/run_experiment.py for strategy-specific computations"
    )


if __name__ == "__main__":
    main()

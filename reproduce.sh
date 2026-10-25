#!/usr/bin/env bash
# Regenerate workloads, paired experiments, statistics, and test evidence.
set -euo pipefail
export ENERGY_AWARE_NO_BG=1
export PYTHONIOENCODING=utf-8

echo "=== 1. Configuration check ==="
python -c "from eaes.config import load_configs; c=load_configs(); print('configs OK', sorted(c))"

echo "=== 2. Paired simulation (6 workloads x 10 seeds x 5 strategies) ==="
python -m experiments.run_v3

echo "=== 3. Statistical analysis, tables, and EAES diagnostic ==="
python -m analysis.analyze
python -m analysis.diagnose

echo "=== 4. Test suite ==="
python -m pytest -q

echo "=== 5. Verify original dataset hashes ==="
python analysis/verify_dataset_hashes.py

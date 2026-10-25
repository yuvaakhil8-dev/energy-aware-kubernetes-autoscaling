# Regenerate workloads, paired experiments, statistics, and test evidence.
# Run from the flask-kubernetes directory in PowerShell.
$ErrorActionPreference = "Stop"
$env:ENERGY_AWARE_NO_BG = "1"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "=== 1. Configuration check ==="
python -c "from eaes.config import load_configs; c=load_configs(); print('configs OK', sorted(c))"

Write-Host "=== 2. Paired simulation (6 workloads x 10 seeds x 5 strategies) ==="
python -m experiments.run_v3

Write-Host "=== 3. Statistical analysis, tables, and EAES diagnostic ==="
python -m analysis.analyze
python -m analysis.diagnose

Write-Host "=== 4. Test suite ==="
python -m pytest -q

Write-Host "=== 5. Verify original dataset hashes ==="
python analysis/verify_dataset_hashes.py

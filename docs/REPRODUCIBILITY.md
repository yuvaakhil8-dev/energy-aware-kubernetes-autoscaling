# Reproducibility

## 1. What can be reproduced

- The 300-run paired simulation from fixed configs and seeds.
- All descriptive statistics, bootstrap CIs, paired tests, Friedman/Nemenyi tables, forecast evaluation, and sensitivity tables.
- The raw per-tick logs.
- The three-page dashboard and legacy API surface.
- The unit/integration test suite.
- Optionally, the separate Minikube/HPA validation, if Docker Desktop and Minikube are available.

The simulation does **not** require Docker or Kubernetes. The cluster validation does.

## 2. Repository and environment

```text
Repository: C:\Users\yuvaa\OneDrive\Desktop\Documents\Default Project\flask-kubernetes
Branch:     research-rebuild
```

Confirmatory run manifest:

| Field | Value |
|---|---|
| `run_id` | `v3_paired_20261025T220942Z` |
| `git_commit` | `431810fd8daa3cfd7dceaf11acb18dd6b14ea0ea` |
| `git_tracked_dirty` | `false` |
| `execution_mode` | `simulation` |
| `n_runs` | 300 |
| `energy_scenario` | `nominal` |
| Python | 3.11.9 |
| Flask | 3.1.3 |
| PyYAML | 6.0.3 |
| pytest | 8.3.3 |
| OS | Windows-10-10.0.26200-SP0 |
| `kubernetes` package | broken/unknown; not used by the simulation |

The Docker image uses `python:3.12-slim` and installs the pinned requirements. The local simulation used Python 3.11.9. The simulator is pure Python and has no compiled dependency.

## 3. Fresh-clone quick reproduction

```powershell
cd "C:\Users\yuvaa\OneDrive\Desktop\Documents\Default Project\flask-kubernetes"
python -m pip install -r requirements.txt

# Full simulation (6 workloads x 10 seeds x 5 strategies, 300 s each)
python -m experiments.run_v3

# Statistics and tables
python -m analysis.analyze

# Raw-log EAES diagnostic
python -m analysis.diagnose

# Tests
$env:ENERGY_AWARE_NO_BG='1'
python -m pytest -q
```

The commands are also wrapped by `reproduce.ps1` (PowerShell) and `reproduce.sh` (POSIX shell).

## 4. Expected artifacts

After `run_v3`:

```text
results/runs/<new_run_id>/manifest.json
results/runs/<new_run_id>/summary.json
results/runs/<new_run_id>/<workload>_seed<seed>_<strategy>.jsonl   # 300 files
results/latest_run.json
```

After `analyze`:

```text
results/RESULTS.md
results/analysis_manifest.json
results/tables/descriptive.csv
results/tables/paired.csv
results/tables/friedman.csv
results/tables/nemenyi.csv
results/tables/forecasting.csv
results/tables/sensitivity.csv
results/tables/*.md
```

After `diagnose`:

```text
results/EAES_DIAGNOSTIC.md
results/diagnostic.json
```

The exact run id changes with the timestamp. The numbers should match for the fixed configs and seed set; the manifest’s config/trace hashes are the check.

## 5. Determinism checks

The confirmatory run’s manifest records:

- per-config SHA-256 hashes;
- combined config hash;
- 60 trace hashes in `trace_index`;
- Python/package versions;
- git commit and tracked-dirty flag.

To verify a rerun:

```powershell
$m = Get-Content results\latest_run.json | ConvertFrom-Json
$run = Join-Path (Get-Location) $m.run_dir
Get-Content (Join-Path $run 'manifest.json') | Select-String 'config_hash|trace_hash|git_commit|git_tracked_dirty'
(Get-Content (Join-Path $run 'summary.json') | ConvertFrom-Json).Count
```

A full rerun should produce 300 summaries. The manifest’s config hashes should match `configs/`; the trace hashes should match `traces/index.json`.

The simulation uses `random.Random(seed)` and deterministic trace files. Reusing an existing trace is deliberate: the trace generator validates the existing file and hashes it rather than overwriting it.

## 6. Original data verification

The originals are outside the repository:

```powershell
$parent = 'C:\Users\yuvaa\OneDrive\Desktop\Documents\Default Project'
Get-FileHash "$parent\experiment_results_v2.json" -Algorithm SHA256
Get-FileHash "$parent\experiment_results.json" -Algorithm SHA256
```

Expected:

```text
v2:     6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E
legacy: C4BF4BFFFA8D0242395D2A2FB966C16DBC4884078BE7E82395E778EF87968451
```

The tracked copies under `data/` are byte-identical; the test suite checks them.

## 7. Test command and expected result

```powershell
$env:ENERGY_AWARE_NO_BG='1'
$env:PYTHONIOENCODING='utf-8'
python -m pytest -q
```

At the documentation checkpoint this is **91 passed**. The final saved output is `results/test_report.txt`; the earlier phase outputs are `results/test_dashboard.txt`, `results/test_pre_rerun.txt`, `results/test_phase7.txt`, `results/test_phase6.txt`, and `results/test_phase1_4.txt`.

`ENERGY_AWARE_NO_BG=1` prevents the app’s background workload thread from starting during tests.

## 8. Container build

```powershell
minikube image build -t flask-k8s-demo:latest .
kubectl -n energy-aware-dev rollout restart deployment/energy-aware-app
kubectl -n energy-aware-dev rollout status deployment/energy-aware-app --timeout=180s
kubectl port-forward -n energy-aware-dev svc/energy-aware-service 5001:5000
```

On this Windows host, `minikube image build` prints progress to stderr and can return a non-zero shell status even when the final Docker export/naming succeeds. Check the last lines of `results/image_build_final.log` and verify the pod starts before treating the build as failed.

The final image smoke test is recorded in `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md`.

## 9. Real-cluster reproduction

Prerequisites: Docker Desktop Linux engine, Minikube, kubectl, metrics-server. See `docs/CLUSTER_ENVIRONMENT.md`.

```powershell
minikube start --driver=docker --cpus=2 --memory=4096
minikube addons enable metrics-server
minikube image build -t flask-k8s-demo:latest .
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -n energy-aware-dev -f kubernetes/deployment.yaml -f kubernetes/service.yaml
kubectl rollout status deployment/energy-aware-app -n energy-aware-dev --timeout=180s
kubectl top nodes
kubectl port-forward -n energy-aware-dev svc/energy-aware-service 5001:5000
python -m experiments.run_cluster_validation --repetitions 3 --duration 60 --rate 80
```

This reproduces the real-cluster check, not the confirmatory simulation. The observed replica counts and request outcomes should be broadly similar, but timings and HPA behavior will vary.

## 10. Known non-determinism

- Run ids contain UTC timestamps.
- Real-cluster CPU, latency, and HPA timing vary.
- Python version differences can alter floating-point last digits.
- `kubectl top` values are sampled and can lag.
- The Flask development server is not a production server.
- Power models are assumptions, not measurements.

## 11. Commit chain

```text
431810f analysis: record run/analysis commits and accurate EAES direction wording
603d1de phase 8: three-page research dashboard, immutable data copies, container packaging
2e1816f phase 7: real Minikube/HPA validation and kubectl cluster backend
cce700b phase 6: paired statistics, bootstrap CIs, Holm/Friedman/Nemenyi, sensitivity
97a99dc phase 5: 10-seed paired experiments, raw logs, and EAES diagnostic
e3160d9 phase 5: freeze analysis plan before confirmatory diagnostic
9ca53b5 phase 4: five strategies, forecasting ablation, paired experiment engine
4d6fda6 phase 3: node-level energy model with attribution and sensitivity scenarios
```

The baseline snapshot is `c5ec94d` on `pre-rebuild-snapshot`.

## 12. What is not reproducible

- The paywalled full text of Li et al. (2025); only metadata was verified.
- A physical power measurement.
- A production multi-node cluster run.
- The original student project’s unrecorded environment exactly; the preserved code is in Git, but its external data and runtime history are not fully reconstructible.

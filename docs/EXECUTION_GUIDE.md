# Execution Guide

This guide covers local execution, analysis, dashboard use, tests, Docker, and
the optional Kubernetes validation. The simulation does not require Docker or
Kubernetes.

## 1. Prerequisites

| Component | Requirement |
|---|---|
| Python | 3.11+ (tested 3.11.9) |
| Python packages | `Flask==3.1.3`, `PyYAML==6.0.3` from `requirements.txt` |
| Browser | Current Edge/Chrome/Firefox for the dashboard |
| Docker / Minikube | Only for the separate cluster validation |
| Git | Used for provenance and clean-checkout reproduction |

Install:

```powershell
# Change to the repository root (run this from a PowerShell prompt while inside the repo)
Set-Location (git rev-parse --show-toplevel)
python -m pip install -r requirements.txt
```

## 2. Test first

The dashboard background workload thread is disabled for tests:

```powershell
$env:ENERGY_AWARE_NO_BG='1'
python -m pytest -q
```

Expected: `113 passed`. The suite includes route contracts, simulation
invariants, statistics, headline generation, dashboard APIs, extension
manifests, and forecast zero-exclusion checks. See `docs/TESTING.md`.

## 3. Run the dashboard

```powershell
$env:ENERGY_AWARE_NO_BG='1'
python app.py
```

Open `http://127.0.0.1:5000/`.

Pages:

- `/` - results, filters, selection KPIs, workload/CPU/replica time series,
  strategy comparison, energy-versus-drop scatter, tables, cluster validation.
- `/eaes-diagnostics` - recorded controller trace, final state, decision reason,
  cooldown/stabilization status, actual versus forecast, scaling history.
- `/methodology` - architecture, execution flow, workload generation, metrics,
  energy estimator, Kubernetes integration, APIs, limitations.

The app reads `results/` artifacts. If the confirmatory run is missing, pages
show an explicit error rather than invented data.

## 4. Reproduce the committed analysis

Default mode reuses the preserved confirmatory run and regenerates derived
tables, charts, diagnostics, and tests:

```powershell
.\reproduce.ps1
```

```bash
./reproduce.sh
```

What it does:

1. checks Python and dependencies;
2. loads and validates configs;
3. verifies protected dataset hashes;
4. runs `analysis.analyze --run-dir results/runs/v3_paired_20261025T220942Z`;
5. runs `analysis.diagnose`;
6. regenerates forecast-accuracy tables;
7. regenerates Pareto SVGs;
8. replays the recorded native-HPA samples;
9. runs the test suite;
10. validates required documents and references;
11. prints a summary and any working-tree changes.

Optional:

```powershell
.\reproduce.ps1 -Rerun        # rerun 300 paired simulations (new run id)
.\reproduce.ps1 -Extensions   # regenerate oracle/startup/30-seed/sensitivity
.\reproduce.ps1 -SkipTests
```

`-Rerun` does not overwrite the preserved confirmatory run; it creates a new run
directory and updates `results/latest_run.json`. The old run remains intact.

### Clean-checkout reproduction

```powershell
.\scripts\clean_checkout_reproduction.ps1
```

This clones the current branch into `%TEMP%`, runs `reproduce.ps1 -SkipTests`,
runs the tests separately, compares committed derived artifacts by SHA-256, and
writes `results/extension/clean_checkout/REPRODUCTION_REPORT.txt`. It never
modifies the original working tree.

## 5. Run the confirmatory experiment manually

```powershell
$env:ENERGY_AWARE_NO_BG='1'
python -m experiments.run_v3
```

This creates `results/runs/v3_paired_<timestamp>/` and updates
`results/latest_run.json`. It does not modify the preserved
`v3_paired_20261025T220942Z` directory.

Then:

```powershell
python -m analysis.analyze --run-dir results/runs/<run-id>
python -m analysis.diagnose --run-dir results/runs/<run-id>
python -m analysis.forecast_accuracy
python -m analysis.energy_vs_drop
python -m analysis.hpa_replay
```

## 6. Regenerate extensions

Extensions are exploratory and separate:

```powershell
python -m experiments.run_extensions
python -m analysis.energy_sensitivity
python -m analysis.energy_vs_drop
python -m analysis.hpa_replay
python -m analysis.forecast_accuracy
```

Outputs:

- `results/extension/oracle/`
- `results/extension/startup_sweep/`
- `results/extension/seed30/`
- `results/extension/energy_sensitivity/`
- `results/extension/energy_vs_drop/`
- `results/extension/hpa_replay/`
- `results/tables/forecast_accuracy*`

Run the extension runner only when the tracked tree is clean if you need
`git_tracked_dirty: false` in its manifests. Untracked outputs do not count as
dirty.

## 7. Docker

Build and run locally:

```powershell
docker build -t flask-k8s-demo:latest .
docker run --rm -p 5000:5000 flask-k8s-demo:latest
```

The image includes `results/` and the raw confirmatory JSONL logs because the
time-series and controller-trace APIs read them. Cluster per-request logs are
excluded. The container runs the Flask development server, not a production
WSGI server.

## 8. Native Kubernetes / Minikube validation

This is optional and separate from the confirmatory result. It requires Docker
Desktop and Minikube.

```powershell
minikube start --driver=docker --cpus=2 --memory=4096
minikube addons enable metrics-server
minikube image build -t flask-k8s-demo:latest .
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -n energy-aware-dev -f kubernetes/deployment.yaml -f kubernetes/service.yaml
kubectl rollout status deployment/energy-aware-app -n energy-aware-dev --timeout=180s
kubectl apply -f kubernetes/hpa.yaml -n energy-aware-dev
kubectl port-forward -n energy-aware-dev svc/energy-aware-service 5001:5000
python -m experiments.run_cluster_validation --repetitions 3 --duration 60 --rate 80
```

Static mode requires deleting the HPA and fixing the Deployment at three
replicas. The recorded validation already exists in
`results/cluster_validation/`; do not overwrite it unless you intend to generate
new evidence. See `docs/KUBERNETES_VALIDATION.md`.

## 9. Troubleshooting

| Symptom | Cause / action |
|---|---|
| Dashboard shows "No generated research run" | Run/analyze the confirmatory run or restore `results/` |
| Time-series API returns 400 | Invalid workload/strategy/seed; the error names the field |
| Charts blank | Check browser console; Chart.js is vendored at `static/vendor/chart.umd.min.js` |
| Tests start a background thread | Set `ENERGY_AWARE_NO_BG=1` |
| `kubectl` commands fail | Start Docker Desktop/Minikube; check `kubectl config current-context` |
| `import kubernetes` is broken | Known local issue; the research backend uses `kubectl` |
| Protected hash check fails | Stop; restore `data/` copies from the repository, do not edit them |

## 10. What not to do

- Do not overwrite `results/runs/v3_paired_20261025T220942Z/`.
- Do not edit generated tables by hand.
- Do not pool extensions with the confirmatory 10-seed result.
- Do not describe `hpa_formula` as native Kubernetes HPA.
- Do not describe modelled energy as measured power.
- Do not use the original 27-row dataset for inference.

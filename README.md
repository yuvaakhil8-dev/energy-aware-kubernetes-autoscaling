# Energy-Aware Autoscaling: Reproducible Research Build

This repository is a research rebuild of a Flask/Kubernetes energy-aware
autoscaling demonstration. It contains:

- a deterministic discrete-time simulation of a small Kubernetes-like cluster;
- five separately implemented autoscaling strategies;
- a node-level energy **model**;
- paired statistical analysis with seed-level pairing and bootstrap intervals;
- a three-page dashboard driven by generated backend artifacts;
- a separate real single-node Minikube / native-HPA validation;
- exploratory extensions that are reported separately from the confirmatory run.

**All simulation energy is modelled, not measured.** The real-cluster validation
contains real replica counts and request outcomes, but its energy column is also
modelled from measured node CPU. No power meter or Kepler measurement exists for
any result in this repository.

## Status at a glance

| Item | Value |
|---|---|
| Confirmatory run | `v3_paired_20261025T220942Z` (preserved; never overwritten) |
| Design | 6 workloads x 10 seeds x 5 strategies = 300 runs |
| Simulated duration | 300 s per run, 5 s control interval, 30 s warm-up excluded |
| Execution mode | `simulation` |
| Run git commit | `431810fd8daa3cfd7dceaf11acb18dd6b14ea0ea` |
| Tracked tree at run | clean (`git_tracked_dirty: false`) |
| Tests | 112 passing (see `results/test_report.txt`) |
| Confirmatory inference | paired by workload + seed, 5,000-resample bootstrap, Holm-adjusted Wilcoxon |
| Real cluster | Single-node Minikube v1.39.0 / Kubernetes v1.37.0, Docker driver |
| Dashboard | `/`, `/eaes-diagnostics`, `/methodology` |

## The short result

In the confirmatory 10-seed simulation, EAES has lower mean estimated energy per
served request than the simulated HPA formula on every workload by mean, and is
exactly tied on light. It also provisions fewer replica-hours in every workload.
**None of these paired energy differences survives Holm correction at alpha =
0.05 on the ten confirmatory seeds.** The confidence intervals and effect sizes
are reported instead of a significance claim. A separate 30-seed extension shows
the same directional pattern with Holm-adjusted p < 0.05 for several workloads,
but it is explicitly exploratory.

The advantage is not free:

- reactive EAES has small SLA-violation rates on variable (mean `0.0119`) and
  bursty (mean `0.0170`) workloads;
- the forecasting variant removes those variable-workload violations but uses
  more energy per served request on that workload;
- static replicas can show the lowest energy per served request while dropping
  about 40% of heavy and bursty traffic, so those rows are not a safe policy;
- the simulated HPA formula over-provisions strongly in these 300 s runs and is
  not the native Kubernetes HPA controller.

See `RESULTS.md` for the table and `results/RESULTS.md` for the authoritative
generated report.

## What is deliberately not claimed

- No physical power measurement, calibrated power curve, or Kepler result.
- No reproduction of Li et al. (2025). The full text was paywalled; only
  bibliographic metadata was verified through Crossref.
- No production or multi-node cluster evaluation. The cluster check is a
  single-node Minikube smoke validation with three repetitions per mode.
- No claim that the legacy `cpu_threshold` strategy is Kubernetes HPA.
- No claim that the simulated `hpa_formula` is the native HPA controller.
- No inferential use of the original 27-row dataset; it is nine deterministic
  cells copied three times.
- No claim that the dashboard shows live cluster data. It is a read-only view
  over committed/generated artifacts.

## Project structure

```text
flask-kubernetes/
  app.py                         Flask service, legacy routes, research APIs, dashboard
  controller.py                  Original demo controller (preserved, not the research model)
  eaes/                          Simulation package
    backend.py                   Simulated cluster and kubectl validation backend
    config.py                    YAML loading, hashing, git provenance, atomic writes
    energy.py                    Node-level energy model and pod attribution
    engine.py                    Paired experiment loop and raw tick logs
    forecast.py                  Holt and EWMA forecasters
    strategies.py                Five confirmatory strategies plus extension oracle
    workloads/                   Deterministic workload trace generation
  analysis/                      Statistics, diagnostics, extensions, plots
  experiments/                   Confirmatory, cluster, and extension runners
  configs/                       Experiment, simulation, energy, SLA, strategy YAML
  traces/                        Deterministic traces, including extension seeds
  data/                          Read-only copies of the original datasets
  results/                       Generated reports, tables, raw ticks, cluster records
  templates/research/            Three-page dashboard
  static/                        Dashboard CSS/JS and vendored Chart.js
  docs/                          Architecture, reproduction, testing, extensions, limits
  kubernetes/                    Deployment, service, HPA, namespace manifests
  scripts/                       Document validation and clean-checkout reproduction
```

## Quick start

Requirements: Python 3.11+ (tested on 3.11.9), Flask 3.1.3, PyYAML 6.0.3.
The simulation, analysis, and tests are standard-library based apart from Flask
and PyYAML. They do not require Docker or Kubernetes.

```powershell
python -m pip install -r requirements.txt
$env:ENERGY_AWARE_NO_BG='1'
python -m pytest -q
python app.py
```

Open `http://127.0.0.1:5000/`. Main pages:

- `/` - results dashboard, workload/strategy/seed filters, time series,
  energy-versus-drop comparison, tables, and cluster validation;
- `/eaes-diagnostics` - EAES decomposition, controller trace, actual versus
  forecast, scaling history, rule counts, and ablations;
- `/methodology` - architecture, execution flow, workload generation, metrics,
  energy estimator, Kubernetes integration, APIs, and limitations.

Legacy HTML URLs (`/autoscaling-comparison`, `/energy-analysis`,
`/performance-analysis`, `/experiment-explorer`, `/research-methodology`) return
HTTP 200 compatibility views. Existing JSON APIs are preserved;
`/api/v1/experiments` still serves the original 27 records from `data/`.

## Reproduce

Default mode reuses the preserved confirmatory raw run and regenerates derived
tables, charts, diagnostics, and tests. It does not silently invent a new run.

```powershell
# Verify protected dataset hashes, regenerate tables/charts, run tests, validate docs.
.\reproduce.ps1
```

```bash
./reproduce.sh
```

Options:

```powershell
.\reproduce.ps1 -Rerun        # run the 300 paired simulations again
.\reproduce.ps1 -Extensions   # also regenerate oracle/startup/30-seed/sensitivity
.\reproduce.ps1 -SkipTests
```

To reproduce in a disposable clone and compare every committed derived artifact:

```powershell
.\scripts\clean_checkout_reproduction.ps1
```

The report is written to `results/extension/clean_checkout/REPRODUCTION_REPORT.txt`.
The original working tree is not modified. See `docs/REPRODUCIBILITY.md`.

## Documentation map

| Document | Content |
|---|---|
| `METHODOLOGY.md` | Confirmatory design, strategies, workloads, metrics, energy model, statistics |
| `RESULTS.md` | Confirmatory results with generated tables and paired comparisons |
| `LIMITATIONS.md` | Consolidated limitations and threats to validity |
| `docs/ARCHITECTURE.md` | Components, data flow, APIs, storage, execution modes |
| `docs/EXECUTION_GUIDE.md` | Install, run, dashboard, experiments, tests, Docker, cluster |
| `docs/DASHBOARD_GUIDE.md` | Page-by-page dashboard guide and data definitions |
| `docs/TESTING.md` | Test catalog, commands, and isolation rules |
| `docs/EXTENSIONS.md` | Oracle, startup sweep, 30 seeds, sensitivity, Pareto, forecast, HPA replay |
| `docs/REVERSAL_EXPLANATION.md` | Why old energy numbers reversed and what changed |
| `docs/KUBERNETES_VALIDATION.md` | Real cluster validation, native HPA replay, and limits |
| `docs/REPRODUCIBILITY.md` | Reproduction and clean-checkout workflow |
| `docs/verification_log.txt` | Commands, hashes, test runs, and verification evidence |
| `AUDIT.md` | Original defects and dataset audit |
| `ANALYSIS_PLAN.md` | Frozen analysis plan |
| `docs/FINAL_REPORT.md` | Earlier phase report; not the final submission report |

## Real-cluster validation

The validation was performed on a single-node Minikube cluster:

```powershell
minikube start --driver=docker --cpus=2 --memory=4096
minikube addons enable metrics-server
minikube image build -t flask-k8s-demo:latest .
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -n energy-aware-dev -f kubernetes/deployment.yaml -f kubernetes/service.yaml
kubectl apply -f kubernetes/hpa.yaml -n energy-aware-dev
kubectl port-forward -n energy-aware-dev svc/energy-aware-service 5001:5000
python -m experiments.run_cluster_validation --repetitions 3 --duration 60 --rate 80
```

Three static and three native-HPA repetitions were recorded. All 4,731-4,890
offered requests were served per run, p95 latency was 29.3-32.7 ms, and the
native HPA was observed at four replicas after an unobserved 1->4 scale-up.
Energy per served request in the cluster table is modelled from node CPU and is
dominated by the 150 W idle term; it is not a hardware measurement. See
`docs/KUBERNETES_VALIDATION.md`.

## Provenance

- Protected dataset hashes:
  - `experiment_results_v2.json`:
    `6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E`
  - `experiment_results.json`:
    `C4BF4BFFFA8D0242395D2A2FB966C16DBC4884078BE7E82395E778EF87968451`
- The confirmatory run directory is preserved as generated and is verified
  against its manifest and trace hashes.
- Extension outputs live under `results/extension/` and are labelled
  exploratory. They are never pooled with the confirmatory tables.

## License / attribution

This is a research/teaching artifact. It is EAES-inspired but does not reproduce
Li et al. (2025). See `docs/RELATED_WORK.md` for the limited verified metadata.

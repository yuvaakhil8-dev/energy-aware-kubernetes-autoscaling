# Energy-Aware Autoscaling: Reproducible Research Build

This repository is a research rebuild of a Flask/Kubernetes autoscaling demonstration. It now contains a configurable discrete-time simulation, five explicitly separated scaling strategies, a node-level energy model, paired statistical analysis, a three-page dashboard, and a separate real-Minikube/HPA validation.

**All simulation energy is modelled, not measured.** The real-cluster validation contains real replica counts and request outcomes, but its energy column is also modelled from measured node CPU, not from a power meter.

## Current evidence

| Item | Value |
|---|---|
| Confirmatory run | `v3_paired_20261025T220942Z` |
| Execution mode | `simulation` |
| Design | 6 workloads × 10 seeds × 5 strategies = 300 runs |
| Simulated duration | 300 s per run, 5 s control interval, 30 s warm-up excluded |
| Run git commit | `431810fd8daa3cfd7dceaf11acb18dd6b14ea0ea` |
| Tracked working tree at run | clean (`git_tracked_dirty: false`) |
| Tests | 91 passing at the documentation checkpoint; see `results/test_report.txt` |
| Statistically planned α | 0.05, paired by seed, Holm correction |
| Real cluster | Single-node Minikube v1.39.0 / Kubernetes v1.37.0, Docker driver |

Key result in one paragraph: in this simulation, EAES has lower energy per served request than the simulated HPA formula in steady, medium, heavy, variable, and bursty workloads, and equal energy in the light workload. It also provisions fewer replica-hours. The advantage is not free: reactive EAES has SLA violations on the variable workload (mean `0.0119`) and bursty workload (mean `0.0170`) while the HPA formula has none, and the forecasting variant removes the variable-workload violations at a higher energy cost. Static replicas are the lowest or tied-lowest energy choice on steady, light, medium, and variable load because three replicas cover those traces, but static drops about 40% of heavy/bursty traffic and is not a safe general policy. See `results/RESULTS.md` and `results/EAES_DIAGNOSTIC.md`.

## What is deliberately not claimed

- No physical power measurement. Kepler or an external meter was not available.
- No reproduction of Li et al. (2025). The full text was paywalled; only bibliographic metadata was verified through Crossref.
- No production multi-node cluster evaluation. Phase 7 is a single-node Minikube validation.
- No claim that the legacy `cpu_threshold` strategy is Kubernetes HPA.
- No use of the original 27-row dataset for inferential statistics. It contains nine deterministic cells copied three times.

## Project structure

```text
flask-kubernetes/
├── app.py                       # Flask service, preserved APIs, three-page dashboard
├── controller.py                # Original demo controller (preserved)
├── eaes/                        # Simulation package
│   ├── backend.py               # SimulatedCluster and kubectl validation backend
│   ├── config.py                # YAML loading, hashing, provenance helpers
│   ├── energy.py                # Node-level energy model and pod attribution
│   ├── engine.py                # Paired experiment loop and raw tick logs
│   ├── forecast.py              # Holt and EWMA forecasters
│   ├── strategies.py            # Five scaling strategies
│   └── workloads/               # Deterministic workload trace generation
├── analysis/                    # Statistics and EAES diagnostics
├── experiments/                 # Full run and real-cluster validation entry points
├── configs/                     # Experiment, simulation, energy, SLA, strategy YAML
├── traces/                      # Deterministic per-workload/per-seed traces
├── data/                        # Byte-identical read-only copies of original datasets
├── results/                     # Generated tables, reports, raw tick logs, cluster logs
├── templates/research/          # Three-page dashboard
├── static/research.css/js       # Dashboard assets
├── docs/                        # Methodology, validation, provenance, final report
└── kubernetes/                  # Deployment, service, HPA manifests
```

## Quick start

```powershell
cd "C:\Users\yuvaa\OneDrive\Desktop\Documents\Default Project\flask-kubernetes"
python -m pip install -r requirements.txt
$env:ENERGY_AWARE_NO_BG='1'
python -m pytest -q
python app.py
```

Open `http://127.0.0.1:5000/`. The three main pages are:

- `/` — paired results
- `/eaes-diagnostics` — decomposition, forecasting ablation, control-rule evidence
- `/methodology` — assumptions, config values, hashes, limitations

Legacy HTML URLs (`/autoscaling-comparison`, `/energy-analysis`, `/performance-analysis`, `/experiment-explorer`, `/research-methodology`) still return HTML 200 as compatibility views. Existing JSON APIs are preserved; `/api/v1/experiments` still serves the original 27 records from `data/`.

## Reproduce the research

```powershell
# 1. Rebuild deterministic traces and run all 300 paired simulations.
python -m experiments.run_v3

# 2. Generate descriptive statistics, bootstrap CIs, paired tests, Friedman/Nemenyi,
#    forecast evaluation, and low/nominal/high + PUE sensitivity tables.
python -m analysis.analyze

# 3. Recompute the EAES diagnostic directly from raw per-tick JSONL logs.
python -m analysis.diagnose

# 4. Full test suite.
$env:ENERGY_AWARE_NO_BG='1'
python -m pytest -q
```

`reproduce.ps1` and `reproduce.sh` wrap these steps. The run is deterministic for a fixed config and seed set; the run manifests record the config hashes, trace index, Python/package versions, git commit, and whether tracked files were dirty.

## Real-cluster validation

The separate validation used:

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

Results: 3 static repetitions and 3 native-HPA repetitions, all requests served at 80 req/s in the validation window, with HPA scaling from 1 replica to 4. See `results/cluster_validation/CLUSTER_VALIDATION.md` and `docs/CLUSTER_ENVIRONMENT.md`. This validation is not the paired experiment and does not validate the simulation's energy ranking.

## Documentation map

| Document | Content |
|---|---|
| `AUDIT.md` | Original defects, preserved assets, dataset audit |
| `docs/PROJECT_REVIEW_AND_PLAN.md` | Phase 0 plan and acceptance criteria |
| `ANALYSIS_PLAN.md` | Frozen pre-registered analysis plan |
| `docs/METHODOLOGY.md` | Research design and modelling assumptions |
| `docs/SIMULATION_MODEL.md` | Queue, capacity, startup, latency model |
| `docs/ENERGY_MODEL.md` | Power model, PUE, attribution, limitations |
| `docs/STRATEGIES.md` | Exact decision rules for all five strategies |
| `docs/EXPERIMENT_PROTOCOL.md` | Paired execution protocol and windows |
| `docs/STATISTICAL_ANALYSIS.md` | Tests, corrections, effect sizes, software implementation |
| `docs/RESULTS_AND_INTERPRETATION.md` | Results narrative and guardrails |
| `docs/FAILURE_ANALYSIS.md` | Where EAES fails and why |
| `docs/THREATS_TO_VALIDITY.md` | Construct, internal, external, conclusion threats |
| `docs/KUBERNETES_VALIDATION.md` | Real-cluster validation record |
| `docs/DATA_PROVENANCE.md` | Original data hashes and pseudo-replication |
| `docs/REPRODUCIBILITY.md` | Exact commands, versions, artifact layout |
| `docs/TESTING.md` | Test inventory and results |
| `docs/DASHBOARD.md` | Dashboard pages, APIs, compatibility routes |
| `docs/RELATED_WORK.md` | Verified related work and positioning |
| `docs/RESEARCH_CONTRIBUTIONS.md` | What is new and what is not |
| `docs/LIMITATIONS.md` | Consolidated limitations |
| `docs/FINAL_REPORT.md` | 20-section final report |
| `docs/CLUSTER_ENVIRONMENT.md` | Minikube/metrics-server environment |
| `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md` | Container smoke test record |

## Original datasets

The originals remain outside the repository and were not modified:

- `experiment_results_v2.json` — SHA-256 `6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E`
- `experiment_results.json` — SHA-256 `C4BF4BFFFA8D0242395D2A2FB966C16DBC4884078BE7E82395E778EF87968451`

`data/` contains byte-identical copies so the legacy API works in a fresh clone and inside the container. The 27-row v2 file is not independent evidence; see `docs/DATA_PROVENANCE.md`.

## License and attribution

The original application code is preserved from the student project baseline. The research additions are provided for academic inspection. Li et al. (2025), *Energy-aware elastic scaling algorithm for microservices in Kubernetes clouds*, DOI `10.1016/j.jnca.2025.104218`, is cited as related work only; this repository does not claim to reproduce it.

# Architecture

This document describes the implemented system, not a proposed architecture. The
project deliberately separates the confirmatory simulation, the analysis
pipeline, the dashboard read path, the real-cluster validation, and exploratory
extensions.

## 1. Component map

```text
                    +-------------------------------+
                    |  Flask app (app.py)           |
                    |  - 3 research pages           |
                    |  - legacy HTML compatibility  |
                    |  - preserved JSON APIs        |
                    |  - demo workload endpoints    |
                    +---------------+---------------+
                                    |
                    reads generated artifacts (read-only)
                                    |
        +---------------------------+---------------------------+
        |                           |                           |
  results/tables/*.csv      results/runs/<run>/*.jsonl    results/cluster_validation/
        |                           |                           |
  analysis/make_headline_table  eaes/engine.py            experiments/run_cluster_validation.py
  analysis/diagnose             eaes/strategies.py         eaes/backend.py (kubectl)
  analysis/forecast_accuracy    eaes/energy.py             Kubernetes / Minikube
  analysis/energy_*             eaes/workload.py
  analysis/hpa_replay
```

## 2. Layered responsibilities

| Layer | Code / path | Responsibility |
|---|---|---|
| Flask application | `app.py` | Three-page dashboard, preserved routes, research APIs, demo endpoints |
| Configuration and provenance | `eaes/config.py`, `configs/*.yaml` | Validated YAML, canonical hashes, git state, atomic JSON writes |
| Workload generation | `eaes/workload.py`, `traces/` | Six deterministic traces per seed with SHA-256 trace hashes |
| Simulation backend | `eaes/backend.py` | Bounded queue, pod capacity, node placement, startup delay, accounting |
| Autoscaling engine | `eaes/strategies.py`, `eaes/forecast.py` | Five confirmatory controllers plus extension oracle and forecasters |
| Energy estimator | `eaes/energy.py` | Node-level idle/dynamic power, PUE, pod attribution, conservation check |
| Experiment engine | `eaes/engine.py`, `experiments/run_v3.py` | Paired runs, raw JSONL ticks, summaries, manifest |
| Confirmatory analysis | `analysis/analyze.py`, `analysis/make_headline_table.py` | Descriptive intervals, paired effects, Friedman/Nemenyi, headline tables |
| Diagnostics | `analysis/diagnose.py` | EAES decomposition, rule evidence, forecast ablation from raw ticks |
| Extensions | `experiments/run_extensions.py`, `analysis/energy_sensitivity.py`, `analysis/energy_vs_drop.py`, `analysis/forecast_accuracy.py`, `analysis/hpa_replay.py` | Exploratory evidence under `results/extension/` and labelled tables |
| Cluster validation | `experiments/run_cluster_validation.py`, `kubernetes/` | Real Minikube observations with modelled energy |
| Dashboard assets | `templates/research/`, `static/research.css`, `static/research.js`, `static/vendor/chart.umd.min.js` | Three-page UI and local Chart.js |
| Verification | `tests/`, `scripts/validate_docs.py`, `scripts/clean_checkout_reproduction.ps1` | Test suite, document reference check, clean-clone comparison |

## 3. Data flow: confirmatory run

1. `experiments/run_v3.py` loads `configs/experiment.yaml`,
   `simulation.yaml`, `energy.yaml`, `sla.yaml`, and `strategies.yaml`.
2. `eaes/workload.py` generates or loads deterministic traces and records their
   SHA-256 hashes.
3. For each workload x seed x strategy, `eaes/engine.py` runs the same trace
   through the selected controller for 300 simulated seconds.
4. Each 5 s tick writes one JSONL row: observed/offered/served/dropped requests,
   CPU, ready/desired/pending replicas, backlog, latency, modelled energy,
   scaling action, rule, reason, forecast, SLA margin, and decision details.
5. The run directory contains `manifest.json`, `summary.json`, and one JSONL per
   workload/seed/strategy. The manifest records config hashes, trace hashes, git
   commit, dirty state, package versions, execution mode, and energy scenario.
6. `analysis/analyze.py --run-dir <dir>` aggregates ticks to run-level metrics,
   generates tables, and delegates the authoritative headline report to
   `analysis/make_headline_table.py`.
7. `analysis/diagnose.py` recomputes the EAES diagnostic from raw ticks.
8. The dashboard reads the generated tables and raw logs. It does not re-run the
   experiment.

## 4. Dashboard read path

### Pages

- `/` - results.
- `/eaes-diagnostics` - controller trace and decomposition.
- `/methodology` - architecture, execution flow, config, APIs, limitations.

### Research APIs

| Route | Backing data |
|---|---|
| `/api/v1/research/results` | Run manifest, summaries, headline/descriptive/paired tables, cluster aggregate |
| `/api/v1/research/diagnostic` | `results/diagnostic.json` and diagnostic tables |
| `/api/v1/research/timeseries?workload=&strategy=&seed=` | Raw JSONL for one seed, or a tick-wise mean over all seeds |
| `/api/v1/research/controller-trace?workload=&strategy=&seed=` | Final controller state, decision, reason, cooldown status, scaling history, actual vs forecast |
| `/api/v1/research/methodology` | Configs, architecture metadata, hashes, limitations |
| `/api/v1/research/cluster` | Cluster validation manifest and aggregate |
| `/api/v1/research/tables/<name>` | Whitelisted generated CSV as JSON |

Invalid filters return HTTP 400 with an `error` field. The seed selector is
explicit: one real run, or `all` for a tick mean. The mean is not an extra
independent observation.

### Preserved compatibility

Existing HTML routes (`/autoscaling-comparison`, `/energy-analysis`,
`/performance-analysis`, `/experiment-explorer`, `/research-methodology`) return
HTTP 200 compatibility views. Existing JSON routes such as `/api/status`,
`/health`, `/ready`, `/info`, `/workload/status`, `/status`,
`/controller/status`, and `/api/v1/experiments` remain available. The legacy
`/api/v1/experiments` serves the original 27-row dataset and is not research
evidence.

## 5. Execution modes

| Mode | What is real | What is modelled | Used for |
|---|---|---|---|
| `simulation` | Deterministic traces and controller code | Replicas, queue, latency, energy | All confirmatory results |
| `kubernetes_validation` | Pods, Service, HTTP requests, node CPU, native HPA decisions | Energy from node CPU | Separate smoke validation only |
| `dashboard` | Generated artifacts | Nothing live | Read-only presentation |

These modes are never merged into one ranking. The HPA formula in the simulation
is not the native HPA controller.

## 6. Storage and provenance

```text
results/runs/v3_paired_20261025T220942Z/
  manifest.json          # immutable provenance
  summary.json           # 300 run-level summaries
  <workload>_seed<N>_<strategy>.jsonl
results/tables/
  headline.csv/.md
  paired_headline.csv
  descriptive.csv, paired.csv, friedman.csv, nemenyi.csv
  forecasting.csv, sensitivity.csv
  forecast_accuracy.csv/.md, forecast_accuracy_summary.csv
results/extension/
  oracle/, startup_sweep/, seed30/, energy_sensitivity/, energy_vs_drop/, hpa_replay/
results/cluster_validation/
  manifest.json, summary.json/csv, per-request JSONL
```

- Protected input datasets are copied byte-for-byte into `data/` and verified by
  `analysis/verify_dataset_hashes.py`.
- The confirmatory run is preserved; analysis writes derived artifacts only.
- Each extension has a manifest with `label`, `confirmatory_run_unchanged`,
  `git_commit`, and `git_tracked_dirty`.
- The extension config is separate (`configs/extensions.yaml`) so adding the
  oracle does not change the confirmatory strategy-config hash.

## 7. Error handling and invariants

- YAML loading validates duration/interval compatibility, replica bounds,
  utilisation thresholds, power scenarios, and strategy blocks.
- Trace hashes are checked; a mismatched trace is not accepted as paired
  evidence.
- Energy values are null when there are no served requests. No artificial
  denominator is used.
- Node/pod energy conservation error is recorded and checked.
- Invalid dashboard filters return 400 rather than silently substituting a
  different run.
- `scripts/validate_docs.py` checks required files and local references.
- `scripts/clean_checkout_reproduction.ps1` clones the branch, runs the
  reproduction, compares generated artifacts by SHA-256, and writes a report.

## 8. Dependency boundary

The simulation and analysis are standard-library Python plus PyYAML and Flask on
the web side. The installed Python `kubernetes` package is broken in the local
environment, so the real backend uses `kubectl` subprocesses. The cluster path is
therefore operational but not part of the pytest suite.

See `METHODOLOGY.md`, `docs/EXECUTION_GUIDE.md`, and
`docs/DASHBOARD_GUIDE.md` for the corresponding workflows.

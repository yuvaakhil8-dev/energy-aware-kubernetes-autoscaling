# Reproducibility

## 1. What can be reproduced

- The 300-run paired simulation from fixed configs and seeds.
- All descriptive statistics, bootstrap intervals, paired tests,
  Friedman/Nemenyi tables, forecast evaluation, and sensitivity tables.
- The raw per-tick logs.
- The three-page dashboard and preserved API surface.
- The 112-test suite.
- The separate Minikube/HPA validation if Docker Desktop and Minikube are
  available.

The simulation and analysis do not require Docker or Kubernetes. The cluster
validation does.

## 2. Preserved confirmatory run

```text
run_id:            v3_paired_20261025T220942Z
git_commit:        431810fd8daa3cfd7dceaf11acb18dd6b14ea0ea
git_tracked_dirty: false
execution_mode:    simulation
n_runs:            300
energy_scenario:   nominal
python:            3.11.9
Flask:             3.1.3
PyYAML:            6.0.3
pytest:            8.3.3
```

Do not overwrite `results/runs/v3_paired_20261025T220942Z/`. `-Rerun` creates a
new run id and updates `results/latest_run.json`; it does not delete the old run.

## 3. Protected input hashes

Verified by `analysis/verify_dataset_hashes.py`:

```text
data/experiment_results_v2.json
6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E

data/experiment_results.json
C4BF4BFFFA8D0242395D2A2FB966C16DBC4884078BE7E82395E778EF87968451
```

The original workspace files are also checked when present. A mismatch is a
hard failure, not a warning.

## 4. Default reproduction

```powershell
.\reproduce.ps1
```

or:

```bash
./reproduce.sh
```

Default behavior:

1. check Python and dependencies;
2. load and validate YAML;
3. verify protected hashes;
4. reuse the preserved run;
5. regenerate `results/RESULTS.md` and `results/tables/headline.csv` /
   `paired_headline.csv`;
6. regenerate descriptive and paired tables and the diagnostic;
7. regenerate forecast-accuracy tables;
8. regenerate six Pareto SVGs;
9. replay recorded native-HPA samples;
10. run the full test suite;
11. validate documents and references;
12. print a summary and any working-tree changes.

Expected non-byte-identical outputs after a default run:

- `results/analysis_manifest.json` - `analyzed_at` timestamp and possibly the
  analysis commit;
- `results/diagnostic.json` - generation timestamp;
- extension `manifest.json` files if regenerated - `started_at`/`created_at`.

The clean-checkout comparison excludes the analysis manifest and compares the
substantive tables, reports, SVGs, and replay outputs.

## 5. Options

```powershell
.\reproduce.ps1 -Rerun        # rerun 300 simulations under a new run id
.\reproduce.ps1 -Extensions   # regenerate oracle/startup/30-seed/sensitivity
.\reproduce.ps1 -SkipTests
```

`-Extensions` is intentionally optional: it is exploratory and takes longer.

## 6. Determinism

- Traces are generated deterministically from workload/seed/config and hashed.
- Strategies are deterministic; forecasts update online.
- `hpa_formula` uses a fixed tolerance and stabilization rule.
- Bootstrap resampling uses fixed stable seeds derived from workload, strategy,
  baseline, and metric.
- The run summary preserves the exact git commit and dirty state.
- Analysis tables are regenerated from the same raw summaries and raw ticks.

If the tracked tree is dirty when `experiments.run_extensions` runs, its manifests
will honestly record `git_tracked_dirty: true`. Re-run from a clean tree if you
need a clean extension manifest. Untracked generated outputs do not count as
dirty.

## 7. Clean-checkout comparison

```powershell
.\scripts\clean_checkout_reproduction.ps1
```

The script:

1. clones the current branch into `%TEMP%` (original tree untouched);
2. hashes committed derived artifacts;
3. runs `reproduce.ps1 -SkipTests` in the clone;
4. runs the test suite in the clone;
5. re-hashes generated artifacts;
6. records matches, differences, missing files, git status, and exit codes;
7. writes `results/extension/clean_checkout/REPRODUCTION_REPORT.txt`.

It exits non-zero on a substantive mismatch or failed test. See
`docs/verification_log.txt` for the latest run.

## 8. Environment notes

- The repository is on Windows; paths use `C:\...`.
- The simulation is standard-library Python plus PyYAML.
- Chart.js is vendored locally; dashboard charts do not require a CDN.
- The Python `kubernetes` package is broken locally; the real backend uses
  `kubectl`.
- Docker Desktop/Minikube were unavailable at final verification time, so no
  new cluster repetitions were run.
- Raw confirmatory JSONL logs are included in the Docker image because the
  dashboard APIs read them. Cluster per-request logs are excluded.

## 9. Failure handling

If a reproduction step fails:

1. read the console output and `results/extension/clean_checkout/*.txt`;
2. check config hashes and the preserved run manifest;
3. check protected hashes;
4. inspect `results/analysis_manifest.json` for the run dir;
5. re-run with `-SkipTests` to isolate analysis vs tests;
6. do not hand-edit a generated table to make the comparison pass.

## 10. What is not reproducible here

- The exact Minikube host VM state (Docker Desktop/WSL kernel).
- Physical power measurements (none exist).
- The full text of Li et al. (2025) (paywalled; only metadata verified).
- A production multi-node cluster.

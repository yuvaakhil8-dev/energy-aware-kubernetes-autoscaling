# Data Provenance

## 1. Rule

The original datasets are **read-only evidence**. They were hashed before the rebuild and again after; neither the originals nor the tracked copies were edited. No result in the new research run is derived from the original 27-row file.

## 2. Original files (outside the repository)

| File | Records | SHA-256 |
|---|---:|---|
| `..\experiment_results_v2.json` | 27 | `6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E` |
| `..\experiment_results.json` | 18 | `C4BF4BFFFA8D0242395D2A2FB966C16DBC4884078BE7E82395E778EF87968451` |
| `..\experiment_execution_log.json` | — | `B099C16AF1579DD0168CFF5FF653D892B6D714423B4EA1364830A7A1C9499F62` |

These paths are one level above `flask-kubernetes/`. The files were not modified by the rebuild.

## 3. Tracked byte-identical copies

So that a fresh clone and the Docker image keep the legacy API working, `data/` contains copies:

| File | SHA-256 |
|---|---|
| `data/experiment_results_v2.json` | `6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E` |
| `data/experiment_results.json` | `C4BF4BFFFA8D0242395D2A2FB966C16DBC4884078BE7E82395E778EF87968451` |
| `data/experiment_execution_log.json` | `B099C16AF1579DD0168CFF5FF653D892B6D714423B4EA1364830A7A1C9499F62` |

`tests/test_app.py::test_app_local_dataset_copies_are_byte_identical` checks the two result datasets. `tests/test_app.py::test_loader_uses_app_local_copies` checks that the loader can operate with only the app-local copies.

The loader prefers the originals one level above the app and falls back to `data/`. In the container, only `data/` exists. This is why `/api/v1/experiments` returns 27 records inside the image.

## 4. What the 27-row dataset actually is

The audit (`docs/original_dataset_audit.txt`) shows:

- 3 strategies (`static`, `hpa`, `energy_aware`) × 3 workloads (`light`, `medium`, `heavy`) × 3 repetitions = 27 rows.
- All 9 strategy × workload cells have **three identical repetitions**.
- No seed field in any row.
- No raw samples in any row.
- Execution mode is `simulation` in all 27 rows.

Therefore the effective sample size is 9 deterministic cells, not 27 independent observations. The repetitions are copies, not replicates. Any confidence interval or significance test computed as if `n = 27` would be pseudo-replication.

The original energy numbers also use inconsistent denominators and are not comparable across strategies. Examples from the audit:

| Workload | Static | HPA (toy rule) | Energy-aware |
|---|---:|---:|---:|
| light | 37.50 | 7.50 | 24.89 |
| medium | 13.75 | 2.75 | 36.50 |
| heavy | 7.25 | 1.45 | 48.11 |

These values are recorded for provenance, not used as evidence.

## 5. What the new run uses

The confirmatory run uses newly generated traces and new raw logs:

- run `v3_paired_20261025T220942Z`;
- 300 summaries in `results/runs/v3_paired_20261025T220942Z/summary.json`;
- 300 per-tick JSONL files in the same directory;
- manifest with config hashes, trace index, versions, git commit, and `git_tracked_dirty`;
- `results/latest_run.json` points at this run.

The original files are not inputs to `experiments/run_v3.py`, `analysis/analyze.py`, or `analysis/diagnose.py`.

## 6. Integrity checks

```powershell
$parent = 'C:\Users\yuvaa\OneDrive\Desktop\Documents\Default Project'
$root = Join-Path $parent 'flask-kubernetes'
Get-FileHash "$parent\experiment_results_v2.json", "$parent\experiment_results.json" -Algorithm SHA256
Get-FileHash "$root\data\experiment_results_v2.json", "$root\data\experiment_results.json" -Algorithm SHA256
$env:ENERGY_AWARE_NO_BG='1'
python -m pytest -q
```

Expected: matching hashes and a passing test that asserts the tracked copies are byte-identical.

## 7. Retention

- The originals remain outside Git, untouched.
- The tracked copies are in Git so the app and image are self-contained.
- `archive/` is ignored by Git and was used for pre-rebuild originals during the rebuild; it is not part of the final evidence chain.
- Raw simulation logs are kept in `results/runs/` for audit, but are excluded from Docker images by `.dockerignore` to keep the image small.

## 8. Known provenance gap

The first full run `v3_paired_20261025T212043Z` was produced while two diagnostic fields (`ready_replicas_after`, `pending_replicas_after`) were present in the working tree but not yet committed. The confirmatory run was therefore repeated as `v3_paired_20261025T220942Z` from clean commit `431810f` with `git_tracked_dirty: false`. The metrics are deterministic and match; the newer run is the one referenced everywhere. This gap is recorded rather than hidden.

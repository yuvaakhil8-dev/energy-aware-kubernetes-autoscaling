# AUDIT — Original Project Condition (Pre-Rebuild)

**Date:** 2026-10-26
**Project:** `flask-kubernetes`
**Branch:** `research-rebuild` (baseline commit `c5ec94d` on `pre-rebuild-snapshot`)
**Scope:** read-only audit of the application, controller, experiments, datasets, tests, and manifests.

---

## 1. Location verification

| Check | Result |
|---|---|
| Working directory | `...\Default Project\flask-kubernetes` |
| OneDrive project confirmed | Yes |
| `OneRoad` duplicate used | **No** |
| Git repository before rebuild | None (initialized in Phase 0) |
| Python | 3.11.9 |
| Flask | 3.1.0 |
| OS | Windows (win32) |
| Global packages relevant | `yaml`, `numpy`, `matplotlib`, `kubernetes`, `flask`, `pytest` present; `pandas`, `scipy` absent |
| Repository venv | `flask-kubernetes/venv/` exists (ignored by Git) |

---

## 2. Project inventory

### 2.1 Python modules

| File | Role |
|---|---|
| `app.py` | Flask application; 6 dashboard routes, 13 JSON/monitoring routes, dataset loader, workload state |
| `controller.py` | 881-line controller, metrics collector, legacy energy model, K8s client probe (stub) |
| `experiments/run_experiment.py` | Legacy 18-experiment deterministic simulation runner |
| `experiments/run_experiment_v2.py` | 27-record runner wrapper; fills missing fields with defaults |
| `live_demo.py` | Demo script |
| `test_endpoint.py` | Standalone endpoint script; pre-existing syntax error |
| `workloads/profile_generator.py` | Workload profiles |
| `analysis/audit_original_dataset.py` | New read-only dataset audit (Phase 0) |

### 2.2 Routes

HTML: `/`, `/autoscaling-comparison`, `/energy-analysis`, `/performance-analysis`, `/experiment-explorer`, `/research-methodology`.

JSON/monitoring: `/api/status`, `/health`, `/ready`, `/info`, `/workload/status`, `/workload/change` (POST), `/cpu/light`, `/cpu/intensive`, `/metrics`, `/api/v1/experiments`, `/api/v1/research-papers`, `/status`, `/controller/status`.

### 2.3 Templates / static

`templates/base.html`, `templates/dashboard/*.html` (6 pages + 404/500), `static/dashboard.css`, `static/dashboard.js`.

### 2.4 Experiments / datasets

- `experiment_results_v2.json` — 27 records (3 strategies × 3 workloads × 3 repetitions).
- `experiment_results.json` — 18 legacy records.
- `experiment_execution_log.json` — execution log.
- `scaling_decisions.csv` — controller decision log.

### 2.5 Deployment

`Dockerfile`, `.dockerignore`, `kubernetes/{namespace,deployment,service,configmap,hpa}.yaml`.

### 2.6 Tests

`tests/test_app.py` (9), `tests/test_controller.py` (12), `tests/test_dataset.py` (8) = **29 tests**.

---

## 3. Baseline test result

Command:

```powershell
$env:ENERGY_AWARE_NO_BG='1'
python -m pytest -q
```

Result: **29 passed in 0.55s**. Full output: `docs/test_status.txt`.

The suite verifies routes, basic controller decisions, legacy energy arithmetic, replica limits, cooldown, and dataset shape. It does **not** verify fair energy accounting, independent repetitions, a real HPA formula, a real cluster, or forecast accuracy.

---

## 4. Dataset audit

Script: `analysis/audit_original_dataset.py`. Output: `docs/original_dataset_audit.txt`.

| Fact | Value |
|---|---|
| v2 records | 27 |
| v2 SHA-256 | `6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E` |
| legacy records | 18 |
| legacy SHA-256 | `C4BF4BFFFA8D0242395D2A2FB966C16DBC4884078BE7E82395E778EF87968451` |
| factorial cells | 9 |
| cells with identical repetitions | **9/9** |
| records with a seed field | **0/27** |
| records with raw samples | **0/27** |
| execution mode | simulation (27/27) |

**Conclusion:** the 27 rows are **not 27 independent observations**. They are 9 deterministic cells copied three times. No statistical inference is valid on them.

Energy values by cell (J/request, as recorded — **not comparable** because denominators differ):

| Workload | Static | HPA | EAES |
|---|---:|---:|---:|
| Light | 37.50 | 7.50 | 24.89 |
| Medium | 13.75 | 2.75 | 36.50 |
| Heavy | 7.25 | 1.45 | 48.11 |

---

## 5. HPA misrepresentation audit

| Location | Existing wording | Problem |
|---|---|---|
| `app.py:79, 445` | `HPA`; "Kubernetes default Horizontal Pod Autoscaler" | The experiment baseline is a 1 s 65/35 rule, not Kubernetes HPA |
| `app.py:632` | `"energy_reduction_claim": "15.34% compared to default Kubernetes HPA"` | Unverified claim; not reproduced by this project |
| `controller.py:224` | "enhances the standard Kubernetes HPA feedback control method" | Overstates alignment with Li et al. |
| `templates/.../research_methodology.html:53` | "Mirrors Kubernetes HPA feedback control" | False equivalence |
| `experiments/run_experiment.py:107-184` | `run_hpa_mode` with 65/35 thresholds, 1 s loop | Toy rule; no tolerance, no stabilization window, CPU independent of replicas |

The rebuilt project separates:

- `CPUThresholdBaseline` (the old 80/30 rule, kept for continuity),
- `HPAFormulaBaseline` (Kubernetes replica formula with tolerance + stabilization),
- real Kubernetes HPA (only if Phase 7 cluster validation succeeds).

---

## 6. Energy-model audit

Existing model (`controller.py:98-151`):

```
P(u) = 30 + 50·u/100                 [W]
E = P·15                             [J]
E_req = E / N_success                [J/request]
```

Confirmed defects:

1. Constants are described as per-container power but are never multiplied by replicas; accounting boundary undefined.
2. Live controller uses a **cumulative** successful count, so `E_req` falls over time at constant power.
3. Zero requests yield `450 J/request` because `max(1, count)` is used (`/controller/status` evidence: 450.0 J at CPU 0).
4. Experiment runner passes `successful=5` per tick regardless of workload rate.
5. `energy_total = energy_per_req × 5` is an unexplained constant.
6. Static/EAES/HPA use different request denominators.
7. No PUE, memory, node-level accounting, or pod attribution.

---

## 7. Kubernetes backend audit

| Check | Result |
|---|---|
| `kubernetes` Python package | Installed globally |
| kubeconfig / in-cluster config | Not available to the app |
| `K8S_AVAILABLE` | False in practice; `/controller/status` reports `mode=simulated` |
| `_apply_scaling()` | Contains comment "In real K8s mode, call the API here"; **never calls the API** (`controller.py:676-688`) |
| Real deployment | **None**; manifests are static files only |

Environment probes (2026-10-26):

| Tool | Result |
|---|---|
| WSL | v3.0.3; Ubuntu distro present, **Stopped**; WSL2 |
| Docker client/server | 29.8.2; Docker Desktop Linux engine **responding** |
| kubectl | Client v1.36.1; no cluster context verified |
| minikube | Installed; profile "minikube" not found |
| kind | Not installed |

**Conclusion:** a real cluster attempt is feasible in Phase 7 via Minikube's Docker driver. It has **not** been attempted yet, and no deployment claim is made.

---

## 8. Confirmed vs. unconfirmed problems

| Problem | Status | Evidence |
|---|---|---|
| Identical repetitions / pseudo-replication | **Confirmed** | 9/9 cells identical |
| HPA baseline not real HPA | **Confirmed** | `run_experiment.py:107-184` |
| Ambiguous energy boundary | **Confirmed** | `controller.py:86-99`; no replica multiplication |
| Idle power charged at wrong granularity | **Confirmed** | 30 W per "container" but no `R` term |
| EAES energy higher under heavy load | **Confirmed in data, invalid as finding** | 48.11 vs 7.25 vs 1.45, different denominators |
| Throughput not consistently recorded | **Confirmed** | v2 records lack throughput; legacy has it |
| Inconsistent request denominators | **Confirmed** | `run_experiment.py:44, 219-226` |
| Real K8s implementation is a stub | **Confirmed** | `_apply_scaling` has no API call |
| Docker/WSL2 `0x40010004` blocker still present | **Not confirmed** | Docker server now responds; WSL Ubuntu stopped; no cluster tried |
| Prometheus operational | **NOT VERIFIED** | No instance probed |
| Kepler operational | **NOT VERIFIED** (excluded) | Windows host; no cluster |
| `test_endpoint.py` syntax error | **Confirmed** | Excluded via `pytest.ini`; to be archived/fixed |

---

## 9. Archival actions

Originals copied to `archive/pre-rebuild/`:

- `app.py`, `controller.py`, `requirements.txt`, `Dockerfile`, `README.md`, `pytest.ini`, `test_endpoint.py`
- `templates/`, `static/`, `tests/`, `kubernetes/`, `experiments/`
- `datasets/experiment_results_v2.json`, `datasets/experiment_results.json`, `datasets/experiment_execution_log.json`

The archive is excluded from Git via `.gitignore` but retained on disk.

---

## 10. Audit verdict

The original project is a **working Flask demo** with a **valid dashboard and APIs**, but its research claims are **not supported** by its data or code. The rebuild must replace the experiment engine, energy model, and baselines while preserving the working web application and the original datasets.

*End of audit.*

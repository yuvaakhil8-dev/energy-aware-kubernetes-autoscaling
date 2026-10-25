# Testing

## 1. Command

```powershell
cd "C:\Users\yuvaa\OneDrive\Desktop\Documents\Default Project\flask-kubernetes"
$env:ENERGY_AWARE_NO_BG='1'
$env:PYTHONIOENCODING='utf-8'
python -m pytest -q
```

`ENERGY_AWARE_NO_BG=1` suppresses the app’s background workload thread. The test suite does not require Docker, Minikube, network access, or a power meter.

## 2. Current result

**91 passed** at the documentation checkpoint.

Saved outputs:

| File | Tests | Purpose |
|---|---:|---|
| `results/test_report.txt` | 91 | Final full-suite report |
| `results/test_dashboard.txt` | 91 | Dashboard phase |
| `results/test_pre_rerun.txt` | 91 | Before confirmatory re-run |
| `results/test_phase7.txt` | 84 | Real-cluster backend phase |
| `results/test_phase6.txt` | 82 | Statistics phase |
| `results/test_phase1_4.txt` | 73 | Simulator/energy/strategy phases |

The original baseline suite was **29 passed** before the rebuild; its report is in `docs/test_status.txt`.

## 3. Inventory

| File | Tests | Focus |
|---|---:|---|
| `tests/test_app.py` | 16 | HTML routes, JSON APIs, dashboard payloads, table whitelist, cluster label, local data hashes, 404 |
| `tests/test_backend.py` | 11 | Backend interface, `kubectl` safety, CPU parsing, startup delay, scale-down, drops, zero-replica energy, conservation, latency, invalid input |
| `tests/test_controller.py` | 11 | Preserved original controller: power arithmetic, limits, scale decisions, cooldown, status shape |
| `tests/test_dataset.py` | 9 | Original 27-row dataset shape, factorial coverage, pseudo-replication flag, unchanged legacy data |
| `tests/test_energy_model.py` | 10 | Power curve, PUE/dt, invalid inputs, attribution conservation, zero denominators, scenarios, monotonicity |
| `tests/test_engine.py` | 6 | Trace/strategy reproducibility, shared trace hash, per-tick conservation, zero-request null, EAES vs static under heavy load, provenance fields |
| `tests/test_statistics.py` | 9 | Tied ranks, deterministic bootstrap, Wilcoxon cases, Holm, Cliff’s delta, chi-square df4, Friedman complete/incomplete blocks |
| `tests/test_strategies.py` | 13 | All five strategies: static, threshold hysteresis/warm-up, HPA formula tolerance/stabilization/metric outage, EAES safety, backlog, max replica, forecast, serialization |
| `tests/test_workload.py` | 6 | Trace validity/determinism, workload shapes, trace reuse/hash validation, config hash stability, bad scenario rejection |

Total: 91.

## 4. What the tests establish

### Application contract

- `/` is HTML and there is exactly one root endpoint.
- The three research pages and legacy compatibility pages return HTML 200.
- `/health`, `/ready`, `/api/status`, `/info`, `/workload/status`, `/metrics`, `/status`, `/controller/status`, `/api/v1/experiments`, `/api/v1/research-papers` respond with expected shapes.
- The six research endpoints return generated data, and the table endpoint rejects unknown names.
- Static CSS/JS assets are served.
- The dataset copies are byte-identical to the recorded SHA-256 values.
- The loader can operate from the app-local `data/` directory.
- Unknown routes return HTML 404, not a JSON surprise.

### Simulation correctness

- Scale-up is delayed by startup; scale-down is immediate in the backend.
- Capacity and drops are accounted for; zero replicas drop everything and use no energy.
- Node/pod energy is conserved within floating tolerance in every tick.
- Backlog increases latency.
- Invalid arrivals are rejected.
- The same trace and strategy are reproducible.
- All strategies use the same trace hash for a workload/seed.
- Zero-request denominators are null, not fabricated.

### Strategy rules

- Static stays at three.
- Threshold uses 80/30 with 5% hysteresis and warm-up suppression.
- HPA formula uses target, tolerance, +1/-1 behavior, stabilization, and metric-unavailable fallback.
- EAES scales up only to restore margin, scales down only when safe and stable, never with backlog, and respects bounds.
- Forecasting EAES consumes observations and produces serializable decisions.

### Statistics

- Average ranks handle ties.
- Bootstrap CI is deterministic and brackets the mean on the test case.
- Wilcoxon behaves for all-positive and small samples.
- Holm adjustment is monotone and capped at 1.
- Cliff’s delta reaches ±1 at separation.
- Chi-square df4 values are exact for the implemented formula.
- Friedman handles complete and incomplete blocks.

### Data and provenance

- The 27-row dataset has 27 unique IDs and full 3 × 3 × 3 factorial coverage.
- Repetitions are identical, and the pseudo-replication flag is set.
- No measured-energy claim is present.
- Legacy data hash is unchanged.

## 5. What is not covered by the automated suite

- A full 300-run experiment (too slow for a unit suite); it is a separate command.
- A Docker image build.
- A live Minikube/metrics-server test.
- A real Kubernetes HPA timing test.
- Network failures in the real-cluster backend beyond the missing-`kubectl` safety test.
- Physical power measurement.
- A production WSGI server.
- Multi-node scheduling and node failure.
- The paywalled Li et al. full text.

These are integration/environment checks, documented separately in `docs/KUBERNETES_VALIDATION.md` and `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md`.

## 6. Reproducing the test result

```powershell
$env:ENERGY_AWARE_NO_BG='1'
$env:PYTHONIOENCODING='utf-8'
python -m pytest -q 2>&1 | Tee-Object -FilePath results\test_report.txt
```

Expected tail:

```text
91 passed
```

If the count changes, update this document and the README rather than forcing the old number.

## 7. Test design notes

- Flask’s test client is session-scoped for speed.
- The app module is imported once; tests that mutate globals restore them via `monkeypatch`.
- No network calls are made by the suite; the `kubectl` backend is tested only for safe failure when `kubectl` is absent.
- Statistical functions are implemented without scipy to keep the environment small and the formulas inspectable.
- The original dataset tests are read-only and never rewrite the source files.

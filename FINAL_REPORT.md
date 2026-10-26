# Final Report

**Project:** Energy-aware autoscaling for containerised microservices  
**Repository:** `flask-kubernetes`  
**Branch:** `research-rebuild`  
**Verification code/evidence commit:** `1f8af3c`  
**Report date:** 2026-10-26  
**Working tree at report generation:** clean  
**Final test suite:** 113 passed  
**Document validation:** PASS (15 required files, 17 documents scanned)  
**Clean-checkout reproduction:** PASS (25/25 substantive artifacts byte-identical)

> All energy values in this project are modelled/estimated. No physical power
> measurement exists. The real-cluster validation has real replicas and request
> outcomes, but its energy column is also modelled from node CPU.

---

## 1. Preserved data and confirmatory run

**Status: COMPLETE**

- The original datasets are preserved byte-for-byte:
  - `data/experiment_results_v2.json`:
    `6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E`
  - `data/experiment_results.json`:
    `C4BF4BFFFA8D0242395D2A2FB966C16DBC4884078BE7E82395E778EF87968451`
- The confirmatory run is preserved without modification:
  - run ID: `v3_paired_20261025T220942Z`
  - 300 summaries and 300 raw JSONL files
  - `git_commit = 431810fd8daa3cfd7dceaf11acb18dd6b14ea0ea`
  - `git_tracked_dirty = false`
  - execution mode: `simulation`
  - energy scenario: `nominal`
- The original 27-row dataset remains an audit artifact only. Its nine cells are
  copied three times and are not used as independent inferential evidence.

## 2. Reversal and denominator repair

**Status: COMPLETE**

The old prototype reported static `7.25`, HPA `1.45`, and EAES `48.11`
J/request for heavy load. Those numbers were not on a common denominator:

- static/HPA-style values used fixed rate-derived request counts;
- EAES used a cumulative `successful_count`, so its per-request value fell every
  tick and the reported average was `48.1143`;
- zero-request handling used `max(1, count)`, producing an artificial value.

The rebuilt engine computes energy and outcomes on the same 5 s tick and
aggregates over the same measured window:

```text
energy_per_served  = sum(tick_energy) / sum(tick_served)
energy_per_offered = sum(tick_energy) / sum(tick_offered)
```

A zero-served case produces null, not a fabricated denominator. Energy per
served is always shown with energy per offered, drop rate, and SLA. The full
reconstruction is in `docs/REVERSAL_EXPLANATION.md`.

## 3. Five strategies plus Oracle

**Status: COMPLETE**

Implemented separately:

| Strategy | Role | Native Kubernetes HPA? |
|---|---|---|
| `static` | Fixed three replicas | No |
| `cpu_threshold` | Legacy 80/30 rule with hysteresis/cooldowns | No |
| `hpa_formula` | Simulated HPA replica formula | No; simulation only |
| `eaes` | SLA-first, lexicographic energy-aware controller | No; EAES-inspired |
| `forecasting_eaes` | EAES with Holt forecast | No; ablation |
| `oracle` | Perfect-foresight extension | No; not deployable |

The original toy HPA rule is preserved under the honest name `cpu_threshold`.
The simulated `hpa_formula` is never described as the native controller. Native
HPA is exercised only in the separate cluster validation.

## 4. Simulation engine and energy model

**Status: COMPLETE — MODELLED ENERGY ONLY**

- Deterministic discrete-time simulation.
- Bounded queue, ready/pending replicas, 10 s pod startup, 1–10 replicas.
- Four pods per node, 10 req/s per ready pod.
- 300 s run, 5 s control interval, 30 s warm-up excluded.
- One raw JSONL row per tick with requests, queue, replicas, CPU, latency,
  energy, decision, rule, reason, forecast, and SLA margin.
- Node energy:

```text
P_node(u) = P_idle + (P_max - P_idle) * u
E_node    = P_node(u) * dt * PUE
```

Nominal assumptions: `P_idle = 150 W`, `P_max = 500 W`, `PUE = 1.2`.
Node/pod energy conservation error is recorded (maximum observed `1.819e-12` J).
All values are model estimates, never hardware measurements.

## 5. Confirmatory experiment

**Status: COMPLETE**

- 6 workloads × 10 seeds × 5 strategies = **300 runs**.
- Workloads: steady, light, medium, heavy, variable, bursty.
- Identical trace per workload and seed across strategies.
- Traces are deterministic and SHA-256 hashed; ten distinct hashes per workload.
- Primary metrics aggregate 54 post-warm-up ticks to one run-level value.
- Manifest records config hashes, trace hashes, git state, package versions, and
  execution mode.

## 6. Statistical analysis

**Status: COMPLETE**

- Mean, median, standard deviation, and 95% bootstrap intervals.
- Paired by workload + seed, not by tick.
- Median paired difference with 5,000-resample bootstrap CI.
- Two-sided Wilcoxon signed-rank with a documented normal approximation.
- Holm adjustment within the pre-specified family.
- Cliff’s delta effect size.
- Five-second ticks are never treated as independent observations.
- Non-testable exact ties are marked `not testable`; no p-value is invented.

## 7. Confirmatory results

**Status: COMPLETE — DIRECTIONAL, NOT HOLM-SIGNIFICANT**

Mean estimated energy per served request (J):

| Workload | static | cpu_threshold | hpa_formula | eaes | forecasting_eaes |
|---|---:|---:|---:|---:|---:|
| steady | 22.58 | 22.58 | 30.70 | 22.58 | 22.58 |
| light | 46.72 | 46.72 | 46.72 | 46.72 | 46.72 |
| medium | 17.74 | 17.74 | 32.21 | 20.96 | 21.10 |
| heavy | 16.50 | 17.39 | 21.34 | 18.58 | 18.65 |
| variable | 21.87 | 21.87 | 44.55 | 23.02 | 26.83 |
| bursty | 21.11 | 23.03 | 30.45 | 29.46 | 29.46 |

Key readings:

- EAES has lower mean energy per served request than the simulated HPA formula
  in all six workloads by mean, and is exactly tied on light.
- EAES provisions fewer replica-hours than the HPA formula in every workload.
- EAES has small SLA violation rates on variable (`0.0119`) and bursty
  (`0.0170`); forecasting removes the variable violations but costs more energy
  there (`26.83` vs `23.02`).
- Static has low energy per served request on heavy/bursty only because it drops
  about 38–40% of offered traffic. Heavy static SLA violation rate is `1.0000`.
- **No EAES-vs-HPA energy comparison is Holm-significant at α = 0.05 with ten
  confirmatory seeds.** Medium/heavy/variable/bursty median CIs exclude zero and
  Cliff’s delta is `-1.00`, but Holm p remains above 0.05.

Paired EAES minus HPA-formula energy per served request:

| Workload | Median diff J [95% CI] | Holm p | Cliff’s d |
|---|---:|---:|---:|
| steady | -11.1557 [-11.8710, 0.0000] | 0.1437 | -0.77 |
| light | 0.0000 [0.0000, 0.0000] | not testable | 0.00 |
| medium | -11.3242 [-12.0849, -10.1942] | 0.0624 | -1.00 |
| heavy | -2.8408 [-3.5907, -2.1220] | 0.0882 | -1.00 |
| variable | -21.5639 [-22.7475, -20.3176] | 0.0619 | -1.00 |
| bursty | -0.9880 [-0.9947, -0.9776] | 0.0755 | -1.00 |

Authoritative generated report: `results/RESULTS.md`.  
Tables: `results/tables/headline.csv`, `results/tables/paired_headline.csv`.

## 8. Dashboard

**Status: COMPLETE — BROWSER-VERIFIED**

Three pages:

- `/` — paired results, filters, selection KPIs, workload/CPU/replica charts,
  strategy comparison, energy-vs-drop scatter, descriptive/paired tables, and
  the separate cluster validation.
- `/eaes-diagnostics` — recorded controller trace, final decision, rule, reason,
  cooldown/stabilization state, SLA margin, actual vs forecast, scaling history,
  rule counts, and EAES decomposition.
- `/methodology` — architecture, execution flow, workload generation, metrics,
  APIs, execution modes, strategy distinctions, energy model, statistics,
  reproduction, extensions, dataset integrity, and limitations.

Browser check:

- five live Chart.js charts on `/`;
- two charts on `/eaes-diagnostics`;
- 16 methodology sections rendered;
- filters loaded real backend data;
- no uncaught JavaScript errors after restarting the current app.

Chart.js 4.4.1 is served locally. The dashboard is read-only and shows generated
artifacts, not live cluster metrics.

## 9. Extensions

**Status: COMPLETE — EXPLORATORY ONLY**

All extension outputs are separate under `results/extension/`:

| Extension | Runs | Result |
|---|---:|---|
| Oracle upper bound | 360 | Lower E/served than EAES on medium/heavy/variable/bursty; not deployable |
| Startup-delay sweep | 360 | Forecasting improves variable SLA at 10/20 s, at higher energy; no bursty SLA benefit |
| 30-seed extension | 600 | Direction agrees with confirmatory; medium/heavy/variable/bursty Holm p < 0.05, exploratory |
| Energy/PUE sensitivity | 3,600 | No rank changes across low/nominal/high power or PUE 1.0–1.6 |
| Energy-vs-drop Pareto | 6 SVGs | Uses energy per offered request and drop rate |
| Forecast accuracy | 120 rows / 12 summaries | EWMA MAE below Holt; bursty remains hard |
| Native-HPA replay | 30 transitions | 100% agreement, zero mismatches, weak steady-state evidence |

Oracle example: bursty `26.63` J/served vs EAES `29.46`, with oracle SLA `0.0000`
and fewer replica-hours. This is an information upper bound, not an online
controller.

The extensions are never pooled with the pre-specified ten-seed confirmatory
inference.

## 10. Native Kubernetes validation

**Status: COMPLETE BUT LIMITED**

Historical single-node Minikube validation:

- Minikube v1.39.0, Kubernetes v1.37.0, Docker driver.
- Native `autoscaling/v2` HPA, CPU target 50%, min 1, max 10.
- 80 req/s for 60 s; three static and three HPA repetitions.
- Zero client-side failed requests; all recorded offered traffic served.
- p95 latency 29.3–32.7 ms.
- HPA observed at four replicas; the initial 1→4 transition is not in the
  recorded samples.
- Cluster energy is modelled from measured node CPU, not measured power.

Native-HPA replay:

- 30 recorded transitions;
- 100% agreement between predicted and next recorded spec;
- zero predicted or observed changes between samples.

This is weak evidence: steady load, short window, stable replica count, no
observed cold start or burst. Docker Desktop/Minikube were unavailable at final
verification, so no additional repetitions were run.

## 11. Testing

**Status: COMPLETE**

Command:

```powershell
$env:ENERGY_AWARE_NO_BG='1'
python -m pytest -q
```

Final result: **113 passed**.

Coverage includes:

- simulation queue/capacity/startup invariants;
- all five strategies and Oracle future-peak behavior;
- energy model, PUE, pod attribution, conservation;
- bootstrap, Wilcoxon, Holm, Cliff’s delta, Friedman/Nemenyi;
- headline tables and non-fabricated generated values;
- protected dataset hashes;
- dashboard pages, APIs, filters, timeseries, controller trace;
- extension manifests and design counts;
- forecast zero/near-zero MAPE exclusion;
- sensitivity exact nominal recompute;
- HPA replay scope and limitations;
- clean-checkout-safe dataset paths.

Full output: `results/test_report.txt`.

## 12. Reproducibility

**Status: COMPLETE**

Default reproduction:

```powershell
.\reproduce.ps1
```

What it does:

1. checks Python/dependencies;
2. validates YAML configs;
3. verifies protected dataset hashes;
4. reuses the preserved confirmatory run;
5. regenerates statistical tables, headline report, diagnostic, forecast
   tables, Pareto SVGs, and HPA replay;
6. runs tests;
7. validates required documents and references.

Clean-checkout reproduction:

```powershell
.\scripts\clean_checkout_reproduction.ps1
```

Final result at commit `e00de41`:

- **25 substantive artifacts matched by SHA-256**
- **0 differed, 0 missing**
- clean-clone tests: **113 passed**
- reproduce exit code: 0
- report: `results/extension/clean_checkout/REPRODUCTION_REPORT.txt`

Four provenance-only files change by design because they record analysis
commit/timestamp fields:

- `results/analysis_manifest.json`
- `results/diagnostic.json`
- `results/EAES_DIAGNOSTIC.md`
- `results/extension/hpa_replay/manifest.json`

They are excluded from the substantive comparison and documented as such.

## 13. Documentation and provenance

**Status: COMPLETE**

Required documents exist, are tracked, and pass validation:

- `README.md`
- `METHODOLOGY.md`
- `LIMITATIONS.md`
- `RESULTS.md`
- `docs/EXTENSIONS.md`
- `docs/REVERSAL_EXPLANATION.md`
- `docs/verification_log.txt`
- `docs/ARCHITECTURE.md`
- `docs/EXECUTION_GUIDE.md`
- `docs/TESTING.md`
- `docs/DASHBOARD_GUIDE.md`
- `docs/KUBERNETES_VALIDATION.md`
- `docs/REPRODUCIBILITY.md`
- `docs/LIMITATIONS.md`
- `docs/METHODOLOGY.md`

Validation result:

```text
DOCUMENT VALIDATION PASSED: 15 required files; 17 documents scanned
```

Verification evidence, commands, hashes, clean-clone details, and environment
limitations are in `docs/verification_log.txt`.

## 14. Limitations and final assessment

**Status: IMPLEMENTATION COMPLETE; EXTERNAL VALIDITY LIMITED**

Established:

- The Flask application and three-page dashboard work with real backend data.
- The simulation is deterministic, paired, and reproducible.
- The analysis aggregates ticks correctly and reports uncertainty and effect
  sizes.
- EAES shows a consistent directional energy-per-served advantage over the
  simulated HPA formula, with lower replica-hours.
- The confirmatory advantage is **not Holm-significant** with ten seeds.
- The extensions strengthen the direction but remain exploratory.

Not established:

- physical energy savings;
- production, multi-node, or failure behavior;
- native-HPA equivalence under bursts or cold starts;
- optimality, cost savings, or carbon savings;
- reproduction of Li et al. (2025); only Crossref metadata was verified because
  the full text was paywalled;
- Prometheus verification; only metrics-server was exercised;
- additional cluster repetitions at the final checkpoint, because Docker
  Desktop/Minikube were unavailable.

Final assessment: this is a working, tested, documented, and reproducible
simulation study with a real single-node Kubernetes smoke validation. Its claims
are deliberately narrower than a production energy-saving claim: the evidence
supports a consistent directional simulation result, not a measured hardware
saving.

---

## Reproduction quick reference

```powershell
# Tests
$env:ENERGY_AWARE_NO_BG='1'
python -m pytest -q

# Dashboard
python app.py
# open http://127.0.0.1:5000/

# Reproduction
.\reproduce.ps1

# Clean-checkout comparison
.\scripts\clean_checkout_reproduction.ps1
```

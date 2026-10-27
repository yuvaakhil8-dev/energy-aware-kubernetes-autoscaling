# Final Report: Energy-Aware Autoscaling Rebuild

**Project:** `flask-kubernetes`  
**Branch:** `research-rebuild`  
**Evidence commit:** `431810f` (confirmatory run, code, results)  
**Documentation commit preceding this report:** `f26d840`  
**Confirmatory run:** `v3_paired_20261025T220942Z`  
**Mode:** paired discrete-time simulation with a separate real-cluster validation  
**Report format:** 20 numbered sections, as required by the rebuild brief

---

## 1. Executive Summary

The original project was a Flask/Kubernetes demonstration with a working dashboard but unsupported research claims: the “HPA” baseline was a one-second 65/35 rule, the energy accounting had no node boundary and produced 450 J/request at zero requests, the 27-row dataset was nine deterministic cells copied three times, and the cited “15.34% better than HPA” result was not reproducible.

This rebuild preserves the application while turning the research claims into testable evidence. It adds:

- a configurable simulation with a real startup delay, bounded queue, per-node capacity, and raw per-tick logs;
- five explicitly separated strategies: `static`, `cpu_threshold`, `hpa_formula`, `eaes`, and `forecasting_eaes`;
- a node-level energy model with idle power, PUE, pod attribution, conservation checks, and low/nominal/high sensitivity;
- 300 paired runs (6 workloads × 10 seeds × 5 strategies), a frozen analysis plan, bootstrap CIs, Wilcoxon/Holm tests, Friedman/Nemenyi, effect sizes, and forecast evaluation;
- a three-page dashboard and preserved legacy APIs/routes;
- a separate real single-node Minikube validation with a native HPA, real HTTP load, real replica counts, and modelled energy;
- 19 research documents, 91 passing tests, hashed original data, and committed raw logs.

The main result is conditional. EAES uses less modelled energy per served request than the simulated HPA formula on steady, medium, heavy, variable, and bursty workloads, and the same on light. After Holm correction, the difference is significant on medium, heavy, variable, and bursty; the steady result is not significant after correction. EAES also uses fewer replica-hours than the HPA formula.

The result is not a universal win. EAES is worse than static three replicas on medium (20.962 vs 17.736 J/request) and worse than the threshold controller on medium. It has startup-delay SLA violations on variable (0.0119) and bursty (0.0170) workloads while the HPA formula has none. Forecasting removes the variable violations at 16.5% higher energy and 17.0% more replica-hours, but does not help the abrupt burst. Static looks energy-efficient on heavy and bursty only because it drops about 40% of offered requests.

**Bottom line:** the rebuilt project supports a careful, simulation-bounded claim that an EAES-inspired SLA-first controller can reduce modelled energy and provisioning relative to an HPA-formula baseline and can be safer than static under high load, but it does not dominate simpler baselines and it does not provide measured or production evidence.

---

## 2. Research Questions and Scope

The rebuild was organized around four questions:

1. Under a fixed trace and identical simulated cluster, does an EAES-inspired controller use less modelled energy per served request than a simulated Kubernetes HPA replica-formula baseline?
2. Does any advantage survive denominator checks (energy per offered request), drop-rate checks, SLA checks, and replica-hours?
3. Does adding a short-horizon forecast improve the SLA/energy trade-off under variable and bursty load?
4. Can the deployment and a native Kubernetes HPA be exercised in a real cluster without conflating that validation with the paired simulation?

Scope:

- **In scope:** simulation, controller comparison, energy modelling, statistical analysis, dashboard, single-node Minikube validation, reproducibility.
- **Out of scope:** physical power measurement, production multi-node cluster, reproduction of Li et al. (2025), new algorithm invention, Bayesian/sequential analysis, public web deployment.

The claims are limited to the six synthetic workloads, the configured cluster, the nominal/alternative power scenarios, and the simulation window.

---

## 3. Original Repository Audit and Preserved Assets

### 3.1 What was preserved

- The Flask app, routes/APIs, templates, and static assets needed by the demonstration.
- The original controller, including its legacy energy arithmetic, as a preserved component.
- The original test suite (29 tests) and the legacy dataset behaviour.
- The three original dashboard pages’ URLs, now compatibility views.
- The original datasets, byte-for-byte.

### 3.2 Defects found

| Defect | Evidence |
|---|---|
| “HPA” was a 1 s 65/35 rule | `AUDIT.md`, `experiments/run_experiment.py` |
| Energy boundary undefined; no replica multiplier | `controller.py:98–151` in the baseline |
| Cumulative denominator made J/request fall over time | baseline controller |
| Zero requests produced 450 J/request | `/controller/status` evidence at CPU 0 |
| Dataset repetitions were identical copies | `docs/original_dataset_audit.txt` |
| “15.34% better than HPA” claim unsupported | baseline `app.py` |
| No raw samples, no seeds, no real cluster execution | audit |

The detailed audit is in `AUDIT.md`; the read-only dataset audit is in `docs/original_dataset_audit.txt`.

### 3.3 Preservation controls

- Baseline commit: `c5ec94d` (`pre-rebuild-snapshot`).
- Rebuild branch: `research-rebuild`.
- Original files were hashed before and after; see section 19.
- Original 29-test suite passed at baseline.
- The obsolete `OneRoad` duplicate was not used.

---

## 4. Research Contributions

1. **Separation of concepts:** native HPA, HPA formula, legacy threshold, and EAES are distinct in code, labels, and results.
2. **Node-level energy model:** explicit idle/dynamic power, PUE, pod attribution, conservation, zero-denominator handling, and sensitivity.
3. **Reproducible paired experiment:** 300 runs, fixed traces, 10 seeds, raw tick logs, config/trace hashes, git provenance.
4. **Falsification-oriented diagnostic:** denominator checks, drop/SLA checks, replica-hours, startup/queue effects, rule activity, forecasting ablation.
5. **Honest negative results:** static and threshold counterexamples, EAES SLA violations, forecast cost, HPA-formula over-provisioning, light-load flat energy.
6. **Separate real-cluster validation:** genuine replica/request/CPU observations, explicitly not a measured-energy experiment.
7. **Three-page dashboard:** results, diagnostics, methodology, plus compatibility routes and preserved APIs.
8. **Reproducible packaging:** research package/configs/data/results in the container; final image smoke-tested in Minikube.

The detailed contribution statement is in `docs/RESEARCH_CONTRIBUTIONS.md`.

---

## 5. System Architecture and Repository Map

```text
Browser / HTTP client
  |
  v
Flask app (app.py)
  |-- three research pages:
  |     /, /eaes-diagnostics, /methodology
  |-- legacy compatibility HTML routes
  |-- preserved monitoring/legacy APIs
  |-- six research JSON APIs
  |
  |-- results/latest_run.json -> results/runs/<run_id>/
  |-- results/tables/*
  |-- results/cluster_validation/*
  |
  v
Generated artifacts from:
  experiments/run_v3.py
  analysis/analyze.py
  analysis/diagnose.py
  experiments/run_cluster_validation.py
```

Key paths:

| Path | Role |
|---|---|
| `app.py` | Flask routes, data layer, dashboard |
| `controller.py` | Original demo controller (preserved) |
| `eaes/backend.py` | `SimulatedCluster`, `KubernetesCluster` via `kubectl` |
| `eaes/energy.py` | Node power model and pod attribution |
| `eaes/engine.py` | Paired run loop, raw logs, manifest |
| `eaes/strategies.py` | Five strategies |
| `eaes/forecast.py` | EWMA and Holt |
| `eaes/workload.py` | Deterministic traces |
| `analysis/analyze.py` | Statistics and tables |
| `analysis/diagnose.py` | Raw-log EAES diagnostic |
| `experiments/run_v3.py` | Full 300-run execution |
| `experiments/run_cluster_validation.py` | Real Minikube/HPA validation |
| `configs/` | Experiment, simulation, energy, SLA, strategy YAML |
| `traces/` | 60 deterministic traces + index |
| `results/` | Runs, tables, reports, cluster validation |
| `templates/research/` | Three-page dashboard |
| `static/research.css/js` | Dashboard styling and charts |
| `data/` | Byte-identical original dataset copies |
| `docs/` | 19 research documents |
| `kubernetes/` | Namespace, deployment, service, HPA |

The detailed architecture is in `README.md` and `docs/DASHBOARD.md`.

---

## 6. Simulation Model

`eaes.backend.SimulatedCluster` is a discrete-time model, not a Kubernetes emulator.

### 6.1 Configuration

| Parameter | Value |
|---|---|
| Pods per node | 4 |
| Capacity per ready pod | 10 req/s |
| Tick | 5 s |
| Startup delay | 10 s |
| Initial replicas | 3 |
| Replica bounds | 1–10 |
| Base latency | 20 ms |
| Queue bound | 2 × per-tick capacity |
| Active nodes | `ceil(ready / 4)` |
| Max nodes | 10 (declared, not binding) |

### 6.2 Tick logic

1. Activate pending replicas whose ready time has arrived.
2. Read ready, pending, desired, backlog, capacity, CPU, and previous arrival rate.
3. Ask the strategy for a replica target.
4. Apply scale-up as a delayed batch; scale-down removes pending first, then ready.
5. Serve `min(backlog + arrivals, ready × 10 × 5)`.
6. Drop overflow above the queue bound.
7. Compute latency, CPU, node energy, and pod attribution.
8. Write a raw JSONL row.

### 6.3 Capacity and latency

```text
capacity_requests = ready × 10 × 5
served            = min(backlog + arrivals, capacity_requests)
wait_s            = backlog_before / capacity_rps
avg_latency_ms    = 20 + wait_s × 1000
p95_latency_ms    = 20 + 3 × wait_s × 1000
cpu_util          = served / capacity_requests
```

Only ready replicas contribute capacity. This is the mechanism that makes reactive scaling during a burst expensive: a decision made now cannot serve until the 10 s startup delay has passed.

### 6.4 Omissions

No scheduler, image pull, network latency, retries, per-request latency distribution, heterogeneous nodes, pod anti-affinity, node autoscaling, failures, or real Kubernetes controller timing. These are external-validity limits, not hidden assumptions.

Full details: `docs/SIMULATION_MODEL.md`.

---

## 7. Energy Model

All energy is **modelled**, not measured.

### 7.1 Equations

```text
P_node(u) = P_idle + (P_max − P_idle) × u       [W]
E_node    = P_node(u) × Δt × PUE + startup      [J]
u         = node_served / (4 × 10 × 5)          [0, 1]
```

Nominal assumptions:

| Parameter | Value |
|---|---|
| `P_idle` | 150 W |
| `P_max` | 500 W |
| `PUE` | 1.2 |
| Tick | 5 s |
| Startup energy | 0 J |

Alternative scenarios: low 80/300 W, high 250/800 W; PUE sweep 1.0, 1.2, 1.4, 1.6.

### 7.2 Attribution

Dynamic node energy is split by pod work share; idle/startup energy is split by pod count. Node and pod energy are conserved within floating tolerance. The diagnostic reports a maximum conservation error of `1.819e-12 J`; the nominal raw-log recomputation agrees with the engine to `8.061e-16` relative error.

### 7.3 Denominators

```text
E/served  = measurement_energy / measurement_served
E/offered = measurement_energy / measurement_offered
```

If served = 0, E/served is null. The old 450 J/request artefact is not repeated.

### 7.4 Critical limitation

Energy is charged per active node, not per pod. On light load, reducing replicas from three to one does not necessarily remove the node, so energy can stay flat while replica-hours fall. This effect is visible and is reported as a model limitation.

Full details: `docs/ENERGY_MODEL.md`.

---

## 8. Workloads and Traces

All traces are 300 s at 5 s ticks (60 ticks), generated deterministically with Poisson arrivals.

| Workload | Offered rate | Pattern |
|---|---|---|
| steady | 15 req/s | constant |
| light | 5 req/s | constant |
| medium | 25 req/s | constant |
| heavy | 50 req/s | constant |
| variable | 5–25 req/s | `15 + 10 sin(2πt/120)` |
| bursty | 5 or 80 req/s | 20 s at 80 req/s every 60 s |

Each workload × seed has one trace, shared by all five strategies. Traces are hashed and validated on reuse; a metadata or hash mismatch raises an error instead of silently regenerating.

The synthetic traces are a controlled comparison, not a production workload benchmark. In particular, static three replicas covers steady/light/medium/variable, which strongly affects the baseline comparison.

Full protocol: `docs/EXPERIMENT_PROTOCOL.md`.

---

## 9. Scaling Strategies and Baselines

### 9.1 Static

Fixed three replicas, no feedback. A lower-bound provisioning baseline.

### 9.2 `cpu_threshold`

Legacy 80/30 rule with 5% hysteresis, 30 s up cooldown, 60 s down cooldown, warm-up scale-down suppression. **Not HPA.**

### 9.3 `hpa_formula`

Simulated Kubernetes HPA replica formula:

```text
ratio   = current_cpu / target_cpu
desired = ceil(current_replicas × ratio)
```

with 50% target, ±10% tolerance, bounds 1–10, 300 s scale-down stabilization, at least +1 on scale-up, at most −1 on scale-down, and metric-unavailable fallback. **Not the native HPA controller.**

### 9.4 `eaes`

SLA-first, lexicographic, no scalar weights:

```text
projected = max(1, ready + pending)
demand    = previous arrival rate, or backlog/Δt if needed
predicted = demand / (projected × 10)
margin    = 0.8 − predicted
target    = 0.8 − 0.1 = 0.7
```

Scale up if `margin < 0.1`:

```text
required = ceil(demand / (10 × 0.7))
new      = min(10, max(current + 1, required), current + max_step)
```

Scale down only when not warming up, above minimum, backlog = 0, cooldown/dwell/stabilization satisfied, and the smaller configuration is predicted safe. EAES does not trade SLA for energy.

### 9.5 `forecasting_eaes`

EAES with `demand = max(current_rate, Holt_forecast)`, Holt α=0.5, β=0.3, horizon 2 ticks (10 s). Before enough observations, it falls back to the current rate.

All strategies start at three replicas, use the same backend, and see the same trace. Full rules: `docs/STRATEGIES.md`.

---

## 10. Experimental Design and Protocol

- 6 workloads × 10 seeds × 5 strategies = 300 runs.
- Paired by workload × seed.
- 300 s simulated duration, 5 s control interval.
- 30 s warm-up excluded from primary metrics.
- Primary window 30–300 s = 54 ticks.
- Identical trace for all strategies within a workload × seed.
- Fresh backend and fresh strategy per run.
- Analysis plan frozen before the confirmatory run (`ANALYSIS_PLAN.md`).
- No optional stopping, no seed removal, no post-hoc strategy addition.

The run manifest records run id, timestamps, mode, energy scenario, git commit, `git_tracked_dirty`, config hashes, 60 trace hashes, Python/package versions, seeds, workloads, strategies, and `n_runs`.

Confirmatory run: `results/runs/v3_paired_20261025T220942Z/`  
Raw logs: 300 JSONL files, one per run, plus `manifest.json` and `summary.json`.

---

## 11. Metrics and Measurement Windows

Primary:

- **E/served:** measurement-window node energy / measurement-window served requests.
- **SLA violation rate:** (dropped + served requests in ticks with average latency > 500 ms) / offered.
- **Replica-hours:** time-integrated ready replicas over the measurement window.
- **Drop rate:** dropped / offered.

Secondary/diagnostic:

- E/offered;
- served/offered;
- average and p95 latency;
- scaling events and oscillations;
- max pending/ready replicas;
- over-provisioning;
- cooldown/stabilization holds;
- rule counts;
- node/pod energy conservation error.

The SLA rule is conservative: an over-500 ms tick charges every served request in that tick. It is applied identically to every strategy.

---

## 12. Statistical Analysis

- Paired Wilcoxon signed-rank tests, normal approximation with tie correction; fewer than five nonzero differences → `not_testable`.
- 5,000-resample percentile bootstrap 95% CIs with deterministic seeds.
- Holm correction within each workload × baseline family (up to 14 tests including both EAES variants and all metrics).
- Friedman test across five strategies per workload × metric, chi-square df = 4.
- Nemenyi post-hoc with `q_0.05 = 2.728` for five groups.
- Cliff’s delta on the two samples.
- No scipy; implementations are in `analysis/analyze.py` and tested in `tests/test_statistics.py`.

The analysis is pre-registered. The report shows raw and Holm p-values separately.

Full details: `docs/STATISTICAL_ANALYSIS.md`.

---

## 13. Primary Results

Means over 10 seeds, nominal energy. Full tables: `results/RESULTS.md`.

### 13.1 EAES vs HPA formula

| Workload | EAES E/served | HPA E/served | Mean diff [95% CI] | Raw p | Holm p |
|---|---:|---:|---|---:|---:|
| steady | 22.577 | 30.700 | −8.123 [−11.447, −4.604] | 0.0180 | 0.0718 |
| light | 46.722 | 46.722 | 0 | — | — |
| medium | 20.962 | 32.208 | −11.247 [−11.844, −10.679] | 0.0051 | 0.0446 |
| heavy | 18.578 | 21.338 | −2.759 [−3.178, −2.315] | 0.0051 | 0.0407 |
| variable | 23.022 | 44.547 | −21.525 [−22.325, −20.755] | 0.0051 | 0.0352 |
| bursty | 29.462 | 30.447 | −0.985 [−0.992, −0.978] | 0.0050 | 0.0302 |

Interpretation:

- Medium, heavy, variable, and bursty survive Holm.
- Steady is raw-significant but not Holm-significant; do not call it confirmed.
- Light has no nonzero differences for per-request energy.

### 13.2 Replica-hours

EAES uses fewer replica-hours than the HPA formula on every testable workload:

| Workload | EAES RH | HPA RH | Ratio |
|---|---:|---:|---:|
| steady | 0.215 | 0.363 | 0.59 |
| light | 0.113 | 0.225 | 0.50 |
| medium | 0.335 | 0.750 | 0.45 |
| heavy | 0.610 | 0.750 | 0.81 |
| variable | 0.275 | 0.726 | 0.38 |
| bursty | 0.717 | 0.750 | 0.96 |

### 13.3 SLA and drop outcomes

| Workload | EAES SLA | HPA SLA | EAES drop | HPA drop |
|---|---:|---:|---:|---:|
| steady | 0.000 | 0.000 | 0.000 | 0.000 |
| light | 0.000 | 0.000 | 0.000 | 0.000 |
| medium | 0.000 | 0.000 | 0.000 | 0.000 |
| heavy | 0.000 | 0.000 | 0.000 | 0.000 |
| variable | **0.0119** | 0.000 | 0.000 | 0.000 |
| bursty | **0.0170** | 0.000 | 0.000 | 0.000 |

The variable and bursty SLA penalties are the main negative findings for EAES.

### 13.4 Static and threshold counterexamples

Static:

- steady: 22.577 J, 0 SLA, 0 drop;
- light: 46.722 J, 0 SLA, 0 drop;
- medium: 17.736 J, 0 SLA, 0 drop;
- variable: 21.870 J, 0 SLA, 0 drop;
- heavy: 16.500 J but drop 0.398 and SLA 1.000;
- bursty: 21.115 J but drop 0.380 and SLA 0.841.

`cpu_threshold`:

- medium: 17.736 J, 0 SLA, 0 drop (better than EAES energy);
- heavy: 17.394 J, SLA 0.320, drop 0.0105;
- bursty: 23.031 J, SLA 0.748, drop 0.0339.

So EAES is not the lowest-energy strategy on medium, heavy, variable, or bursty in the raw per-request table. Its case is the combination of energy and service outcomes relative to the over-provisioning HPA formula and its safety relative to static/threshold under high load.

### 13.5 Friedman

Friedman energy tests are significant on all workloads except light; replica-hours are significant on all. SLA is significant on heavy and bursty; variable is marginal (`p = 0.0749`). Nemenyi is conservative and does not localize every omnibus result; for example, steady energy is omnibus-significant but no pair exceeds the critical difference.

---

## 14. EAES Diagnostic and Forensic Checks

The diagnostic (`results/EAES_DIAGNOSTIC.md`) recomputes metrics directly from raw tick logs and checks whether the headline could be an artefact.

### 14.1 Denominator check

EAES vs HPA E/offered ratios equal the E/served ratios in every workload because drops are zero in both strategies. The energy advantage is not created by serving fewer requests.

### 14.2 Replica-hours and provisioning

EAES uses fewer replica-hours, but the HPA formula often sits at or near maximum replicas. At medium it reaches 10 ready; at heavy and bursty it reaches 10. The HPA’s 50% target, +1 minimum scale-up, and 300 s scale-down stabilization interact with a 300 s run.

### 14.3 Startup and pending replicas

EAES’s variable and bursty SLA violations coincide with startup delay and pending replicas. The diagnostic reports max pending and rule counts; the forecast ablation tests whether pre-scaling helps.

### 14.4 Light-load artefact

All strategies use 46.722 J/request on light despite different replica-hours. One active node dominates idle power; fewer pods on that node do not remove it. This is a node-model artefact, not evidence that autoscaling is useless.

### 14.5 Conservation

Node energy and pod-attributed energy are conserved. The diagnostic reports `1.819e-12 J` maximum conservation error. Pod attribution does not create or destroy energy.

### 14.6 Failure summary

- EAES is too conservative at medium load (target 70% vs enough capacity at 83%).
- EAES is reactive and pays startup delay on a rising sinusoid and a step burst.
- Forecasting helps only the smooth sinusoid.
- Static is efficient only where three replicas cover the trace.
- HPA formula is configuration-sensitive.
- Threshold is not HPA and has severe SLA failures under heavy/bursty load.

See `docs/FAILURE_ANALYSIS.md`.

---

## 15. Forecasting Ablation

Held-out final 50% of each trace:

| Workload | EWMA MAE | Holt MAE |
|---|---:|---:|
| steady | 1.524 | 1.901 |
| light | 0.874 | 1.077 |
| medium | 1.984 | 2.471 |
| heavy | 2.798 | 3.481 |
| variable | 6.687 | 6.563 |
| bursty | 39.660 | 45.327 |

Holt wins only on the variable sinusoid, by a small margin.

Forecasting EAES:

- variable: SLA 0.0119 → 0.000, energy 23.022 → 26.830 J (+16.5%), replica-hours 0.275 → 0.322 (+17.0%);
- bursty: identical to reactive EAES (SLA 0.0170, energy 29.462 J, RH 0.717);
- other workloads: ≤0.65% energy change and no SLA benefit.

The forecast is a mixed result, not a general improvement.

---

## 16. Energy and PUE Sensitivity

Low/nominal/high and PUE 1.0–1.6 recomputation is in `results/tables/sensitivity.csv`.

EAES/HPA energy-per-served ratio:

| Workload | Low | Nominal | High |
|---|---:|---:|---:|
| steady | 0.750 | 0.734 | 0.729 |
| light | 1.000 | 1.000 | 1.000 |
| medium | 0.670 | 0.651 | 0.644 |
| heavy | 0.881 | 0.871 | 0.867 |
| variable | 0.536 | 0.517 | 0.510 |
| bursty | 0.970 | 0.968 | 0.967 |

PUE multiplies all strategies equally and cannot change rankings. Low/high power assumptions change the idle/dynamic mixture but not the sign of the EAES-vs-HPA difference in these runs.

This is a **model sensitivity**, not proof of robustness to a different power curve. The absolute joules remain uncalibrated.

---

## 17. Real Kubernetes Validation

### 17.1 Environment

| Item | Value |
|---|---|
| Minikube | v1.39.0 |
| Kubernetes | v1.37.0 |
| kubectl | v1.36.1 |
| Docker engine | 29.8.2 |
| Driver | Docker, WSL2 kernel 6.18.54.1 |
| Node | one Ready control-plane node |
| metrics-server | enabled; `kubectl top` worked |
| Namespace / deployment | `energy-aware-dev` / `energy-aware-app` |
| Native HPA | `autoscaling/v2`, CPU 50%, min 1, max 10 |
| Load | 80 req/s, 60 s, 3 repetitions per mode |

### 17.2 Results

| Mode | Reps | Served | Offered | Drop | Avg repl | Max repl | p95 ms | Modelled J/req |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| static | 3 | 4871/4817/4821 | all | 0 | 3 | 3 | 29.3–30.7 | 2.25–2.32 |
| native HPA | 3 | 4832/4890/4731 | all | 0 | 4 | 4 | 30.4–32.7 | 2.28–2.30 |

All client requests succeeded. Native HPA scaled 1 → 4; static stayed at 3. Node CPU was 3–4%, so J/request is dominated by idle-node charging and should not be compared in absolute terms with the simulation.

### 17.3 What this proves

- The image builds and runs in Kubernetes.
- Service, port-forward, metrics-server, and native HPA work.
- The Flask app serves under real HTTP load.
- Real replica counts and request outcomes were observed.

### 17.4 What it does not prove

- It does not validate the simulation’s energy ranking.
- It does not compare all five strategies on one real workload.
- It does not measure power.
- It is not a multi-node or production cluster.
- It used the Flask development server.

The 60 s validation ran on commit `cce700b`. The final dashboard image was later rebuilt from later content and smoke-tested separately; all pages/APIs returned 200. See `docs/KUBERNETES_VALIDATION.md` and `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md`.

---

## 18. Threats to Validity, Negative Findings, and Limitations

### 18.1 Construct validity

- Energy is modelled from CPU, not measured.
- CPU utilisation is a proxy.
- SLA is a coarse tick-level rule.
- `hpa_formula` is not native HPA.
- EAES is not a reproduction of Li et al.

### 18.2 Internal validity

- Warm-up, cooldowns, targets, and stabilization are design choices.
- Static three replicas is unusually strong because it covers four workloads.
- Node-level energy hides scale-down benefits within a node.
- HPA-formula over-provisioning is partly a 300 s-run + 300 s-stabilization artefact.
- No node autoscaling; `max_nodes` is not binding.

### 18.3 External validity

- Six synthetic traces.
- One simulated cluster shape.
- One single-node Minikube validation.
- Windows/Docker Desktop host.
- No production traffic.

### 18.4 Statistical conclusion validity

- Ten seeds; limited power.
- Holm family includes 14 tests.
- Wilcoxon normal approximation, not exact.
- Bootstrap resamples the observed seeds, not a real population.
- The steady EAES-vs-HPA result is not significant after correction.

### 18.5 Reporting risks

- Low J/request can mean dropped traffic; static demonstrates this.
- HPA-formula results must not be presented as native-HPA measurements.
- Modelled joules must not be presented as measured power.
- The original 27-row dataset must not be treated as 27 independent observations.

### 18.6 Negative findings that must remain visible

1. EAES is worse than static on medium energy (20.962 vs 17.736 J).
2. EAES is worse than the threshold controller on medium.
3. EAES has SLA violations on variable (0.0119) and bursty (0.0170).
4. Forecasting costs 16.5% energy and 17.0% replica-hours on variable.
5. Forecasting does not help bursty.
6. Light-load energy is flat despite fewer replicas.
7. Steady EAES-vs-HPA is not Holm-significant.
8. Static has the lowest J/request on heavy/bursty only by dropping ~40%.

Full lists: `docs/THREATS_TO_VALIDITY.md`, `docs/LIMITATIONS.md`, `docs/FAILURE_ANALYSIS.md`.

---

## 19. Reproducibility, Tests, Data Provenance, and Commits

### 19.1 Exact commands

```powershell
# Change to the repository root (run this from a PowerShell prompt while inside the repo)
Set-Location (git rev-parse --show-toplevel)
python -m pip install -r requirements.txt
python -m experiments.run_v3
python -m analysis.analyze
python -m analysis.diagnose
$env:ENERGY_AWARE_NO_BG='1'
$env:PYTHONIOENCODING='utf-8'
python -m pytest -q
```

Optional cluster validation:

```powershell
# Change to the repository root (run this from a PowerShell prompt while inside the repo)
Set-Location (git rev-parse --show-toplevel)
minikube start --driver=docker --cpus=2 --memory=4096
minikube addons enable metrics-server
minikube image build -t flask-k8s-demo:latest .
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -n energy-aware-dev -f kubernetes/deployment.yaml -f kubernetes/service.yaml
kubectl rollout status deployment/energy-aware-app -n energy-aware-dev --timeout=180s
kubectl port-forward -n energy-aware-dev svc/energy-aware-service 5001:5000
python -m experiments.run_cluster_validation --repetitions 3 --duration 60 --rate 80
```

### 19.2 Confirmatory run provenance

| Field | Value |
|---|---|
| Run | `v3_paired_20261025T220942Z` |
| Git commit | `431810fd8daa3cfd7dceaf11acb18dd6b14ea0ea` |
| Tracked dirty | `false` |
| Summaries | 300 |
| Raw tick logs | 300 JSONL files |
| Energy scenario | nominal |
| Python | 3.11.9 |
| Flask | 3.1.3 |
| PyYAML | 6.0.3 |
| pytest | 8.3.3 |
| OS | Windows-10-10.0.26200-SP0 |

Manifest: `results/runs/v3_paired_20261025T220942Z/manifest.json`  
Pointer: `results/latest_run.json`  
Generated report: `results/RESULTS.md`  
Diagnostic: `results/EAES_DIAGNOSTIC.md`

### 19.3 Tests

Final saved result: `results/test_report.txt`.

```text
91 passed in 1.72s
```

Test distribution:

| File | Tests |
|---|---:|
| `test_app.py` | 16 |
| `test_backend.py` | 11 |
| `test_controller.py` | 11 |
| `test_dataset.py` | 9 |
| `test_energy_model.py` | 10 |
| `test_engine.py` | 6 |
| `test_statistics.py` | 9 |
| `test_strategies.py` | 13 |
| `test_workload.py` | 6 |

Baseline suite: 29 passed. Full inventory: `docs/TESTING.md`.

### 19.4 Data provenance

| File | SHA-256 |
|---|---|
| original `experiment_results_v2.json` | `6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E` |
| original `experiment_results.json` | `C4BF4BFFFA8D0242395D2A2FB966C16DBC4884078BE7E82395E778EF87968451` |
| `data/experiment_results_v2.json` | identical |
| `data/experiment_results.json` | identical |

The 27-row dataset is nine deterministic cells copied three times. It is preserved for compatibility, not inference. Details: `docs/DATA_PROVENANCE.md`.

### 19.5 Commit chain

```text
f26d840 phase 9: research documentation, provenance, and final validation records
431810f analysis: record run/analysis commits and accurate EAES direction wording
603d1de phase 8: three-page research dashboard, immutable data copies, container packaging
2e1816f phase 7: real Minikube/HPA validation and kubectl cluster backend
cce700b phase 6: paired statistics, bootstrap CIs, Holm/Friedman/Nemenyi, sensitivity
97a99dc phase 5: 10-seed paired experiments, raw logs, and EAES diagnostic
e3160d9 phase 5: freeze analysis plan before confirmatory diagnostic
9ca53b5 phase 4: five strategies, forecasting ablation, paired experiment engine
4d6fda6 phase 3: node-level energy model with attribution and sensitivity scenarios
3412133 phase 2: cluster backend abstraction and simulated capacity model
17e579b phase 1: configuration-driven traces, provenance, reproduction scripts
88ca40e phase 0: audit, backup, dataset hashes, baseline evidence
c5ec94d baseline: pre-rebuild snapshot
```

This report is added after `f26d840`. Its own commit is the last commit on `research-rebuild`; it cannot meaningfully print its own hash. The evidence and documentation chain above is the reproducible record.

### 19.6 Container

Final image digest: `sha256:f2c95c3f24841933da309396c60e15d56222373650cd8d340683ba4f4fda238e`  
Embedded run: `v3_paired_20261025T220942Z`.  
All pages and research APIs returned 200 in the real cluster; `/api/v1/experiments` returned 27. See `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md`.

---

## 20. Conclusions and Future Work

### 20.1 Conclusions supported by the evidence

1. The rebuilt project replaces the original unsupported claims with a reproducible simulation, raw logs, a frozen analysis plan, and explicit distinctions between native HPA, HPA formula, threshold control, and EAES.
2. Against the simulated HPA formula, EAES reduces modelled energy per served request and replica-hours on the tested workloads; medium, heavy, variable, and bursty differences survive Holm correction. The steady difference does not.
3. EAES is not a dominant policy. Static is lower-energy on medium/variable and tied on steady/light; the threshold controller is lower-energy on medium; static is unsafe on heavy/bursty.
4. Reactive EAES has startup-delay SLA violations on variable and bursty load. Forecasting removes the variable violations at a real energy/replica cost and does not help the abrupt burst.
5. The HPA-formula baseline over-provisions in this configuration; the result is partly configuration-dependent.
6. The real Minikube validation proves deployment, metrics-server, service, and native HPA operation, but not the simulation’s energy ranking.
7. All energy remains modelled, not measured.

### 20.2 What must not be claimed

- That EAES saves energy in production.
- That native Kubernetes HPA uses 30–45 J/request.
- That the paper Li et al. (2025) was reproduced.
- That the original 27-row dataset supports inference.
- That the modelled joules match the validation host.
- That static is a safe policy.
- That forecasting is a general improvement.

### 20.3 Future work

1. **Measured energy:** deploy Kepler or an external power meter and calibrate the CPU-to-power curve on the validation host.
2. **Fair HPA baseline:** sweep target utilisation, tolerance, scrape interval, and stabilization; compare native HPA under the same traces.
3. **More realistic workloads:** production traces, diurnal cycles, heavy-tailed service times, retries, and multi-service dependencies.
4. **Less conservative EAES:** tune the target and add an explicit energy-aware hold rule; evaluate on a new pre-registered run.
5. **Node-level autoscaling:** model node power-down, consolidation, and empty-node removal to test whether replica reductions actually save energy.
6. **Multi-node cluster:** validate scheduling, anti-affinity, node failure, and real HPA timing.
7. **Paper reproduction:** if the Li et al. full text becomes available, implement their algorithm separately and compare fairly.
8. **Operational dashboard:** live cluster metrics with clear labels; keep precomputed research artifacts separate from live state.
9. **Broader statistics:** more seeds, equivalence testing, and hierarchical models that account for workload and seed variation.
10. **Security and productionisation:** authentication, production WSGI server, resource limits, and observability.

### 20.4 Final statement

The rebuild succeeds as a reproducibility and honesty intervention: it makes the claims inspectable, preserves the working application, and reports where the proposed controller loses. It does not establish a production energy saving. The strongest defensible claim is the conditional one in section 1: an EAES-inspired SLA-first controller reduces modelled energy and provisioning relative to an HPA-formula baseline on several synthetic workloads, while failing to dominate static provisioning and incurring startup-delay SLA penalties on variable and bursty traffic.

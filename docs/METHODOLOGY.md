# Methodology

**Project:** Energy-aware autoscaling for containerised microservices
**Evidence type:** discrete-time simulation with a separate, non-confirmatory real-cluster validation
**Frozen analysis plan:** `ANALYSIS_PLAN.md`
**Confirmatory run:** `v3_paired_20261025T220942Z`

## 1. Research questions

1. Under a fixed request trace and identical simulated cluster, does an SLA-first energy-aware controller (EAES) use less modelled energy per served request than a simulated Kubernetes HPA replica-formula baseline?
2. Does any apparent energy advantage survive a change of denominator (served vs offered requests), a drop-rate/SLA check, and a replica-hours check?
3. Does adding a short-horizon Holt forecast to EAES improve the SLA/energy trade-off under variable and bursty load?
4. Can a real single-node Kubernetes HPA be exercised to verify that the deployment, metrics path, and HPA controller work, without presenting that validation as the confirmatory experiment?

## 2. What is being compared

Five strategies are implemented separately:

| Name | Role | Is it Kubernetes HPA? |
|---|---|---|
| `static` | Fixed three replicas | No |
| `cpu_threshold` | Legacy 80%/30% rule with 5% hysteresis and cooldowns | No |
| `hpa_formula` | Simulated HPA replica formula with tolerance and scale-down stabilization | No; simulated formula only |
| `eaes` | SLA-first lexicographic controller using demand, ready/pending replicas, backlog, margin, cooldown, dwell, and stabilization | No; EAES-inspired |
| `forecasting_eaes` | EAES with a Holt forecast over the startup horizon | No; EAES-inspired with ablation |

The original project used the word “HPA” for a toy 65/35 rule. That rule is now labelled `cpu_threshold`. The actual Kubernetes HPA controller is used only in Phase 7’s separate validation.

## 3. Design

- **Unit of analysis:** one workload × seed × strategy run.
- **Within-unit pairing:** every strategy is run on the same deterministic arrival trace for a given workload and seed.
- **Workloads:** steady, light, medium, heavy, variable, bursty.
- **Seeds:** 1–10, ten per workload.
- **Runs:** 6 × 10 × 5 = 300.
- **Simulated duration:** 300 s.
- **Control interval:** 5 s.
- **Warm-up:** 30 s excluded from primary metrics; raw logs retain every tick, including warm-up.
- **Initial replicas:** three for all strategies, so the trajectory is not seeded by a strategy-specific advantage.
- **Primary window:** 30–300 s, 54 ticks per run.

The same trace is reused across strategies for a seed. Traces are generated deterministically and hashed in `traces/index.json` and in each run manifest. The experiment runner refuses to treat a mismatched trace as paired evidence.

## 4. Simulation model in brief

The simulated cluster has fixed-capacity nodes (four pods per node), 10 req/s per ready pod, a 10 s pod startup delay, a bounded queue, and a minimum/maximum of 1/10 replicas. Only **ready** replicas contribute capacity. A controller that adds replicas during a burst therefore pays the startup delay.

Per tick:

1. Read ready replicas, pending replicas, capacity, backlog, CPU utilisation, and the previous arrival rate.
2. Ask the strategy for a desired replica count.
3. Apply the change; new replicas enter a pending queue.
4. Serve up to `ready_replicas × pod_capacity_rps × Δt` requests from backlog plus new arrivals.
5. Drop requests only when the bounded queue overflows.
6. Compute modelled node energy from node utilisation.
7. Record one raw JSONL row with all decisions and outcomes.

The full model is in `docs/SIMULATION_MODEL.md`.

## 5. Energy model in brief

For each active node and tick:

```text
P_node(u) = P_idle + (P_max - P_idle) · u          [W]
E_node    = P_node(u) · Δt · PUE + startup_energy  [J]
u         = served requests on that node / node capacity in the tick
```

Nominal assumptions: `P_idle = 150 W`, `P_max = 500 W`, `PUE = 1.2`. Low and high scenarios and PUE 1.0–1.6 are used for sensitivity. Dynamic node energy is attributed to pods by CPU-use share; idle/startup energy by requested-resource share. Conservation is tested and recomputed from raw logs.

Energy is an **output metric**, never a scaling input. This is why the post-hoc power/PUE sensitivity recomputation is valid: changing power assumptions cannot change which replicas each controller chose.

The full model and caveats are in `docs/ENERGY_MODEL.md`.

## 6. Metrics

Primary metrics:

- **Energy per served request (J):** measurement-window node energy divided by measurement-window served requests. Null when served = 0; no artificial denominator.
- **SLA violation rate:** `(dropped + served requests whose average latency exceeds 500 ms) / offered requests`.
- **Replica-hours:** time-integrated ready replicas over the measurement window.
- **Drop rate:** dropped / offered in the measurement window.

Diagnostic metrics: energy per offered request, served/offered ratio, average and p95 latency, scaling events, oscillations, pending replicas, over-provisioning, cooldown/stabilization holds, rule counts, and node/pod conservation error.

## 7. Statistical analysis

- Paired by workload and seed.
- 5,000-resample bootstrap 95% confidence intervals.
- Wilcoxon signed-rank tests for paired strategy differences, Holm correction within each workload × baseline family.
- Friedman test across the five strategies per workload and metric; Nemenyi post-hoc with critical difference.
- Cliff’s delta for paired effect size.
- Forecast evaluation on the held-out final 50% of each trace (EWMA vs Holt).
- Separate low/nominal/high and PUE sensitivity tables.

The analysis is pre-registered in `ANALYSIS_PLAN.md`; tests were not selected after seeing outcomes. Full details are in `docs/STATISTICAL_ANALYSIS.md`.

## 8. Real-cluster validation

A separate Phase 7 validation used a real single-node Minikube cluster, metrics-server, a native `autoscaling/v2` HPA, and the Flask service. It ran three static repetitions and three HPA repetitions at 80 req/s for 60 s after reset. Replica counts and request outcomes are real Kubernetes observations. Energy in that file is modelled from measured node CPU.

This validation is **not** the paired experiment, does **not** use the simulated traces, and does **not** support the simulation’s energy rankings. See `docs/KUBERNETES_VALIDATION.md`.

## 9. What would falsify the main claim

The main claim would be undermined if, after the denominator and drop/SLA checks:

- EAES had higher energy per served request than the HPA formula on most workloads;
- EAES’s advantage disappeared when energy per offered request was used;
- EAES served materially fewer requests;
- the advantage existed only under one power scenario or PUE; or
- the advantage came from a single seed or a post-hoc metric change.

The generated diagnostic explicitly checks the first four conditions. The run is fixed-seed and paired to address the fifth.

## 10. Provenance

Each run manifest records the config hashes, trace index, Python/package versions, git commit, and a `git_tracked_dirty` flag. The confirmatory run was produced from commit `431810f` with a clean tracked tree. The original datasets are frozen and hashed in `docs/DATA_PROVENANCE.md`.

## 11. Ethical and reporting stance

- Modelled energy is never called measured energy.
- The threshold baseline is never called HPA.
- Li et al. (2025) is cited as related work, not as a reproduced result.
- Negative findings (EAES SLA violations on variable/bursty load; forecasting cost) are reported prominently.
- The original pseudo-replicated dataset is not used for significance testing.

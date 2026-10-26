# Methodology

**Project:** energy-aware autoscaling for containerised microservices  
**Evidence type:** discrete-time simulation, with a separate non-confirmatory
real-cluster validation and separate exploratory extensions  
**Frozen analysis plan:** `ANALYSIS_PLAN.md`  
**Confirmatory run:** `v3_paired_20261025T220942Z`  
**Authoritative generated report:** `results/RESULTS.md`  
**Long-form modelling detail:** `docs/METHODOLOGY.md`,
`docs/SIMULATION_MODEL.md`, and `docs/ENERGY_MODEL.md`

## 1. Research questions

1. Under an identical request trace and simulated cluster, does an SLA-first,
   energy-aware controller (EAES) use less modelled energy per served request
   than a simulated Kubernetes HPA replica-formula baseline?
2. Does any apparent energy advantage survive a change of denominator
   (served versus offered requests), a drop-rate/SLA check, and a replica-hours
   check?
3. Does adding a short-horizon Holt forecast to EAES improve the SLA/energy
   trade-off under variable and bursty load?
4. Can a real single-node Kubernetes HPA be exercised to verify that the
   deployment, metrics path, and HPA controller work, without presenting that
   validation as the confirmatory experiment?

## 2. What is compared

Five strategies are implemented separately. No strategy calls itself Kubernetes
HPA.

| Name | Role | Kubernetes HPA? |
|---|---|---|
| `static` | Fixed three replicas | No |
| `cpu_threshold` | Legacy 80%/30% rule with 5% hysteresis and cooldowns | No |
| `hpa_formula` | Simulated HPA replica formula with 50% target, 10% tolerance, and 300 s scale-down stabilization | No; simulated formula only |
| `eaes` | SLA-first lexicographic controller using demand, ready/pending replicas, backlog, margin, cooldown, dwell, and stabilization | No; EAES-inspired |
| `forecasting_eaes` | EAES with a Holt forecast over the startup horizon | No; EAES-inspired ablation |

The original project used the word HPA for a toy 65/35 rule. That rule is now
labelled `cpu_threshold`. The actual Kubernetes HPA controller is used only in
the separate cluster validation. The `hpa_formula` strategy is a simulation of
the documented replica formula, not a deployed HPA object.

## 3. Confirmatory design

- **Unit of analysis:** one workload x seed x strategy run.
- **Pairing:** every strategy is run on the same deterministic arrival trace for
  a given workload and seed.
- **Workloads:** steady, light, medium, heavy, variable, bursty.
- **Seeds:** 1-10, ten per workload.
- **Runs:** 6 x 10 x 5 = 300.
- **Simulated duration:** 300 s.
- **Control interval:** 5 s.
- **Warm-up:** 30 s excluded from primary metrics; raw logs retain every tick,
  including warm-up.
- **Initial replicas:** three for all strategies, so no strategy starts with a
  strategy-specific advantage.
- **Primary window:** 30-300 s, 54 ticks per run, aggregated to one run-level
  value before inference.
- **Bootstrap:** 5,000 resamples, median paired difference for the headline
  effect, and mean/median descriptive intervals.
- **Test:** two-sided Wilcoxon signed-rank with a normal approximation on
  non-zero paired differences; Holm adjustment within each workload x baseline
  family. Cliff's delta is reported as an effect size.
- **Alpha:** 0.05, two-sided.

The same trace is reused across strategies for a seed. Traces are generated
deterministically and hashed in `traces/index.json` and the run manifest. The
runner records the trace hash per workload and verifies that all strategies used
the same trace.

## 4. Simulation model

The simulated cluster has fixed-capacity nodes (four pods per node), 10 req/s per
ready pod, a 10 s pod startup delay, a bounded queue, and min/max 1/10 replicas.
Only ready replicas contribute capacity. A controller that adds replicas during
a burst pays the startup delay.

Per 5 s tick:

1. Read ready replicas, pending replicas, capacity, backlog, CPU utilisation,
   and the previous arrival rate.
2. Ask the strategy for a desired replica count.
3. Apply the change; new replicas enter a pending queue.
4. Serve up to `ready_replicas x pod_capacity_rps x dt` requests from backlog
   plus new arrivals.
5. Drop requests only when the bounded queue overflows.
6. Compute modelled node energy from node utilisation.
7. Record one raw JSONL row with the decision, forecast, queue state, outcomes,
   and energy.

The initial state is three replicas and a 30 s warm-up. Primary metrics exclude
warm-up; raw logs retain it.

## 5. Workloads

Six deterministic classes are generated per seed:

| Class | Intended shape |
|---|---|
| `steady` | Constant moderate load |
| `light` | Low constant load |
| `medium` | Higher constant load |
| `heavy` | Near-capacity constant load |
| `variable` | Piecewise changes in demand |
| `bursty` | Short high-load bursts separated by low load |

All arrivals are seeded and recorded as counts per 5 s interval. The same trace
is used for all five strategies at a given workload and seed. Trace hashes in
the manifest make silent regeneration detectable.

## 6. Metrics

Run-level metrics are aggregated from the 54 post-warm-up ticks before any
inference:

- **Energy per served request (J):** modelled energy divided by served requests.
  The value is null, not zero or an artificial large number, when no requests
  were served.
- **Energy per offered request (J):** modelled energy divided by offered
  requests. This is shown beside the served denominator so a policy cannot look
  efficient merely by dropping traffic.
- **Drop rate:** dropped requests divided by offered requests.
- **SLA violation rate:** fraction of offered requests that were dropped or
  whose latency exceeded 500 ms. For a tick, the simulated latency is the
  analytic p95-like latency `base + 3 x wait`; charged requests above 500 ms are
  counted. This is a coarse tick-level rule, not a per-request empirical
  distribution.
- **P95 latency (ms):** run-level p95 of the modelled tick latency. It is not a
  measured per-request percentile.
- **Replica-hours:** integral of ready replicas over the measured duration,
  divided by 3600.
- **Scaling events:** number of up/down decisions in the measured window.
- **Oscillations:** up/down reversals within the configured window.
- **Total modelled energy (J)** and **average ready replicas** are shown on the
  dashboard for the selected workload and strategy.

Ticks are never treated as independent observations. Five-second ticks within a
run are strongly autocorrelated and are aggregated before any test.

## 7. Energy model

The node-level model is:

```text
P_node(u) = P_idle + (P_max - P_idle) * u        [W], u in [0, 1]
E_node    = P_node(u) * dt * PUE                 [J]
```

Nominal assumptions:

| Parameter | Value |
|---|---:|
| `P_idle` | 150 W |
| `P_max` | 500 W |
| PUE | 1.2 |
| Active nodes | `ceil(ready_replicas / 4)` |
| Pod attribution | Proportion of node power by pod CPU share; conservation checked |

Sensitivity scenarios use low (`80/300 W`) and high (`250/800 W`) power, with PUE
1.0, 1.2, 1.4, and 1.6. The controllers are energy-independent, so sensitivity
recomputes reported energy rather than decisions. The nominal recomputation
matched the confirmatory run exactly (maximum relative error `0.000e+00`).

**All energy values are estimates from a model.** They are not measured power.
See `docs/ENERGY_MODEL.md` for the limitations of the linear curve.

## 8. Strategy distinctions

### `static`

Three replicas, no scaling. It is a useful reference because it is cheap on
steady/light load and unsafe on heavy/bursty load.

### `cpu_threshold`

Legacy 80% scale-up / 30% scale-down rule with 5% hysteresis and 30 s / 60 s
cooldowns. It is retained for continuity. It is **not** Kubernetes HPA.

### `hpa_formula`

Simulated HPA replica formula:

```text
desired = ceil(current_replicas * current_metric / target_metric)
```

with tolerance and scale-down stabilization. It is a baseline implementation,
not the native HPA control loop. In these 300 s runs its 300 s scale-down
stabilization and 50% target make it provision heavily.

### `eaes`

SLA-first, lexicographic controller:

1. If predicted utilisation exceeds the SLA-safe target (`ceiling - margin`),
   scale up to the smallest count that restores the margin.
2. Otherwise consider one scale-down only after cooldown, minimum dwell, and an
   SLA-safe stabilization window.
3. Hold.

It uses demand, ready/pending replicas, backlog, CPU, and the margin. It is
EAES-inspired, not a reproduction of Li et al. (2025).

### `forecasting_eaes`

EAES with a Holt forecast over the startup horizon. The forecast is updated
online. It is an ablation, not a claim that forecasting is universally better.

### `oracle` (extension only)

Perfect foresight over the startup-delay horizon. It is an information upper
bound, not deployable, and it is never included in the confirmatory tables.

## 9. Real-cluster validation

The real validation is separate:

- single-node Minikube, Docker driver;
- native `autoscaling/v2` HPA, CPU target 50%, min 1, max 10;
- 80 req/s for 60 s, three repetitions per mode;
- real replica counts and HTTP outcomes;
- energy modelled from measured node CPU, not measured power.

It verifies packaging, metrics-server, the native HPA, and basic request service.
It does not validate the simulation's energy ranking. See
`docs/KUBERNETES_VALIDATION.md`.

## 10. Extensions

All extensions are labelled exploratory and live under `results/extension/` or
are explicitly labelled extension tables:

- perfect-foresight oracle upper bound;
- startup-delay sweep at 5, 10, and 20 s;
- 30-seed extension using seeds 11-30;
- energy/PUE sensitivity;
- energy-versus-drop Pareto plots;
- held-out forecast accuracy with zero-excluded MAPE;
- native-HPA recorded-sample replay.

None of these is pooled with the pre-specified 10-seed confirmatory comparison.
See `docs/EXTENSIONS.md`.

## 11. Reproducibility and provenance

The confirmatory run manifest records:

- run ID and start/end timestamps;
- config hashes and combined config hash;
- trace hashes;
- git commit and `git_tracked_dirty`;
- Python/package versions;
- energy scenario and execution mode;
- 300 summaries and 300 raw JSONL logs.

The protected input datasets are copied into `data/` and verified against fixed
SHA-256 hashes. The confirmatory run is preserved. Derived tables are generated
from it, not hand-edited. `reproduce.ps1` / `reproduce.sh` regenerate the
analysis; `scripts/clean_checkout_reproduction.ps1` reproduces in a disposable
clone and compares committed artifacts byte-for-byte.

See `docs/REPRODUCIBILITY.md` and `docs/verification_log.txt`.

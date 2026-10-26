# Methodology (detailed notes)

The authoritative methodology is [`../METHODOLOGY.md`](../METHODOLOGY.md). This
file records the simulation and statistical details needed to audit the
implementation. It does not replace the frozen plan in
[`../ANALYSIS_PLAN.md`](../ANALYSIS_PLAN.md).

## 1. Confirmatory unit and pairing

- Unit: one workload x seed x strategy run.
- Files: `results/runs/v3_paired_20261025T220942Z/<workload>_seed<N>_<strategy>.jsonl`.
- Pairing key: `(workload, seed)`.
- Sample size: 10 pairs per workload/strategy/baseline comparison.
- Ticks per run: 60 (300 s / 5 s), of which 54 are post-warm-up (30-300 s).
- Primary metrics are aggregated once per run; ticks are never independent
  observations.

## 2. Simulation mechanics

The backend is a deterministic discrete-time model:

- nodes hold four pods;
- a ready pod serves 10 req/s;
- new pods take 10 s to become ready;
- the queue is bounded by `max_queue_factor` x per-tick capacity;
- initial replicas are 3, min/max are 1/10;
- latency is modelled as `base_latency_ms + 3 x queue_wait`;
- requests are dropped only when the bounded queue overflows;
- CPU utilisation is derived from demand and ready capacity;
- energy is computed per tick from active-node CPU and PUE.

The model is not a Kubernetes scheduler or network simulator. It does not model
container image pull time, readiness-probe details, node pressure, retries,
multi-service dependencies, or heterogeneous hardware.

## 3. Statistics

### Descriptive

For each workload x strategy x metric, the generated table reports n, missing,
mean, median, standard deviation, mean 95% bootstrap CI, and median 95%
bootstrap CI. The bootstrap uses 5,000 resamples and fixed stable seeds derived
from the table key.

### Paired effects

For each workload x strategy x baseline x metric:

- differences are computed within each seed: strategy value minus baseline;
- the headline is the median paired difference with a 95% bootstrap CI;
- the mean paired difference is also generated;
- Wilcoxon signed-rank uses the normal approximation with tie correction;
- p-values are Holm-adjusted within each workload x baseline family across all
  metrics in that family;
- Cliff's delta is computed from the paired values.

If there are fewer than five non-zero differences, the test is marked
`not_testable` and no p-value is invented. This is why exact ties (for example,
EAES vs HPA on light) show `not testable`.

### Friedman/Nemenyi

The analysis generates Friedman and Nemenyi tables as secondary omnibus checks.
They are not used to rescue a non-significant pre-specified comparison. See
`results/tables/friedman.csv` and `results/tables/nemenyi.csv`.

## 4. Energy accounting

The model is:

```text
P_node(u) = P_idle + (P_max - P_idle) * u
E_node = P_node(u) * dt * PUE
```

Active nodes are `ceil(ready_replicas / 4)` with a minimum of one. Pod energy is
attributed by pod CPU share; the conservation error between node and pod totals
is recorded. Nominal `P_idle=150 W`, `P_max=500 W`, `PUE=1.2`.

The run-level energy per served request is:

```text
sum(node_energy_j over measured ticks) / sum(served_requests over measured ticks)
```

and energy per offered request uses the same numerator with offered requests.
A zero-served run yields null for the served denominator. No `max(1, count)` or
other artificial denominator is used.

## 5. Forecast

`forecasting_eaes` uses Holt with alpha 0.5 and beta 0.3 over a two-tick (10 s)
horizon. The forecast is updated online and recorded at decision time. The
held-out accuracy analysis uses the final 50% of each trace and MAPE excludes
zero and below-0.5 req/s actuals, with excluded counts reported.

The forecasting ablation is not a claim of universal superiority. Accuracy is
necessary but not sufficient for better control.

## 6. Extensions

The oracle, startup-delay sweep, 30-seed extension, energy/PUE sensitivity,
Pareto plots, forecast accuracy, and HPA replay are documented in
[`EXTENSIONS.md`](EXTENSIONS.md). They are exploratory and are not pooled with
the confirmatory result.

## 7. Historical documents

`SIMULATION_MODEL.md`, `STATISTICAL_ANALYSIS.md`, `ENERGY_MODEL.md`,
`EXPERIMENT_PROTOCOL.md`, and `THREATS_TO_VALIDITY.md` contain additional
historical detail. Where an older document conflicts with the root
[`../METHODOLOGY.md`](../METHODOLOGY.md), the root document and the generated
`results/RESULTS.md` are authoritative.

# Statistical Analysis

**Plan:** `ANALYSIS_PLAN.md` (frozen before the confirmatory run)  
**Run:** `v3_paired_20261025T220942Z`  
**Code:** `analysis/analyze.py`, `analysis/diagnose.py`  
**Outputs:** `results/tables/*.csv`, `results/RESULTS.md`, `results/analysis_manifest.json`

## 1. Unit, pairing, and sample size

The unit is a run (workload × seed × strategy). For each workload and seed, the five strategies consume the same deterministic arrival trace. Analysis is therefore paired by `(workload, seed)`.

- Workloads: 6.
- Seeds per workload: 10.
- Strategies: 5.
- Runs: 300.
- Paired comparisons: EAES and forecasting EAES each versus `cpu_threshold` and `hpa_formula`.
- Measurement window: 30–300 s (54 ticks of 5 s); warm-up retained only in raw logs.

The design is balanced: every strategy has 10 observations per workload, and every pair has 10 paired differences. There is no missing cell.

## 2. Descriptive statistics and confidence intervals

For each workload × strategy × metric:

- mean, median, standard deviation;
- 95% bootstrap percentile CI with 5,000 resamples;
- resampling seeds derived deterministically from workload, strategy, and metric via SHA-256.

The bootstrap is implemented without scipy. For a sample of `n`, each resample draws `n` values with replacement, computes the mean, and the 2.5th/97.5th percentiles are taken from the sorted resample means. The seed is stable, so rerunning produces identical intervals.

Bootstrap intervals describe uncertainty in the mean under the simulation’s seed-to-seed variation. They are not confidence intervals for a real cluster.

## 3. Paired tests

For every strategy-vs-baseline pair and metric, the analysis computes:

```text
diff_i = strategy_i − baseline_i
```

and applies a Wilcoxon signed-rank test:

- zero differences are discarded;
- absolute differences are average-ranked with ties;
- the normal approximation is used with tie correction;
- if fewer than five nonzero differences remain, the test is reported as `not_testable`;
- p-values are two-sided.

There is **no exact/permutation Wilcoxon branch** and no continuity correction. This is a deliberate, simple implementation to avoid a scipy dependency. With 10 pairs the normal approximation is reasonable but not exact.

The test is implemented in `wilcoxon_signed_rank()` and unit-tested against known small cases and edge conditions.

## 4. Multiple comparisons

Holm’s step-down correction is applied within each `(workload, baseline)` family. The family contains both EAES and forecasting-EAES rows and all metrics, i.e. up to 14 tests per family. The corrected value is stored as `p_holm`.

This is a conservative and pre-specified choice. It means a raw `p = 0.018` can fail after correction; that is reported rather than hidden.

The two baselines are separate families. No global correction across all six workloads is applied. The omnibus Friedman/Nemenyi analysis is a secondary check, not a replacement for the planned paired tests.

## 5. Effect size

Cliff’s delta is reported for each comparison:

```text
delta = (count(a > b) − count(a < b)) / (n_a × n_b)
```

It is computed over all pairs of observed values in the two strategy samples, not only over matched seeds. Values near ±1 indicate separation; values near 0 indicate overlap. It is an ordinal effect size, not a percentage energy saving.

## 6. Omnibus test and post-hoc ranks

The Friedman test is run for each workload × metric across the five strategies:

- complete seed blocks only;
- average ranks with tie correction;
- chi-square approximation with 4 degrees of freedom (five strategies);
- p-value from the exact chi-square survival function for df = 4.

Nemenyi’s post-hoc procedure uses the standard critical values for five groups (`q_0.05 = 2.728`) and:

```text
CD = q_0.05 × sqrt(k(k+1) / (6n))
```

Pairs whose mean-rank difference exceeds `CD` are marked significant. No correction is applied across workloads.

The Nemenyi result is deliberately secondary. It is conservative with 10 blocks; for example, the steady-workload energy omnibus test is significant (`Q = 28.0`, `p < 0.001`), but no steady energy pair exceeds the critical difference. This is not a contradiction: the omnibus test says at least one rank distribution differs, while the post-hoc procedure cannot localize it with this sample size.

## 7. Primary outcomes

The pre-specified primary metrics are:

- `energy_per_served_request_j`;
- `sla_violation_rate`;
- `replica_hours`;
- `drop_rate`.

Energy per offered request, served/offered ratio, latency, scaling events, oscillations, pending/ready replicas, over-provisioning, and rule counts are secondary/diagnostic.

No metric was added or removed after seeing the results.

## 8. Key numerical outcomes

All values are means over 10 seeds; nominal energy model.

### EAES vs simulated HPA formula

| Workload | E/served (EAES vs HPA) | Difference | Raw p | Holm p | Decision |
|---|---|---|---|---|---|
| steady | 22.577 vs 30.700 J | −8.123 J | 0.0180 | 0.0718 | Not significant after Holm |
| light | 46.722 vs 46.722 J | 0 | — | — | No nonzero differences |
| medium | 20.962 vs 32.208 J | −11.247 J | 0.0051 | 0.0446 | Significant |
| heavy | 18.578 vs 21.338 J | −2.759 J | 0.0051 | 0.0407 | Significant |
| variable | 23.022 vs 44.547 J | −21.525 J | 0.0051 | 0.0352 | Significant |
| bursty | 29.462 vs 30.447 J | −0.985 J | 0.0050 | 0.0302 | Significant |

EAES also has significantly fewer replica-hours than the HPA formula on every workload where the difference is testable, including steady and light where per-request energy is equal. Light is the important case: **fewer replica-hours did not reduce energy**, because three or fewer replicas fit on the same active node and the node pays idle power regardless. The node-level model is discussed in `docs/ENERGY_MODEL.md`.

### EAES vs legacy threshold

- Steady and light: no energy difference.
- Medium: EAES is **worse** by 3.225 J/request (Holm `p = 0.0470`).
- Heavy: EAES is worse by 1.184 J/request raw `p = 0.0051`, Holm `p = 0.0594` (not significant after correction), while EAES has much lower SLA violation rate (0.000 vs 0.320) and drop rate (0.000 vs 0.0105).
- Variable: EAES is worse by 1.152 J/request raw `p = 0.0431`, Holm `p = 0.1293`.
- Bursty: EAES is worse by 6.431 J/request raw `p = 0.0051`, Holm `p = 0.0506` (borderline), while EAES has much lower SLA violation rate (0.017 vs 0.748) and drop rate (0.000 vs 0.0339).

The threshold controller is not energy-aware and is not HPA. It is greedy and often under-provisions; its energy per served request can look attractive because it drops traffic or violates latency.

### Static baseline

Static three replicas is the lowest-energy strategy on steady, light, medium, and variable because 3 × 10 req/s covers those traces. It fails badly on heavy (drop rate 0.398, SLA violation rate 1.000) and bursty (drop rate 0.380, SLA violation rate 0.841). It is not a viable general policy, but its strong low-load energy result is a genuine finding and a caution against claiming that EAES dominates all baselines.

## 9. Forecasting ablation

- Holt and EWMA were evaluated on the held-out final 50% of each trace.
- EWMA has lower MAE than Holt on five of six workloads; Holt is slightly better only on `variable` (6.563 vs 6.687 req/s).
- Forecasting EAES removes the variable-workload SLA violations (0.0119 → 0.000) at 16.5% higher energy per served request (23.022 → 26.830 J) and more replica-hours (0.2699 → 0.3168).
- On bursty load, forecasting EAES is identical to reactive EAES (SLA 0.017, same energy and replica-hours). The forecast does not anticipate the 20 s burst enough to change the trajectory.
- On steady/light/medium/heavy, forecasting changes energy by at most 0.65% and provides no SLA benefit.

This is a mixed result: forecasting helps only where it has a smooth, predictable trend, and it costs energy even there. It is not a general improvement.

## 10. Sensitivity

Energy is recomputed from raw active-node and utilisation data under:

- `low`: 80/300 W;
- `nominal`: 150/500 W;
- `high`: 250/800 W;
- PUE 1.0, 1.2, 1.4, 1.6.

The planning assumption is that rankings are mostly preserved because all strategies share the same node utilisation signal. The tables in `results/tables/sensitivity.csv` should be consulted for exact values. The nominal recomputation agrees with the engine to `8.061e-16` relative error.

This is a **model sensitivity**, not an empirical robustness check. A different power curve could change the magnitude and, in close cases, the ranking.

## 11. Power and interpretation limits

- Ten seeds per cell provide limited power for small effects.
- Holm correction is conservative, and the family includes 14 tests.
- The HPA-formula baseline’s over-provisioning is partly a consequence of the configured 50% target and 300 s scale-down stabilization in a 300 s run. A different HPA configuration would produce different energy.
- The static baseline is unusually strong on four of six synthetic workloads because 3 × 10 req/s covers them. This is a property of the chosen traces.
- The node-level energy model does not reward reducing replicas while staying on the same node, which attenuates the apparent benefit of autoscaling on light load.
- Simulation significance is not external validity.

## 12. Reproduction

```powershell
python -m analysis.analyze
python -m analysis.diagnose
```

`analysis.analyze` writes `results/RESULTS.md`, `results/tables/*.csv`, and `results/analysis_manifest.json`. `analysis.diagnose` reads the raw JSONL tick logs and writes `results/EAES_DIAGNOSTIC.md` and `results/diagnostic.json`.

# Analysis Plan (pre-registered before the confirmatory diagnostic)

**Created:** 2026-10-26
**Status:** Frozen before the full 10-seed experiment was run.
**Scope:** paired simulation experiment, six workloads, five strategies.

## 1. Research question

Under a common trace, common backend, and common energy model, how do the five
strategies differ in modelled energy per served request, SLA violation rate,
replica-hours, and drop rate; and is any EAES energy disadvantage explained by
denominators, provisioning, or a genuine resource cost?

## 2. Design

- Workloads: steady, light, medium, heavy, variable, bursty.
- Seeds: 1–10 per workload (10 independent traces).
- Strategies: static, CPU threshold (legacy 80/30), HPA formula, EAES,
  forecasting EAES.
- One trace per (workload, seed), reused by all five strategies.
- Simulated duration 300 s; control interval 5 s; measurement window 30–300 s.
- Primary metrics are computed on the measurement window. Warm-up values are
  retained in raw logs and in `overall_*` fields.

## 3. Primary metrics and direction

| Metric | Direction | Definition |
|---|---|---|
| Energy per served request (J) | lower is better | modelled node energy / served requests; null if zero served |
| SLA violation rate | lower is better | (dropped + served above 500 ms) / offered |
| Replica-hours | lower is better | sum of ready replicas × dt / 3600 |
| Drop rate | lower is better | dropped / offered |

Secondary: P95 latency, scaling events, oscillations, forecast MAE/MAPE.

## 4. Statistical procedure

- Descriptive mean, median, 95% bootstrap CI (5,000 resamples, seed 12345).
- Paired differences by seed against CPU threshold and HPA formula.
- Bootstrap CI for paired mean differences.
- Wilcoxon signed-rank test, normal approximation with tie correction.
- Holm correction within each workload × baseline family.
- Friedman test across the five strategies per workload.
- Nemenyi post-hoc with critical difference at α = 0.05.
- Cliff's delta for effect size.
- No test is reported when the paired sample is too small or all differences
  are zero; such cases are labelled `not_testable` rather than given a p-value.
- Significance describes the simulation only.

## 5. EAES diagnostic (pre-specified)

1. Compare EAES vs HPA replica-hours.
2. Compare drop-rate differences.
3. Compare energy per served vs energy per offered.
4. Inspect cooldown/stabilization effects in raw decisions.
5. Compare node-level and pod-attributed energy.
6. Inspect startup-delay-driven replica inflation.
7. Check whether the SLA guard over-provisions.
8. Determine whether an energy disadvantage is caused by denominators or by
   actual modelled resource consumption.

Evidence must come from per-tick logs (replica trajectory, served, dropped,
energy). The diagnostic may conclude that EAES is worse; that outcome will be
reported without adjustment.

## 6. Multiplicity and exclusions

- All five strategies are analysed; no strategy is dropped after seeing results.
- Holm correction is applied to the pre-specified paired comparisons.
- Zero-served runs yield null energy per served; they are not replaced with an
  artificial denominator.
- Warm-up ticks are excluded from primary metrics but not deleted.

## 7. Sensitivity

Energy is recomputed from the same per-tick active-node and node-utilization
data under low, nominal, and high power scenarios and PUE 1.0–1.6. Scaling
decisions do not depend on energy, so this is a valid post-hoc energy
recalculation, not a new experiment.

## 8. What would falsify the energy-aware claim

EAES would not be supported as an energy-aware improvement if, for the same
trace, it fails to reduce SLA violations relative to static while also using
more energy per served request than HPA formula, or if its apparent advantage
disappears when the denominator is changed from served to offered requests.

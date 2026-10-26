# Results

**Confirmatory run:** `v3_paired_20261025T220942Z`  
**Design:** 6 workloads x 10 seeds x 5 strategies = 300 paired simulation runs  
**Execution mode:** simulation  
**Energy:** estimated from a node-level power model, **not measured**  
**Authoritative generated report:** `results/RESULTS.md`  
**Machine-readable tables:** `results/tables/headline.csv`,
`results/tables/paired_headline.csv`

The values below are generated from the preserved confirmatory run. They are not
typed from a separate analysis and are not pooled with extensions.

## 1. How to read the result

Lower is better for every metric in the table. Two denominators are always shown:

- **J/served** answers "how much modelled energy per request actually served?"
- **J/offered** answers "how much modelled energy per request offered?"

A strategy can look efficient per served request by dropping traffic. The drop
and SLA columns expose that. All energy values are model estimates.

SLA violation means a request was dropped or its modelled tick latency exceeded
500 ms. Ticks are aggregated to one run-level value before inference; the 54
post-warm-up ticks per run are not independent observations.

## 2. Descriptive results (10 seeds per cell)

Mean values. The 95% bootstrap intervals and medians are in
`results/tables/headline.csv`.

| Workload | Strategy | E/served J | E/offered J | Drop | SLA | Replica-h | P95 ms |
|---|---|---:|---:|---:|---:|---:|---:|
| steady | static | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2250 | 20.0000 |
| steady | cpu_threshold | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2250 | 20.0000 |
| steady | hpa_formula | 30.6999 | 30.6999 | 0.0000 | 0.0000 | 0.3633 | 20.0000 |
| steady | eaes | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2151 | 20.0000 |
| steady | forecasting_eaes | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2167 | 20.0000 |
| light | static | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.2250 | 20.0000 |
| light | cpu_threshold | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.0974 | 20.0000 |
| light | hpa_formula | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.2250 | 20.0000 |
| light | eaes | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.1131 | 20.0000 |
| light | forecasting_eaes | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.1146 | 20.0000 |
| medium | static | 17.7362 | 17.7362 | 0.0000 | 0.0000 | 0.2250 | 20.0000 |
| medium | cpu_threshold | 17.7362 | 17.7362 | 0.0000 | 0.0000 | 0.3000 | 20.0000 |
| medium | hpa_formula | 32.2085 | 32.2085 | 0.0000 | 0.0000 | 0.7500 | 20.0000 |
| medium | eaes | 20.9615 | 20.9615 | 0.0000 | 0.0000 | 0.3353 | 20.0000 |
| medium | forecasting_eaes | 21.0980 | 21.0980 | 0.0000 | 0.0000 | 0.3376 | 20.0000 |
| heavy | static | 16.5000 | 9.9344 | 0.3979 | 1.0000 | 0.2250 | 30020.0000 |
| heavy | cpu_threshold | 17.3944 | 17.7221 | 0.0105 | 0.3202 | 0.5062 | 26654.3000 |
| heavy | hpa_formula | 21.3375 | 21.3375 | 0.0000 | 0.0000 | 0.7500 | 20.0000 |
| heavy | eaes | 18.5782 | 18.5782 | 0.0000 | 0.0000 | 0.6101 | 20.0000 |
| heavy | forecasting_eaes | 18.6521 | 18.6521 | 0.0000 | 0.0000 | 0.6126 | 20.0000 |
| variable | static | 21.8699 | 21.8699 | 0.0000 | 0.0000 | 0.2250 | 20.0000 |
| variable | cpu_threshold | 21.8699 | 21.8699 | 0.0000 | 0.0094 | 0.2582 | 111.5000 |
| variable | hpa_formula | 44.5468 | 44.5468 | 0.0000 | 0.0000 | 0.7258 | 20.0000 |
| variable | eaes | 23.0221 | 23.0221 | 0.0000 | 0.0119 | 0.2753 | 20.0000 |
| variable | forecasting_eaes | 26.8300 | 26.8300 | 0.0000 | 0.0000 | 0.3221 | 20.0000 |
| bursty | static | 21.1145 | 13.2261 | 0.3803 | 0.8412 | 0.2250 | 30020.0000 |
| bursty | cpu_threshold | 23.0307 | 22.4041 | 0.0339 | 0.7483 | 0.4500 | 25057.8750 |
| bursty | hpa_formula | 30.4467 | 30.4467 | 0.0000 | 0.0000 | 0.7500 | 20.0000 |
| bursty | eaes | 29.4617 | 29.4617 | 0.0000 | 0.0170 | 0.7167 | 337.1375 |
| bursty | forecasting_eaes | 29.4617 | 29.4617 | 0.0000 | 0.0170 | 0.7167 | 337.1375 |

### Immediate observations

- **Static heavy/bursty is unsafe.** Static drops 39.8% of heavy and 38.0% of
  bursty offered traffic, and its SLA violation rates are 100% and 84.1%. Its low
  energy per served request is therefore not a valid efficiency win.
- **EAES ties or beats the HPA formula on energy per served request** in all six
  workloads by mean, with the largest gap on variable (23.02 vs 44.55 J) and
  medium (20.96 vs 32.21 J). It is identical on light.
- **EAES provisions fewer replica-hours than the HPA formula** in every workload
  (for example, light 0.1131 versus 0.2250; medium 0.3353 versus 0.7500).
- **EAES pays for it with small SLA violations** on variable (1.19%) and bursty
  (1.70%). The forecast variant removes the variable violations but costs more
  energy there (26.83 vs 23.02 J/served); it does not remove bursty violations.
- **The `hpa_formula` baseline is aggressive.** Its 300 s scale-down
  stabilization and 50% target keep 0.75 replica-hours in medium/heavy/bursty
  and 0.36/0.73 in steady/variable. A different HPA configuration would change
  the comparison.

## 3. Paired EAES-versus-HPA energy per served request

Cells are **median paired difference [95% bootstrap CI]** for EAES minus
`hpa_formula`, paired by workload and seed. Negative favours EAES. The p-value is
the Holm-adjusted Wilcoxon p-value within the pre-specified workload x baseline
family.

| Workload | Median diff J [95% CI] | Holm p | Cliff's d |
|---|---:|---:|---:|
| steady | -11.1557 [-11.8710, 0.0000] | 0.1437 | -0.77 |
| light | 0.0000 [0.0000, 0.0000] | not testable | 0.00 |
| medium | -11.3242 [-12.0849, -10.1942] | 0.0624 | -1.00 |
| heavy | -2.8408 [-3.5907, -2.1220] | 0.0882 | -1.00 |
| variable | -21.5639 [-22.7475, -20.3176] | 0.0619 | -1.00 |
| bursty | -0.9880 [-0.9947, -0.9776] | 0.0755 | -1.00 |

**No confirmatory comparison is Holm-significant at alpha = 0.05.** The intervals
exclude zero for medium, heavy, variable, and bursty, and Cliff's delta is -1.00
there, but the Holm-adjusted p-values remain above 0.05. The honest summary is
"consistent direction and large paired effect, not statistically significant
under the pre-specified correction with ten seeds."

EAES versus `cpu_threshold` is also not Holm-significant. It is equal on
steady/light and *higher* by median on medium (+3.06 J), heavy (+1.11 J),
variable (+1.13 J), and bursty (+6.40 J), because the legacy threshold rule
provisions less and sometimes violates the SLA. This is not an energy win; it is
a different operating point.

## 4. 30-seed extension (exploratory)

The 30-seed extension uses seeds 11-30 and is reported separately. Combined with
the confirmatory seeds it gives 30 traces per workload. It is not a replacement
for the pre-specified 10-seed inference. In the extension, EAES versus
`hpa_formula` energy per served request is Holm-significant for medium, heavy,
variable, and bursty; steady and light are not testable or not significant.
Directions agree with the confirmatory table. See
`results/extension/seed30/RESULTS_30SEED.md`.

This is the correct reading: the confirmatory result is directionally consistent
but underpowered after correction; the larger exploratory extension strengthens
the direction without changing the confirmatory claim.

## 5. Energy/PUE sensitivity (exploratory)

Low/nominal/high power and PUE 1.0-1.6 produced **no rank changes** across the
five strategies in any workload. The controllers are energy-independent, so this
is a post-hoc recalculation of the same trajectories. Ties are exact and their
numeric rank order is arbitrary. Nominal recomputation matched the confirmatory
run with maximum relative error `0.000e+00`. See
`results/extension/energy_sensitivity/ENERGY_SENSITIVITY.md`.

## 6. Forecasting evidence (exploratory/ablation)

Held-out EWMA has lower MAE than Holt on every workload inspected; the 30-seed
extension is not used for forecast accuracy. On the confirmatory run, the
forecast variant does not remove bursty SLA violations and costs more energy on
variable load. The startup sweep shows the forecast variant improves variable
SLA at 10 s and 20 s startup delays while using more energy; at 20 s delay it
also slightly increases heavy and medium energy. See
`results/tables/forecast_accuracy.md` and
`results/extension/startup_sweep/STARTUP_SWEEP.md`.

Forecast accuracy alone is not a controller win. The decision relevance table is
in `results/tables/forecast_decision_relevance.csv`.

## 7. Oracle upper bound (exploratory only)

The perfect-foresight oracle over the startup horizon is an information upper
bound, not a deployable controller. It matches or beats EAES on energy per
served request in several workloads, but it also uses more replica-hours than
EAES in some cells and is never included in the confirmatory comparison. For
example, bursty E/served is 26.63 J for the oracle versus 29.46 J for EAES, with
oracle SLA 0.0000 versus 0.0170. This is a bound on the value of better workload
information, not evidence that an online controller can achieve it. See
`results/extension/oracle/ORACLE.md`.

## 8. Native-HPA replay (exploratory validation)

Thirty recorded steady-state transitions from the Minikube validation were
replayed through the offline `hpa_formula` strategy. Predicted desired replicas
agreed with the next recorded spec in 100% of transitions; there were zero
predicted or observed changes between samples. This is weak evidence: load was
steady, the native HPA was already at four replicas, and the initial 1->4
scale-up was not observed. It does not validate bursts or cold starts. See
`results/extension/hpa_replay/HPA_REPLAY.md`.

## 9. What this does and does not establish

Established in this simulation:

- the five strategies are implemented separately and run on identical traces;
- the analysis pipeline aggregates ticks to run-level values and pairs by seed;
- EAES has a consistent directional energy-per-served advantage over the
  simulated HPA formula, with lower replica-hours on most workloads;
- the advantage comes with small SLA violations on variable/bursty load and is
  not Holm-significant in the confirmatory 10-seed analysis;
- static's low energy per served request on heavy/bursty is explained by
  dropping traffic, not by efficiency.

Not established:

- physical energy savings;
- production behavior, multi-node behavior, or behavior under failures;
- native-HPA equivalence under bursts or cold starts;
- optimality, cost savings, or carbon savings;
- reproducibility of Li et al. (2025).

See `LIMITATIONS.md` for the full list.

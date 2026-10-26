# Extensions

All work in this document is **exploratory/extension evidence**. It is generated
and stored separately from the pre-specified ten-seed confirmatory comparison.
Extension manifests record `label: exploratory_extension` (or
`validation_extension`), `confirmatory_run_unchanged:
v3_paired_20261025T220942Z`, the git commit, and `git_tracked_dirty: false`.

All energy is modelled, not measured.

## 1. Oracle upper bound

**Output:** `results/extension/oracle/`  
**Runner:** `python -m experiments.run_extensions`  
**Design:** 6 workloads x 10 seeds x 6 controllers = 360 runs. The oracle reads
the true future arrival trace over the startup-delay horizon and sizes for its
peak.

The oracle uses the same simulation, energy model, replica bounds (1-10), SLA
margin, and traces. It is an information upper bound, not a deployable
controller.

Selected results (mean E/served J, SLA, replica-hours):

| Workload | EAES | Forecasting EAES | Oracle | Oracle vs EAES |
|---|---:|---:|---:|---|
| steady | 22.58 / 0.0000 / 0.215 | 22.58 / 0.0000 / 0.217 | 22.58 / 0.0000 / 0.225 | energy tie; more replica-hours |
| light | 46.72 / 0.0000 / 0.113 | 46.72 / 0.0000 / 0.115 | 46.72 / 0.0000 / 0.085 | energy tie; fewer replica-hours |
| medium | 20.96 / 0.0000 / 0.335 | 21.10 / 0.0000 / 0.338 | 18.83 / 0.0000 / 0.316 | lower energy and replica-hours |
| heavy | 18.58 / 0.0000 / 0.610 | 18.65 / 0.0000 / 0.613 | 17.96 / 0.0000 / 0.603 | lower energy and replica-hours |
| variable | 23.02 / 0.0119 / 0.275 | 26.83 / 0.0000 / 0.322 | 22.10 / 0.0000 / 0.229 | lower energy, SLA 0, fewer replica-hours |
| bursty | 29.46 / 0.0170 / 0.717 | 29.46 / 0.0170 / 0.717 | 26.63 / 0.0000 / 0.618 | lower energy, SLA 0, fewer replica-hours |

Interpretation: the gap between EAES and the oracle is a rough bound on what
better workload information could buy in this simulation. It is not evidence
that any online controller can achieve the oracle, and the oracle is excluded
from the confirmatory table.

## 2. Startup-delay sweep

**Output:** `results/extension/startup_sweep/`  
**Design:** 6 workloads x 2 strategies (EAES, forecasting EAES) x 3 delays
(5, 10, 20 s) x 10 seeds = 360 runs.

Where forecasting changes the outcome:

| Delay | Workload | EAES E/served | Forecast E/served | EAES SLA | Forecast SLA |
|---:|---|---:|---:|---:|---:|
| 5 s | variable | 23.13 | 25.89 | 0.0000 | 0.0000 |
| 10 s | medium | 20.96 | 21.10 | 0.0000 | 0.0000 |
| 10 s | heavy | 18.58 | 18.65 | 0.0000 | 0.0000 |
| 10 s | variable | 23.02 | 26.83 | 0.0119 | 0.0000 |
| 20 s | medium | 20.41 | 20.95 | 0.0000 | 0.0000 |
| 20 s | heavy | 18.36 | 18.65 | 0.0352 | 0.0352 |
| 20 s | variable | 22.81 | 28.20 | 0.1136 | 0.0035 |

No delay produced a forecasting SLA benefit on bursty load. Forecasting improved
variable-load SLA at 10 s and 20 s but at higher energy per served request. At
20 s it did not reduce heavy SLA and cost slightly more energy. The sweep covers
only three delays and cannot represent arbitrary Kubernetes scheduling or image
pull latency.

## 3. 30-seed extension

**Output:** `results/extension/seed30/`  
**Design:** seeds 11-30 x 6 workloads x 5 confirmatory strategies = 600 runs.
Combined with confirmatory seeds 1-10, this gives 30 traces per workload. It is
not a replacement for the pre-specified ten-seed inference.

EAES versus HPA formula, energy per served request, median paired difference
[95% CI] and Holm p:

| Workload | Median diff J [95% CI] | Holm p |
|---|---:|---:|
| steady | 0.0000 [0.0000, 0.0000] | 0.3449 |
| light | 0.0000 [0.0000, 0.0000] | not testable |
| medium | -10.7518 [-11.4153, -10.2688] | 0.001094 |
| heavy | -2.8399 [-2.8612, -2.1717] | 0.001522 |
| variable | -20.1116 [-21.7246, -17.9496] | 0.001165 |
| bursty | -0.9790 [-0.9832, -0.9729] | 0.001504 |

EAES versus CPU threshold remains higher in energy per served request on medium,
heavy, variable, and bursty; the threshold rule provides less capacity and has
worse SLA on heavy/bursty. The direction of the 30-seed EAES-vs-HPA result agrees
with the confirmatory direction. The steady result is an instability worth
reporting: with 30 seeds the median paired difference is exactly zero, while the
confirmatory ten-seed median was -11.16 J with a CI touching zero and a
non-significant Holm p.

## 4. Energy and PUE sensitivity

**Output:** `results/extension/energy_sensitivity/`  
**Design:** 3 power scenarios (low `80/300 W`, nominal `150/500 W`, high
`250/800 W`) x 4 PUE values (1.0, 1.2, 1.4, 1.6) x 300 runs = 3,600 runs.

The controllers are energy-independent, so this is a post-hoc recalculation of
the same trajectories. Nominal recomputation matched the confirmatory run with
maximum relative error `0.000e+00`.

**No rank changes** were observed across the tested power/PUE configurations.
Exact ties share values; their numeric rank order is arbitrary and should not be
interpreted as a real difference. See
`results/extension/energy_sensitivity/ENERGY_SENSITIVITY.md` and
`rank_stability.csv`.

## 5. Energy-versus-drop Pareto plots

**Output:** `results/extension/energy_vs_drop/`

Six SVGs, one per workload. The x axis is estimated energy per **offered**
request; the y axis is drop rate. A policy that serves less traffic cannot look
efficient merely because its denominator is smaller.

| Workload | Pareto-frontier strategies |
|---|---|
| bursty | static, cpu_threshold, eaes, forecasting_eaes |
| heavy | static, cpu_threshold, eaes |
| light | static, cpu_threshold, hpa_formula, eaes, forecasting_eaes |
| medium | static, cpu_threshold |
| steady | static, cpu_threshold, eaes, forecasting_eaes |
| variable | static, cpu_threshold |

The frontier includes static and CPU threshold on heavy/bursty because they use
less energy per offered request, but those points have very high drop/SLA. The
Pareto plot is a two-axis view, not a policy recommendation. It does not encode
latency, SLA, or replica-hours.

## 6. Forecast accuracy and decision relevance

**Outputs:** `results/tables/forecast_accuracy.md`,
`forecast_accuracy.csv`, `forecast_accuracy_summary.csv`,
`forecast_decision_relevance.csv`  
**Runner:** `python -m analysis.forecast_accuracy`

Design: final 50% of each trace, two-step (10 s) horizon, online update, 10
workload/seed traces. MAPE excludes actual rates below 0.5 req/s and every zero;
the excluded count is reported. This is a held-out final segment, not a
rolling-origin retraining study.

Findings:

- EWMA has lower MAE than Holt on every workload inspected.
- Bursty MAE is very large for both (EWMA 39.66, Holt 45.33) because a two-step
  horizon cannot anticipate a burst that starts after the forecast is made.
- On the confirmatory run, forecasting did not remove bursty SLA violations
  (0.0170 for both) and cost more energy on variable (26.83 vs 23.02 J/served).
- Accuracy alone is not a controller win. The decision-relevance table is the
  appropriate join.

## 7. Native-HPA replay

**Output:** `results/extension/hpa_replay/`  
**Runner:** `python -m analysis.hpa_replay`

The recorded native-HPA pod CPU and replica samples from the Minikube validation
were replayed through the offline `hpa_formula` strategy. No metric series or
replica trajectory was invented.

- recorded files: `hpa_rep1.json`, `hpa_rep2.json`, `hpa_rep3.json`;
- comparable transitions: 30;
- predicted desired replicas agree with the next recorded spec: 100%;
- predicted replica changes: 0;
- observed replica changes between samples: 0.

This is weak evidence. Load was steady, the native HPA was already at four
replicas, and the initial 1->4 scale-up was not observed. It does not validate
bursts, cold starts, or the native controller's full loop. See
`results/extension/hpa_replay/HPA_REPLAY.md`.

## 8. Status summary

| Extension | Implementation | Generated evidence | Interpretation status |
|---|---|---|---|
| Oracle upper bound | Complete | 360 runs + report | Exploratory; not deployable |
| Startup-delay sweep | Complete | 360 runs + report | Exploratory; 3 delays only |
| 30-seed extension | Complete | 600 runs + report | Exploratory; direction agrees |
| Energy/PUE sensitivity | Complete | 3,600 runs + report | Exploratory; no rank change |
| Energy-vs-drop Pareto | Complete | 6 SVGs + CSV | Exploratory; two-axis view |
| Forecast accuracy | Complete | 120 forecast rows + 12 summaries + report | Ablation; short horizon |
| Native-HPA replay | Complete | 30 transitions + report | Weak steady-state validation |

All extension outputs are outside the confirmatory inference. See
`results/extension/manifest.json` and the individual manifests for provenance.

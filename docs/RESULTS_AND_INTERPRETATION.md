# Results and Interpretation

**Generated source:** `results/RESULTS.md`, `results/EAES_DIAGNOSTIC.md`  
**Run:** `v3_paired_20261025T220942Z`  
**Mode:** simulation, 10 seeds per workload, 30–300 s measurement window  
**Energy:** modelled at nominal `P_idle = 150 W`, `P_max = 500 W`, `PUE = 1.2`

This document interprets the generated results. It does not replace the generated tables, and it does not turn simulation output into measurements.

## 1. Headline

Against the simulated Kubernetes HPA formula, EAES uses less modelled energy per served request on steady, medium, heavy, variable, and bursty workloads, and the same energy on light. After Holm correction, the per-request energy difference is statistically significant on medium, heavy, variable, and bursty; the steady difference is not significant after correction.

Against the legacy threshold controller, EAES is not an energy win: its per-request energy is higher on medium (significant after Holm), and higher on heavy, variable, and bursty before correction, with the heavy and bursty Holm results falling just above or at the 0.05 boundary. It does, however, avoid most or all of the threshold controller’s SLA violations on heavy and bursty.

Against static three replicas, EAES is not the lowest-energy policy on four of six workloads. Static is efficient on steady, light, medium, and variable because 30 req/s of capacity covers those traces. Static fails on heavy and bursty, where it drops about 40% of requests and violates the SLA for essentially all offered work.

**The honest summary is therefore conditional, not triumphal:** EAES is a better energy/SLA compromise than the over-provisioning HPA-formula baseline and a much safer policy than static under heavy/bursty load, but it is not Pareto-dominant, and its energy advantage over the HPA formula is partly a consequence of the HPA configuration and the synthetic traces.

## 2. Primary table

Means over 10 seeds. `E/served` is J per served request; `SLA` is violation fraction of offered requests; `Drop` is dropped fraction of offered; `RH` is replica-hours in the measurement window.

### Steady (15 req/s)

| Strategy | E/served | SLA | Drop | RH |
|---|---:|---:|---:|---:|
| static | 22.577 | 0.000 | 0.000 | 0.225 |
| cpu_threshold | 22.577 | 0.000 | 0.000 | 0.225 |
| hpa_formula | 30.700 | 0.000 | 0.000 | 0.363 |
| eaes | 22.577 | 0.000 | 0.000 | 0.215 |
| forecasting_eaes | 22.577 | 0.000 | 0.000 | 0.217 |

### Light (5 req/s)

| Strategy | E/served | SLA | Drop | RH |
|---|---:|---:|---:|---:|
| static | 46.722 | 0.000 | 0.000 | 0.225 |
| cpu_threshold | 46.722 | 0.000 | 0.000 | 0.097 |
| hpa_formula | 46.722 | 0.000 | 0.000 | 0.225 |
| eaes | 46.722 | 0.000 | 0.000 | 0.113 |
| forecasting_eaes | 46.722 | 0.000 | 0.000 | 0.115 |

### Medium (25 req/s)

| Strategy | E/served | SLA | Drop | RH |
|---|---:|---:|---:|---:|
| static | 17.736 | 0.000 | 0.000 | 0.225 |
| cpu_threshold | 17.736 | 0.000 | 0.000 | 0.300 |
| hpa_formula | 32.208 | 0.000 | 0.000 | 0.750 |
| eaes | 20.962 | 0.000 | 0.000 | 0.335 |
| forecasting_eaes | 21.098 | 0.000 | 0.000 | 0.338 |

### Heavy (50 req/s)

| Strategy | E/served | SLA | Drop | RH |
|---|---:|---:|---:|---:|
| static | 16.500 | 1.000 | 0.398 | 0.225 |
| cpu_threshold | 17.394 | 0.320 | 0.011 | 0.506 |
| hpa_formula | 21.338 | 0.000 | 0.000 | 0.750 |
| eaes | 18.578 | 0.000 | 0.000 | 0.610 |
| forecasting_eaes | 18.652 | 0.000 | 0.000 | 0.613 |

### Variable (5–25 req/s sinusoid)

| Strategy | E/served | SLA | Drop | RH |
|---|---:|---:|---:|---:|
| static | 21.870 | 0.000 | 0.000 | 0.225 |
| cpu_threshold | 21.870 | 0.009 | 0.000 | 0.258 |
| hpa_formula | 44.547 | 0.000 | 0.000 | 0.726 |
| eaes | 23.022 | 0.012 | 0.000 | 0.275 |
| forecasting_eaes | 26.830 | 0.000 | 0.000 | 0.322 |

### Bursty (5 req/s, 20 s at 80 req/s every 60 s)

| Strategy | E/served | SLA | Drop | RH |
|---|---:|---:|---:|---:|
| static | 21.115 | 0.841 | 0.380 | 0.225 |
| cpu_threshold | 23.031 | 0.748 | 0.034 | 0.450 |
| hpa_formula | 30.447 | 0.000 | 0.000 | 0.750 |
| eaes | 29.462 | 0.017 | 0.000 | 0.717 |
| forecasting_eaes | 29.462 | 0.017 | 0.000 | 0.717 |

## 3. Why the HPA-formula baseline uses so much energy

The simulated HPA formula is not a strawman in its arithmetic: it implements a target utilisation, a tolerance band, `ceil(current × ratio)`, bounds, and a scale-down stabilization window. But three choices interact badly in a 300 s experiment:

1. **Target 50%** means a steady 15 req/s load on 3 × 10 req/s pods is already at 50%. Small utilisation noise pushes the ratio above the tolerance, and the formula adds replicas.
2. **At least +1 on scale-up** plus no scale-down during the 300 s stabilization window means those replicas are retained for the rest of the run.
3. **The simulated CPU signal includes queueing and warm-up transients**, so the HPA sees above-target load before the system settles.

The result is that the HPA formula ends steady with about 4.9 ready replicas and medium with the maximum 10, even though 3 replicas can serve those offered loads. This is a real property of this simulated configuration, not a universal property of Kubernetes HPA. Real HPA performance depends on scrape interval, tolerance, stabilization, target, and workload; the Phase 7 Minikube validation shows the native HPA scaling 1 → 4 under its own configuration, not these numbers.

This is a threat to the fairness of the comparison and is discussed in `docs/THREATS_TO_VALIDITY.md`.

## 4. Why light-load energy is flat while replica-hours fall

On the light workload, EAES uses 0.113 replica-hours versus 0.225 for static/HPA, but all strategies have the same 46.722 J per served request. This is not a bug: at 5 req/s, one node with one to four pods is dominated by node idle power. Reducing from three ready replicas to one or two does not necessarily remove the node, so total node energy stays nearly flat. The dynamic component is small, and node utilisation is computed against a full four-pod node capacity.

This is an important modelling limitation. Replica-hours are a more sensitive indicator of provisioning than modelled energy in this regime. A finer-grained node/power model, or a model that powers down empty nodes, would produce a different result. The model does power down nodes when `ready = 0`, but not when a node remains occupied by one pod.

## 5. Why medium is a negative result for EAES

At 25 req/s, three pods provide 30 req/s, so static serves everything with no drops and no SLA violations at 17.736 J/request. EAES targets 70% utilisation; 25/30 = 83.3% is above its 80% ceiling, so EAES scales to 4–5 replicas. That restores margin but costs 20.962 J/request, significantly more than static and significantly more than the threshold controller in this trace.

This is a direct consequence of the SLA-first target, not an implementation accident. If the goal is to minimise energy while meeting a 500 ms SLA, EAES is too conservative at moderate load. A tuned EAES with a higher ceiling or an explicit energy-aware hold rule could avoid this, but that would be a different, post-hoc design. It is not claimed here.

## 6. Variable and bursty: EAES’s real failure mode

Reactive EAES has zero drops on variable and bursty, and its SLA violation rates are small in absolute terms (0.012 and 0.017). But the comparison baseline HPA has zero. The violations come from startup delay: EAES decides to scale when the margin is breached, but the new replicas need 10 s to become ready. During that window, some requests queue long enough to exceed 500 ms.

On variable load, forecasting EAES removes the violations by anticipating the sinusoid, at 16.5% higher energy and 17.0% more replica-hours. That is a genuine trade-off, not a free improvement.

On bursty load, forecasting EAES is identical to reactive EAES. The 20 s burst is too abrupt for a 2-tick Holt forecast to anticipate. All adaptive strategies reach 10 replicas; the HPA formula stays at 10 and therefore records zero violations, while EAES tries to scale down between bursts and gets caught by the next one. The result is a small but real EAES SLA penalty.

## 7. Static is not a safe shortcut

Static has the lowest energy per served request on heavy (16.500 J) and bursty (21.115 J), but it drops 39.8% and 38.0% of offered requests respectively and has SLA violation rates of 1.000 and 0.841. Reporting only J/request would make static look best. This is exactly the denominator/drop trap that the diagnostic was designed to catch. Any use of static as a baseline must include drop and SLA columns.

## 8. Forecast evaluation

Holt is not generally better than EWMA on these traces:

| Workload | EWMA MAE | Holt MAE |
|---|---:|---:|
| steady | 1.524 | 1.901 |
| light | 0.874 | 1.077 |
| medium | 1.984 | 2.471 |
| heavy | 2.798 | 3.481 |
| variable | 6.687 | 6.563 |
| bursty | 39.660 | 45.327 |

Holt wins only on the smooth variable sinusoid, by a small margin. This explains why forecast EAES helps there and not elsewhere. The name `forecasting_eaes` should not be read as evidence that Holt is the right forecaster in general.

## 9. Sensitivity

The low/nominal/high and PUE tables are in `results/tables/sensitivity.csv`. In the tested scenarios, the EAES/HPA energy-per-served ratio is stable:

| Workload | Low | Nominal | High |
|---|---:|---:|---:|
| steady | 0.750 | 0.734 | 0.729 |
| light | 1.000 | 1.000 | 1.000 |
| medium | 0.670 | 0.651 | 0.644 |
| heavy | 0.881 | 0.871 | 0.867 |
| variable | 0.536 | 0.517 | 0.510 |
| bursty | 0.970 | 0.968 | 0.967 |

PUE multiplies every strategy’s energy by the same factor, so it cannot change rankings. The low/high scenarios change the idle/dynamic mixture but not the sign of the EAES-vs-HPA difference in these runs. This is a model sensitivity result, not proof of robustness to a different power curve.

## 10. Statistical reading

- Medium, heavy, variable, and bursty EAES-vs-HPA energy differences survive Holm correction.
- Steady EAES-vs-HPA is raw `p = 0.0180`, Holm `p = 0.0718`; the bootstrap CI excludes zero but the corrected test does not. Do not call it significant.
- Light has no nonzero paired differences for per-request energy because all strategies produce the same energy.
- Replica-hour reductions are significant on every testable workload.
- EAES’s higher energy than the threshold controller on medium is significant; the heavy and bursty differences are not significant after Holm, but the SLA improvements are large and directionally important.
- Friedman tests support differences in energy and replica-hours across strategies on most workloads; Nemenyi is conservative and does not localize every omnibus result.

See `docs/STATISTICAL_ANALYSIS.md` for the test mechanics and correction family.

## 11. What can and cannot be concluded

Can conclude, within this simulation:

- The simulated HPA formula over-provisions relative to EAES under these traces and configuration.
- EAES reduces replica-hours relative to the HPA formula.
- EAES is safer than static under heavy and bursty load.
- Reactive EAES has a small startup-delay SLA penalty on variable and bursty load.
- Forecasting helps the variable sinusoid and fails to help the abrupt burst.
- Static is a strong low-load energy baseline and an unsafe heavy/bursty policy.
- The results are sensitive to controller targets, HPA stabilization, trace shape, and the node-level energy model.

Cannot conclude:

- That EAES would save energy in a production cluster.
- That a native Kubernetes HPA with a different configuration would behave like `hpa_formula`.
- That the modelled joules correspond to any specific hardware.
- That Li et al. (2025) reported these numbers.
- That the original 27-row dataset supports any of this.

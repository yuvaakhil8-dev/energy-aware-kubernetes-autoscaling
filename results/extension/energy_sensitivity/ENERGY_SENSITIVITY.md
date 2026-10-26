# Energy sensitivity (extension)

The controllers are energy-independent, so low/nominal/high power and PUE values only recompute the reported energy. Every configuration uses the same seeds and traces.

Nominal recomputation check against the confirmatory run: maximum relative error `0.000e+00` across all 300 nominal/PUE-1.2 runs.

## Ranking by mean estimated energy per served request (nominal power)

Rank 1 is the lowest energy per served request. Read this with the drop and SLA columns; a low rank can reflect unmet demand. Exact energy ties share the same value; their numeric rank order is arbitrary and should not be interpreted as a real difference.

| Workload | Strategy | Rank | E/served J | E/offered J | Drop | SLA | Replica-h |
|---|---|---|---|---|---|---|---|
| bursty | static | 1 | 21.1145 | 13.2261 | 0.3803 | 0.8412 | 0.2250 |
| bursty | cpu_threshold | 2 | 23.0307 | 22.4041 | 0.0339 | 0.7483 | 0.4500 |
| bursty | eaes | 3 | 29.4617 | 29.4617 | 0.0000 | 0.0170 | 0.7167 |
| bursty | forecasting_eaes | 4 | 29.4617 | 29.4617 | 0.0000 | 0.0170 | 0.7167 |
| bursty | hpa_formula | 5 | 30.4467 | 30.4467 | 0.0000 | 0.0000 | 0.7500 |
| heavy | static | 1 | 16.5000 | 9.9344 | 0.3979 | 1.0000 | 0.2250 |
| heavy | cpu_threshold | 2 | 17.3944 | 17.7221 | 0.0105 | 0.3202 | 0.5062 |
| heavy | eaes | 3 | 18.5782 | 18.5782 | 0.0000 | 0.0000 | 0.6101 |
| heavy | forecasting_eaes | 4 | 18.6521 | 18.6521 | 0.0000 | 0.0000 | 0.6126 |
| heavy | hpa_formula | 5 | 21.3375 | 21.3375 | 0.0000 | 0.0000 | 0.7500 |
| light | cpu_threshold | 1 | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.0974 |
| light | eaes | 2 | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.1131 |
| light | forecasting_eaes | 3 | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.1146 |
| light | hpa_formula | 4 | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.2250 |
| light | static | 5 | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.2250 |
| medium | cpu_threshold | 1 | 17.7362 | 17.7362 | 0.0000 | 0.0000 | 0.3000 |
| medium | static | 2 | 17.7362 | 17.7362 | 0.0000 | 0.0000 | 0.2250 |
| medium | eaes | 3 | 20.9615 | 20.9615 | 0.0000 | 0.0000 | 0.3353 |
| medium | forecasting_eaes | 4 | 21.0980 | 21.0980 | 0.0000 | 0.0000 | 0.3376 |
| medium | hpa_formula | 5 | 32.2085 | 32.2085 | 0.0000 | 0.0000 | 0.7500 |
| steady | cpu_threshold | 1 | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2250 |
| steady | eaes | 2 | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2151 |
| steady | forecasting_eaes | 3 | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2167 |
| steady | static | 4 | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2250 |
| steady | hpa_formula | 5 | 30.6999 | 30.6999 | 0.0000 | 0.0000 | 0.3633 |
| variable | cpu_threshold | 1 | 21.8699 | 21.8699 | 0.0000 | 0.0094 | 0.2582 |
| variable | static | 2 | 21.8699 | 21.8699 | 0.0000 | 0.0000 | 0.2250 |
| variable | eaes | 3 | 23.0221 | 23.0221 | 0.0000 | 0.0119 | 0.2753 |
| variable | forecasting_eaes | 4 | 26.8300 | 26.8300 | 0.0000 | 0.0000 | 0.3221 |
| variable | hpa_formula | 5 | 44.5468 | 44.5468 | 0.0000 | 0.0000 | 0.7258 |

## Rank stability across power and PUE

Each cell is the rank under that configuration (nominal PUE 1.2 is the reference). A change indicates that the power assumptions, not the controller, changed the ordering.

| Workload | Strategy | nominal/1.2 | low/1.0 | low/1.6 | high/1.0 | high/1.6 |
|---|---|---|---|---|---|---|
| bursty | static | 1 | 1 | 1 | 1 | 1 |
| bursty | cpu_threshold | 2 | 2 | 2 | 2 | 2 |
| bursty | hpa_formula | 5 | 5 | 5 | 5 | 5 |
| bursty | eaes | 3 | 3 | 3 | 3 | 3 |
| bursty | forecasting_eaes | 4 | 4 | 4 | 4 | 4 |
| heavy | static | 1 | 1 | 1 | 1 | 1 |
| heavy | cpu_threshold | 2 | 2 | 2 | 2 | 2 |
| heavy | hpa_formula | 5 | 5 | 5 | 5 | 5 |
| heavy | eaes | 3 | 3 | 3 | 3 | 3 |
| heavy | forecasting_eaes | 4 | 4 | 4 | 4 | 4 |
| light | static | 5 | 5 | 5 | 5 | 5 |
| light | cpu_threshold | 1 | 1 | 1 | 1 | 1 |
| light | hpa_formula | 4 | 4 | 4 | 4 | 4 |
| light | eaes | 2 | 2 | 2 | 2 | 2 |
| light | forecasting_eaes | 3 | 3 | 3 | 3 | 3 |
| medium | static | 2 | 2 | 2 | 2 | 2 |
| medium | cpu_threshold | 1 | 1 | 1 | 1 | 1 |
| medium | hpa_formula | 5 | 5 | 5 | 5 | 5 |
| medium | eaes | 3 | 3 | 3 | 3 | 3 |
| medium | forecasting_eaes | 4 | 4 | 4 | 4 | 4 |
| steady | static | 4 | 4 | 4 | 4 | 4 |
| steady | cpu_threshold | 1 | 1 | 1 | 1 | 1 |
| steady | hpa_formula | 5 | 5 | 5 | 5 | 5 |
| steady | eaes | 2 | 2 | 2 | 2 | 2 |
| steady | forecasting_eaes | 3 | 3 | 3 | 3 | 3 |
| variable | static | 2 | 2 | 2 | 2 | 2 |
| variable | cpu_threshold | 1 | 1 | 1 | 1 | 1 |
| variable | hpa_formula | 5 | 5 | 5 | 5 | 5 |
| variable | eaes | 3 | 3 | 3 | 3 | 3 |
| variable | forecasting_eaes | 4 | 4 | 4 | 4 | 4 |

## Stable and changing comparisons

No rank change was observed across the tested power and PUE configurations.

Direct pairwise direction checks (for example EAES versus HPA formula) are in the CSV. Because the same scaling trajectory is used in every configuration, any ordering change is an artefact of the idle/dynamic energy split and PUE, not of different control decisions.

## Interpretation

- The nominal configuration reproduces the confirmatory energy exactly (error above).
- Scaling decisions are not recomputed differently; this is a post-hoc energy recalculation.
- Ranking changes are possible when idle power dominates (low load) or dynamic power dominates (high load).
- All values are model estimates, not physical measurements.


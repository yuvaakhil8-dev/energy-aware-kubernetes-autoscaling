# Oracle upper bound (extension)

Run at `2026-10-26T05:59:46.730412+00:00`; git `b986f8821a669c90102742ae268f30e744f258e3`; tracked dirty `false`.

The oracle reads the true future arrival trace over the startup-delay horizon. It uses the same simulation, energy model, replica bounds (1-10), and SLA margin. It is an **information upper bound**, not a deployable autoscaler, and it is not part of the confirmatory five-strategy comparison.

All energy is modelled, not measured.

| Workload | Strategy | E/served J | E/offered J | Drop | SLA | Replica-h | P95 ms |
|---|---|---|---|---|---|---|---|
| steady | static | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2250 | 20.0000 |
| steady | cpu_threshold | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2250 | 20.0000 |
| steady | hpa_formula | 30.6999 | 30.6999 | 0.0000 | 0.0000 | 0.3633 | 20.0000 |
| steady | eaes | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2151 | 20.0000 |
| steady | forecasting_eaes | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2167 | 20.0000 |
| steady | oracle | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2246 | 20.0000 |
| light | static | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.2250 | 20.0000 |
| light | cpu_threshold | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.0974 | 20.0000 |
| light | hpa_formula | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.2250 | 20.0000 |
| light | eaes | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.1131 | 20.0000 |
| light | forecasting_eaes | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.1146 | 20.0000 |
| light | oracle | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.0850 | 20.0000 |
| medium | static | 17.7362 | 17.7362 | 0.0000 | 0.0000 | 0.2250 | 20.0000 |
| medium | cpu_threshold | 17.7362 | 17.7362 | 0.0000 | 0.0000 | 0.3000 | 20.0000 |
| medium | hpa_formula | 32.2085 | 32.2085 | 0.0000 | 0.0000 | 0.7500 | 20.0000 |
| medium | eaes | 20.9615 | 20.9615 | 0.0000 | 0.0000 | 0.3353 | 20.0000 |
| medium | forecasting_eaes | 21.0980 | 21.0980 | 0.0000 | 0.0000 | 0.3376 | 20.0000 |
| medium | oracle | 18.8322 | 18.8322 | 0.0000 | 0.0000 | 0.3162 | 20.0000 |
| heavy | static | 16.5000 | 9.9344 | 0.3979 | 1.0000 | 0.2250 | 30020.0000 |
| heavy | cpu_threshold | 17.3944 | 17.7221 | 0.0105 | 0.3202 | 0.5062 | 26654.3000 |
| heavy | hpa_formula | 21.3375 | 21.3375 | 0.0000 | 0.0000 | 0.7500 | 20.0000 |
| heavy | eaes | 18.5782 | 18.5782 | 0.0000 | 0.0000 | 0.6101 | 20.0000 |
| heavy | forecasting_eaes | 18.6521 | 18.6521 | 0.0000 | 0.0000 | 0.6126 | 20.0000 |
| heavy | oracle | 17.9639 | 17.9639 | 0.0000 | 0.0000 | 0.6028 | 20.0000 |
| variable | static | 21.8699 | 21.8699 | 0.0000 | 0.0000 | 0.2250 | 20.0000 |
| variable | cpu_threshold | 21.8699 | 21.8699 | 0.0000 | 0.0094 | 0.2582 | 111.5000 |
| variable | hpa_formula | 44.5468 | 44.5468 | 0.0000 | 0.0000 | 0.7258 | 20.0000 |
| variable | eaes | 23.0221 | 23.0221 | 0.0000 | 0.0119 | 0.2753 | 20.0000 |
| variable | forecasting_eaes | 26.8300 | 26.8300 | 0.0000 | 0.0000 | 0.3221 | 20.0000 |
| variable | oracle | 22.1003 | 22.1003 | 0.0000 | 0.0000 | 0.2294 | 20.0000 |
| bursty | static | 21.1145 | 13.2261 | 0.3803 | 0.8412 | 0.2250 | 30020.0000 |
| bursty | cpu_threshold | 23.0307 | 22.4041 | 0.0339 | 0.7483 | 0.4500 | 25057.8750 |
| bursty | hpa_formula | 30.4467 | 30.4467 | 0.0000 | 0.0000 | 0.7500 | 20.0000 |
| bursty | eaes | 29.4617 | 29.4617 | 0.0000 | 0.0170 | 0.7167 | 337.1375 |
| bursty | forecasting_eaes | 29.4617 | 29.4617 | 0.0000 | 0.0170 | 0.7167 | 337.1375 |
| bursty | oracle | 26.6298 | 26.6298 | 0.0000 | 0.0000 | 0.6181 | 20.0000 |

## Interpretation

The oracle is useful as a bound on what better workload information could buy. It is not evidence that any online controller can achieve the same result. Its extra scaling activity and energy cost are reported rather than hidden.


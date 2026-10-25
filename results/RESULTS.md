# Results (generated)

Run: `v3_paired_20261025T220942Z`  
Git commit: `431810fd8daa3cfd7dceaf11acb18dd6b14ea0ea`  
Execution mode: **simulation**  
Energy scenario: **nominal**  
Seeds: 10 per workload; workloads: steady, light, medium, heavy, variable, bursty  
Summaries: 300  

> All energy values are model estimates, not physical measurements. The primary window is after the 30 s warm-up; raw logs retain every tick.

## Primary metrics: mean [95% bootstrap CI]

### steady

| Strategy | Metric | n | Mean [95% CI] | Median |
|---|---|---|---|---|
| static | energy_per_served_request_j | 10 | 22.5772 [22.4145, 22.7677] | 22.5267 |
| static | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| static | replica_hours | 10 | 0.2250 [0.2250, 0.2250] | 0.2250 |
| static | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| cpu_threshold | energy_per_served_request_j | 10 | 22.5772 [22.4066, 22.7643] | 22.5267 |
| cpu_threshold | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| cpu_threshold | replica_hours | 10 | 0.2250 [0.2250, 0.2250] | 0.2250 |
| cpu_threshold | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| hpa_formula | energy_per_served_request_j | 10 | 30.6999 [27.2950, 33.8765] | 33.6667 |
| hpa_formula | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| hpa_formula | replica_hours | 10 | 0.3633 [0.3319, 0.3956] | 0.3667 |
| hpa_formula | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| eaes | energy_per_served_request_j | 10 | 22.5772 [22.4162, 22.7697] | 22.5267 |
| eaes | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| eaes | replica_hours | 10 | 0.2151 [0.2144, 0.2158] | 0.2153 |
| eaes | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| forecasting_eaes | energy_per_served_request_j | 10 | 22.5772 [22.4103, 22.7701] | 22.5267 |
| forecasting_eaes | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| forecasting_eaes | replica_hours | 10 | 0.2167 [0.2158, 0.2176] | 0.2167 |
| forecasting_eaes | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |

### light

| Strategy | Metric | n | Mean [95% CI] | Median |
|---|---|---|---|---|
| static | energy_per_served_request_j | 10 | 46.7218 [45.9584, 47.5180] | 46.5005 |
| static | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| static | replica_hours | 10 | 0.2250 [0.2250, 0.2250] | 0.2250 |
| static | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| cpu_threshold | energy_per_served_request_j | 10 | 46.7218 [45.9657, 47.5335] | 46.5005 |
| cpu_threshold | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| cpu_threshold | replica_hours | 10 | 0.0974 [0.0949, 0.1015] | 0.0951 |
| cpu_threshold | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| hpa_formula | energy_per_served_request_j | 10 | 46.7218 [45.9329, 47.5091] | 46.5005 |
| hpa_formula | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| hpa_formula | replica_hours | 10 | 0.2250 [0.2250, 0.2250] | 0.2250 |
| hpa_formula | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| eaes | energy_per_served_request_j | 10 | 46.7218 [45.9448, 47.5229] | 46.5005 |
| eaes | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| eaes | replica_hours | 10 | 0.1131 [0.1072, 0.1189] | 0.1125 |
| eaes | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| forecasting_eaes | energy_per_served_request_j | 10 | 46.7218 [45.9321, 47.5490] | 46.5005 |
| forecasting_eaes | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| forecasting_eaes | replica_hours | 10 | 0.1146 [0.1089, 0.1200] | 0.1187 |
| forecasting_eaes | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |

### medium

| Strategy | Metric | n | Mean [95% CI] | Median |
|---|---|---|---|---|
| static | energy_per_served_request_j | 10 | 17.7362 [17.6590, 17.8240] | 17.7123 |
| static | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| static | replica_hours | 10 | 0.2250 [0.2250, 0.2250] | 0.2250 |
| static | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| cpu_threshold | energy_per_served_request_j | 10 | 17.7362 [17.6605, 17.8263] | 17.7123 |
| cpu_threshold | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| cpu_threshold | replica_hours | 10 | 0.3000 [0.3000, 0.3000] | 0.3000 |
| cpu_threshold | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| hpa_formula | energy_per_served_request_j | 10 | 32.2085 [31.9818, 32.4693] | 32.1369 |
| hpa_formula | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| hpa_formula | replica_hours | 10 | 0.7500 [0.7500, 0.7500] | 0.7500 |
| hpa_formula | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| eaes | energy_per_served_request_j | 10 | 20.9615 [20.4276, 21.4523] | 20.7661 |
| eaes | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| eaes | replica_hours | 10 | 0.3353 [0.3283, 0.3421] | 0.3347 |
| eaes | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| forecasting_eaes | energy_per_served_request_j | 10 | 21.0980 [20.5917, 21.5680] | 21.0033 |
| forecasting_eaes | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| forecasting_eaes | replica_hours | 10 | 0.3376 [0.3318, 0.3431] | 0.3354 |
| forecasting_eaes | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |

### heavy

| Strategy | Metric | n | Mean [95% CI] | Median |
|---|---|---|---|---|
| static | energy_per_served_request_j | 10 | 16.5000 [16.5000, 16.5000] | 16.5000 |
| static | sla_violation_rate | 10 | 1.0000 [1.0000, 1.0000] | 1.0000 |
| static | replica_hours | 10 | 0.2250 [0.2250, 0.2250] | 0.2250 |
| static | drop_rate | 10 | 0.3979 [0.3927, 0.4025] | 0.3993 |
| cpu_threshold | energy_per_served_request_j | 10 | 17.3944 [17.3443, 17.4496] | 17.3840 |
| cpu_threshold | sla_violation_rate | 10 | 0.3202 [0.3131, 0.3277] | 0.3218 |
| cpu_threshold | replica_hours | 10 | 0.5062 [0.4961, 0.5171] | 0.5090 |
| cpu_threshold | drop_rate | 10 | 0.0105 [0.0093, 0.0118] | 0.0100 |
| hpa_formula | energy_per_served_request_j | 10 | 21.3375 [21.2552, 21.4298] | 21.3124 |
| hpa_formula | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| hpa_formula | replica_hours | 10 | 0.7500 [0.7500, 0.7500] | 0.7500 |
| hpa_formula | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| eaes | energy_per_served_request_j | 10 | 18.5782 [18.1740, 18.9903] | 18.5043 |
| eaes | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| eaes | replica_hours | 10 | 0.6101 [0.5979, 0.6221] | 0.6097 |
| eaes | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| forecasting_eaes | energy_per_served_request_j | 10 | 18.6521 [18.2256, 19.0668] | 18.7973 |
| forecasting_eaes | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| forecasting_eaes | replica_hours | 10 | 0.6126 [0.6000, 0.6246] | 0.6174 |
| forecasting_eaes | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |

### variable

| Strategy | Metric | n | Mean [95% CI] | Median |
|---|---|---|---|---|
| static | energy_per_served_request_j | 10 | 21.8699 [21.7818, 21.9544] | 21.8618 |
| static | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| static | replica_hours | 10 | 0.2250 [0.2250, 0.2250] | 0.2250 |
| static | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| cpu_threshold | energy_per_served_request_j | 10 | 21.8699 [21.7816, 21.9554] | 21.8618 |
| cpu_threshold | sla_violation_rate | 10 | 0.0094 [0.0000, 0.0282] | 0.0000 |
| cpu_threshold | replica_hours | 10 | 0.2582 [0.2501, 0.2628] | 0.2618 |
| cpu_threshold | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| hpa_formula | energy_per_served_request_j | 10 | 44.5468 [44.2815, 44.8295] | 44.5338 |
| hpa_formula | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| hpa_formula | replica_hours | 10 | 0.7258 [0.7035, 0.7471] | 0.7465 |
| hpa_formula | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| eaes | energy_per_served_request_j | 10 | 23.0221 [22.3482, 23.6956] | 23.0242 |
| eaes | sla_violation_rate | 10 | 0.0119 [0.0000, 0.0242] | 0.0000 |
| eaes | replica_hours | 10 | 0.2753 [0.2653, 0.2854] | 0.2750 |
| eaes | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| forecasting_eaes | energy_per_served_request_j | 10 | 26.8300 [26.1705, 27.4013] | 27.2552 |
| forecasting_eaes | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| forecasting_eaes | replica_hours | 10 | 0.3221 [0.3118, 0.3311] | 0.3312 |
| forecasting_eaes | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |

### bursty

| Strategy | Metric | n | Mean [95% CI] | Median |
|---|---|---|---|---|
| static | energy_per_served_request_j | 10 | 21.1145 [21.0576, 21.1753] | 21.0733 |
| static | sla_violation_rate | 10 | 0.8412 [0.8393, 0.8430] | 0.8422 |
| static | replica_hours | 10 | 0.2250 [0.2250, 0.2250] | 0.2250 |
| static | drop_rate | 10 | 0.3803 [0.3774, 0.3835] | 0.3795 |
| cpu_threshold | energy_per_served_request_j | 10 | 23.0307 [22.9396, 23.1261] | 23.0546 |
| cpu_threshold | sla_violation_rate | 10 | 0.7483 [0.7333, 0.7595] | 0.7566 |
| cpu_threshold | replica_hours | 10 | 0.4500 [0.4500, 0.4500] | 0.4500 |
| cpu_threshold | drop_rate | 10 | 0.0339 [0.0305, 0.0372] | 0.0348 |
| hpa_formula | energy_per_served_request_j | 10 | 30.4467 [30.3084, 30.5808] | 30.5069 |
| hpa_formula | sla_violation_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| hpa_formula | replica_hours | 10 | 0.7500 [0.7500, 0.7500] | 0.7500 |
| hpa_formula | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| eaes | energy_per_served_request_j | 10 | 29.4617 [29.3275, 29.5893] | 29.5189 |
| eaes | sla_violation_rate | 10 | 0.0170 [0.0000, 0.0450] | 0.0000 |
| eaes | replica_hours | 10 | 0.7167 [0.7167, 0.7167] | 0.7167 |
| eaes | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |
| forecasting_eaes | energy_per_served_request_j | 10 | 29.4617 [29.3256, 29.5913] | 29.5189 |
| forecasting_eaes | sla_violation_rate | 10 | 0.0170 [0.0000, 0.0455] | 0.0000 |
| forecasting_eaes | replica_hours | 10 | 0.7167 [0.7167, 0.7167] | 0.7167 |
| forecasting_eaes | drop_rate | 10 | 0.0000 [0.0000, 0.0000] | 0.0000 |

## Paired EAES comparisons (primary metrics)

| Workload | Baseline | Metric | Mean diff [95% CI] | p | Holm p | Cliff's d |
|---|---|---|---|---|---|---|
| steady | cpu_threshold | energy_per_served_request_j | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| steady | cpu_threshold | sla_violation_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| steady | cpu_threshold | replica_hours | -0.0099 [-0.0106, -0.0092] | 0.0046 | 0.0137 | -1.0000 |
| steady | cpu_threshold | drop_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| steady | hpa_formula | energy_per_served_request_j | -8.1227 [-11.4468, -4.6039] | 0.0180 | 0.0718 | -0.7700 |
| steady | hpa_formula | sla_violation_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| steady | hpa_formula | replica_hours | -0.1482 [-0.1803, -0.1171] | 0.0050 | 0.0356 | -1.0000 |
| steady | hpa_formula | drop_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| light | cpu_threshold | energy_per_served_request_j | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| light | cpu_threshold | sla_violation_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| light | cpu_threshold | replica_hours | 0.0157 [0.0103, 0.0215] | 0.0050 | 0.0299 | 0.9000 |
| light | cpu_threshold | drop_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| light | hpa_formula | energy_per_served_request_j | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| light | hpa_formula | sla_violation_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| light | hpa_formula | replica_hours | -0.1119 [-0.1178, -0.1058] | 0.0048 | 0.0287 | -1.0000 |
| light | hpa_formula | drop_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| medium | cpu_threshold | energy_per_served_request_j | 3.2253 [2.6651, 3.7056] | 0.0051 | 0.0470 | 1.0000 |
| medium | cpu_threshold | sla_violation_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| medium | cpu_threshold | replica_hours | 0.0353 [0.0281, 0.0418] | 0.0050 | 0.0470 | 1.0000 |
| medium | cpu_threshold | drop_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| medium | hpa_formula | energy_per_served_request_j | -11.2470 [-11.8444, -10.6788] | 0.0051 | 0.0446 | -1.0000 |
| medium | hpa_formula | sla_violation_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| medium | hpa_formula | replica_hours | -0.4147 [-0.4221, -0.4082] | 0.0050 | 0.0446 | -1.0000 |
| medium | hpa_formula | drop_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| heavy | cpu_threshold | energy_per_served_request_j | 1.1838 [0.7617, 1.5919] | 0.0051 | 0.0594 | 1.0000 |
| heavy | cpu_threshold | sla_violation_rate | -0.3202 [-0.3278, -0.3130] | 0.0051 | 0.0594 | -1.0000 |
| heavy | cpu_threshold | replica_hours | 0.1039 [0.0939, 0.1140] | 0.0049 | 0.0594 | 1.0000 |
| heavy | cpu_threshold | drop_rate | -0.0105 [-0.0118, -0.0093] | 0.0051 | 0.0594 | -1.0000 |
| heavy | hpa_formula | energy_per_served_request_j | -2.7594 [-3.1780, -2.3152] | 0.0051 | 0.0407 | -1.0000 |
| heavy | hpa_formula | sla_violation_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| heavy | hpa_formula | replica_hours | -0.1399 [-0.1521, -0.1278] | 0.0049 | 0.0407 | -1.0000 |
| heavy | hpa_formula | drop_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| variable | cpu_threshold | energy_per_served_request_j | 1.1522 [0.4589, 1.8474] | 0.0431 | 0.1293 | 0.6100 |
| variable | cpu_threshold | sla_violation_rate | 0.0025 [-0.0220, 0.0234] | null | null | 0.1700 |
| variable | cpu_threshold | replica_hours | 0.0171 [0.0035, 0.0318] | 0.1383 | 0.1383 | 0.2000 |
| variable | cpu_threshold | drop_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| variable | hpa_formula | energy_per_served_request_j | -21.5247 [-22.3247, -20.7545] | 0.0051 | 0.0352 | -1.0000 |
| variable | hpa_formula | sla_violation_rate | 0.0119 [0.0000, 0.0260] | null | null | 0.3000 |
| variable | hpa_formula | replica_hours | -0.4506 [-0.4660, -0.4349] | 0.0050 | 0.0352 | -1.0000 |
| variable | hpa_formula | drop_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |
| bursty | cpu_threshold | energy_per_served_request_j | 6.4310 [6.3762, 6.4937] | 0.0051 | 0.0506 | 1.0000 |
| bursty | cpu_threshold | sla_violation_rate | -0.7313 [-0.7529, -0.7058] | 0.0051 | 0.0506 | -1.0000 |
| bursty | cpu_threshold | replica_hours | 0.2667 [0.2667, 0.2667] | 0.0016 | 0.0250 | 1.0000 |
| bursty | cpu_threshold | drop_rate | -0.0339 [-0.0371, -0.0307] | 0.0051 | 0.0506 | -1.0000 |
| bursty | hpa_formula | energy_per_served_request_j | -0.9850 [-0.9916, -0.9781] | 0.0050 | 0.0302 | -1.0000 |
| bursty | hpa_formula | sla_violation_rate | 0.0170 [0.0000, 0.0400] | null | null | 0.2000 |
| bursty | hpa_formula | replica_hours | -0.0333 [-0.0333, -0.0333] | 0.0016 | 0.0188 | -1.0000 |
| bursty | hpa_formula | drop_rate | 0.0000 [0.0000, 0.0000] | null | null | 0.0000 |

## Friedman tests (primary metrics)

| Workload | Metric | n | Q | p |
|---|---|---|---|---|
| steady | energy_per_served_request_j | 10 | 28.0000 | 0.0000 |
| steady | sla_violation_rate | 10 | 0.0000 | 1.0000 |
| steady | replica_hours | 10 | 39.4839 | 0.0000 |
| steady | drop_rate | 10 | 0.0000 | 1.0000 |
| light | energy_per_served_request_j | 10 | 0.0000 | 1.0000 |
| light | sla_violation_rate | 10 | 0.0000 | 1.0000 |
| light | replica_hours | 10 | 39.8011 | 0.0000 |
| light | drop_rate | 10 | 0.0000 | 1.0000 |
| medium | energy_per_served_request_j | 10 | 39.4783 | 0.0000 |
| medium | sla_violation_rate | 10 | 0.0000 | 1.0000 |
| medium | replica_hours | 10 | 39.5102 | 0.0000 |
| medium | drop_rate | 10 | 0.0000 | 1.0000 |
| heavy | energy_per_served_request_j | 10 | 39.8115 | 0.0000 |
| heavy | sla_violation_rate | 10 | 40.0000 | 0.0000 |
| heavy | replica_hours | 10 | 39.5052 | 0.0000 |
| heavy | drop_rate | 10 | 40.0000 | 0.0000 |
| variable | energy_per_served_request_j | 10 | 38.2857 | 0.0000 |
| variable | sla_violation_rate | 10 | 8.5000 | 0.0749 |
| variable | replica_hours | 10 | 37.1256 | 0.0000 |
| variable | drop_rate | 10 | 0.0000 | 1.0000 |
| bursty | energy_per_served_request_j | 10 | 40.0000 | 0.0000 |
| bursty | sla_violation_rate | 10 | 38.8434 | 0.0000 |
| bursty | replica_hours | 10 | 40.0000 | 0.0000 |
| bursty | drop_rate | 10 | 40.0000 | 0.0000 |

## Forecast evaluation (held-out final 50% of each trace)

| Workload | Method | n | MAE (req/s) |
|---|---|---|---|
| bursty | ewma | 10 | 39.6602 |
| bursty | holt | 10 | 45.3271 |
| heavy | ewma | 10 | 2.7977 |
| heavy | holt | 10 | 3.4814 |
| light | ewma | 10 | 0.8744 |
| light | holt | 10 | 1.0771 |
| medium | ewma | 10 | 1.9841 |
| medium | holt | 10 | 2.4705 |
| steady | ewma | 10 | 1.5243 |
| steady | holt | 10 | 1.9010 |
| variable | ewma | 10 | 6.6865 |
| variable | holt | 10 | 6.5627 |

## Energy sensitivity (nominal recomputation check)

Maximum relative difference between the raw-log recomputation and the engine's nominal energy: `8.061e-16`.

See `results/tables/sensitivity.csv` for low/nominal/high power and PUE 1.0-1.6.

## Interpretation guardrails

- These are paired simulation results, not cluster measurements.
- Statistical significance does not establish real-world performance.
- The static strategy can show low energy per served request while dropping a large share of traffic; read it with the drop/SLA columns.
- The HPA-formula baseline is a simulated formula, not the Kubernetes HPA controller.

# EAES Diagnostic (generated from raw tick logs)

Run: `v3_paired_20261025T220942Z`  
Run git commit: `431810fd8daa3cfd7dceaf11acb18dd6b14ea0ea`  
Analysis commit: `b11325e96b13ed5d92bfbcf8125e92696f3dc0a3`  
Execution mode: **simulation**  

> All energy is modelled, not measured. The diagnostic looks for evidence that could favour or harm EAES and does not adjust any result.

## 1. EAES vs HPA formula decomposition

| Workload | EAES E/served | HPA E/served | Ratio | EAES E/offered | HPA E/offered | Ratio | EAES repl-h | HPA repl-h | Ratio | EAES drop | HPA drop | EAES SLA | HPA SLA |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| steady | 22.5772 | 30.6999 | 0.7354 | 22.5772 | 30.6999 | 0.7354 | 0.2108 | 0.3633 | 0.5803 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| light | 46.7218 | 46.7218 | 1.0000 | 46.7218 | 46.7218 | 1.0000 | 0.1096 | 0.2250 | 0.4870 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| medium | 20.9615 | 32.2085 | 0.6508 | 20.9615 | 32.2085 | 0.6508 | 0.3318 | 0.7500 | 0.4424 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| heavy | 18.5782 | 21.3375 | 0.8707 | 18.5782 | 21.3375 | 0.8707 | 0.6053 | 0.7500 | 0.8070 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| variable | 23.0221 | 44.5468 | 0.5168 | 23.0221 | 44.5468 | 0.5168 | 0.2699 | 0.7258 | 0.3718 | 0.0000 | 0.0000 | 0.0119 | 0.0000 |
| bursty | 29.4617 | 30.4467 | 0.9676 | 29.4617 | 30.4467 | 0.9676 | 0.7111 | 0.7500 | 0.9481 | 0.0000 | 0.0000 | 0.0170 | 0.0000 |

## 2. Denominator and throughput check

| Workload | Seeds EAES serves more | Seeds | Seeds E/served worse | Seeds E/offered worse | Seeds total energy higher |
|---|---|---|---|---|---|
| steady | 0 | 10 | 0 | 0 | 0 |
| light | 0 | 10 | 0 | 0 | 0 |
| medium | 0 | 10 | 0 | 0 | 0 |
| heavy | 0 | 10 | 0 | 0 | 0 |
| variable | 0 | 10 | 0 | 0 | 0 |
| bursty | 0 | 10 | 0 | 0 | 0 |

## 3. Forecasting ablation (forecasting EAES vs reactive EAES)

| Workload | Seeds | EAES E/served | Forecast E/served | Ratio | EAES SLA | Forecast SLA | EAES repl-h | Forecast repl-h |
|---|---|---|---|---|---|---|---|---|
| steady | 10 | 22.5772 | 22.5772 | 1.0000 | 0.0000 | 0.0000 | 0.2108 | 0.2128 |
| light | 10 | 46.7218 | 46.7218 | 1.0000 | 0.0000 | 0.0000 | 0.1096 | 0.1111 |
| medium | 10 | 20.9615 | 21.0980 | 1.0065 | 0.0000 | 0.0000 | 0.3318 | 0.3344 |
| heavy | 10 | 18.5782 | 18.6521 | 1.0040 | 0.0000 | 0.0000 | 0.6053 | 0.6078 |
| variable | 10 | 23.0221 | 26.8300 | 1.1654 | 0.0119 | 0.0000 | 0.2699 | 0.3168 |
| bursty | 10 | 29.4617 | 29.4617 | 1.0000 | 0.0170 | 0.0170 | 0.7111 | 0.7111 |

## 4. Strategy metrics (mean over seeds, raw recomputation)

| Workload | Strategy | E/served | E/offered | Drop | SLA | Served/offered | Replica-hours | Max ready | Max pending | Cooldown/stab holds |
|---|---|---|---|---|---|---|---|---|---|---|
| steady | static | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 1.0000 | 0.2250 | 3 | 0 | 0 |
| steady | cpu_threshold | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 1.0000 | 0.2250 | 3 | 0 | 0 |
| steady | hpa_formula | 30.6999 | 30.6999 | 0.0000 | 0.0000 | 1.0000 | 0.3633 | 4.9000 | 1 | 54.3000 |
| steady | eaes | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 1.0000 | 0.2108 | 3 | 1 | 40.5000 |
| steady | forecasting_eaes | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 1.0000 | 0.2128 | 3 | 1 | 37.3000 |
| light | static | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 1.0000 | 0.2250 | 3 | 0 | 0 |
| light | cpu_threshold | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 1.0000 | 0.0944 | 3 | 0.1000 | 5 |
| light | hpa_formula | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 1.0000 | 0.2250 | 3 | 0 | 60 |
| light | eaes | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 1.0000 | 0.1096 | 3 | 0.7000 | 18.8000 |
| light | forecasting_eaes | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 1.0000 | 0.1111 | 3 | 0.8000 | 20 |
| medium | static | 17.7362 | 17.7362 | 0.0000 | 0.0000 | 1.0000 | 0.2250 | 3 | 0 | 0 |
| medium | cpu_threshold | 17.7362 | 17.7362 | 0.0000 | 0.0000 | 1.0000 | 0.3000 | 4 | 1 | 1.3000 |
| medium | hpa_formula | 32.2085 | 32.2085 | 0.0000 | 0.0000 | 1.0000 | 0.7500 | 10 | 3.7000 | 56.4000 |
| medium | eaes | 20.9615 | 20.9615 | 0.0000 | 0.0000 | 1.0000 | 0.3318 | 5 | 1.1000 | 39.5000 |
| medium | forecasting_eaes | 21.0980 | 21.0980 | 0.0000 | 0.0000 | 1.0000 | 0.3344 | 5 | 1.1000 | 38.9000 |
| heavy | static | 16.5000 | 9.9344 | 0.3979 | 1.0000 | 0.6021 | 0.2250 | 3 | 0 | 0 |
| heavy | cpu_threshold | 17.3944 | 17.7221 | 0.0105 | 0.3202 | 1.0188 | 0.5062 | 7.6000 | 1 | 17.9000 |
| heavy | hpa_formula | 21.3375 | 21.3375 | 0.0000 | 0.0000 | 1.0000 | 0.7500 | 10 | 4 | 4.3000 |
| heavy | eaes | 18.5782 | 18.5782 | 0.0000 | 0.0000 | 1.0000 | 0.6053 | 8.7000 | 4.8000 | 44.6000 |
| heavy | forecasting_eaes | 18.6521 | 18.6521 | 0.0000 | 0.0000 | 1.0000 | 0.6078 | 8.7000 | 4.8000 | 44.2000 |
| variable | static | 21.8699 | 21.8699 | 0.0000 | 0.0000 | 1.0000 | 0.2250 | 3 | 0 | 0 |
| variable | cpu_threshold | 21.8699 | 21.8699 | 0.0000 | 0.0094 | 1.0000 | 0.2554 | 4 | 1 | 14.5000 |
| variable | hpa_formula | 44.5468 | 44.5468 | 0.0000 | 0.0000 | 1.0000 | 0.7258 | 9.7000 | 3.3000 | 55.1000 |
| variable | eaes | 23.0221 | 23.0221 | 0.0000 | 0.0119 | 1.0000 | 0.2699 | 4.5000 | 1 | 44.1000 |
| variable | forecasting_eaes | 26.8300 | 26.8300 | 0.0000 | 0.0000 | 1.0000 | 0.3168 | 5 | 1 | 45 |
| bursty | static | 21.1145 | 13.2261 | 0.3803 | 0.8412 | 0.6264 | 0.2250 | 3 | 0 | 0 |
| bursty | cpu_threshold | 23.0307 | 22.4041 | 0.0339 | 0.7483 | 0.9728 | 0.4500 | 8 | 1 | 50.6000 |
| bursty | hpa_formula | 30.4467 | 30.4467 | 0.0000 | 0.0000 | 1.0000 | 0.7500 | 10 | 4 | 39 |
| bursty | eaes | 29.4617 | 29.4617 | 0.0000 | 0.0170 | 1.0000 | 0.7111 | 10 | 7 | 34.1000 |
| bursty | forecasting_eaes | 29.4617 | 29.4617 | 0.0000 | 0.0170 | 1.0000 | 0.7111 | 10 | 7 | 34 |

## 5. Startup, overprovisioning, and control-rule activity

| Workload | Strategy | Max pending | Max ready | Max nodes | Mean overprovision | Cooldown/stab holds | Conservation err | Top rules |
|---|---|---|---|---|---|---|---|---|
| steady | eaes | 1 | 3 | 1 | 0.1111 | 40.5000 | 0.0000 | stabilization=245; cooldown=160; scale_down_would_breach_sla=74; warmup_no_scaledown=60 |
| steady | hpa_formula | 1 | 4.9000 | 1.7000 | null | 54.3000 | 0.0000 | hpa_down_stabilization=543; hpa_formula_within_tolerance=38; hpa_formula_above_tolerance=19 |
| steady | cpu_threshold | 0 | 3 | 1 | null | 0 | 0.0000 | within_band_or_bounds=590; warmup_no_scaledown=10 |
| light | eaes | 0.7000 | 3 | 1 | 0.4296 | 18.8000 | 0.0000 | min_replicas=318; stabilization=97; cooldown=91; warmup_no_scaledown=60 |
| light | hpa_formula | 0 | 3 | 1 | null | 60 | 0.0000 | hpa_down_stabilization=600 |
| light | cpu_threshold | 0.1000 | 3 | 1 | null | 5 | 0.0000 | within_band_or_bounds=469; warmup_no_scaledown=59; down_cooldown=50; cpu_below_scale_down=21 |
| medium | eaes | 1.1000 | 5 | 2 | 0.4019 | 39.5000 | 0.0000 | cooldown=213; stabilization=182; scale_down_would_breach_sla=95; warmup_no_scaledown=46 |
| medium | hpa_formula | 3.7000 | 10 | 3 | null | 56.4000 | 0.0000 | hpa_down_stabilization=564; hpa_formula_above_tolerance=31; hpa_formula_within_tolerance=5 |
| medium | cpu_threshold | 1 | 4 | 1 | null | 1.3000 | 0.0000 | within_band_or_bounds=567; up_cooldown=13; warmup_no_scaledown=10; cpu_above_scale_up=10 |
| heavy | eaes | 4.8000 | 8.7000 | 2.7000 | 0.4593 | 44.6000 | 0.0000 | cooldown=227; stabilization=219; sla_margin_below_threshold=47; warmup_no_scaledown=46 |
| heavy | hpa_formula | 4 | 10 | 3 | null | 4.3000 | 0.0000 | hpa_formula_within_tolerance=479; hpa_formula_above_tolerance=78; hpa_down_stabilization=43 |
| heavy | cpu_threshold | 1 | 7.6000 | 2 | null | 17.9000 | 0.0000 | within_band_or_bounds=365; up_cooldown=179; cpu_above_scale_up=46; warmup_no_scaledown=10 |
| variable | eaes | 1 | 4.5000 | 1.5000 | 0.8481 | 44.1000 | 0.0000 | cooldown=283; stabilization=158; warmup_no_scaledown=50; sla_margin_below_threshold=48 |
| variable | hpa_formula | 3.3000 | 9.7000 | 3 | null | 55.1000 | 0.0000 | hpa_down_stabilization=551; hpa_formula_above_tolerance=36; hpa_formula_within_tolerance=13 |
| variable | cpu_threshold | 1 | 4 | 1 | null | 14.5000 | 0.0000 | within_band_or_bounds=395; down_cooldown=105; up_cooldown=40; cpu_above_scale_up=30 |
| bursty | eaes | 7 | 10 | 3 | 5.2352 | 34.1000 | 0.0000 | cooldown=171; stabilization=170; max_replicas_reached=169; safe_scale_down=40 |
| bursty | hpa_formula | 4 | 10 | 3 | null | 39 | 0.0000 | hpa_down_stabilization=390; hpa_formula_above_tolerance=210 |
| bursty | cpu_threshold | 1 | 8 | 2 | null | 50.6000 | 0.0000 | down_cooldown=287; up_cooldown=219; cpu_above_scale_up=50; within_band_or_bounds=34 |

## 6. Findings

- steady: EAES energy per served request is lower than HPA formula (22.577 vs 30.700 J, ratio 0.735); energy per offered request ratio is 0.735; not explained by the denominator. EAES serves 0/10 seeds more requests, has 0.0000 vs 0.0000 drop rate and 0.0000 vs 0.0000 SLA violation rate, and uses 0.580x the replica-hours.
- light: EAES energy per served request is equal to HPA formula (46.722 vs 46.722 J, ratio 1.000); energy per offered request ratio is 1.000; not explained by the denominator. EAES serves 0/10 seeds more requests, has 0.0000 vs 0.0000 drop rate and 0.0000 vs 0.0000 SLA violation rate, and uses 0.487x the replica-hours.
- medium: EAES energy per served request is lower than HPA formula (20.961 vs 32.208 J, ratio 0.651); energy per offered request ratio is 0.651; not explained by the denominator. EAES serves 0/10 seeds more requests, has 0.0000 vs 0.0000 drop rate and 0.0000 vs 0.0000 SLA violation rate, and uses 0.442x the replica-hours.
- heavy: EAES energy per served request is lower than HPA formula (18.578 vs 21.338 J, ratio 0.871); energy per offered request ratio is 0.871; not explained by the denominator. EAES serves 0/10 seeds more requests, has 0.0000 vs 0.0000 drop rate and 0.0000 vs 0.0000 SLA violation rate, and uses 0.807x the replica-hours.
- variable: EAES energy per served request is lower than HPA formula (23.022 vs 44.547 J, ratio 0.517); energy per offered request ratio is 0.517; not explained by the denominator. EAES serves 0/10 seeds more requests, has 0.0000 vs 0.0000 drop rate and 0.0119 vs 0.0000 SLA violation rate, and uses 0.372x the replica-hours.
- bursty: EAES energy per served request is lower than HPA formula (29.462 vs 30.447 J, ratio 0.968); energy per offered request ratio is 0.968; not explained by the denominator. EAES serves 0/10 seeds more requests, has 0.0000 vs 0.0000 drop rate and 0.0170 vs 0.0000 SLA violation rate, and uses 0.948x the replica-hours.

## 7. Interpretation

- A lower energy per served request can be an artefact of serving fewer requests; the offered-request column is the denominator check.
- Replica-hours expose provisioning cost that per-request energy can hide.
- Pending replicas and cooldown/stabilization holds show whether startup delay or conservative control caused the trajectory.
- Node energy and pod-attributed energy are conserved within the reported error; pod attribution does not create energy.
- These are simulation findings, not cluster measurements.


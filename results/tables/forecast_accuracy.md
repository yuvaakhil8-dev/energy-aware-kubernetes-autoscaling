# Forecast accuracy (held-out)

Evaluation window: final 50% of each trace, two-step (10 s) horizon, online update. MAPE excludes actual rates below 0.5 req/s and every zero actual; the excluded count is shown. This is a held-out segment, not a rolling-origin retraining study.

| Workload | Method | Seeds | Held-out points | MAE mean [95% CI] | MAE median [95% CI] | MAPE mean % [95% CI] | MAPE points | Excluded | Zero actuals |
|---|---|---|---|---|---|---|---|---|---|
| steady | ewma | 10 | 280 | 1.5243 [1.3552, 1.7191] | 1.4290 [1.2986, 1.7523] | 10.5718 [9.2247, 12.2224] | 280 | 0 | 0 |
| steady | holt | 10 | 280 | 1.9010 [1.6596, 2.1771] | 1.7506 [1.5658, 2.1872] | 13.0869 [11.2590, 15.4633] | 280 | 0 | 0 |
| light | ewma | 10 | 280 | 0.8744 [0.8218, 0.9353] | 0.8500 [0.8006, 0.9325] | 18.7446 [17.4057, 20.3780] | 280 | 0 | 0 |
| light | holt | 10 | 280 | 1.0771 [0.9938, 1.1613] | 1.0938 [0.9764, 1.1719] | 22.7288 [21.0141, 24.4018] | 280 | 0 | 0 |
| medium | ewma | 10 | 280 | 1.9841 [1.7710, 2.2331] | 1.8478 [1.6943, 2.2416] | 8.1387 [7.1721, 9.3114] | 280 | 0 | 0 |
| medium | holt | 10 | 280 | 2.4705 [2.1560, 2.8259] | 2.2807 [2.0643, 2.8000] | 10.0853 [8.7672, 11.7081] | 280 | 0 | 0 |
| heavy | ewma | 10 | 280 | 2.7977 [2.4933, 3.1426] | 2.6336 [2.3880, 3.1837] | 5.6730 [5.0180, 6.4550] | 280 | 0 | 0 |
| heavy | holt | 10 | 280 | 3.4814 [3.0545, 3.9610] | 3.2311 [2.8840, 3.9849] | 7.0405 [6.0988, 8.1623] | 280 | 0 | 0 |
| variable | ewma | 10 | 280 | 6.6865 [6.5126, 6.8478] | 6.6493 [6.5391, 6.9419] | 61.7962 [57.8836, 66.1421] | 280 | 0 | 0 |
| variable | holt | 10 | 280 | 6.5627 [6.3150, 6.8235] | 6.5134 [6.2605, 6.8586] | 51.2874 [48.3920, 54.7574] | 280 | 0 | 0 |
| bursty | ewma | 10 | 280 | 39.6602 [39.2438, 40.0510] | 39.6465 [39.3067, 40.2771] | 484.9491 [472.6358, 496.7996] | 280 | 0 | 0 |
| bursty | holt | 10 | 280 | 45.3271 [44.8052, 45.8074] | 45.1862 [44.9543, 46.1946] | 601.1474 [589.1906, 613.6612] | 280 | 0 | 0 |

## What the forecast errors mean for control

Lower MAE/MAPE is a necessary but not sufficient condition for better autoscaling. The table below joins the confirmatory forecasting-EAES comparison to show whether the forecast changed energy, SLA violations, and provisioning. These are run-level means over the ten confirmatory seeds; they are not causal estimates.

| Workload | EAES E/served | Forecast E/served | EAES SLA | Forecast SLA | EAES repl-h | Forecast repl-h |
|---|---|---|---|---|---|---|
| bursty | 29.4617 | 29.4617 | 0.0170 | 0.0170 | 0.7167 | 0.7167 |
| heavy | 18.5782 | 18.6521 | 0.0000 | 0.0000 | 0.6101 | 0.6126 |
| light | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.1131 | 0.1146 |
| medium | 20.9615 | 21.0980 | 0.0000 | 0.0000 | 0.3353 | 0.3376 |
| steady | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.2151 | 0.2167 |
| variable | 23.0221 | 26.8300 | 0.0119 | 0.0000 | 0.2753 | 0.3221 |

Interpretation guardrails:

- Holt and EWMA are deliberately small forecasters, not tuned production models.
- A forecast error on a smooth trace can be small while the resulting scaling decision is unchanged.
- On bursty traces, a two-step horizon can be too short to pre-provision a 10 s startup delay; the startup-delay sweep in `results/extension/startup_sweep/` tests this directly.
- Forecasting did not remove bursty SLA violations in the confirmatory run. Accuracy alone does not make the forecasting controller universally superior.


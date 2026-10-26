# Startup-delay sweep (extension)

Startup delays: 5, 10, 20 s. Every run uses the same traces, seeds, replica bounds, and energy model.

| Delay s | Workload | EAES E/served | Forecast E/served | EAES drop | Forecast drop | EAES SLA | Forecast SLA | Forecast - EAES SLA |
|---|---|---|---|---|---|---|---|---|
| 5 | steady | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 5 | light | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 5 | medium | 21.2425 | 21.2425 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 5 | heavy | 18.6447 | 18.6447 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 5 | variable | 23.1268 | 25.8933 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 5 | bursty | 29.7080 | 29.7080 | 0.0000 | 0.0000 | 0.0060 | 0.0060 | 0.0000 |
| 10 | steady | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 10 | light | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 10 | medium | 20.9615 | 21.0980 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 10 | heavy | 18.5782 | 18.6521 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 10 | variable | 23.0221 | 26.8300 | 0.0000 | 0.0000 | 0.0119 | 0.0000 | -0.0119 |
| 10 | bursty | 29.4617 | 29.4617 | 0.0000 | 0.0000 | 0.0170 | 0.0170 | 0.0000 |
| 20 | steady | 22.5772 | 22.5772 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 20 | light | 46.7218 | 46.7218 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 20 | medium | 20.4125 | 20.9517 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 20 | heavy | 18.3566 | 18.6533 | 0.0000 | 0.0000 | 0.0352 | 0.0352 | 0.0000 |
| 20 | variable | 22.8126 | 28.1980 | 0.0000 | 0.0000 | 0.1136 | 0.0035 | -0.1101 |
| 20 | bursty | 28.9692 | 28.9692 | 0.0000 | 0.0000 | 0.0181 | 0.0181 | 0.0000 |

## Where forecasting changes the outcome

- 5 s / variable: forecasting same SLA; energy per served changes from 23.1268 to 25.8933 J.
- 10 s / medium: forecasting same SLA; energy per served changes from 20.9615 to 21.0980 J.
- 10 s / heavy: forecasting same SLA; energy per served changes from 18.5782 to 18.6521 J.
- 10 s / variable: forecasting improves SLA; energy per served changes from 23.0221 to 26.8300 J.
- 20 s / medium: forecasting same SLA; energy per served changes from 20.4125 to 20.9517 J.
- 20 s / heavy: forecasting same SLA; energy per served changes from 18.3566 to 18.6533 J.
- 20 s / variable: forecasting improves SLA; energy per served changes from 22.8126 to 28.1980 J.


# Energy-versus-drop Pareto plots (extension)

One SVG per workload. The x axis is **estimated** energy per offered request; the y axis is the request drop rate. A strategy that serves less traffic cannot look efficient merely because its denominator is smaller. Ringed points and the dashed line are the Pareto frontier.

| Workload | Pareto-frontier strategies |
|---|---|
| bursty | static, cpu_threshold, eaes, forecasting_eaes |
| heavy | static, cpu_threshold, eaes |
| light | static, cpu_threshold, hpa_formula, eaes, forecasting_eaes |
| medium | static, cpu_threshold |
| steady | static, cpu_threshold, eaes, forecasting_eaes |
| variable | static, cpu_threshold |

Generated from the confirmatory 10-seed summary (300 runs). Energy is modelled, not measured.


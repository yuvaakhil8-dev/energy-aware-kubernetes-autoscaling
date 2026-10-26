# Dashboard Guide

The dashboard is a read-only research UI over committed/generated artifacts. It
does not run experiments on request, does not show live cluster state, and does
not invent data. Chart.js 4.4.1 is vendored locally, so charts work offline.

Start:

```powershell
$env:ENERGY_AWARE_NO_BG='1'
python app.py
```

Open `http://127.0.0.1:5000/`.

## 1. Page 1: `/` Results

### Run banner

Shows the run ID, execution mode, number of runs, seeds per workload, and energy
scenario. Every page states that energy is modelled, not measured.

### Global KPIs

- paired runs (300);
- EAES/HPA energy-per-served ratio (workload mean);
- EAES/HPA replica-hours ratio;
- EAES/HPA SLA violation rates;
- static drop rate, with the warning that low energy can mean unmet demand.

### Explore a confirmatory run

Filters:

- **Workload:** steady, light, medium, heavy, variable, bursty.
- **Strategy:** static, CPU threshold, HPA formula, EAES, forecasting EAES.
- **Seed:** `all` (tick-wise mean of ten runs) or one real seed.

The selection KPIs are:

- selected workload and selected strategy;
- final-tick offered rate, CPU, and replicas;
- average replica count;
- estimated total energy;
- estimated energy per served and per offered request;
- drop rate;
- SLA violation rate;
- p95 latency;
- replica-hours;
- scaling events.

The final-tick values are the last 5 s interval, not a live reading. The seed
selector is explicit: choosing one seed loads one raw run; choosing `all`
averages the ten raw runs tick by tick. The latter does not increase the sample
size for inference.

### Charts

1. **Workload over time:** offered requests/s and, for forecasting EAES, the
   recorded forecast and the actual rate two ticks ahead.
2. **CPU over time:** controller-observed CPU utilisation.
3. **Replicas over time:** ready, desired, and pending replicas.
4. **Strategy comparison by workload:** mean across ten seeds, selectable metric
   (energy per served/offered, replica-hours, SLA, drop, p95, scaling events,
   oscillations).
5. **Estimated energy versus request drop:** scatter of all strategies and
   workloads using energy per offered request and drop rate. This prevents a
   low-volume or traffic-dropping strategy from looking efficient.

All chart data is loaded from `/api/v1/research/results` and
`/api/v1/research/timeseries`. There is no hard-coded series.

### Tables

- descriptive statistics: mean [95% bootstrap CI], median, n for the primary
  metrics;
- paired tests: EAES and forecasting EAES versus HPA formula, median paired
  difference [95% CI], Holm-adjusted p, Cliff's delta;
- separate cluster validation: static vs native HPA, real replica/request
  observations, modelled energy per served request.

The table downloads are whitelisted JSON renderings of the generated CSVs:
`/api/v1/research/tables/headline`,
`/api/v1/research/tables/paired_headline`,
`/api/v1/research/tables/descriptive`, and
`/api/v1/research/tables/paired`.

### Extension links

The results page links to forecast accuracy, all paired comparisons, headline
tables, and cluster records. The full extension reports are under
`results/extension/` and `docs/EXTENSIONS.md`.

## 2. Page 2: `/eaes-diagnostics`

### Controller trace

Filters: workload, strategy, seed. The trace is a real recorded run, not a
synthetic UI stream.

The page shows:

- current workload and final tick time;
- observed request rate;
- CPU utilisation;
- ready/desired replicas;
- scaling decision (`up`, `down`, `hold`);
- rule fired;
- cooldown/stabilization status;
- SLA margin;
- forecast, when applicable;
- estimated energy per tick;
- decision reason and decision-detail JSON;
- actual-versus-predicted chart (observed, forecast at decision time, actual at
  t+2);
- recent scaling history (time, action, from -> to, rule, reason, observed rate);
- rule and action counts for the run.

The forecast is the value recorded at decision time. The "actual at t+2" line is
the observed rate two ticks later, matching the two-step horizon. It is not a
retrained prediction.

### EAES decomposition and ablation

- energy per served and offered request;
- replica-hours;
- drops and SLA;
- forecasting delta versus EAES;
- rule evidence and denominator checks;
- raw-tick conservation error.

### Aggregate diagnostics

The page includes the generated diagnostic tables and findings from
`results/diagnostic.json` and `results/EAES_DIAGNOSTIC.md`.

## 3. Page 3: `/methodology`

Sections:

- scope and execution modes;
- system architecture with component paths;
- end-to-end execution flow;
- workload generation and metrics collection;
- dashboard APIs and read path;
- Kubernetes integration;
- strategy distinctions (static, CPU threshold, HPA formula, EAES, forecasting
  EAES, oracle extension);
- statistics and pairing;
- energy model and sensitivity;
- configuration values and hashes;
- original dataset integrity;
- limitations;
- reproduction commands.

The page is generated from the research methodology payload and local configs.
It does not hard-code the current run's results.

## 4. Data definitions

| Term | Definition |
|---|---|
| Energy per served request | Modelled energy / served requests; null if none served |
| Energy per offered request | Modelled energy / offered requests |
| Drop rate | Dropped / offered |
| SLA violation | Dropped or modelled latency > 500 ms, as a fraction of offered requests |
| P95 latency | Run-level p95 of the modelled tick latency, not per-request empirical |
| Replica-hours | Integral of ready replicas over measured duration / 3600 |
| Scaling events | Up/down decisions in the measured window |
| Oscillation | Up/down reversal within the configured window |
| Forecast | Holt/EWMA prediction recorded at decision time |
| Actual at t+2 | Observed offered rate two ticks later |

## 5. Visual and interaction notes

- Dark professional theme, responsive grid, sidebar navigation.
- Tables scroll horizontally on narrow screens.
- Charts use `maintainAspectRatio: false` with fixed-height containers.
- Missing data produces an explicit message; the UI does not silently plot
  zeros.
- Invalid API filters return HTTP 400.
- The page is read-only; there are no mutation endpoints in the research UI.

## 6. Accessibility and browser checks

The verification log records a browser smoke test of all three pages, API
responses, asset loading, and console errors. If a browser is unavailable, use
the Flask test client and `curl`/`Invoke-WebRequest` checks documented in
`docs/TESTING.md`.

## 7. Known presentation limits

- The dashboard does not show live Kubernetes metrics.
- The cluster section is a separate validation, not a fifth simulation arm.
- The dashboard does not prove the simulation is externally valid.
- The selected-run charts can look smooth because they average ten seeds when
  `all` is chosen.
- The energy values are model estimates; every page says so.

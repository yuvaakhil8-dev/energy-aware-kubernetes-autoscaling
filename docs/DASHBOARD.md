# Dashboard

The Flask app serves a three-page research dashboard plus a set of compatibility and monitoring routes. The dashboard is read-only: it displays generated simulation artifacts and the separate cluster validation. It does not run experiments or change the results.

## 1. Pages

| Route | Template | Purpose |
|---|---|---|
| `/` | `templates/research/results.html` | KPI cards, metric chart, descriptive table with 95% CIs, paired tests vs HPA formula, real-cluster summary, run provenance |
| `/eaes-diagnostics` | `templates/research/diagnostics.html` | EAES-vs-HPA decomposition, denominator/throughput checks, forecasting ablation, per-strategy diagnostic table, rule activity |
| `/methodology` | `templates/research/methodology.html` | RQs, strategy definitions, config values, run hashes, cluster provenance, limitations |

The sidebar has exactly these three primary links. On viewports below 900 px it becomes an off-canvas panel toggled by `#menuBtn`.

## 2. Compatibility routes

These routes continue to return HTML 200 using `templates/research/compatibility.html`:

- `/autoscaling-comparison`
- `/energy-analysis`
- `/performance-analysis`
- `/experiment-explorer`
- `/research-methodology` (renders the methodology page, not the compatibility shell)

They are not the old chart sets. They are explicit compatibility views that point to the new dashboard, so old links do not 404. Their content is intentionally short; the authoritative data is on `/`, `/eaes-diagnostics`, and `/methodology`.

## 3. Preserved monitoring and legacy APIs

| Route | Method | Notes |
|---|---|---|
| `/api/status` | GET | Service status, workload, uptime, dashboard page list |
| `/health` | GET | Health check |
| `/ready` | GET | Readiness |
| `/info` | GET | Application info, five strategies, energy model, dataset |
| `/workload/status` | GET | Current demo workload |
| `/workload/change` | POST | Change demo workload; demo only |
| `/cpu/light` | GET | Demo response |
| `/cpu/intensive` | GET | Demo response |
| `/metrics` | GET | Plain-text metrics for the demo |
| `/api/v1/experiments` | GET | Original 27 records from `data/experiment_results_v2.json` |
| `/api/v1/research-papers` | GET | Bibliographic metadata for the primary related paper |
| `/status` | GET | Environment status, now updated to reflect the real Minikube validation |
| `/controller/status` | GET | Preserved legacy controller state |

`/api/v1/experiments` is intentionally still the old dataset. It is not evidence for the new results. The new results are under `/api/v1/research/*`.

## 4. Research APIs

| Route | Payload |
|---|---|
| `/api/v1/research/results` | Run manifest summary, KPIs, chart series, descriptive/paired tables, forecast rows, cluster summary |
| `/api/v1/research/diagnostic` | EAES decomposition, ablation, rule rows, denominator checks, findings |
| `/api/v1/research/methodology` | Configs, run hashes, environment, model description, limitations |
| `/api/v1/research/cluster` | Real-cluster aggregate rows, raw rows, manifest, energy note |
| `/api/v1/research/tables/<name>` | One of `descriptive`, `paired`, `friedman`, `nemenyi`, `forecasting`, `sensitivity` |

Unknown table names return HTTP 404 with the allowed list. The table endpoint is whitelisted; it does not read arbitrary files.

## 5. Data flow

```text
configs/*.yaml
    + traces/*.json
        -> experiments.run_v3
            -> results/runs/<run_id>/manifest.json
            -> results/runs/<run_id>/summary.json
            -> results/runs/<run_id>/*.jsonl
        -> analysis.analyze
            -> results/tables/*.csv
            -> results/RESULTS.md
        -> analysis.diagnose
            -> results/diagnostic.json
            -> results/EAES_DIAGNOSTIC.md
        -> Flask
            -> _load_research_bundle()
            -> templates/research/*
            -> /api/v1/research/*
```

`results/latest_run.json` is the pointer. If it is missing or points to a non-existent directory, the app falls back to the newest directory under `results/runs/`. If no run exists, the research payloads return `available: false` and the pages render an unavailable state rather than crashing.

The app reads `results/cluster_validation/summary.csv` and `manifest.json` for the cluster card. That data is separate from the simulation run.

## 6. Chart behaviour

- Chart.js 4.4.1 is loaded from jsDelivr in `templates/research/base.html`.
- If the CDN is unavailable, the chart canvas is hidden and a note points to the tables; the tables are always server-rendered and remain authoritative.
- The results chart has a metric selector for energy, SLA, drop rate, replica-hours, and latency metrics exposed in the payload.
- The diagnostics chart shows EAES vs HPA-formula energy per served request by workload.
- Charts are decorative summaries; all numbers are in the HTML tables.

This means the dashboard is not fully offline-capable for charts, but it is fully functional for data inspection without the CDN.

## 7. Styling and layout

- `static/research.css` provides the dark research theme, cards, KPI grid, tables, chart container, and responsive sidebar.
- `static/research.js` handles the mobile menu, result chart, metric selector, and diagnostic chart.
- No frontend build step, bundler, npm install, or framework is required.
- Tables use a `.table-scroll` wrapper for narrow screens; horizontal scrolling is intentional for wide statistical tables.
- All pages carry the same “energy is modelled, not measured” footer/notice.

## 8. Running locally

```powershell
cd "C:\Users\yuvaa\OneDrive\Desktop\Documents\Default Project\flask-kubernetes"
$env:ENERGY_AWARE_NO_BG='1'
python app.py
```

Open `http://127.0.0.1:5000/`. `ENERGY_AWARE_NO_BG=1` is optional for normal use; it only suppresses the demo background thread.

## 9. Container

The Dockerfile copies `app.py`, `controller.py`, `eaes/`, `configs/`, `data/`, `results/`, `templates/`, and `static/`. `.dockerignore` excludes raw JSONL tick logs, tests, experiments, analysis, archives, docs, and runtime logs. The container therefore contains the generated summary/tables needed by the dashboard but not the 19 MB raw log set.

The final image was smoke-tested in Minikube; all pages and research APIs returned 200. See `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md`.

## 10. Known limitations

- Chart.js is an external CDN dependency; no local vendored copy.
- The dashboard displays precomputed artifacts; it does not re-run analysis on request.
- The legacy `/api/v1/experiments` dataset is pseudo-replicated and must not be read as new evidence.
- The UI does not expose every raw tick; raw logs are on disk.
- No authentication; this is a research demo, not a public service.
- The Flask development server is used in the container, not a production WSGI server.
- The cluster card can only show pre-recorded validation rows; it does not query the cluster live.

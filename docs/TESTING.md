# Testing

## 1. Supported command

```powershell
$env:ENERGY_AWARE_NO_BG='1'
python -m pytest -q
```

`ENERGY_AWARE_NO_BG=1` prevents the Flask app's demo workload background thread
from starting during tests. `tests/conftest.py` also redirects the legacy
controller decision log to a temporary directory so tests do not modify tracked
artifacts.

Current result: **113 passed** (see `results/test_report.txt` and
`docs/verification_log.txt`).

## 2. Test files

| File | Focus |
|---|---|
| `tests/conftest.py` | Shared fixtures, isolated test environment, background-thread suppression, log redirect |
| `tests/test_app.py` | HTTP contract for all HTML/JSON routes, dashboard APIs, static assets, legacy compatibility, selectors, and real backend series |
| `tests/test_backend.py` | Queue/capacity/startup behavior and request accounting |
| `tests/test_controller.py` | Preserved legacy controller behavior and isolation |
| `tests/test_dataset.py` | Protected dataset presence/hashes and pseudo-replication audit |
| `tests/test_energy_model.py` | Power curve, PUE, pod attribution, conservation |
| `tests/test_engine.py` | Paired run invariants, trace reuse, summary fields, energy null handling |
| `tests/test_extensions.py` | Oracle future-peak behavior and bounds; extension manifests; forecast zero/near-zero MAPE exclusion; sensitivity exact nominal recompute; HPA replay scope; extension design counts and reports |
| `tests/test_headline.py` | Headline table shape, generated README/RESULTS, paired table, non-fabricated values |
| `tests/test_statistics.py` | Bootstrap, Wilcoxon, Holm, Cliff's delta, Friedman/Nemenyi |
| `tests/test_strategies.py` | Five strategies' rules, labels, bounds, and distinctions |
| `tests/test_workload.py` | Trace determinism, trace hashes, config validation |

## 3. What is intentionally not in pytest

- Minikube/Docker/native-HPA execution. It requires Docker Desktop and a
  running cluster; the recorded artifacts are tested for structure by the app
  and replay tests.
- A full 300-run confirmatory regeneration on every test run. The suite checks
  the committed run and generation logic; `reproduce.ps1 -Rerun` performs the
  expensive run.
- Browser rendering (Chart.js canvas pixels). The dashboard HTTP/API contract is
  tested; browser verification is recorded in `docs/verification_log.txt`.
- Physical power measurement. No such measurement exists.

## 4. Test isolation rules

- Never write to `results/runs/v3_paired_20261025T220942Z/`.
- Never write to protected `data/` copies.
- The controller log is redirected via `ENERGY_AWARE_DECISIONS_LOG`.
- Dashboard tests use Flask's test client and read committed artifacts.
- Tests must not require network access or a cluster.
- Tests must not treat ticks as independent observations.

## 5. Statistical test coverage

`tests/test_statistics.py` exercises:

- deterministic bootstrap resampling;
- paired bootstrap median CI;
- Wilcoxon signed-rank behavior with ties and non-testable small samples;
- Holm adjustment monotonicity;
- Cliff's delta bounds and direction;
- Friedman and Nemenyi outputs when testable.

The analysis does not depend on SciPy; it uses a documented normal
approximation for Wilcoxon and a chi-square survival function for Friedman.

## 6. Dashboard/API coverage

`tests/test_app.py` covers:

- `/`, `/eaes-diagnostics`, `/methodology` return HTML 200;
- all preserved legacy HTML routes return HTML 200;
- all preserved JSON routes return JSON 200;
- `/api/v1/research/timeseries` returns 60 ticks, real seed data, forecast and
  actual-forward series;
- invalid workload/strategy/seed filters return HTTP 400;
- `/api/v1/research/controller-trace` returns latest decision, rule, reason,
  cooldown status, SLA margin, details, behavior counts, and history;
- results payload exposes chart choices and metrics;
- methodology payload exposes architecture, flow, execution modes, APIs, and
  native-HPA text;
- Chart.js is served locally from `static/vendor/chart.umd.min.js`.

## 7. Extension coverage

`tests/test_extensions.py` covers:

- oracle uses the true future peak and respects replica bounds;
- extension manifests are labelled exploratory, record the unchanged
  confirmatory run, and report `git_tracked_dirty: false`;
- MAPE excludes zero and below-0.5 req/s actuals and reports the excluded count;
- sensitivity nominal recompute max relative error is exactly `0.0`;
- HPA replay reports 30 transitions, 100% agreement, and the missing 1->4
  transition limitation;
- extension summary counts match the design (oracle 360, startup 360, seed30
  600);
- extension reports exist and are labelled as extensions.

## 8. Reproduction validation

`scripts/clean_checkout_reproduction.ps1`:

1. clones the branch into a temp directory;
2. hashes committed derived artifacts;
3. runs `reproduce.ps1 -SkipTests`;
4. runs the test suite in the clone;
5. re-hashes generated artifacts;
6. records matches, differences, missing files, git status, and exit codes;
7. writes `results/extension/clean_checkout/REPRODUCTION_REPORT.txt`.

The expected non-byte-identical file is `results/analysis_manifest.json` because
it records an analysis timestamp and possibly the analysis commit. The comparison
list excludes that file and compares the substantive tables, reports, SVGs, and
replay outputs.

## 9. How to add a test safely

- Prefer pure functions and in-memory fixtures.
- If a test must read generated artifacts, treat them as read-only.
- If a test needs a temp directory, use `tmp_path`.
- If a test starts the app, set `ENERGY_AWARE_NO_BG=1`.
- If a test changes configuration, pass a temporary config directory rather than
  editing `configs/`.
- Do not add a test that silently regenerates the protected confirmatory run.

## 10. Failure triage

| Failure | First check |
|---|---|
| Missing run/table | Confirm `results/runs/v3_paired_20261025T220942Z` and `results/tables/` exist |
| Dashboard API 400 | Check filter value against manifest workloads/strategies/seeds |
| Extension manifest dirty flag | Run extension code from a clean tracked tree |
| Protected hash mismatch | Restore `data/` copies; do not edit protected files |
| Chart unavailable | Check vendored asset path and browser console |
| Cluster test skipped/failed | Start Docker Desktop/Minikube; see `docs/KUBERNETES_VALIDATION.md` |

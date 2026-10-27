# Experiment Protocol

**Status:** frozen before the confirmatory run. See `ANALYSIS_PLAN.md`.
**Run:** `v3_paired_20261025T220942Z`
**Execution mode:** `simulation`

## 1. Hypotheses

- **H1:** EAES has lower energy per served request than the `hpa_formula` baseline under identical traces and cluster assumptions.
- **H2:** Any energy difference is not solely a denominator artefact; energy per offered request, drop rate, and served/offered ratio are checked.
- **H3:** EAES does not achieve its energy result by serving materially fewer requests or violating the latency SLA more often than the baseline.
- **H4:** Forecasting EAES improves the SLA/energy trade-off under variable/bursty load relative to reactive EAES.

H3 is an honest constraint, not an assumption. The results show it is **not** fully satisfied for reactive EAES on variable and bursty workloads.

## 2. Workloads

Each trace is 300 s at 5 s ticks (60 ticks). Offered arrivals are Poisson with the following mean rates:

| Workload | Mean offered rate | Pattern |
|---|---|---|
| steady | 15 req/s | constant |
| light | 5 req/s | constant |
| medium | 25 req/s | constant |
| heavy | 50 req/s | constant |
| variable | 5–25 req/s | sinusoid, 120 s period: `15 + 10 sin(2πt/120)` |
| bursty | 5 or 80 req/s | 20 s at 80 req/s every 60 s, otherwise 5 req/s |

The rates are **offered** load; served load can be lower because of capacity or drops. The generator uses Python's `random.Random(seed)` with Poisson sampling. Traces are persisted and hashed; an existing trace is never silently regenerated.

## 3. Design and pairing

- 6 workloads × 10 seeds × 5 strategies = 300 runs.
- Seeds 1–10.
- For each workload × seed, all five strategies consume the same trace.
- Initial replicas = 3 for every strategy.
- Warm-up = 30 s, excluded from primary metrics.
- Measurement window = 30–300 s (54 ticks).
- Every run is independent of other runs; strategies do not share state.

The pairing is at the **workload × seed** level. It is not a repeated-measures design across real machines.

## 4. Execution order

The runner builds the trace index first, then loops over workloads and seeds, and runs the five strategies. Each strategy gets a fresh backend and a fresh strategy object. Results are written per run to:

```text
results/runs/<run_id>/<workload>_seed<seed>_<strategy>.jsonl
```

and one summary row per strategy to `summary.json`. A manifest records:

- run id;
- start/end timestamps;
- execution mode;
- energy scenario;
- git commit;
- `git_tracked_dirty`;
- config hashes;
- trace index;
- Python/package versions;
- seeds, workloads, strategies, and run count.

## 5. Primary and secondary metrics

Primary (pre-specified):

1. `energy_per_served_request_j`
2. `sla_violation_rate`
3. `replica_hours`
4. `drop_rate`

Secondary/diagnostic:

- energy per offered request;
- served/offered ratio;
- average and p95 latency;
- scaling events and oscillations;
- max pending and max ready replicas;
- over-provisioning;
- cooldown/stabilization holds;
- rule counts;
- energy conservation error.

## 6. Windows and denominators

- Raw logs contain all 60 ticks, including warm-up, for transparency.
- Primary metrics use the 54 post-warm-up ticks.
- Energy per served request uses measurement-window energy / measurement-window served requests.
- Energy per offered request uses measurement-window energy / measurement-window offered requests.
- If served = 0, per-served energy is null; no artificial denominator is inserted.
- SLA violation rate uses violations / offered requests in the measurement window.

## 7. Statistical plan

- Bootstrap 95% CI: 5,000 resamples, seed 12345, percentile method.
- Pairing: by workload and seed.
- Wilcoxon signed-rank for EAES vs each baseline, using the normal approximation with tie correction (no exact/permutation branch). Tests with fewer than five nonzero paired differences are reported as `not_testable`.
- Holm correction within each workload × baseline family.
- Friedman across five strategies per workload × metric; Nemenyi critical difference as a secondary omnibus check.
- Cliff’s delta for paired ordinal effect size.
- α = 0.05, two-sided.
- No scipy dependency; implementations are in `analysis/analyze.py` and tested.

## 8. Stopping rule and deviations

The full 300-run design was executed once. There was no optional stopping, no dropping of “bad” seeds, and no post-hoc addition of strategies. The analysis plan was frozen before the run.

The earlier run `v3_paired_20261025T212043Z` was superseded by `v3_paired_20261025T220942Z` after diagnostic-field and provenance commits. The metrics are deterministic and essentially identical; the newer manifest is the one used because its `git_commit` and `git_tracked_dirty` accurately describe the code and tree that produced the raw logs.

## 9. Exact commands

```powershell
# Change to the repository root (run this from a PowerShell prompt while inside the repo)
Set-Location (git rev-parse --show-toplevel)
python -m experiments.run_v3
python -m analysis.analyze
python -m analysis.diagnose
$env:ENERGY_AWARE_NO_BG='1'
python -m pytest -q
```

## 10. What was not done

- No physical power measurement.
- No multi-node cluster experiment.
- No production traffic capture.
- No Bayesian analysis, equivalence testing, or sequential testing.
- No reproduction of Li et al. (2025).
- No use of the original 27-row dataset for inference.

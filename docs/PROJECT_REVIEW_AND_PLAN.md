# Project Review and Rebuild Plan

**Date:** 2026-10-26
**Original baseline commit:** `c5ec94d` (`pre-rebuild-snapshot`)
**Working branch:** `research-rebuild`

## 1. Review

The existing project is a Flask demonstration with a working dashboard and API surface, but it is not yet an experimentally defensible research framework.

Strengths to preserve:

- The Flask app starts and serves all six pages and the existing APIs.
- The original 29-test suite passes.
- The dashboard is usable and the controller has a clear threshold-based structure.
- Both original datasets are present and can be preserved byte-for-byte.

Defects to repair:

1. The 27-row dataset is 9 deterministic cells repeated three times. It cannot support statistical claims.
2. The "HPA" baseline is a toy 1 s 65/35 rule, not Kubernetes HPA and not the HPA replica formula.
3. Energy accounting has no node boundary, never multiplies by replicas, charges idle power to an undefined unit, and divides by cumulative successes.
4. Zero-request division produces 450 J/request.
5. Strategy comparisons use different request denominators.
6. The Kubernetes backend is a stub; no deployment is evidenced.
7. The dashboard contains an unverified "15.34% better than HPA" claim.

## 2. Rebuild strategy

- Preserve the original app, templates, tests, experiments, manifests, and datasets in `archive/pre-rebuild/` and in the Git baseline.
- Keep the original datasets outside the repository untouched; record hashes before and after.
- Build a new, self-contained simulation stack rather than modifying the old runner in place.
- Keep the Flask app and all existing API routes compatible; add new research APIs and three new pages.
- Use simulation only for confirmatory experiments. Any cluster validation is separate and must be labelled as such.
- Report the actual result, including any EAES disadvantage.

## 3. Phase plan and acceptance criteria

| Phase | Work | Acceptance criterion |
|---|---|---|
| 0 | Audit, backup, Git baseline, dataset hashes, baseline tests | `AUDIT.md`, test log, plan, baseline branch |
| 1 | Config-driven structure, workload generator, reproduction scripts | Deterministic trace hashes; config/trace provenance recorded |
| 2 | `ClusterBackend` abstraction and `SimulatedCluster` | Scaling changes capacity; served/dropped/latency tracked |
| 3 | Node-level energy model with PUE, attribution, scenarios | Conservation test; zero-request null; sensitivity output |
| 4 | Five strategies, including HPA formula and EAES | Unit tests for each strategy and decision logs |
| 5 | Paired experiments: 6 workloads × 10 seeds × 5 strategies | Identical trace per seed; raw tick logs; diagnostic |
| 6 | Statistical analysis without scipy | Bootstrap CIs, paired tests, Holm, Friedman, Nemenyi, Cliff's delta |
| 7 | Real Kubernetes attempt | Either verified cluster run or exact blocker documented |
| 8 | Three-page research dashboard | Results/diagnostics/methodology from generated data; old routes compatible |
| 9 | Full tests and validation | All tests pass; report saved; original datasets unchanged |
| 10 | Documentation and final report | Docs match code and generated results; no fabricated claims |

## 4. Planned technical defaults

- Duration: 300 s simulated; control interval 5 s.
- Seeds: 1–10 (10 independent seeds per workload).
- Workloads: steady, light, medium, heavy, variable, bursty.
- Strategies: static, CPU threshold, HPA formula, EAES, forecasting EAES.
- Cluster: 4 pods per node, 10 req/s per pod, 10 s pod startup delay, bounded queue.
- Energy: nominal `P_idle=150 W`, `P_max=500 W`, `PUE=1.2`; low/high scenarios for sensitivity.
- SLA: 500 ms latency threshold; drop rate is the primary hard constraint; utilization ceiling 0.8.
- Statistics: 5,000 bootstrap resamples, paired by seed, Holm correction, Friedman/Nemenyi.

These are modelling assumptions, not measurements. They will be stated in `METHODOLOGY.md` and `LIMITATIONS.md`.

## 5. Infrastructure status

- Docker Desktop Linux engine responds.
- WSL2 Ubuntu is installed but stopped.
- `kubectl` client and Minikube are installed; no cluster exists yet.
- Kind is not installed.
- Phase 7 will make one controlled Minikube attempt. If it fails, the exact commands and errors will be recorded and the simulation results will not be described as cluster results.

## 6. Integrity rules for this rebuild

- Never edit the original datasets.
- Never label model output as measured power.
- Never call the threshold controller Kubernetes HPA.
- Never claim Li et al. reproduction.
- Never present copied repetitions as independent samples.
- Commit each completed phase on `research-rebuild`.

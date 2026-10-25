# Research Contributions

## 1. Summary

This rebuild turns a demonstration project into an inspectable research artifact. It does not claim a new autoscaling algorithm or a production result. Its contributions are the separation of previously conflated ideas, a reproducible measurement protocol, and honest negative findings.

## 2. Contribution 1: disambiguating four “HPA” claims

The original project used “HPA” for a 65/35 one-second rule, embedded an unverified “15.34% better” claim, and had no real cluster HPA. This rebuild distinguishes:

1. native Kubernetes HPA (validated separately in Minikube);
2. a simulated HPA replica formula with tolerance and stabilization;
3. the legacy 80/30 threshold controller;
4. an EAES-inspired SLA-first controller.

Evidence:

- `eaes/strategies.py`
- `docs/STRATEGIES.md`
- `docs/KUBERNETES_VALIDATION.md`
- `AUDIT.md`

## 3. Contribution 2: a node-level energy model with explicit assumptions

The original model charged undefined per-container power and divided by a cumulative success count, producing 450 J/request at zero requests. The new model:

- defines a node boundary;
- charges idle power per active node;
- computes dynamic power from node utilisation;
- applies PUE;
- attributes energy to pods and checks conservation;
- returns null for zero denominators;
- keeps energy out of the control loop;
- supports low/nominal/high and PUE sensitivity.

Evidence:

- `eaes/energy.py`
- `docs/ENERGY_MODEL.md`
- `results/tables/sensitivity.csv`
- `results/diagnostic.json`

The model is uncalibrated and this is stated everywhere. The contribution is transparency, not measurement.

## 4. Contribution 3: a reproducible paired experiment

- 6 workloads × 10 seeds × 5 strategies = 300 runs.
- 300 s per run, 5 s ticks, 30 s warm-up excluded.
- identical trace per workload × seed across strategies;
- initial replicas = 3 for all;
- raw per-tick JSONL for every run;
- manifest with config hashes, trace hashes, versions, git commit, and tracked-dirty flag;
- frozen analysis plan before the confirmatory run.

Evidence:

- `configs/*.yaml`
- `traces/`
- `results/runs/v3_paired_20261025T220942Z/`
- `ANALYSIS_PLAN.md`
- `docs/EXPERIMENT_PROTOCOL.md`
- `docs/REPRODUCIBILITY.md`

## 5. Contribution 4: a diagnostic that tries to falsify the headline

The diagnostic explicitly checks:

- energy per offered request as well as per served;
- drop rate and served/offered;
- replica-hours;
- whether EAES serves more/fewer requests;
- whether the denominator changes the sign;
- startup delay, pending replicas, over-provisioning;
- rule and hold counts;
- forecasting ablation;
- conservation error.

This is why the report can say that the light-load energy equality is a node-model artefact, that static wins on medium, and that EAES has SLA violations on variable/bursty load.

Evidence:

- `analysis/diagnose.py`
- `results/EAES_DIAGNOSTIC.md`
- `docs/FAILURE_ANALYSIS.md`

## 6. Contribution 5: honest negative results

The project reports:

- EAES is worse than static at 25 req/s: 20.962 vs 17.736 J/request.
- EAES is worse than the threshold controller on medium by a significant margin.
- EAES has SLA violations on variable (0.0119) and bursty (0.0170).
- Forecasting removes variable violations but costs 16.5% energy and 17.0% replica-hours.
- Forecasting does not help the abrupt burst.
- Fewer replicas on light load do not reduce modelled energy because the node stays active.
- The HPA-formula baseline over-provisions in this 300 s configuration.
- The steady EAES-vs-HPA energy difference is not significant after Holm correction.

These are not footnotes; they change the interpretation.

## 7. Contribution 6: a separate real-cluster validation

The Minikube validation demonstrates that the deployment, Service, metrics-server, and native HPA work. It records real replicas, request outcomes, latency, node CPU, and versions. It does not validate the simulation’s energy ranking, and its energy column is modelled.

Evidence:

- `experiments/run_cluster_validation.py`
- `results/cluster_validation/`
- `docs/CLUSTER_ENVIRONMENT.md`
- `docs/KUBERNETES_VALIDATION.md`

## 8. Contribution 7: a three-page research dashboard

The dashboard exposes results, diagnostics, and methodology without requiring the reader to parse JSON. It keeps legacy routes alive as compatibility views and preserves the original monitoring APIs. It labels energy as modelled and links the numbers to their source.

Evidence:

- `app.py`
- `templates/research/`
- `static/research.css`
- `static/research.js`
- `docs/DASHBOARD.md`

## 9. Contribution 8: reproducible packaging

The container now includes the research package, configs, data copies, and generated summary artifacts. The final image was smoke-tested in the real cluster for all pages and APIs. Raw tick logs are excluded from the image to keep it small but remain in the repository.

Evidence:

- `Dockerfile`
- `.dockerignore`
- `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md`

## 10. What is not a contribution

- A new autoscaling algorithm.
- A reproduction of Li et al. (2025).
- A physical energy measurement.
- A production cluster evaluation.
- A general workload benchmark.
- A proof that EAES saves energy in real clouds.
- A statistically significant steady-workload energy result after correction.

## 11. Contribution statement for a report

A defensible one-sentence statement is:

> This work contributes a reproducible simulation and diagnostic protocol that separates native Kubernetes HPA, an HPA-formula baseline, a legacy threshold controller, and an EAES-inspired controller, and reports that the EAES-inspired controller reduces modelled energy relative to the HPA formula on several workloads while failing to dominate static provisioning and incurring startup-delay SLA violations on variable and bursty traffic.

That sentence is supported by the artifacts. Stronger claims are not.

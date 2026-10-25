# Threats to Validity

This project follows a simulation-first design with a separate real-cluster check. Each layer has different threats. They are listed here rather than collapsed into a generic “limitations” paragraph.

## 1. Construct validity

### 1.1 Energy is a model output

The construct “energy per served request” is computed from CPU utilisation and assumed power parameters. It is not a meter reading. A strategy with lower modelled energy may not use less wall power, especially if CPU frequency, memory, network, or storage dominate.

**Mitigation:** every report labels energy as modelled; raw node/pod energy is retained; low/nominal/high and PUE sensitivity are reported; no absolute joule prediction is claimed.

### 1.2 CPU utilisation is a proxy

Node utilisation is computed from served work relative to a full node’s pod capacity. It is not measured CPU. The real-cluster validation uses `kubectl top node` CPU percentages, which are also a proxy.

**Mitigation:** the simulation and cluster use separate models and are not merged. The cluster energy column is explicitly labelled modelled.

### 1.3 SLA definition is coarse

A tick is charged with an SLA violation for every served request if the tick-average latency exceeds 500 ms, and every dropped request is a violation. This is not a per-request latency distribution. It can overstate violations during a mixed-latency tick and understate tail latency within a fast tick.

**Mitigation:** the same rule is applied to every strategy; average and p95 latency are reported; the rule is documented.

### 1.4 The HPA formula is not native HPA

`hpa_formula` implements a replica formula with a tolerance band and stabilization, not the Kubernetes HPA control loop. Native HPA uses metrics-server scrape intervals, a different stabilization algorithm, and a different tolerance implementation.

**Mitigation:** separate naming, separate Phase 7 validation, and explicit labels in every table.

### 1.5 EAES is not a reproduction of the cited paper

The controller is EAES-inspired: SLA-first, margin-based, startup-aware. The full text of Li et al. (2025) was unavailable behind a paywall, so their exact algorithm, parameters, and results were not reproduced.

**Mitigation:** the project never claims a reproduction. The citation is related work only.

## 2. Internal validity

### 2.1 Pairing is correct but limited

All strategies share the same trace for a workload × seed. This controls arrival variability. It does not control controller-specific state, because each strategy has its own backend and starts fresh.

**Mitigation:** deterministic traces, hashed trace index, fresh backend per run, initial replicas = 3.

### 2.2 Warm-up choice

The primary window starts at 30 s. A different warm-up would change the measured energy and SLA, especially for the HPA formula and EAES, which are still settling.

**Mitigation:** raw logs retain all 60 ticks; the analysis plan fixed 30 s before the run; `total_*` and measurement-window fields are both retained.

### 2.3 Stabilization and cooldown choices

EAES uses 30 s cooldowns, 30 s dwell, and 60 s stabilization. The HPA formula uses 300 s scale-down stabilization. These are design choices, not universal constants. They strongly affect the 300 s results.

**Mitigation:** documented in `docs/STRATEGIES.md`; no post-hoc tuning; the negative medium-load result is reported.

### 2.4 Confounding from static capacity

Static three replicas exactly covers 30 req/s. Four of the six workloads have mean or peak offered load at or below 30 req/s. This makes static a strong baseline on those traces and weakens any general claim that EAES is needed for low/medium load.

**Mitigation:** report static explicitly, including its failures on heavy/bursty; do not claim EAES dominance.

### 2.5 Node-level energy attribution

Idle power is charged per active node, not per pod. Reducing replicas on the same node may not reduce energy. This is a defensible node-boundary choice, but it attenuates the benefit of scale-down.

**Mitigation:** documented in `docs/ENERGY_MODEL.md`; replica-hours are reported separately; the light-load flat energy is discussed.

### 2.6 No node autoscaling

The model uses `ceil(ready / pods_per_node)` active nodes but does not implement a node autoscaler, node draining, or pod rescheduling. `max_nodes` is declared but not binding at 10 replicas.

**Mitigation:** explicitly stated; no claim about cluster-level node energy management.

## 3. External validity

### 3.1 Synthetic traces

The six traces are generated from fixed rates and simple sinusoids/steps. They are not production traffic. Real workloads have burst correlations, heavy tails, retries, multi-service dependencies, and diurnal patterns.

**Mitigation:** the design is a controlled comparison, not a benchmark; no production claims.

### 3.2 Single simulated cluster configuration

Four pods per node, 10 req/s per pod, 10 s startup, 1–10 replicas. A different cluster shape or startup delay would change the results.

**Mitigation:** parameters are explicit and configurable; sensitivity to power assumptions is reported, but sensitivity to cluster shape is not.

### 3.3 Single-node Minikube validation

The real-cluster validation is one Docker-driver Minikube node. It says nothing about multi-node scheduling, anti-affinity, node failures, or production networking.

**Mitigation:** the validation is presented as operational evidence only.

### 3.4 Windows host

The development and validation host is Windows. The simulation is platform-independent Python, but the cluster validation used Docker Desktop/Minikube on Windows. Path, timing, and process behavior may differ elsewhere.

**Mitigation:** versions and commands are recorded in `docs/CLUSTER_ENVIRONMENT.md` and `docs/REPRODUCIBILITY.md`.

## 4. Statistical conclusion validity

### 4.1 Small sample

Ten seeds per cell. The paired tests have limited power for small effects. The steady energy result is borderline after correction.

**Mitigation:** report CIs, raw and Holm p-values, and effect sizes; do not dichotomize at 0.05 without context.

### 4.2 Multiple testing

Many metrics and workloads. Holm correction reduces false positives but is conservative, and the family includes 14 tests per workload × baseline. Nemenyi is also conservative.

**Mitigation:** the analysis plan was frozen; primary metrics are separated; Holm-adjusted values are shown; omnibus and post-hoc results are not over-interpreted.

### 4.3 Bootstrap dependence

Bootstrap CIs resample the ten observed seeds. They describe seed-to-seed variation in this simulation, not sampling uncertainty from a real population.

**Mitigation:** stated in the methods; no claim of population inference.

### 4.4 HPA baseline configuration

The HPA formula’s target and stabilization are plausible but not tuned to be competitive in a 300 s run. Its poor energy performance drives several significant results.

**Mitigation:** the HPA configuration is explicit; a native-HPA check is separate; the report says the comparison is configuration-dependent.

## 5. Reproducibility threats

- Python and package versions are recorded, but the environment is not containerized for the simulation.
- The Minikube/Docker versions are recorded, but the host kernel and Docker Desktop version are outside the repository.
- `results/runs/` raw logs are large and may be excluded from a container image.
- The original datasets are outside the repository; byte-identical copies are tracked under `data/`.
- The paywalled paper prevents an exact reproduction of the cited method.

**Mitigations:** run manifests with config/trace hashes and git commit; deterministic seeds; `git_tracked_dirty`; `docs/REPRODUCIBILITY.md`; hashes in `docs/DATA_PROVENANCE.md`.

## 6. Reporting threats

- It is tempting to report only the five workloads where EAES beats the HPA formula and omit the static and medium-load counterexamples.
- It is tempting to call the HPA formula “Kubernetes HPA” and imply production relevance.
- It is tempting to quote absolute joules as measured.

**Mitigations:** this report includes the negative results, uses the exact strategy names, labels energy as modelled, and separates simulation from validation.

## 7. Highest-priority residual risks

1. The energy model is uncalibrated, so absolute energy claims are unsupported.
2. The HPA-formula baseline is configuration-sensitive and may be unfairly weak.
3. The synthetic traces make static unusually strong.
4. The node-level model hides scale-down benefits on light load.
5. The real-cluster validation is too small to validate the simulation ranking.

These risks bound what the project can claim. They do not invalidate the software, the paired design, or the negative findings.

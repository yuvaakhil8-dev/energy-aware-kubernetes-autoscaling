# Limitations

This file is the consolidated, current limitation list for the final build. It
supersedes older notes in `docs/LIMITATIONS.md` and `docs/THREATS_TO_VALIDITY.md`
where they conflict. Detailed threat analysis remains in
`docs/THREATS_TO_VALIDITY.md`; failure analysis is in
`docs/FAILURE_ANALYSIS.md`; energy caveats are in `docs/ENERGY_MODEL.md`.

## 1. Evidence and measurement

1. **No physical power measurement.** All energy is modelled from CPU
   utilisation and assumed `P_idle`, `P_max`, and PUE. Kepler was unavailable and
   no external meter was used.
2. **The power curve is linear and uncalibrated.** It ignores frequency scaling,
   non-linear low-load behaviour, memory/disk/network power, cooling variation,
   and hardware heterogeneity.
3. **The real-cluster energy is modelled too.** `kubectl top node` CPU is a proxy,
   not power. The cluster values around 2.25-2.33 J/request are dominated by
   charging a mostly idle node, not by a hardware measurement.
4. **No Prometheus verification.** metrics-server was verified; Prometheus was
   not used or verified.
5. **No full-text verification of Li et al. (2025).** The Elsevier paper was
   paywalled. Only Crossref metadata was verified. The implementation is
   EAES-inspired, not a reproduction.

## 2. Simulation design

6. **The confirmatory experiment is a simulation.** Replica counts, requests,
   latency, and energy are model outputs, not a cluster run.
7. **Synthetic traces only.** Six workload classes, ten seeds each, 300 s. No
   production traffic, diurnal pattern, heavy-tailed request cost, retries,
   multi-service dependency, or adversarial load.
8. **Ten seeds is limited power for small effects.** None of the confirmatory
   EAES-versus-HPA energy differences survives Holm correction at alpha = 0.05.
   The 30-seed extension is exploratory and cannot retroactively change the
   pre-specified inference.
9. **One simulated cluster shape.** Four pods per node, 10 req/s per pod, 10 s
   startup, 1-10 replicas. Other shapes could change rankings. The startup sweep
   covers only 5, 10, and 20 s.
10. **No node autoscaling.** The model activates `ceil(ready / 4)` nodes but does
    not implement a node autoscaler, draining, or rescheduling. `max_nodes = 10`
    is not a binding production constraint.
11. **No heterogeneous nodes, anti-affinity, failures, or network effects.**
12. **The HPA formula is configuration-sensitive.** A 50% target, 10% tolerance,
    +1 minimum scale-up, and 300 s scale-down stabilization in a 300 s run
    produce heavy over-provisioning. A different HPA configuration could change
    the comparison.
13. **The static baseline is unusually strong** on steady/light/medium/variable
    because three replicas cover those traces. It is not a general-purpose
    policy, and it fails badly on heavy/bursty load.
14. **The node-level model hides some scale-down savings** when replicas remain
    on the same active node. Light-load energy can be flat even when
    replica-hours fall.
15. **The SLA rule is coarse.** A tick-level analytic latency above 500 ms
    charges every request in that tick; p95 is modelled, not an empirical
    per-request percentile. The SLA violation rate is therefore not directly
    comparable to a production SLO measured per request.
16. **One fixed 300 s horizon.** The HPA scale-down stabilization is 300 s, so
    the run is shorter than one full stabilization window. This is a design
    choice, not a neutral default.

## 3. Statistics

17. **Multiple testing is controlled only within workload x baseline families.**
    There is no global correction across all workloads, metrics, and strategy
    pairs. The Holm-adjusted p-values in the headline table are the pre-specified
    family-wise adjustment.
18. **The Wilcoxon test uses a normal approximation, not an exact permutation
    test.** With 10 pairs and ties this is defensible but not exact.
19. **Bootstrap intervals describe this simulation's run distribution.** They are
    not confidence intervals for a production system or a different hardware
    configuration.
20. **No equivalence testing.** A non-significant result is not evidence that two
    strategies are equivalent.
21. **The paired difference is reported as a median.** Mean differences and
    Cliff's delta are also generated, but the median is the headline effect and
    can differ from the mean under skew.
22. **Energy per served request can be gamed by dropping traffic.** The report
    always shows energy per offered request, drop rate, and SLA violation rate.
    Readers must use them together.

## 4. Real cluster

23. **One Minikube node.** Docker driver, single control-plane node. No
    multi-node scheduling, node failure, or production networking.
24. **Flask development server.** The container runs `python app.py`, not
    gunicorn/uWSGI.
25. **The cluster validation is not the paired experiment.** Different workload,
    no five-strategy comparison, no measured power, and only three repetitions
    per mode.
26. **The native HPA scale-up transition is unobserved.** The sampler starts
    after the HPA has reached four replicas. The initial 1->4 transition and its
    latency are not in the recorded samples.
27. **The HPA replay validates only steady-state sampled decisions.** Thirty
    transitions, 100% agreement, zero observed or predicted changes between
    samples. This is weak evidence and says nothing about bursts or cold starts.
28. **The validation image commit and final dashboard image differ.** The 60 s
    HPA validation ran on commit `cce700b`; the final dashboard was rebuilt later
    and smoke-tested separately. See
    `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md`.
29. **Port-forwarding and cluster state are manual.** A stopped port-forward or a
    deleted HPA changes reproducibility. Docker Desktop/Minikube were not
    available at the final verification time, so no additional cluster
    repetitions were run.
30. **No automated cluster integration test in pytest.** Cluster checks are
    separate commands and are not part of the 112-test suite.

## 5. Implementation

31. **The Python `kubernetes` package is broken in the local environment.**
    `import kubernetes` returns a namespace object without usable client
    metadata. The real backend uses `kubectl` subprocesses.
32. **The dashboard reads precomputed artifacts.** It does not run the experiment
    or analysis on request and does not display live cluster state.
33. **Chart.js is vendored locally.** The dashboard works offline; this fixes an
    older CDN-only limitation. The vendored file is not audited beyond its
    published version and size.
34. **Raw confirmatory JSONL logs are included in the Docker image** so the
    time-series and controller-trace APIs work. This increases image size.
    Cluster per-request logs remain excluded.
35. **The legacy `/api/v1/experiments` dataset is pseudo-replicated.** It remains
    for compatibility; it is not new evidence.
36. **The original `controller.py` is preserved.** It still contains legacy
    energy assumptions and is not the research energy model. Use `eaes/` for the
    research results.
37. **The dashboard is a research artifact, not a production UI.** It has no
    authentication, CSRF protection, multi-user isolation, or production WSGI
    server.
38. **Some legacy documentation is historical.** Use the root documents and the
    generated `results/RESULTS.md` as authoritative when older notes conflict.

## 6. Extensions

39. **The oracle is not deployable.** It uses true future arrivals and is an
    information upper bound only.
40. **The startup sweep tests only three delays.** It cannot establish behavior
    under arbitrary Kubernetes scheduling and image-pull latency.
41. **The 30-seed extension was run after the confirmatory analysis.** It is
    exploratory and not covered by the frozen analysis plan.
42. **The energy sensitivity is a post-hoc recalculation.** It changes only the
    modelled power/PUE, not controller decisions or traces.
43. **The forecast evaluation is a held-out final segment, not rolling-origin
    retraining.** MAPE explicitly excludes zero and near-zero actuals, and the
    excluded count is reported.
44. **The Pareto plots use energy per offered request and drop rate.** They do
    not encode latency, SLA, replica-hours, or cost, so a point on the frontier
    is not automatically a desirable operating point.

## 7. Reporting

45. **Statistical significance is not external validity.** A paired simulation
    p-value does not establish production behavior.
46. **No cost model.** Replica-hours are reported, but no monetary or carbon cost
    is claimed.
47. **No claim of optimality.** EAES is a rule-based controller, not an optimal
    policy. The oracle is an upper bound under perfect information, not a
    deployable optimum.

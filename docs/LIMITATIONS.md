# Consolidated Limitations

This file is the short list. Detailed threats are in `docs/THREATS_TO_VALIDITY.md`, failures in `docs/FAILURE_ANALYSIS.md`, and energy caveats in `docs/ENERGY_MODEL.md`.

## Evidence and measurement

1. **No physical power measurement.** All energy is modelled from CPU utilisation and assumed `P_idle`, `P_max`, and PUE. Kepler was unavailable, and no external meter was used.
2. **The power curve is linear and uncalibrated.** It ignores frequency scaling, non-linear low-load behaviour, memory/disk/network power, cooling variation, and hardware heterogeneity.
3. **The real-cluster energy is modelled too.** `kubectl top node` CPU is a proxy, not power. The 2.25–2.32 J/request cluster numbers are dominated by idle-node charging, not a hardware measurement.
4. **No Prometheus verification.** metrics-server was verified; Prometheus was not.
5. **No full-text verification of Li et al. (2025).** The Elsevier paper was paywalled. Only Crossref metadata was verified; the algorithm was not reproduced.

## Design and scope

6. **The confirmatory experiment is a simulation.** Replica counts, requests, latency, and energy are model outputs, not a cluster run.
7. **Synthetic traces only.** Six workload classes, ten seeds each, 300 s. No production traffic, diurnal pattern, heavy-tailed request cost, retries, multi-service dependency, or adversarial load.
8. **Ten seeds.** Limited power for small effects. The steady EAES-vs-HPA energy result does not survive Holm correction.
9. **One simulated cluster shape.** Four pods per node, 10 req/s per pod, 10 s startup, 1–10 replicas. Other shapes could change the rankings.
10. **No node autoscaling.** The model activates `ceil(ready / 4)` nodes but does not implement a node autoscaler, draining, or rescheduling. `max_nodes = 10` is declared but not binding at 10 replicas.
11. **No heterogeneous nodes, anti-affinity, failures, or network effects.**
12. **The HPA formula is configuration-sensitive.** Target 50%, ±10% tolerance, +1 minimum scale-up, and 300 s scale-down stabilization in a 300 s run produce heavy over-provisioning. A different HPA configuration could change the comparison.
13. **The static baseline is unusually strong** on steady/light/medium/variable because 3 × 10 req/s covers those traces. It is not a general-purpose policy.
14. **The node-level model hides scale-down savings** when replicas remain on the same active node. Light-load energy is flat even when replica-hours fall.
15. **The SLA rule is coarse.** A tick-average latency over 500 ms charges every served request in that tick; p95 is analytic (`base + 3 × wait`), not empirical.

## Real cluster

16. **One Minikube node.** Docker driver, single control-plane node. No multi-node scheduling, node failure, or production networking.
17. **Flask development server.** The container runs `python app.py`, not gunicorn/uWSGI.
18. **The cluster validation is not the paired experiment.** Different workload, no five-strategy comparison, no measured power, and only three repetitions per mode.
19. **The validation image commit and final dashboard image differ.** The 60 s HPA validation ran on commit `cce700b`; the final dashboard image was built from later content and smoke-tested separately. See `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md`.
20. **Port-forwarding and cluster state are manual.** A stopped port-forward or a deleted HPA changes reproducibility.

## Implementation

21. **The Python `kubernetes` package is broken in the local environment.** `import kubernetes` returns a namespace object without usable client metadata. The real backend therefore uses `kubectl` subprocesses. The cluster path is tested manually, not in the unit suite.
22. **No automated minikube integration test in pytest.** Cluster checks are separate commands.
23. **Chart.js is loaded from a CDN.** Offline use falls back to tables but loses charts.
24. **The dashboard reads precomputed artifacts.** It does not run the experiment or analysis on request.
25. **The legacy `/api/v1/experiments` dataset is pseudo-replicated.** It remains for compatibility; it is not new evidence.
26. **The original controller is preserved.** It still contains legacy energy assumptions and is not the research energy model. Use `eaes/` for the new model.
27. **The old `test_endpoint.py` is a standalone legacy script.** It is not part of the pytest suite and may contain pre-existing issues. The supported test command is pytest.
28. **Raw JSONL logs are excluded from the Docker image** to keep the image small; they remain in the repository/workspace.
29. **The analysis uses normal-approximation Wilcoxon, not an exact test.** With 10 pairs this is defensible but not exact.
30. **Multiple testing is controlled only within workload × baseline families.** There is no global correction across all workloads and metrics.

## Reporting

31. **Statistical significance is not external validity.** A paired simulation p-value does not establish production behavior.
32. **Energy per served request can be gamed by dropping traffic.** The report includes drop/SLA and energy per offered request, but readers must use them.
33. **The 27-row original dataset cannot support inference.** It is nine deterministic cells copied three times.
34. **The “15.34% better than HPA” claim from the original project is unverified and not used.**
35. **The project does not claim EAES dominance.** EAES loses to static on medium energy, loses to the threshold controller on medium, and has SLA violations on variable/bursty load.
36. **The final report’s conclusions are conditional on the model, traces, and configuration.** Changing them could change the ranking.

## Unresolved operational items at the documentation checkpoint

- The local Flask process and Minikube may still be running on the development host; they should be stopped when the demo is finished.
- The native HPA may still be applied in the cluster.
- The final container image should be rebuilt after the last documentation/requirements commit before archival screenshots or distribution.
- The `kubernetes` Python package remains broken; use `kubectl`.
- Prometheus was not verified.

These are operational notes, not results.

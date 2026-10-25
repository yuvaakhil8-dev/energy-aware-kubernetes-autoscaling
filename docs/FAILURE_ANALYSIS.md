# Failure Analysis

This document records the ways the proposed EAES controller fails, the ways the baselines fail, and the ways the experiment itself could mislead. It is intentionally not a list of successes.

## 1. EAES is worse than static at moderate load

At 25 req/s, three replicas provide 30 req/s. Static serves every request with no drops, no SLA violations, and 17.736 J/request. EAES sees 25/30 = 83.3% utilisation, above its 70% target and 80% ceiling, and scales to 4–5 replicas. It uses 20.962 J/request.

**Cause:** EAES is SLA-first and conservative. Its target is deliberately below the ceiling. It does not know that the 500 ms SLA can still be met at 83% utilisation.

**Consequence:** EAES is not an energy minimiser. It is a safety-margin controller. Any claim that it “reduces energy” must be relative to the over-provisioning HPA baseline and must be paired with the static counterexample.

**Possible fix (not evaluated):** target-aware scaling, an explicit energy-aware hold rule, or a utilisation ceiling closer to the SLA knee. These would be new strategies and would require a new pre-registered experiment.

## 2. EAES violates the latency SLA on variable load

Reactive EAES has mean SLA violation rate 0.0119 on the variable workload, versus 0.000 for the HPA formula and 0.000 for static. Drops are zero; the violations come from queueing during the 10 s startup delay.

**Cause:** the controller reacts after the margin is breached. The new replicas cannot serve until startup completes. The sinusoid rises faster than the reactive loop plus startup.

**Consequence:** a lower energy number is not automatically a better service outcome. The diagnostic reports this explicitly.

**Mitigation evaluated:** forecasting EAES reduces the variable SLA violation rate to 0.000, but costs 16.5% more energy and 17.0% more replica-hours. The mitigation is not free.

## 3. EAES violates the latency SLA on bursty load, and forecasting does not help

Reactive EAES has 0.0170 mean SLA violation rate on the 20 s / 80 req/s bursts. Forecasting EAES has the same 0.0170, the same energy, and the same replica-hours.

**Cause:** the burst is abrupt. A two-tick Holt forecast cannot anticipate a 20 s step; the controller only reacts after the queue builds. All adaptive strategies reach the 10-replica maximum.

**Consequence:** the small EAES penalty versus the HPA formula (which sits at 10 replicas for the whole run and therefore records zero violations) is real. The HPA formula’s zero is bought with maximum provisioning.

**Possible fix (not evaluated):** burst detection, a larger max replicas, faster startup, or a queue-aware admission policy. None of these is in the current design.

## 4. Fewer replicas do not always mean less modelled energy

On light load, EAES uses 0.113 replica-hours versus 0.225 for static, but both use 46.722 J/request. The reason is the node-level model: one to four pods on a single node still incur that node’s idle power. Removing replicas within the same node does not remove the node.

**Consequence:** the energy model under-rewards fine-grained scale-down on lightly loaded nodes. This attenuates EAES’s apparent benefit and is a limitation of the metric, not evidence that autoscaling is useless.

**Possible fix (not evaluated):** power down empty/consolidated nodes, model per-pod power, or use a measured power source. The current `max_nodes` field is not an active node-autoscaling algorithm.

## 5. The HPA-formula baseline is easy to beat in this configuration

The simulated HPA formula reaches about 4.9 ready replicas on steady load and 10 on medium, heavy, variable, and bursty. Its 50% target, +1 minimum scale-up, tolerance band, and 300 s scale-down stabilization interact with a 300 s run so that it rarely scales down.

**Consequence:** the large EAES-vs-HPA energy differences are partly a baseline-configuration effect. A native HPA with a different target, tolerance, scrape interval, or stabilization could behave differently.

**Mitigation in reporting:** the HPA formula is labelled as a simulated formula, not native HPA; the real-cluster validation is separate; and the report does not claim that native HPA would use 30–45 J/request.

## 6. Static is a misleading energy baseline if drops are ignored

Static has 16.500 J/request on heavy and 21.115 J/request on bursty, but it drops 39.8% and 38.0% of offered requests and has SLA violation rates of 1.000 and 0.841. A ranking that uses only J/request would declare static the winner and miss that it is serving less work and violating the SLA.

**Consequence:** every energy table in this project includes drop and SLA columns, and the diagnostic reports energy per offered request and served/offered ratio as denominator checks.

## 7. The legacy threshold controller is not a safe or fair “HPA”

The 80/30 rule scales greedily and has a long down cooldown. On heavy load it has 0.320 SLA violation rate and 0.0105 drop rate; on bursty it has 0.748 SLA violation rate and 0.0339 drop rate. On medium it happens to use less energy than EAES because it stays at three or four replicas.

**Consequence:** “EAES beats the threshold controller on energy” is not universally true. On medium, the threshold controller is significantly better on energy. On heavy/bursty, the threshold controller is worse on SLA. This is a trade-off, not a clean win.

## 8. The workload set is synthetic and small

Six workload classes, ten seeds, 300 s each. The traces are Poisson around fixed or sinusoidal rates. They do not include diurnal cycles, long-tailed request costs, retries, partial failures, multi-service dependencies, or adversarial traffic.

**Consequence:** the results are a controlled comparison, not a workload benchmark. External validity is limited. See `docs/THREATS_TO_VALIDITY.md`.

## 9. The energy model is linear and uncalibrated

`P = P_idle + (P_max − P_idle)u` is a first-order approximation. It does not model frequency scaling, non-linear low-load behaviour, memory/disk/network power, cooling variation, or hardware heterogeneity. The nominal 150/500 W values are assumptions, not measurements of the validation host.

**Consequence:** absolute joules should not be quoted as predictions. Only relative patterns within the model are meaningful, and even those depend on the model.

## 10. The real-cluster validation cannot validate the simulation ranking

The Minikube validation exercises a real deployment, metrics-server, and native HPA. It does not use the same traces, does not run the five strategies, and measures node CPU rather than power. It shows that the deployment and HPA path work; it does not show that EAES saves energy in a cluster.

**Consequence:** do not merge the Phase 7 numbers into the paired results. They are separate evidence with different units of analysis and different limitations.

## 11. The experiment cannot detect small effects reliably

Ten seeds and a 14-test Holm family are underpowered for small differences. The steady EAES-vs-HPA energy effect has a bootstrap CI excluding zero but a Holm-adjusted p of 0.0718. That is a borderline result, not a confirmed effect.

**Consequence:** report effect sizes and CIs alongside p-values; do not turn “raw p < 0.05” into a claim after correction.

## 12. What would overturn the main conclusions

- A native HPA configured at the same target and with a longer run showing that the over-provisioning disappears.
- A node/power model in which idle power is per pod or nodes power down aggressively, changing the light-load and medium-load rankings.
- Traces with sustained loads above 30 req/s where static fails but a less conservative EAES matches the threshold controller’s energy.
- A repeat with more seeds that makes the steady difference clearly significant or clearly null.
- A real power measurement showing that the linear CPU-to-power mapping is badly wrong.

These are stated so the conclusions can be tested, not defended.

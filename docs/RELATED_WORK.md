# Related Work and Positioning

## 1. Primary reference

The project began from a student application that cited:

> Hongjian Li, Wei Rao, Baojian Hu, Yu Tian, Jie Shen. “Energy-aware elastic scaling algorithm for microservices in Kubernetes clouds.” *Journal of Network and Computer Applications*, 242:104218, October 2025. DOI: [10.1016/j.jnca.2025.104218](https://doi.org/10.1016/j.jnca.2025.104218).

This bibliographic record was verified through Crossref. The full text was **not available** through the institutional access used for this project; the Elsevier article was paywalled. Therefore:

- the paper’s exact algorithm, parameters, datasets, and reported numbers were not inspected;
- this repository does **not** reproduce Li et al.;
- the project does **not** claim the paper’s reported energy savings;
- EAES here is an independent, EAES-inspired controller, not the authors’ implementation.

The original app contained a claim of “15.34% compared to default Kubernetes HPA.” The audit found no reproducible evidence for that number, and it is not used. See `AUDIT.md`.

## 2. Kubernetes HPA

The Kubernetes Horizontal Pod Autoscaler is documented by the Kubernetes project. The parts relevant here are:

- the replica-ratio formula based on current and target metric values;
- a tolerance band to avoid thrashing;
- scale-up and scale-down stabilization;
- behaviour when metrics are unavailable.

Kubernetes documentation: <https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/>.

This project separates three things that are often conflated:

1. **Native Kubernetes HPA** — exercised only in the separate Minikube validation (`docs/KUBERNETES_VALIDATION.md`).
2. **`hpa_formula`** — a simulated implementation of the documented replica formula plus tolerance and stabilization, used as a baseline in the paired experiment.
3. **`cpu_threshold`** — the original project’s 80/30 threshold rule, preserved as a legacy threshold baseline. It is not HPA.

This separation is a contribution in itself: the original project used “HPA” for a toy 65/35 rule and made an unsupported savings claim.

## 3. Autoscaling research families

Without attributing specific methods to specific papers, the relevant literature generally contains these families:

- **Reactive threshold controllers**: scale when CPU/queue/latency crosses a threshold. Simple, widely deployed, prone to lag and oscillation.
- **Utilisation-target controllers**: compute a desired replica count from a target metric (the HPA-style approach).
- **Predictive controllers**: forecast demand or queue growth and pre-scale before the SLA is breached.
- **Optimisation/control-theoretic controllers**: minimise a cost subject to constraints, sometimes using queuing models or MPC.
- **Learning-based controllers**: learn a policy from workload traces, often requiring substantial training data and a stable environment.

This project implements one threshold controller, one utilisation-target formula, one SLA-first margin controller, and one forecasting ablation. It does not attempt a survey or a state-of-the-art comparison.

## 4. What is different here

The contribution is methodological and empirical, not a new algorithm:

- explicit separation of simulation, HPA formula, threshold rule, and native HPA;
- a node-level energy model with idle power, PUE, pod attribution, and conservation checks;
- six workloads and ten paired seeds with raw per-tick logs;
- a frozen analysis plan, bootstrap CIs, Wilcoxon/Holm, Friedman/Nemenyi, effect sizes, and sensitivity;
- a diagnostic that looks for denominator artefacts, drop-rate confounds, replica-hours, startup delay, and rule activity;
- negative results: EAES is worse than static at moderate load, has startup-delay SLA violations on variable/bursty load, and forecasting helps only the smooth sinusoid;
- a separate real Minikube/HPA validation that is not merged with the simulation.

## 5. What is not claimed as novel

- The idea of energy-aware autoscaling.
- The HPA formula.
- The Holt/EWMA forecasters.
- The Wilcoxon, Holm, Friedman, Nemenyi, bootstrap, or Cliff’s delta methods.
- The Flask app or Kubernetes manifests as research contributions.

The project’s value is in making the claims testable and in reporting what failed.

## 6. Why the paper could not be reproduced

- Paywall: the full text was not accessible.
- No public artifact was identified from the metadata alone.
- The original app did not contain the paper’s algorithm, only a threshold controller with “energy-aware” labels.
- Reproducing an unavailable method from a title would be fabrication. The project therefore implements an independent EAES-inspired controller and says so.

If the full text becomes available, the correct next step is to extract the authors’ algorithm and parameters, implement it separately, and compare it against the controllers here. That would be a new study, not a relabelling of this one.

## 7. Citation hygiene

- The reference is cited for motivation and positioning only.
- No result in this repository is attributed to Li et al.
- The DOI was verified; the full text was not.
- The original “15.34%” claim is removed/quarantined as unverified.
- The dashboard and reports use “EAES-inspired,” not “EAES reproduction.”

## 8. Selected background references

For implementation details, the project relies on primary documentation rather than secondary summaries:

- Kubernetes HPA documentation (linked above).
- Python `random`, `statistics`, and `math` standard-library documentation for the simulation and tests.
- Chart.js documentation for the dashboard chart layer.

No additional research citations are invented to pad the related-work section. That is deliberate: unverified citations are worse than a short, honest list.

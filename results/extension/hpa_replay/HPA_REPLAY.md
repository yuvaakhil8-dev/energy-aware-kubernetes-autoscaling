# Native-HPA replay (extension)

Recorded native-HPA pod CPU and replica samples from the Minikube validation were replayed through the offline `hpa_formula` strategy. No metric series or replica trajectory was invented.

- Recorded files: hpa_rep1.json, hpa_rep2.json, hpa_rep3.json
- Comparable sample transitions: **30**
- Predicted desired replicas agree with the next recorded spec: **100.00%**
- Predicted replica changes: **0**; observed changes between samples: **0**

## What can and cannot be compared

The native HPA had already scaled from one to four replicas before the sampler's first observation. The scale-up latency of that transition is therefore missing, and this replay does not claim to validate it. The replay compares steady-state desired counts, not the full controller loop. The samples are about 5.7 s apart while the simulation uses 5 s; the formula is evaluated on the recorded timestamps.

## Mismatches

No mismatch occurred in the recorded sample window.

## Interpretation

High agreement here is weak evidence: the recorded window is short, load is steady, and the native HPA is already at a stable count. It does not establish that the simulated formula matches native HPA under bursts or cold starts. Those observations are missing.


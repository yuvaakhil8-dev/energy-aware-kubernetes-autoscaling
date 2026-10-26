# Reversal Explanation

This note explains why the old prototype reported very different energy values
(for example, heavy load: static `7.25`, HPA `1.45`, EAES `48.11` J/request) and
why the rebuilt experiment reports a different ordering (heavy: EAES `18.58` vs
HPA formula `21.34` J per served request). It is a methods/provenance note, not a
new experiment.

## 1. The old numbers were not on a common denominator

The original 27-row dataset (`data/experiment_results_v2.json`, SHA-256
`6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E`) has nine
deterministic cells copied three times. It stores only `avg_energy_per_request`;
it does **not** store offered requests, served requests, per-tick energy, or raw
samples. The three modes therefore cannot be reconstructed from a common
denominator in that file.

The old implementation shows three different accounting paths:

- **Static/HPA-style metrics** used
  `estimate_energy_per_request(cpu, requests_in_interval)` where the denominator
  was derived from a fixed request rate and a 15 s interval.
- **HPA mode** recorded the same per-interval formula while replica count
  changed, so its denominator was a rate-derived request count, not the requests
  the run actually served.
- **EAES mode** called `get_energy_per_request_estimate()`, which divided
  `P * 15 s` by `max(1, self.successful_count)`. `successful_count` was a
  **cumulative** counter, so the per-request value fell every tick. The reported
  value was the average of those decreasing values.

At heavy CPU 85%, the old power curve (`30 W` idle, `80 W` max) gives:

```text
P = 30 + (80 - 30) * 0.85 = 72.5 W
E_interval = 72.5 W * 15 s = 1087.5 J
```

With five successes per tick and a cumulative counter over 15 ticks, the EAES
series is:

```text
1087.5 / 5, 1087.5 / 10, ..., 1087.5 / 75
average = 48.1143 J/request
```

That exactly reproduces the recorded `48.1143`. The HPA value `1.45` is
`1087.5 / 750`, i.e. a 50 req/s x 15 s denominator. The static value `7.25` used
another fixed rate-derived denominator. The audit therefore correctly marked the
three numbers as **not comparable**.

The old zero-request case was also invalid: `max(1, count)` produced an
artificial `450 J/request` at zero requests instead of a null/undefined value.

## 2. The old "HPA" label was wrong

The original `hpa` mode used a 65%/35% CPU threshold with a simplified
replica-count loop. It was not `autoscaling/v2`, not a Kubernetes HPA object, and
not the HPA replica formula. The rebuilt project preserves that rule under the
honest name `cpu_threshold`, implements a separate simulated `hpa_formula`, and
uses native Kubernetes HPA only in the cluster validation.

This matters for the reversal: some of the old "HPA is far more energy-efficient"
claim was an artefact of a threshold rule plus a denominator, not a comparison to
Kubernetes HPA.

## 3. What the rebuilt experiment does instead

The rebuilt `eaes/engine.py` computes energy and outcomes on the same 5 s tick:

1. offer requests from the trace;
2. serve what ready capacity and the bounded queue allow;
3. drop the rest;
4. model node/pod energy for that tick from the actual active nodes and CPU;
5. record offered, served, dropped, ready replicas, pending replicas, backlog,
   energy, and the controller decision in one JSONL row.

The run-level metric is then:

```text
energy_per_served  = sum(tick_energy) / sum(tick_served)
energy_per_offered = sum(tick_energy) / sum(tick_offered)
```

The numerator and denominator cover the **same measured window** (30-300 s).
Served and offered denominators are always reported together, and a zero-served
run yields null, not an artificial number.

In the confirmatory run, heavy load is:

| Strategy | E/served J | E/offered J | Drop | SLA | Replica-h |
|---|---:|---:|---:|---:|---:|
| static | 16.50 | 9.93 | 0.3979 | 1.0000 | 0.2250 |
| cpu_threshold | 17.39 | 17.72 | 0.0105 | 0.3202 | 0.5062 |
| hpa_formula | 21.34 | 21.34 | 0.0000 | 0.0000 | 0.7500 |
| eaes | 18.58 | 18.58 | 0.0000 | 0.0000 | 0.6101 |
| forecasting_eaes | 18.65 | 18.65 | 0.0000 | 0.0000 | 0.6126 |

EAES is lower than the HPA formula because both serve all heavy requests, but the
HPA formula provisions 0.75 replica-hours versus 0.6101 for EAES (and more than
0.225 for static). The HPA formula's 50% target and 300 s scale-down
stabilization keep extra replicas active. The reversal is therefore not "EAES
suddenly became more efficient"; the denominator is now coherent and the HPA
baseline is a different, explicitly simulated controller.

Static is lower still per served request, but it drops 39.79% of heavy traffic
and violates the SLA on every run. Its `9.93 J/offered` is shown precisely so
this is not mistaken for an efficiency win.

## 4. What did not reverse

- The old dataset remains non-inferential: nine cells copied three times.
- The old "15.34% reduction vs default Kubernetes HPA" claim is not reused.
  It was not backed by a native HPA comparison and is not reproduced.
- The old 65/35 rule remains a threshold baseline, not HPA.
- No physical power measurement exists in either version.

## 5. Why the confirmatory result is still cautious

The rebuilt result is directionally consistent but not Holm-significant in the
10-seed confirmatory analysis. For heavy load, the median paired EAES-minus-HPA
difference is `-2.8408 J` with 95% CI `[-3.5907, -2.1220]`, Cliff's delta
`-1.00`, and Holm p `0.0882`. The CI excludes zero, but the pre-specified
multiplicity-adjusted test does not cross 0.05. The 30-seed extension is
exploratory and does cross 0.05 for heavy, but it cannot change the confirmatory
claim. This is why `RESULTS.md` reports the direction and uncertainty rather
than an unqualified win.

## 6. Where the old and new numbers live

- Old dataset: `data/experiment_results_v2.json` and `data/experiment_results.json`
  (protected hashes in `README.md` and verified by
  `analysis/verify_dataset_hashes.py`).
- Old defects: `AUDIT.md`.
- Old provenance: `docs/DATA_PROVENANCE.md`.
- New confirmatory table: `results/tables/headline.csv`.
- New paired tests: `results/tables/paired_headline.csv`.
- New authoritative report: `results/RESULTS.md`.
- New extension evidence: `results/extension/`.

The old numbers are retained only as an audit trail. They are not used in the
rebuilt inference.

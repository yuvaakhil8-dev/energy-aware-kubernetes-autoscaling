# Consolidated Limitations

The authoritative current list is in [`../LIMITATIONS.md`](../LIMITATIONS.md).
This file is retained as a docs-level entry point and adds only the
project-history corrections that older notes got wrong.

## Current corrections

1. **Chart.js is vendored locally** at `static/vendor/chart.umd.min.js`; the
   dashboard no longer depends on a CDN.
2. **Raw confirmatory JSONL logs are included in the Docker image** because the
   time-series and controller-trace APIs read them. Cluster per-request logs are
   still excluded.
3. **The confirmatory result is not Holm-significant** for the EAES-vs-HPA
   energy comparison. The 30-seed extension is exploratory and does not change
   that.
4. **The native HPA scale-up is unobserved.** The first recorded sample already
   shows four replicas.
5. **No physical energy measurement exists.** All energy is modelled.
6. **The cluster validation is a smoke validation**, not a five-strategy
   comparison and not a production test.

## See also

- [`../LIMITATIONS.md`](../LIMITATIONS.md) - full current list
- `THREATS_TO_VALIDITY.md` - detailed threats
- `FAILURE_ANALYSIS.md` - failure analysis
- `ENERGY_MODEL.md` - power-model caveats
- `KUBERNETES_VALIDATION.md` - cluster scope and replay limits
- `REVERSAL_EXPLANATION.md` - why old energy numbers changed

# Energy Model

**All energy in this project is modelled, not measured.** No power meter, IPMI/BMC sensor, or Kepler deployment was available. The model is an output metric; it does not influence any scaling decision.

## 1. Node power curve

For each active node and each tick:

```text
P_node(u) = P_idle + (P_max - P_idle) · u            [W]
E_node    = P_node(u) · Δt · PUE + startup_energy    [J]
u         = node_served / full_node_capacity         [0, 1]
```

where `full_node_capacity = pods_per_node × pod_capacity_rps × Δt`.

The linear curve is a standard first-order approximation. It is not derived from measurements of the host used for validation.

## 2. Nominal assumptions

| Parameter | Value | Unit |
|---|---|---|
| `P_idle` | 150 | W |
| `P_max` | 500 | W |
| `PUE` | 1.2 | ratio |
| Node startup energy | 0 | J |
| Tick | 5 | s |

`P_max > P_idle >= 0`, `PUE >= 1`, and utilisation in `[0, 1]` are enforced by `EnergyModel`. Invalid values raise `EnergyModelError` rather than being silently clipped.

## 3. Scenarios and sensitivity

| Scenario | `P_idle` (W) | `P_max` (W) | Default PUE |
|---|---|---|---|
| low | 80 | 300 | 1.2 |
| nominal | 150 | 500 | 1.2 |
| high | 250 | 800 | 1.2 |
| PUE sweep | nominal | nominal | 1.0, 1.2, 1.4, 1.6 |

The sensitivity analysis recomputes energy from the same raw per-tick active-node and utilisation data under each scenario/PUE. Because energy never feeds back into the controller, changing the power assumptions cannot change the replica trajectory. The recomputation is therefore a valid post-hoc sensitivity analysis, not a new experiment.

At nominal, the engine’s energy and the raw-log recomputation agree to a maximum relative error of `8.061e-16`; node energy and pod attribution agree to `1.819e-12 J` in the diagnostic.

## 4. Node utilisation and placement

Active nodes are `ceil(ready_replicas / pods_per_node)`. Pods are packed in order. Node utilisation is computed against a full node's capacity, so a node with one pod on it pays idle power plus only a small dynamic component.

This matters for the comparison: a strategy that concentrates pods on fewer nodes pays less total idle power than one that spreads the same pods across more nodes. The model therefore rewards consolidation implicitly, but it does so identically for every strategy.

## 5. Pod attribution

For a node with `n` occupied pods:

```text
dynamic_energy_i = dynamic_node_energy × (pod_served_i / total_served)
idle_energy_i    = idle_node_energy / n
startup_energy_i = startup_node_energy / n
pod_energy_i     = dynamic_energy_i + idle_energy_i + startup_energy_i
```

With equal requests per pod, this reduces to an equal split. There is no CPU-frequency or per-pod power model. Attribution is a bookkeeping device to test conservation; it is not a claim that a pod has an independently measurable power draw.

The conservation invariant is:

```text
|node_energy - Σ pod_energy| ≈ 0
```

Raw logs retain `node_energy_j`, `pod_energy_sum_j`, and `conservation_error_j` per tick.

## 6. Derived metrics

```text
energy_per_served_request_j  = measurement_energy_j / measurement_served
energy_per_offered_request_j = measurement_energy_j / measurement_offered
```

When served = 0, the per-served value is `None`/null. It is not set to an arbitrary large number. This directly fixes an old defect where zero requests produced a 450 J/request artefact.

The measurement window excludes the first 30 s. Warm-up energy is retained in `total_energy_j` but not in the primary `measurement_energy_j`.

## 7. Why the old energy model was not defensible

The audit (`AUDIT.md`) found that the original code:

- had no node boundary;
- did not multiply by replicas;
- charged idle power without a defined unit;
- divided by cumulative successes rather than the measurement-window denominator;
- produced a finite energy-per-request value at zero requests;
- reused energy as a scaling input in the controller.

Those defects are not inherited by `eaes.energy`. The new model is used only by the simulation engine.

## 8. Interpretation limits

- The absolute joules are not a prediction of any specific server.
- The linear power curve ignores non-linearity at low utilisation and frequency scaling.
- PUE is applied uniformly; no cooling or facility variation is modelled.
- Node CPU utilisation is a proxy for power, not a measurement.
- The real-cluster validation’s “modelled J/req” column applies this same curve to `kubectl top node` CPU percentages. It is not comparable in absolute terms to the simulation because the hardware and workload differ.
- Energy per request can be reduced by serving fewer requests. The diagnostic therefore reports energy per **offered** request and drop/SLA rates alongside it.

## 9. Reproduction

```powershell
python -m analysis.analyze
python -m analysis.diagnose
```

Outputs:

- `results/tables/sensitivity.csv`
- `results/tables/descriptive.csv`
- `results/diagnostic.json`
- `results/EAES_DIAGNOSTIC.md`
- raw per-tick JSONL in `results/runs/<run_id>/`

# Scaling Strategies

All five strategies receive the same state, trace, cluster, starting replica count (3), and measurement window. They differ only in their decision rule. None of them is the Kubernetes HPA controller.

## 1. Static

```text
replicas = 3 for every tick
```

No feedback. This is a lower-bound provisioning baseline, not an energy-aware method. Its apparent energy efficiency under heavy or bursty load is usually a consequence of dropped traffic.

## 2. CPU threshold (`cpu_threshold`)

The legacy rule from the original project, retained for continuity:

```text
if cpu > 0.80 and replicas < 10 and up-cooldown elapsed:
    replicas += 1
elif cpu < (0.30 - 0.05) and replicas > 1:
    if warm-up: hold
    elif down-cooldown elapsed: replicas -= 1
else:
    hold
```

- Scale-up threshold: 80%.
- Scale-down threshold: 30%.
- Hysteresis: 5 percentage points, so the effective scale-down boundary is 25%.
- Up cooldown: 30 s.
- Down cooldown: 60 s.
- Scale-down is suppressed during warm-up.

This is **not** Kubernetes HPA and must not be labelled as such. It is a fixed-threshold reactive controller.

## 3. HPA formula (`hpa_formula`)

A simulation of the documented HPA replica formula:

```text
ratio    = current_cpu / target_cpu
desired  = ceil(current_replicas × ratio)
```

with:

- target CPU = 50%;
- ±10% tolerance band;
- minimum 1, maximum 10 replicas;
- 300 s scale-down stabilization;
- at least +1 replica when the formula recommends scale-up;
- at most −1 replica when it recommends scale-down;
- scale-up by the formula amount inside the tolerance logic;
- if the metric is unavailable, add one replica until the maximum.

The scale-down path waits until the ratio has been below `1 − tolerance` continuously for 300 s. In a 300 s simulated run, that means the strategy often cannot scale down after a late burst. This is a property of the simulated formula and its configured stabilization, not a claim about every Kubernetes HPA configuration.

## 4. EAES (`eaes`)

EAES is an EAES-inspired, SLA-first, lexicographic controller. It has no hidden scalar weights.

Let:

```text
projected = max(1, ready + pending)
demand    = previous arrival rate, or backlog / Δt if the rate is zero and backlog exists
predicted = demand / (projected × pod_capacity_rps)
margin    = utilization_ceiling − predicted
target    = utilization_ceiling − margin_threshold
```

with `utilization_ceiling = 0.8` and `margin_threshold = 0.1`, so `target = 0.7`.

Decision order:

1. **Scale up if `margin < 0.1`:**
   ```text
   required = ceil(demand / (pod_capacity_rps × target))
   new      = min(10, max(current + 1, required))
   new      = min(new, current + max_scale_step)
   ```
   If `new <= current`, hold at the maximum. This is the only scale-up rule; there is no energy term.

2. **Otherwise, consider scale-down only if all hold:**
   - not warm-up;
   - current > minimum;
   - backlog = 0;
   - cooldown (30 s) elapsed;
   - minimum dwell (30 s) elapsed;
   - the configuration has been SLA-safe for the 60 s stabilization window.

3. **Scale down by one only if the smaller configuration is also safe:**
   ```text
   predicted_smaller = demand / ((current − 1) × pod_capacity_rps)
   predicted_smaller <= target AND cpu_util <= ceiling
   ```
   Otherwise hold with reason `scale_down_would_breach_sla`.

EAES therefore does not trade SLA for energy. It scales to the smallest count that restores the margin, then reduces only when the smaller configuration remains safe.

## 5. Forecasting EAES (`forecasting_eaes`)

Identical to EAES except that `demand` is replaced by:

```text
demand = max(current_arrival_rate, forecast)
```

The forecast is a Holt linear-trend model with `α = 0.5`, `β = 0.3`, over a horizon of:

```text
ceil(startup_delay_s / control_interval_s) = ceil(10 / 5) = 2 ticks
```

Before enough observations exist, the forecast falls back to the current rate. The forecaster is updated with the observed arrival rate at the end of each tick.

## 6. What is shared and what is not

Shared:

- backend capacity, queue, drops, latency, and energy model;
- initial replicas = 3;
- 10 s startup delay;
- 4 pods per node and 10 req/s per pod;
- 1–10 replica bounds;
- identical trace per workload and seed;
- identical warm-up and measurement windows.

Not shared:

- threshold values, target utilisation, tolerance, cooldowns, stabilization, dwell, and forecast;
- the decision rule itself.

The comparison is therefore between controllers, not between different traces or different energy models.

## 7. Strategy naming guardrails

| Wrong label | Correct label |
|---|---|
| “HPA” for the 80/30 rule | `cpu_threshold` |
| “HPA” for the formula simulation | `hpa_formula` (simulated formula) |
| “Kubernetes HPA” for any simulation result | Native HPA only in Phase 7 cluster validation |
| “EAES reproduction of Li et al.” | EAES-inspired controller; full paper unavailable |
| “Measured energy” | Modelled energy from CPU utilisation |

These distinctions are enforced in code, reports, and the dashboard.

## 8. Source

- `eaes/strategies.py`
- `configs/strategies.yaml`
- `tests/test_strategies.py`

# Simulation Model

The confirmatory experiment uses `eaes.backend.SimulatedCluster`. It is a discrete-time, fixed-capacity model designed to expose the cost of startup delay and queue overflow, not to emulate Kubernetes internals faithfully.

## 1. Configuration

| Parameter | Value | Meaning |
|---|---|---|
| `pods_per_node` | 4 | Pods packed per active node |
| `pod_capacity_rps` | 10.0 | Maximum served requests per second per ready pod |
| `control_interval_s` | 5 | Tick length |
| `startup_delay_s` | 10 | Delay before a newly requested replica becomes ready |
| `initial_replicas` | 3 | Same starting point for all strategies |
| `min_replicas` | 1 | Lower bound |
| `max_replicas` | 10 | Upper bound |
| `base_latency_ms` | 20.0 | Service latency with no queue |
| `max_queue_factor` | 2.0 | Backlog cap as a multiple of per-tick capacity |
| `max_nodes` | 10 | Declared for extension; not binding at 10 replicas / 4 pods per node |

At 10 replicas the model uses at most three active nodes. The `max_nodes` field is therefore not an active constraint in the current runs; this is stated rather than implying a multi-node placement algorithm.

## 2. State

Per run the backend tracks:

- `ready`: replicas currently able to serve;
- `desired`: last replica target requested by the controller;
- `pending`: list of `(ready_at, count)` startup batches;
- `backlog`: queued requests carried between ticks;
- cumulative offered, served, and dropped counts;
- last tick's served, dropped, CPU utilisation, and latency.

`ready` and `desired` can differ because of pending startups. The controller sees both.

## 3. Tick sequence

At tick `t` with arrivals `A(t)`:

1. `get_metrics(t)` activates any pending replicas whose `ready_at <= t` and returns ready, desired, pending, active nodes, capacity, backlog, and the previous tick's CPU utilisation.
2. The strategy sees a state containing those values, the previous arrival rate, `pod_capacity_rps`, `startup_delay_s`, `dt_s`, and the warm-up flag.
3. `set_replicas(n)` either records a pending batch (scale-up), removes pending first and then ready replicas (scale-down), or holds.
4. `apply_arrivals(t, A)` computes capacity and serves requests.
5. `compute_energy(t, served)` computes node energy and pod attribution.
6. The engine writes one JSONL row and calls `strategy.observe(arrivals / dt)`.

## 4. Capacity and service

```text
capacity_rps       = ready × pod_capacity_rps
capacity_requests  = capacity_rps × Δt
served             = min(backlog_before + arrivals, capacity_requests)
backlog_after      = backlog_before + arrivals - served
max_queue          = max_queue_factor × capacity_requests
dropped            = max(0, backlog_after - max_queue)   [ceil to integer]
backlog            = min(backlog_after, max_queue)
```

If `capacity_requests = 0`, all arrivals and backlog are dropped.

Only **ready** replicas contribute capacity. This is the central mechanism that makes reactive scaling during a burst costly: a decision made now cannot serve traffic until the 10 s startup delay has elapsed.

## 5. Queueing latency

The model is analytic, not packet-level:

```text
wait_s       = backlog_before / capacity_rps
avg_latency  = base_latency_ms + wait_s × 1000
p95_latency  = base_latency_ms + 3 × wait_s × 1000
cpu_util     = served / capacity_requests     [in [0, 1]]
```

The average wait uses the backlog at the start of the tick. Served requests are a mixture of queued and new work, so the reported average is a conservative approximation. The p95 is an analytic estimate, not an empirical percentile over individual requests.

The **SLA violation** rule counts:

- every dropped request; plus
- every served request in a tick whose average latency exceeds 500 ms.

This is deliberately conservative: it charges the entire served batch when the tick average exceeds the threshold. It is consistent across strategies, so it does not by itself favour one strategy.

## 6. Active nodes and CPU

```text
active_nodes = ceil(ready / pods_per_node)
```

Pods are packed onto nodes in order. If `ready = 5`, node 1 has four pods and node 2 has one. Node utilisation is computed against a **full** node capacity:

```text
full_node_capacity = pods_per_node × pod_capacity_rps × Δt
node_served        = served × node_pods / ready
node_util          = node_served / full_node_capacity
```

A node with one pod therefore does not receive a full node's dynamic power; it pays the idle component and only a share of the dynamic component. This avoids the old defect of charging full power per pod.

The controller's `cpu_util` is the cluster-level served/capacity ratio, not the per-node utilisation used for energy. They are related but not identical. This is intentional: the controller receives a service utilisation signal, while energy is computed at the node boundary.

## 7. Workload traces

Traces are generated deterministically per workload and seed and stored in `traces/`. The trace index records arrival counts and SHA-256 hashes. Each tick's arrivals are integers; `arrival_rate_rps` in the raw log is the **previous** tick's rate, matching what a reactive controller could observe.

Workload profiles are documented in `docs/EXPERIMENT_PROTOCOL.md`. They are synthetic, not captured production traffic.

## 8. What the model deliberately omits

- Container image pull time, scheduler delays, and node autoscaling.
- Network latency, retries, and per-request latency distributions.
- Heterogeneous nodes and pod anti-affinity.
- Real Kubernetes HPA controller timing, metrics-server scrape intervals, and stabilization algorithms.
- Physical power, CPU frequency scaling, and thermal effects.
- Disk/network energy.

These omissions are threats to external validity, not bugs to hide. The separate Minikube validation exercises a real cluster but is not the confirmatory experiment.

## 9. Invariants checked by tests

- Scale-up creates pending replicas that become ready only after the startup delay.
- Capacity depends on ready, not desired, replicas.
- Backlog is bounded and drops occur only on overflow.
- A zero-capacity tick drops all offered work.
- Energy attribution sums to node energy within floating tolerance.
- The same trace is used for every strategy at a given workload and seed.
- Raw tick counts and measurement-window tick counts are consistent with 5 s ticks and a 30 s warm-up.

See `docs/TESTING.md` for the test inventory.

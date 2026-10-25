# Cluster Validation (real Minikube, separate from simulation)

Git commit: `cce700b639cb5059a9a01842358513f03ef81267`  
Cluster: `energy-aware-dev` / `energy-aware-app`  
Target load: 80.0 req/s for 60 s per repetition; 3 repetitions per mode.  
Execution mode: **kubernetes_validation**  

> Replica counts and request outcomes are real Kubernetes observations. Energy is **modelled** by applying the documented node power curve to measured node CPU; it is not a physical power measurement.

## Results

| Mode | Rep | Served | Offered | Drop | Throughput | p50 ms | p95 ms | p99 ms | Avg repl | Max repl | Avg node CPU | Modelled J/req |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| static | 1 | 4871 | 4871 | 0.0000 | 81.20 | 12.8 | 29.3 | 33.2 | 3 | 3 | 3.0 | 2.25 |
| static | 2 | 4817 | 4817 | 0.0000 | 80.24 | 14.3 | 30.7 | 34.6 | 3 | 3 | 3.5 | 2.29 |
| static | 3 | 4821 | 4821 | 0.0000 | 80.33 | 14.7 | 30.7 | 34.6 | 3 | 3 | 4.0 | 2.32 |
| hpa | 1 | 4832 | 4832 | 0.0000 | 80.51 | 13.4 | 30.4 | 34.6 | 4 | 4 | 3.2 | 2.28 |
| hpa | 2 | 4890 | 4890 | 0.0000 | 81.48 | 14.4 | 32.7 | 104.8 | 4 | 4 | 3.8 | 2.28 |
| hpa | 3 | 4731 | 4731 | 0.0000 | 78.85 | 14.7 | 31.9 | 73.2 | 4 | 4 | 3.0 | 2.30 |

## Interpretation

- Native HPA scaling and static-replica scaling were both exercised against the same Flask service.
- These values validate that the cluster, metrics-server, service, and HPA are operational.
- They do not validate the simulation's energy rankings; the simulation has 10 paired seeds and a fixed workload trace.
- No claim of measured energy is made.

## Exact environment

```
NAME       STATUS   ROLES           AGE   VERSION   INTERNAL-IP    EXTERNAL-IP   OS-IMAGE                         KERNEL-VERSION                              CONTAINER-RUNTIME
minikube   Ready    control-plane   19m   v1.37.0   192.168.49.2   <none>        Debian GNU/Linux 12 (bookworm)   6.18.54.1-microsoft-standard-WSL2 (amd64)   containerd://2.3.4
```

## Limitations

- Single-node Minikube on Docker Desktop; not a multi-node production cluster.
- Flask development server is used inside the container, not a production WSGI server.
- Node CPU includes cluster/system overhead and is not per-pod power.
- The load generator is external HTTP traffic, not the simulated arrivals.


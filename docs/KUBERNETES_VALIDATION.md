# Kubernetes Validation

**Type:** real single-node Minikube exercise, separate from the confirmatory
simulation  
**Runner:** `experiments/run_cluster_validation.py`  
**Artifacts:** `results/cluster_validation/`  
**Replay:** `analysis/hpa_replay.py`  
**Environment record:** `docs/CLUSTER_ENVIRONMENT.md`  
**Image/dashboard smoke record:** `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md`

## 1. What this validation does and does not do

It does:

- deploy the Flask service to a real Kubernetes cluster;
- verify the Service, Deployment, metrics-server, and a native
  `autoscaling/v2` HPA;
- generate real HTTP load at 80 req/s for 60 s per repetition;
- record real replica counts, request outcomes, latency, and node CPU;
- apply the documented node power curve to measured node CPU to produce a
  **modelled** J/request.

It does not:

- run the five strategies from the simulation;
- use the simulation traces or seeds;
- measure wall power;
- validate the simulation's energy ranking;
- compare EAES, threshold, HPA formula, and static under the same real workload;
- represent a production cluster.

## 2. Environment

| Item | Value |
|---|---|
| Host | Windows, Docker Desktop Linux engine |
| Minikube | v1.39.0 |
| Kubernetes | v1.37.0 |
| kubectl | v1.36.1 |
| Driver | Docker |
| Node | one node, `minikube`, Ready, control-plane |
| Kernel | `6.18.54.1-microsoft-standard-WSL2` |
| Container runtime | `containerd://2.3.4` |
| metrics-server | enabled; `kubectl top` worked after the first metrics window |
| Namespace / deployment | `energy-aware-dev` / `energy-aware-app` |
| Service | `energy-aware-service`, forwarded to `127.0.0.1:5001` |
| Native HPA | `autoscaling/v2`, CPU target 50%, min 1, max 10 |
| Load | 80 req/s for 60 s, 3 repetitions per mode |

At final verification time (2026-10-26), Docker Desktop was not running and the
kubectl context was unset:

```text
docker: failed to connect to dockerDesktopLinuxEngine (pipe not found)
minikube status: docker container inspect failed
kubectl config current-context: current-context is not set
```

No additional cluster repetitions were run. The recorded validation below is
retained as evidence with that limitation explicit.

## 3. Commands

```powershell
minikube start --driver=docker --cpus=2 --memory=4096
minikube addons enable metrics-server
minikube image build -t flask-k8s-demo:latest .
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -n energy-aware-dev -f kubernetes/deployment.yaml -f kubernetes/service.yaml
kubectl rollout status deployment/energy-aware-app -n energy-aware-dev --timeout=180s
kubectl top nodes
kubectl top pods -n energy-aware-dev
kubectl apply -f kubernetes/hpa.yaml -n energy-aware-dev
kubectl port-forward -n energy-aware-dev svc/energy-aware-service 5001:5000
python -m experiments.run_cluster_validation --repetitions 3 --duration 60 --rate 80
```

Static mode was run with the HPA deleted and the Deployment fixed at three
replicas. HPA mode used the native controller.

## 4. Results (real observations, modelled energy)

`Served/Offered` are request counts; `Drop` is a fraction; latency is measured by
the load generator; `Avg node CPU` is from cluster metrics; `Modelled J/req` is
**not measured power**.

| Mode | Rep | Served | Offered | Drop | Throughput | p50 ms | p95 ms | p99 ms | Avg repl | Max repl | Avg node CPU | Modelled J/req |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| static | 1 | 4871 | 4871 | 0.0000 | 81.20 | 12.8 | 29.3 | 33.2 | 3 | 3 | 3.0% | 2.25 |
| static | 2 | 4817 | 4817 | 0.0000 | 80.24 | 14.3 | 30.7 | 34.6 | 3 | 3 | 3.5% | 2.29 |
| static | 3 | 4821 | 4821 | 0.0000 | 80.33 | 14.7 | 30.7 | 34.6 | 3 | 3 | 4.0% | 2.32 |
| hpa | 1 | 4832 | 4832 | 0.0000 | 80.51 | 13.4 | 30.4 | 34.6 | 4 | 4 | 3.2% | 2.28 |
| hpa | 2 | 4890 | 4890 | 0.0000 | 81.48 | 14.4 | 32.7 | 104.8 | 4 | 4 | 3.8% | 2.28 |
| hpa | 3 | 4731 | 4731 | 0.0000 | 78.85 | 14.7 | 31.9 | 73.2 | 4 | 4 | 3.0% | 2.30 |

### Observations

- The native HPA is reported as having scaled from one replica to four under the
  load. The recorded sampler starts **after** that transition: the first sample
  in every HPA run already shows four ready replicas. The scale-up latency is
  therefore unobserved.
- Static mode stayed at three replicas.
- Every repetition had zero client-side failed requests.
- p50 latency was 12.8-14.7 ms; p95 was 29.3-32.7 ms. Two HPA runs had p99
  outliers (104.8 ms and 73.2 ms), consistent with transient effects.
- Node CPU was low (3-4%), so modelled energy is dominated by the 150 W idle
  term. The ~2.3 J/request values are **not** evidence that the workload is
  intrinsically 2.3 J/request; they are an artefact of charging a mostly idle
  node to a light HTTP load.

## 5. Native-HPA recorded-sample replay

`analysis/hpa_replay.py` replays the recorded pod CPU and replica samples through
the offline `hpa_formula` strategy. It does not invent metrics or a replica
trajectory.

| Result | Value |
|---|---:|
| Recorded files | 3 (`hpa_rep1.json`, `hpa_rep2.json`, `hpa_rep3.json`) |
| Comparable transitions | 30 |
| Predicted desired replicas agree with next recorded spec | 100.00% |
| Predicted replica changes | 0 |
| Observed replica changes between samples | 0 |

This is **weak evidence**. The window is short, load is steady, the native HPA is
already at a stable count, and the initial 1->4 transition is missing. It does
not establish that the simulated formula matches native HPA under bursts, cold
starts, or scale-down. See `results/extension/hpa_replay/HPA_REPLAY.md`.

## 6. What the validation proves

- The container image builds and starts in the cluster.
- The Service and port-forward work.
- The Flask health endpoint and dashboard pages return HTTP 200.
- metrics-server serves metrics.
- The native HPA reads CPU utilisation and changes the Deployment replica count.
- A real HTTP client can sustain roughly 80 req/s for 60 s without failed
  requests.
- The image can be rebuilt with the research dashboard and still serve the new
  pages/APIs (verified separately in
  `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md`).

## 7. What it does not prove

- It does not show that the simulation's replica counts match reality.
- It does not show that EAES saves energy.
- It does not compare the five strategies under one real workload.
- It does not measure power.
- It does not exercise multi-node scheduling, failures, or node autoscaling.
- It does not use a production WSGI server; the container runs the Flask
  development server.
- It does not validate the native HPA's initial scale-up or scale-down behavior.

## 8. Reproducibility caveats

- The validation manifest records commit `cce700b` because that was the commit
  at the time of the 60 s validation runs.
- The image was later rebuilt from commit/content `603d1de` to include the
  research dashboard, and the three pages plus research APIs were smoke-tested in
  the same cluster. That smoke test is packaging evidence, not a re-run of the
  HPA comparison.
- The cluster and host versions are recorded, but Docker Desktop's VM and the
  Windows kernel are outside the repository's control.
- Port-forwarding is manual and can be interrupted; the runner requires a
  reachable service URL.
- Docker Desktop/Minikube were unavailable at final verification time, so the
  cluster run was not repeated.

## 9. Ethical reporting

The validation is reported as "real cluster, modelled energy." It is not merged
with the paired simulation. The `hpa_formula` simulation results are not
described as native-HPA results, and the native HPA's four-replica behavior is
not described as evidence for or against the simulated formula.

## 10. Artifact map

- `results/cluster_validation/CLUSTER_VALIDATION.md` - generated report.
- `results/cluster_validation/summary.csv` and `summary.json` - per-repetition
  aggregates.
- `results/cluster_validation/manifest.json` - versions, commit, duration, rate,
  environment.
- Per-request JSONL - raw load-generator outcomes (excluded from Docker).
- `results/extension/hpa_replay/` - replay table, mismatches, manifest, report.
- `docs/CLUSTER_ENVIRONMENT.md` - versions and commands.

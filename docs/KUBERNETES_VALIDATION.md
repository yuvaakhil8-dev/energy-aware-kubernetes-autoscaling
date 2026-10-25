# Kubernetes Validation

**Type:** real single-node Minikube exercise, separate from the confirmatory simulation  
**Runner:** `experiments/run_cluster_validation.py`  
**Artifacts:** `results/cluster_validation/`  
**Environment:** `docs/CLUSTER_ENVIRONMENT.md`  
**Image validation:** `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md`

## 1. What this validation does and does not do

It does:

- deploy the Flask service to a real Kubernetes cluster;
- verify the Service, Deployment, metrics-server, and a native `autoscaling/v2` HPA;
- generate real HTTP load at 80 req/s for 60 s per repetition;
- record real replica counts, request outcomes, latency, and node CPU;
- apply the documented node power curve to measured node CPU to produce a **modelled** J/req.

It does not:

- run the five strategies from the simulation;
- use the simulation traces or seeds;
- measure wall power;
- validate the simulation’s energy ranking;
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

The static mode was run with the HPA deleted and the deployment fixed at three replicas. The HPA mode used the native controller.

## 4. Results (real observations)

`Served/Offered` are request counts; `Drop` is a fraction; latency is measured by the load generator; `Avg node CPU` is from cluster metrics; `Modelled J/req` is **not measured power**.

| Mode | Rep | Served | Offered | Drop | Throughput | p50 ms | p95 ms | p99 ms | Avg repl | Max repl | Avg node CPU | Modelled J/req |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| static | 1 | 4871 | 4871 | 0.0000 | 81.20 | 12.8 | 29.3 | 33.2 | 3 | 3 | 3.0% | 2.25 |
| static | 2 | 4817 | 4817 | 0.0000 | 80.24 | 14.3 | 30.7 | 34.6 | 3 | 3 | 3.5% | 2.29 |
| static | 3 | 4821 | 4821 | 0.0000 | 80.33 | 14.7 | 30.7 | 34.6 | 3 | 3 | 4.0% | 2.32 |
| hpa | 1 | 4832 | 4832 | 0.0000 | 80.51 | 13.4 | 30.4 | 34.6 | 4 | 4 | 3.2% | 2.28 |
| hpa | 2 | 4890 | 4890 | 0.0000 | 81.48 | 14.4 | 32.7 | 104.8 | 4 | 4 | 3.8% | 2.28 |
| hpa | 3 | 4731 | 4731 | 0.0000 | 78.85 | 14.7 | 31.9 | 73.2 | 4 | 4 | 3.0% | 2.30 |

### Observations

- Native HPA scaled from 1 replica to 4 under the load and stayed at 4 for the measured window.
- Static mode stayed at 3 replicas.
- Every repetition had zero client-side failed requests.
- p50 latency was 12.8–14.7 ms; p95 was 29.3–32.7 ms. Two HPA runs had p99 outliers (104.8 ms and 73.2 ms), consistent with scaling/transient effects.
- Node CPU was low (3–4%), so the modelled energy is dominated by the 150 W idle term. The J/req values around 2.3 are therefore **not** evidence that the workload is intrinsically 2.3 J/request; they are an artefact of charging a mostly idle node to a light HTTP load.

## 5. What the validation proves

- The container image builds and starts in the cluster.
- The Service and port-forward work.
- The Flask health endpoint and dashboard pages return HTTP 200.
- metrics-server serves metrics.
- The native HPA reads CPU utilisation and changes the Deployment replica count.
- A real HTTP client can sustain roughly 80 req/s for 60 s without failed requests.
- The image can be rebuilt with the research dashboard and still serve the new pages/APIs (verified separately in `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md`).

## 6. What it does not prove

- It does not show that the simulation’s replica counts match reality.
- It does not show that EAES saves energy.
- It does not compare EAES, threshold, HPA formula, or static under the same real workload.
- It does not measure power.
- It does not exercise multi-node scheduling, failures, or autoscaling of nodes.
- It does not use a production WSGI server; the container runs the Flask development server.

## 7. Reproducibility caveats

- The validation manifest records commit `cce700b` because that was the commit at the time of the 60 s validation runs.
- The image was later rebuilt from commit/content `603d1de` to include the research dashboard, and the three pages plus research APIs were smoke-tested in the same cluster. That smoke test is packaging evidence, not a re-run of the HPA comparison.
- The cluster and host versions are recorded, but Docker Desktop’s VM and Windows kernel are outside the repository’s control.
- Port-forwarding is manual and can be interrupted; the runner requires a reachable service URL.

## 8. Ethical reporting

The validation is reported as “real cluster, modelled energy.” It is not merged with the paired simulation. The HPA formula baseline’s simulation results are not described as native-HPA results, and the native HPA’s 4-replica behavior is not described as evidence for or against the simulated formula.

## 9. Artifact map

- `results/cluster_validation/CLUSTER_VALIDATION.md` — generated report.
- `results/cluster_validation/summary.csv` and `summary.json` — per-repetition aggregates.
- `results/cluster_validation/manifest.json` — versions, commit, duration, rate, environment.
- Per-request JSONL — raw load-generator outcomes.
- `docs/CLUSTER_ENVIRONMENT.md` — versions and commands.
- `docs/DASHBOARD_AND_CONTAINER_VALIDATION.md` — final image build and endpoint smoke test.

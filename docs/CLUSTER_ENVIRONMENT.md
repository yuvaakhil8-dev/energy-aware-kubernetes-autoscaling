# Cluster Environment and Validation Record

**Date:** 2026-10-26
**Execution mode:** real single-node Minikube validation, separate from the paired simulation.

## Verified versions

| Component | Version / status |
|---|---|
| Docker Desktop Linux engine | 29.8.2, responding |
| Minikube | v1.39.0 |
| kubectl client | v1.36.1 |
| Kubernetes server | v1.37.0 |
| Driver | Docker, WSL2 kernel 6.18.54.1-microsoft-standard-WSL2 |
| Node | `minikube`, Ready, control-plane, one node |
| metrics-server | addon enabled; `kubectl top` served metrics |
| Application image | `docker.io/library/flask-k8s-demo:latest`, built inside Minikube |

## Exact commands used

```powershell
minikube start --driver=docker --cpus=2 --memory=4096
kubectl get nodes -o wide
minikube addons enable metrics-server
minikube image build -t flask-k8s-demo:latest .
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -n energy-aware-dev -f kubernetes/deployment.yaml -f kubernetes/service.yaml
kubectl rollout status deployment/energy-aware-app -n energy-aware-dev --timeout=180s
kubectl top nodes
kubectl top pods -n energy-aware-dev
kubectl apply -f kubernetes/hpa.yaml -n energy-aware-dev
python -m experiments.run_cluster_validation --repetitions 3 --duration 60 --rate 80
```

The validation used a local port-forward:

```powershell
kubectl port-forward -n energy-aware-dev svc/energy-aware-service 5001:5000
```

## What was observed

- Deployment rolled out successfully; pod became Ready; `/health` returned HTTP 200 through the forwarded service.
- metrics-server initially reported `no metrics to serve`; after the first metrics window, `kubectl top nodes` and `kubectl top pods` worked.
- Native Kubernetes HPA (`autoscaling/v2`, CPU target 50%, min 1, max 10) was applied. It scaled the deployment from 1 replica to 4 replicas under the validation load. A post-run reading showed `cpu: 108%/50%, replicas 4`.
- Static mode was run with the HPA deleted and the deployment fixed at 3 replicas.
- Three 60 s repetitions per mode at 80 req/s offered load completed with no client-side failed requests.
- Full measurements are in `results/cluster_validation/CLUSTER_VALIDATION.md`, `summary.csv`, `summary.json`, and per-request JSONL files.

## Integrity statements

- These are real cluster observations of replicas, request outcomes, and CPU metrics.
- Energy in the validation file is **modelled** from measured node CPU; it is not a power measurement.
- The validation is not a paired experiment and is not used to support the simulation's statistical rankings.
- The image used for the validation was built from the commit recorded in `results/cluster_validation/manifest.json`. Dashboard-only changes made later are tested locally; see `LIMITATIONS.md`.

## Limitations

- One Docker Desktop node, not a multi-node production cluster.
- The Flask development server is used in the container.
- Node CPU includes system overhead and is not per-pod power.
- The external load generator is not the simulated arrival trace.
- Native HPA has its own controller timing and is not the `hpa_formula` simulation baseline.

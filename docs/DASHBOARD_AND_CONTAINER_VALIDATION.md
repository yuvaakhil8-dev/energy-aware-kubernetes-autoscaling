# Dashboard and Container Validation Record

**Date:** 2026-10-26  
**App/results commit content:** `431810f` plus the final `requirements.txt` pin; documentation-only changes do not enter the image  
**Image:** `docker.io/library/flask-k8s-demo:latest`  
**Image manifest digest:** `sha256:f2c95c3f24841933da309396c60e15d56222373650cd8d340683ba4f4fda238e`  
**Embedded run:** `v3_paired_20261025T220942Z`

## What was built

The container includes:

- the Flask app and the preserved original controller;
- the `eaes` package;
- `configs/` YAML files;
- byte-identical local copies of the original datasets under `data/`;
- generated dashboard artifacts under `results/`, including the confirmatory run and cluster validation;
- the three research templates and the research CSS/JS assets.

Pinned runtime packages in the final image:

```text
Flask==3.1.3
PyYAML==6.0.3
```

`.dockerignore` excludes tests, experiments, analysis code, archives, docs, raw tick JSONL, and runtime logs.

## Exact commands

```powershell
minikube image build -t flask-k8s-demo:latest .
kubectl -n energy-aware-dev rollout restart deployment/energy-aware-app
kubectl -n energy-aware-dev rollout status deployment/energy-aware-app --timeout=180s
kubectl port-forward -n energy-aware-dev svc/energy-aware-service 5001:5000
```

## Smoke test result

Every page and new API returned HTTP 200 from the image running in the real Minikube cluster:

| Path | Status | Content type |
|---|---|---|
| `/` | 200 | `text/html` |
| `/eaes-diagnostics` | 200 | `text/html` |
| `/methodology` | 200 | `text/html` |
| `/api/v1/research/results` | 200 | `application/json` |
| `/api/v1/research/diagnostic` | 200 | `application/json` |
| `/api/v1/research/methodology` | 200 | `application/json` |
| `/api/v1/research/cluster` | 200 | `application/json` |
| `/api/v1/experiments` | 200 | `application/json` |
| `/health` | 200 | `application/json` |
| `/ready` | 200 | `application/json` |

`/api/v1/research/results` reported `run_id = v3_paired_20261025T220942Z` and `available = true`. `/api/v1/experiments` returned `total_experiments = 27`, confirming that the legacy API works from the packaged app-local dataset copy.

## Important distinction

The image smoke test validates packaging and serving inside the cluster. It is **not** a new energy experiment and **not** a re-run of the HPA comparison. The paired confirmatory results remain the simulation run `v3_paired_20261025T220942Z`. The native-HPA validation remains the separate `cce700b` run documented in `results/cluster_validation/`.

## Build-status caveat

`minikube image build` printed progress to stderr and returned a non-zero PowerShell status after successfully exporting and naming the image. The Docker export completed, the deployment rolled out, and the new pod served all endpoints. The saved build log is `results/image_build_final.log`.

## Reproducing the image check

```powershell
minikube start --driver=docker --cpus=2 --memory=4096
minikube image build -t flask-k8s-demo:latest .
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -n energy-aware-dev -f kubernetes/deployment.yaml -f kubernetes/service.yaml
kubectl -n energy-aware-dev rollout status deployment/energy-aware-app --timeout=180s
kubectl port-forward -n energy-aware-dev svc/energy-aware-service 5001:5000
```

The smoke test used a temporary port-forward; it was stopped after the check.

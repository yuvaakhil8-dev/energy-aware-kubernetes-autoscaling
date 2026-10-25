# Flask Application Deployment Using Docker and Kubernetes (Minikube)

Beginner-friendly project that runs a simple Flask app locally, packages it in Docker, and deploys it to a local Kubernetes cluster (Minikube).

## 1. Project Architecture

```text
Browser
  |
  |  http://<minikube-ip>:30007/  and  /info
  v
NodePort Service (flask-service, port 5000 -> targetPort 5000, nodePort 30007)
  |
  v
Deployment (flask-app, replicas: 1)
  |
  v
Pod -> Container (flask-container, image: flask-k8s-demo:latest, port 5000)
  |
  v
Flask app (app.py, port 5000)
```

Flow:

1. Flask serves two routes on port 5000 inside the container.
2. Docker packages Python + dependencies + `app.py` into image `flask-k8s-demo:latest`.
3. Minikube runs Kubernetes locally in a VM/container using the Docker driver.
4. A Deployment keeps 1 Pod running from that image.
5. A NodePort Service exposes the Pod on every cluster node at port `30007`.

## 2. Project Structure

```text
flask-kubernetes/
├── app.py                  # Flask application (routes / and /info)
├── requirements.txt        # Python dependencies (Flask)
├── Dockerfile              # Instructions to build the Docker image
├── .dockerignore           # Files excluded from the Docker build context
├── README.md               # This documentation
└── kubernetes/
    ├── deployment.yaml     # Deployment: flask-app, 1 replica
    └── service.yaml        # Service: flask-service, NodePort 30007
```

## 3. Purpose of Every File

| File | Purpose |
|------|---------|
| `app.py` | Defines Flask app, `/` and `/info` routes, listens on `0.0.0.0:5000`. `0.0.0.0` is required so the app is reachable from outside the container. |
| `requirements.txt` | Pins `Flask==3.1.0` so Docker and local venv install the same version. |
| `Dockerfile` | `FROM python:3.12-slim` base image, `WORKDIR /app`, install requirements, copy app, `EXPOSE 5000`, `CMD ["python", "app.py"]`. |
| `.dockerignore` | Prevents venv, cache, git, editor files from being sent to Docker daemon. Keeps image small and builds fast. |
| `kubernetes/deployment.yaml` | Desired state: 1 replica of `flask-k8s-demo:latest`, container `flask-container` on port 5000, `imagePullPolicy: IfNotPresent` so Minikube uses the locally loaded image. Labels `app: flask-app` must match selector. |
| `kubernetes/service.yaml` | Stable network endpoint. `type: NodePort` exposes port `30007` on the Minikube node and forwards to `targetPort: 5000` on Pods selected by `app: flask-app`. |

## 4. Flask Application Workflow

`app.py`:

```python
from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "Hello! My Flask application is running."

@app.route("/info")
def info():
    return "This application will be deployed using Docker and Kubernetes."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

- `Flask(__name__)` creates the app.
- `@app.route("/")` maps homepage.
- `@app.route("/info")` maps info page.
- `host="0.0.0.0"` listens on all interfaces (required in Docker/K8s).
- `port=5000` matches Dockerfile `EXPOSE`, `containerPort`, and Service ports.

## 5. Docker Concepts

- **Image:** Read-only template built from Dockerfile. Here: `flask-k8s-demo:latest`.
- **Container:** Running instance of an image. Isolated process with its own filesystem/ports.
- **Dockerfile instructions:**
  - `FROM` — base OS + Python.
  - `WORKDIR` — working directory inside image.
  - `COPY` + `RUN pip install` — add dependencies.
  - `EXPOSE` — documentation/metadata (does not publish the port by itself).
  - `CMD` — default command when container starts.
- **`docker build -t flask-k8s-demo:latest .`** builds the image.
- **`docker run -p 5000:5000 flask-k8s-demo:latest`** maps host port 5000 to container port 5000 for local testing.

## 6. Kubernetes Concepts

- **Pod:** Smallest unit. One or more containers with shared network. Created by the Deployment.
- **Deployment:** Manages ReplicaSets/Pods, ensures desired replica count (here `replicas: 1`). Handles updates and restarts.
- **Service (NodePort):** Stable virtual IP + DNS + port mapping. `port: 5000` is the Service port, `targetPort: 5000` is the Pod port, `nodePort: 30007` (range 30000-32767) is opened on the node for external access.
- **Labels/Selectors:** `app: flask-app` links Service -> Pod and Deployment -> Pod. If they mismatch, the Service has no endpoints.
- **imagePullPolicy: IfNotPresent:** Uses local image if present; does not try to pull from Docker Hub. Required for Minikube with `minikube image load`.

## 7. Prerequisites

- Windows + VS Code
- Python installed
- Docker Desktop installed
- kubectl installed
- Minikube installed

No cloud account needed. Local Minikube only.

## 8. Execution Commands

Run all commands from the `flask-kubernetes/` folder unless stated otherwise.

### Stage 1: Environment verification

```powershell
python --version
docker --version
docker info
kubectl version --client
minikube version
minikube start --driver=docker
kubectl get nodes
```

Expected:

- Python version printed, e.g. `Python 3.12.x`.
- Docker version + `Server: Docker Engine` info (Docker Desktop must be running).
- kubectl client version.
- Minikube version.
- `minikube start` outputs `Done! kubectl is now configured...`.
- `kubectl get nodes` shows one node `STATUS Ready`.

### Stage 2: Flask execution (local, no Docker yet)

```powershell
cd flask-kubernetes
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Test in browser or new terminal:

```powershell
curl http://127.0.0.1:5000/
curl http://127.0.0.1:5000/info
```

Expected:

- `/` -> `Hello! My Flask application is running.`
- `/info` -> `This application will be deployed using Docker and Kubernetes.`
- Stop with `Ctrl+C`, then `deactivate`.

### Stage 3: Docker execution

```powershell
cd flask-kubernetes
docker build -t flask-k8s-demo:latest .
docker images | findstr flask-k8s-demo
docker run -d --name flask-test -p 5000:5000 flask-k8s-demo:latest
docker ps
docker logs flask-test
curl http://127.0.0.1:5000/
curl http://127.0.0.1:5000/info
docker stop flask-test
docker rm flask-test
```

Expected:

- Build ends with `Successfully tagged flask-k8s-demo:latest`.
- Image listed.
- Container `Up` in `docker ps`.
- Logs show `Running on http://0.0.0.0:5000`.
- curl returns the two strings above.
- Container stopped/removed so port 5000 is free for later.

### Stage 4: Kubernetes deployment (Minikube)

```powershell
cd flask-kubernetes
minikube status
kubectl get nodes
minikube image load flask-k8s-demo:latest
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml
kubectl get deployments
kubectl get pods
kubectl get services
kubectl logs -l app=flask-app
minikube service flask-service --url
```

Then open the printed URL in browser, e.g. `http://127.0.0.1:<port>`, and test:

```powershell
# Replace URL with output of previous command
curl <minikube-service-url>/
curl <minikube-service-url>/info
```

Or directly with NodePort:

```powershell
minikube ip
kubectl get svc flask-service
```

Expected:

- `deployment.apps/flask-app created`, `service/flask-service created`.
- Pod `STATUS Running`, `READY 1/1`.
- Service shows `5000:30007/TCP`.
- Logs show Flask running.
- Browser shows both expected strings.

### Stage 5: Testing checklist

- [ ] Homepage returns `Hello! My Flask application is running.`
- [ ] `/info` returns `This application will be deployed using Docker and Kubernetes.`
- [ ] `kubectl get pods` shows 1 Running pod.
- [ ] `kubectl get svc flask-service` shows NodePort 30007.
- [ ] App accessed via `minikube service flask-service --url`.

## 9. Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| `docker info` fails / Docker daemon not running | Start Docker Desktop, wait for green status, retry. |
| `minikube start` fails with driver error | Ensure Docker Desktop is running, run `minikube delete`, then `minikube start --driver=docker`. |
| `kubectl get nodes` shows `NotReady` | Wait 1-2 min, run `minikube status`, `kubectl describe node minikube`. |
| Flask `Address already in use :5000` | Old container/test still running. `docker stop flask-test; docker rm flask-test` or stop local `python app.py` with `Ctrl+C`. |
| `ImagePullBackOff` / `ErrImagePull` | Image not in Minikube. Run `minikube image load flask-k8s-demo:latest`, keep `imagePullPolicy: IfNotPresent`, `kubectl delete pod -l app=flask-app` to recreate. |
| Pod `CrashLoopBackOff` | App crashed. Check `kubectl logs -l app=flask-app` and `kubectl describe pod -l app=flask-app`. Usually wrong port or missing dependency. |
| Service has no endpoints (`kubectl describe svc flask-service` shows `<none>`) | Label mismatch. Deployment Pod must have `app: flask-app` and Service selector must be `app: flask-app`. |
| `curl` to NodePort fails | Use `minikube service flask-service --url` instead of guessing IP. Ensure Minikube tunnel/cluster is running. |
| Windows PowerShell venv activation blocked | Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`, then re-activate. |

Useful diagnostics:

```powershell
kubectl get pods
kubectl describe deployment flask-app
kubectl describe pod -l app=flask-app
kubectl logs -l app=flask-app
kubectl describe svc flask-service
kubectl get events --sort-by=.lastTimestamp
```

## 10. Cleanup

```powershell
kubectl delete -f kubernetes/service.yaml
kubectl delete -f kubernetes/deployment.yaml
docker stop flask-test
docker rm flask-test
docker rmi flask-k8s-demo:latest
deactivate
minikube stop
# To fully remove the cluster:
# minikube delete
```

This leaves code intact but stops the cluster and removes K8s objects, test container, and image.

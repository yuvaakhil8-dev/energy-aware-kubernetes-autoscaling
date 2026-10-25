#!/usr/bin/env python3
"""Energy-Aware Flask Microservice for Kubernetes Autoscaling Demonstration.

This microservice simulates realistic microservice behavior with:
- CPU-intensive and lightweight operations
- Request logging with timing
- Workload-aware endpoints
- Performance metrics collection
- Experiment data access
- Integrated graphical research dashboard

IMPORTANT SCIENTIFIC NOTE
-------------------------
Energy values are *model estimates* derived from CPU utilisation
(P = P_idle + (P_max - P_idle) * CPU/100), NOT physical power measurements.
No real Kubernetes deployment is claimed unless verified separately.
"""

from flask import Flask, jsonify, request, render_template
import time
import random
from datetime import datetime
import json
from collections import Counter, defaultdict
import os
import sys
import threading

# ---------------------------------------------------------------------------
# Paths / imports
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Make sibling modules (controller.py) importable regardless of the CWD used
# to launch the process.
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

PROJECT_ROOT = os.path.dirname(BASE_DIR)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------
request_metrics = []
cpu_samples = []
start_time = time.time()
app_start_time = time.time()

# Simulated CPU utilization (percentage)
simulated_cpu_utilization = 30.0

# Workload profiles: (cpu_percent, request_rate_per_sec, avg_latency_ms)
WORKLOAD_PROFILES = {
    'light': (15, 5, 50),
    'medium': (50, 20, 100),
    'heavy': (85, 50, 200),
}

current_workload = 'light'
workload_change_time = time.time()

# Guard shared runtime state mutated by the background thread and requests.
state_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Experiment data
# ---------------------------------------------------------------------------
# v2 = 27-record factorial design (3 strategies x 3 workloads x 3 repetitions).
# The legacy experiment_results.json (18 records) is retained on disk untouched
# and is only used as a fallback if v2 is unavailable.
EXPERIMENT_RESULTS = []
EXPERIMENT_LOG = []
DATASET_FILE = None
DATASET_IS_FALLBACK = False

STRATEGIES = ['static', 'hpa', 'energy_aware']
WORKLOADS = ['light', 'medium', 'heavy']
STRATEGY_LABELS = {'static': 'Static', 'hpa': 'HPA', 'energy_aware': 'EAES'}


def _load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _load_experiment_data():
    """Load the newest validated dataset, falling back to the legacy one."""
    global EXPERIMENT_RESULTS, EXPERIMENT_LOG, DATASET_FILE, DATASET_IS_FALLBACK

    v2_path = os.path.join(PROJECT_ROOT, 'experiment_results_v2.json')
    legacy_path = os.path.join(PROJECT_ROOT, 'experiment_results.json')

    data = _load_json(v2_path)
    if isinstance(data, list) and data:
        EXPERIMENT_RESULTS = data
        DATASET_FILE = os.path.basename(v2_path)
        DATASET_IS_FALLBACK = False
    else:
        data = _load_json(legacy_path)
        EXPERIMENT_RESULTS = data if isinstance(data, list) else []
        DATASET_FILE = os.path.basename(legacy_path) if EXPERIMENT_RESULTS else None
        DATASET_IS_FALLBACK = bool(EXPERIMENT_RESULTS)

    log = _load_json(os.path.join(PROJECT_ROOT, 'experiment_execution_log.json'))
    EXPERIMENT_LOG = log if isinstance(log, list) else []


_load_experiment_data()


def _rec_strategy(rec):
    return rec.get('mode') or rec.get('strategy') or 'unknown'


def _num(value, default=0.0):
    """Coerce a possibly-missing numeric field without inventing values."""
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _group_records(strategy, workload):
    return [
        r for r in EXPERIMENT_RESULTS
        if _rec_strategy(r) == strategy and r.get('workload') == workload
    ]


def aggregate(strategy, workload):
    """Aggregate a (strategy, workload) cell. Missing data yields None fields."""
    rows = _group_records(strategy, workload)
    if not rows:
        return {
            'count': 0, 'avg_replicas': None, 'avg_cpu': None,
            'avg_energy': None, 'avg_latency': None, 'sla_violations': None,
        }
    energies = [r['avg_energy_per_request'] for r in rows
                if isinstance(r.get('avg_energy_per_request'), (int, float))]
    latencies = [r['average_latency_ms'] for r in rows
                 if isinstance(r.get('average_latency_ms'), (int, float))]
    replicas = [r['average_replicas'] for r in rows
                if isinstance(r.get('average_replicas'), (int, float))]
    cpus = [r['avg_cpu'] for r in rows
            if isinstance(r.get('avg_cpu'), (int, float))]
    return {
        'count': len(rows),
        'avg_replicas': round(sum(replicas) / len(replicas), 2) if replicas else None,
        'avg_cpu': round(sum(cpus) / len(cpus), 2) if cpus else None,
        'avg_energy': round(sum(energies) / len(energies), 4) if energies else None,
        'avg_latency': round(sum(latencies) / len(latencies), 1) if latencies else None,
        'sla_violations': sum(int(r.get('total_sla_violations') or 0) for r in rows),
    }


def build_matrix():
    """Return {strategy: {workload: aggregate}} for the whole dataset."""
    return {
        strategy: {workload: aggregate(strategy, workload) for workload in WORKLOADS}
        for strategy in STRATEGIES
    }


def dataset_summary():
    total = len(EXPERIMENT_RESULTS)
    status_counts = Counter(str(r.get('status', 'unknown')) for r in EXPERIMENT_RESULTS)
    modes = Counter(_rec_strategy(r) for r in EXPERIMENT_RESULTS)
    reps = Counter(r.get('repetition') for r in EXPERIMENT_RESULTS)
    cells = {
        f'{s}:{w}': len(_group_records(s, w))
        for s in STRATEGIES for w in WORKLOADS
    }
    return {
        'file': DATASET_FILE,
        'is_fallback': DATASET_IS_FALLBACK,
        'total': total,
        'expected': 27,
        'status_counts': dict(status_counts),
        'strategy_counts': dict(modes),
        'repetitions': {str(k): v for k, v in sorted(reps.items(), key=lambda x: str(x[0]))},
        'cells': cells,
        'complete_cells': sum(1 for v in cells.values() if v == 3),
    }


def repetitions_identical():
    """Detect pseudo-replication: identical metric values across repetitions."""
    duplicated = 0
    for strategy in STRATEGIES:
        for workload in WORKLOADS:
            rows = _group_records(strategy, workload)
            if len(rows) < 2:
                continue
            fingerprints = {
                (r.get('avg_cpu'), r.get('avg_energy_per_request'),
                 r.get('average_latency_ms'), r.get('average_replicas'))
                for r in rows
            }
            if len(fingerprints) == 1:
                duplicated += 1
    return duplicated


def get_dashboard_stats():
    """High-level KPI data derived only from the loaded dataset."""
    if not EXPERIMENT_RESULTS:
        return {
            'total_experiments': 0, 'successful': 0, 'incomplete': 0,
            'failed': 0, 'avg_replicas': None, 'total_sla_violations': 0,
            'strategies': 0, 'workloads': 0,
        }
    total = len(EXPERIMENT_RESULTS)
    successful = sum(1 for r in EXPERIMENT_RESULTS if r.get('status') == 'success')
    incomplete = sum(1 for r in EXPERIMENT_RESULTS if r.get('status') == 'incomplete')
    failed = sum(1 for r in EXPERIMENT_RESULTS if r.get('status') == 'failed')
    replicas = [r['average_replicas'] for r in EXPERIMENT_RESULTS
                if isinstance(r.get('average_replicas'), (int, float))]
    return {
        'total_experiments': total,
        'successful': successful,
        'incomplete': incomplete,
        'failed': failed,
        'avg_replicas': round(sum(replicas) / len(replicas), 2) if replicas else None,
        'total_sla_violations': sum(int(r.get('total_sla_violations') or 0)
                                    for r in EXPERIMENT_RESULTS),
        'strategies': len({_rec_strategy(r) for r in EXPERIMENT_RESULTS}),
        'workloads': len({r.get('workload') for r in EXPERIMENT_RESULTS}),
    }


def controller_snapshot():
    """Best-effort controller status; never raises for the dashboard."""
    try:
        from controller import EnergyAwareController
        cfg = {
            'min_replicas': 1, 'max_replicas': 10, 'target_cpu_util': 60,
            'scale_up_threshold': 80, 'scale_down_threshold': 30,
            'hysteresis': 5, 'cooldown_seconds': 60,
            'scale_change_cooldown': 30, 'sla_latency_threshold_ms': 500,
            'energy_per_request_target': 1.0, 'metric_samples': 20,
            'check_interval': 15,
        }
        return EnergyAwareController(config=cfg).get_status()
    except Exception as exc:  # pragma: no cover - defensive
        return {'error': f'controller unavailable: {exc}'}


def chart_payload(matrix):
    """Compact JSON payload consumed by the charts."""
    return {
        'labels': [STRATEGY_LABELS[s] for s in STRATEGIES],
        'strategies': STRATEGIES,
        'workloads': WORKLOADS,
        'energy': {
            w: [matrix[s][w]['avg_energy'] for s in STRATEGIES] for w in WORKLOADS
        },
        'replicas': {
            w: [matrix[s][w]['avg_replicas'] for s in STRATEGIES] for w in WORKLOADS
        },
        'cpu': {
            w: [matrix[s][w]['avg_cpu'] for s in STRATEGIES] for w in WORKLOADS
        },
        'latency': {
            w: [matrix[s][w]['avg_latency'] for s in STRATEGIES] for w in WORKLOADS
        },
        'sla': {
            w: [matrix[s][w]['sla_violations'] for s in STRATEGIES] for w in WORKLOADS
        },
    }


# ---------------------------------------------------------------------------
# Dashboard routes
# ---------------------------------------------------------------------------
@app.route("/")
def dashboard():
    """Render the main Overview dashboard (HTML)."""
    matrix = build_matrix()
    return render_template(
        'dashboard/index.html',
        active='overview',
        stats=get_dashboard_stats(),
        summary=dataset_summary(),
        matrix=matrix,
        chart_data=chart_payload(matrix),
        controller=controller_snapshot(),
        current_workload=current_workload,
        simulated_cpu_utilization=round(simulated_cpu_utilization, 1),
        strategies=STRATEGIES,
        strategy_labels=STRATEGY_LABELS,
        workloads=WORKLOADS,
    )


@app.route("/autoscaling-comparison")
def autoscaling_comparison():
    matrix = build_matrix()
    return render_template(
        'dashboard/autoscaling_comparison.html',
        active='comparison',
        stats=get_dashboard_stats(),
        summary=dataset_summary(),
        matrix=matrix,
        chart_data=chart_payload(matrix),
        strategies=STRATEGIES,
        strategy_labels=STRATEGY_LABELS,
        workloads=WORKLOADS,
    )


@app.route("/energy-analysis")
def energy_analysis():
    matrix = build_matrix()
    reduction = {}
    for workload in WORKLOADS:
        static_e = matrix['static'][workload]['avg_energy']
        eaes_e = matrix['energy_aware'][workload]['avg_energy']
        if static_e and eaes_e is not None and static_e != 0:
            reduction[workload] = round((static_e - eaes_e) / static_e * 100, 1)
        else:
            reduction[workload] = None
    return render_template(
        'dashboard/energy_analysis.html',
        active='energy',
        stats=get_dashboard_stats(),
        summary=dataset_summary(),
        matrix=matrix,
        chart_data=chart_payload(matrix),
        reduction=reduction,
        strategies=STRATEGIES,
        strategy_labels=STRATEGY_LABELS,
        workloads=WORKLOADS,
    )


@app.route("/performance-analysis")
def performance_analysis():
    matrix = build_matrix()
    return render_template(
        'dashboard/performance_analysis.html',
        active='performance',
        stats=get_dashboard_stats(),
        summary=dataset_summary(),
        matrix=matrix,
        chart_data=chart_payload(matrix),
        strategies=STRATEGIES,
        strategy_labels=STRATEGY_LABELS,
        workloads=WORKLOADS,
    )


@app.route("/experiment-explorer")
def experiment_explorer():
    rows = []
    for index, rec in enumerate(EXPERIMENT_RESULTS, start=1):
        rows.append({
            'index': index,
            'experiment_id': rec.get('experiment_id') or f'EXP-{index:03d}',
            'strategy': _rec_strategy(rec),
            'strategy_label': STRATEGY_LABELS.get(_rec_strategy(rec), _rec_strategy(rec)),
            'workload': rec.get('workload'),
            'repetition': rec.get('repetition'),
            'replicas': rec.get('average_replicas'),
            'cpu': rec.get('avg_cpu'),
            'energy': rec.get('avg_energy_per_request'),
            'latency': rec.get('average_latency_ms'),
            'sla': rec.get('total_sla_violations'),
            'status': rec.get('status'),
            'execution_mode': rec.get('execution_mode'),
        })
    return render_template(
        'dashboard/experiment_explorer.html',
        active='explorer',
        stats=get_dashboard_stats(),
        summary=dataset_summary(),
        rows=rows,
        repetitions_identical=repetitions_identical(),
        strategies=STRATEGIES,
        strategy_labels=STRATEGY_LABELS,
        workloads=WORKLOADS,
    )


@app.route("/research-methodology")
def research_methodology():
    return render_template(
        'dashboard/research_methodology.html',
        active='methodology',
        stats=get_dashboard_stats(),
        summary=dataset_summary(),
        strategies=STRATEGIES,
        strategy_labels=STRATEGY_LABELS,
        workloads=WORKLOADS,
    )


# ---------------------------------------------------------------------------
# Preserved API routes
# ---------------------------------------------------------------------------
@app.route("/api/status")
def home():
    """JSON service status (formerly served at '/')."""
    return jsonify({
        "message": "Energy-Aware Flask Microservice is running",
        "workload": current_workload,
        "cpu_percent": round(simulated_cpu_utilization, 1),
        "uptime_s": round(time.time() - app_start_time, 1),
        "replicas": 1,  # simulated fixed replica indicator
        "dashboard": "/",
    })


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "workload": current_workload,
        "cpu_percent": round(simulated_cpu_utilization, 1),
        "memory_percent": round(random.uniform(40, 80), 1),
    })


@app.route("/ready")
def ready():
    """Readiness probe endpoint used by the Kubernetes manifest."""
    return jsonify({"status": "ready"}), 200


@app.route("/info")
def info():
    """Information endpoint."""
    return jsonify({
        "application": "Energy-Aware Autoscaling Framework",
        "framework": "Kubernetes-based microservices (simulated)",
        "microservice": "Flask-based resource metrics endpoint",
        "workload": current_workload,
        "cpu_percent": round(simulated_cpu_utilization, 1),
        "memory_percent": round(random.uniform(40, 80), 1),
        "supported_algorithms": [
            "EAES: Energy-Aware Elastic Scaling (proposed base paper algorithm)",
            "CPU-based HPA: Kubernetes default Horizontal Pod Autoscaler",
            "Static: Fixed replica provisioning",
        ],
        "energy_estimation": {
            "method": "CPU-utilization-based estimation (estimate, not measurement)",
            "formula": "P = P_idle + (P_max - P_idle) * CPU/100; E_req = P*dt/N_req",
            "parameters": {"P_idle_W": 30.0, "P_max_W": 80.0, "dt_s": 15},
            "note": "Energy values are estimates based on CPU utilization, not direct hardware power measurements",
        },
        "dataset": dataset_summary()['file'],
        "experiment_count": len(EXPERIMENT_RESULTS),
    })


@app.route("/workload/status")
def workload_status():
    """Get current workload profile status."""
    elapsed = time.time() - workload_change_time
    cpu, rate, latency = WORKLOAD_PROFILES[current_workload]
    return jsonify({
        "profile": current_workload,
        "cpu_percent": cpu,
        "request_rate": rate,
        "avg_latency_ms": latency,
        "seconds_at_profile": round(elapsed, 1),
        "uptime_seconds": round(time.time() - start_time, 1),
        "app_uptime_s": round(time.time() - app_start_time, 1),
    })


@app.route("/cpu/intensive")
def cpu_intensive():
    """CPU-intensive endpoint for generating load."""
    global simulated_cpu_utilization
    profile = WORKLOAD_PROFILES[current_workload]
    base_cpu = profile[0]
    intensity_factor = random.uniform(0.8, 1.2)
    simulated_cpu_utilization = min(95, base_cpu * intensity_factor)

    compute_time = random.uniform(0.05, 0.2)
    _ = sum(i * i for i in range(1000 * int(compute_time * 10)))

    cpu_samples.append({
        "timestamp": time.time(),
        "cpu_percent": simulated_cpu_utilization,
        "endpoint": "/cpu/intensive",
        "workload": current_workload,
    })
    if len(cpu_samples) > 50:
        cpu_samples.pop(0)

    request_metrics.append({
        "timestamp": time.time(),
        "endpoint": "/cpu/intensive",
        "cpu_percent": simulated_cpu_utilization,
        "response_time_ms": round(compute_time * 1000, 2),
        "workload": current_workload,
    })
    if len(request_metrics) > 100:
        request_metrics.pop(0)

    return jsonify({
        "status": "CPU-intensive operation completed",
        "cpu_percent": round(simulated_cpu_utilization, 1),
        "computation_time_ms": round(compute_time * 1000, 2),
        "workload": current_workload,
        "sla_violation": simulated_cpu_utilization > 80,
    })


@app.route("/cpu/light")
def cpu_light():
    """Lightweight endpoint for normal operations."""
    global simulated_cpu_utilization
    _ = 42 + 42
    simulated_cpu_utilization = max(10, simulated_cpu_utilization - 5)

    cpu_samples.append({
        "timestamp": time.time(),
        "cpu_percent": simulated_cpu_utilization,
        "endpoint": "/cpu/light",
        "workload": current_workload,
    })
    if len(cpu_samples) > 50:
        cpu_samples.pop(0)

    request_metrics.append({
        "timestamp": time.time(),
        "endpoint": "/cpu/light",
        "cpu_percent": simulated_cpu_utilization,
        "response_time_ms": 1.0,
        "workload": current_workload,
    })
    if len(request_metrics) > 100:
        request_metrics.pop(0)

    return jsonify({
        "status": "Lightweight operation completed",
        "cpu_percent": round(simulated_cpu_utilization, 1),
        "workload": current_workload,
    })


@app.route("/metrics")
def metrics():
    """Prometheus-compatible metrics endpoint."""
    cpu_avg = (sum(s['cpu_percent'] for s in cpu_samples) / max(len(cpu_samples), 1)
               if cpu_samples else simulated_cpu_utilization)

    recent = [m for m in request_metrics if time.time() - m['timestamp'] < 10]
    request_rate = (len(recent) / max(1, (time.time() - recent[0]['timestamp'])) * 60
                    if recent else 0)

    mem_util = random.uniform(40, 80)
    lines = [
        '# HELP flask_cpu_utilization_current Current CPU utilization percentage',
        '# TYPE flask_cpu_utilization_current gauge',
        f'flask_cpu_utilization_current {cpu_avg:.1f}',
        '# HELP flask_memory_utilization_current Current memory utilization percentage',
        '# TYPE flask_memory_utilization_current gauge',
        f'flask_memory_utilization_current {mem_util:.1f}',
        '# HELP flask_requests_total Total number of requests',
        '# TYPE flask_requests_total counter',
        f'flask_requests_total {len(request_metrics)}',
        '# HELP flask_request_rate_current Current request rate (req/s)',
        '# TYPE flask_request_rate_current gauge',
        f'flask_request_rate_current {request_rate:.1f}',
        '# HELP flask_cpu_utilization_average Average CPU utilization',
        '# TYPE flask_cpu_utilization_average gauge',
        f'flask_cpu_utilization_average {round(sum(s["cpu_percent"] for s in cpu_samples) / max(len(cpu_samples), 1), 1)}',
        '# HELP flask_experiments_loaded Number of experiment records loaded',
        '# TYPE flask_experiments_loaded gauge',
        f'flask_experiments_loaded {len(EXPERIMENT_RESULTS)}',
    ]
    return '\n'.join(lines), 200, {'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}


@app.route("/api/v1/experiments")
def experiments():
    """Experiment data endpoint - returns all experiment results."""
    if not EXPERIMENT_RESULTS:
        return jsonify({"error": "No experiment data available",
                        "total_experiments": 0}), 404

    mode_counts = Counter(_rec_strategy(r) for r in EXPERIMENT_RESULTS)
    energies = [r['avg_energy_per_request'] for r in EXPERIMENT_RESULTS
                if isinstance(r.get('avg_energy_per_request'), (int, float))]
    avg_energy = sum(energies) / len(energies) if energies else 0

    experiment_list = []
    for i, r in enumerate(EXPERIMENT_RESULTS):
        experiment_list.append({
            "id": i + 1,
            "experiment_id": r.get('experiment_id'),
            "mode": _rec_strategy(r),
            "workload": r.get('workload'),
            "repetition": r.get('repetition'),
            "average_replicas": r.get('average_replicas'),
            "avg_cpu_percent": r.get('avg_cpu'),
            "avg_energy_per_request_j": r.get('avg_energy_per_request'),
            "avg_latency_ms": r.get('average_latency_ms') or r.get('avg_latency_ms'),
            "total_sla_violations": r.get('total_sla_violations'),
            "total_samples": r.get('total_samples'),
            "status": r.get('status'),
        })

    return jsonify({
        "dataset": DATASET_FILE,
        "is_fallback_dataset": DATASET_IS_FALLBACK,
        "total_experiments": len(EXPERIMENT_RESULTS),
        "modes": dict(mode_counts),
        "average_energy_per_request_j": round(avg_energy, 4),
        "energy_note": "Estimated from CPU utilization; not measured hardware energy.",
        "experiments": experiment_list,
    })


@app.route("/api/v1/research-papers")
def research_papers():
    """Research papers information endpoint."""
    return jsonify({
        "primary_paper": {
            "title": "Energy-aware elastic scaling algorithm for microservices in Kubernetes clouds",
            "authors": "Hongjian Li, Wei Rao, Baojian Hu, Yu Tian, Jie Shen",
            "venue": "Journal of Network and Computer Applications (Elsevier)",
            "year": 2025,
            "doi": "10.1016/j.jnca.2025.104218",
            "energy_reduction_claim": "15.34% compared to default Kubernetes HPA",
            "note": "This paper result is kept separate from local experimental results",
        },
        "secondary_papers": [
            {"title": "NeuroScaler: Towards Energy-Optimal Autoscaling for Container-Based Services",
             "authors": "Alisson O. Chaves et al.", "venue": "arXiv 2026",
             "focus": "Predictive/RL-based autoscaling"},
            {"title": "Experimenting with Energy-Awareness in Edge-Cloud Containerized Application Orchestration",
             "authors": "Dalal Ali, Rute C. Sofia", "venue": "arXiv 2025",
             "focus": "Energy-aware orchestration in edge-cloud contexts"},
        ],
        "note": "Paper results are distinguished from locally generated experimental results",
    })


@app.route("/status")
def status():
    """Service status endpoint."""
    return jsonify({
        "status": "operational",
        "workload": current_workload,
        "cpu_utilization": round(simulated_cpu_utilization, 1),
        "uptime_s": round(time.time() - app_start_time, 1),
        "flask_version": "2.x+",
        "mode": "simulation-based (Docker Desktop blocked in WSL2)",
        "experiment_count": len(EXPERIMENT_RESULTS),
        "dataset": DATASET_FILE,
        "docker_status": "Desktop daemon blocked - WSL2 exit error 0x40010004",
        "kubernetes_status": "Not operational (Docker dependency required)",
    })


@app.route("/workload/change", methods=["POST"])
def change_workload():
    """Change the current workload profile."""
    global current_workload, workload_change_time, simulated_cpu_utilization
    data = request.get_json(silent=True)
    if data and "profile" in data:
        profile = data["profile"]
        if profile in WORKLOAD_PROFILES:
            with state_lock:
                current_workload = profile
                workload_change_time = time.time()
                cpu, rate, latency = WORKLOAD_PROFILES[profile]
                simulated_cpu_utilization = cpu
            return jsonify({
                "status": f"Workload changed to {profile}",
                "cpu_percent": cpu,
                "request_rate": rate,
                "avg_latency_ms": latency,
            })
    return jsonify({"error": "Invalid profile"}), 400


@app.route("/controller/status")
def controller_status():
    """Energy-aware controller status endpoint."""
    status = controller_snapshot()
    if 'error' in status:
        return jsonify(status), 503
    status['experiment_integration'] = {
        "total_experiments": len(EXPERIMENT_RESULTS),
        "modes_supported": STRATEGIES,
        "workloads_supported": WORKLOADS,
        "energy_formula": "P = P_idle + (P_max - P_idle) * util/100 (estimated)",
        "energy_per_request_formula": "E_req = P * delta_t / N_req (estimated)",
    }
    return jsonify(status)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(error):
    return render_template('dashboard/404.html', active=None), 404


@app.errorhandler(500)
def server_error(error):
    return render_template('dashboard/500.html', active=None), 500


# ---------------------------------------------------------------------------
# Helpers exposed for tests / in-process consumers
# ---------------------------------------------------------------------------
def get_cpu_utilization():
    return simulated_cpu_utilization


def get_workload():
    return current_workload


# ---------------------------------------------------------------------------
# Background workload simulation
# ---------------------------------------------------------------------------
def workload_transition_loop():
    """Periodically switch workload profiles to exercise autoscaling logic."""
    global current_workload, workload_change_time, simulated_cpu_utilization
    profiles = ['light', 'medium', 'heavy', 'medium', 'light']
    while True:
        try:
            for profile in profiles:
                with state_lock:
                    current_workload = profile
                    workload_change_time = time.time()
                    simulated_cpu_utilization = WORKLOAD_PROFILES[profile][0]
                time.sleep(random.uniform(3, 8))
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Workload loop error: {exc}")
            time.sleep(5)


_transition_thread = None


def start_workload_thread():
    """Start the workload simulator exactly once (idempotent)."""
    global _transition_thread
    if _transition_thread is not None and _transition_thread.is_alive():
        return _transition_thread
    _transition_thread = threading.Thread(
        target=workload_transition_loop, name='workload-transition', daemon=True
    )
    _transition_thread.start()
    return _transition_thread


# Start only when executed as a server (avoids duplicate threads under the
# Flask reloader or when imported by tests).
if os.environ.get('ENERGY_AWARE_NO_BG') != '1' and __name__ == '__main__':
    start_workload_thread()


if __name__ == "__main__":
    print("=" * 60)
    print("Energy-Aware Flask Microservice Starting...")
    print("=" * 60)
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Dataset      : {DATASET_FILE} ({len(EXPERIMENT_RESULTS)} records)")
    print(f"Initial workload: {current_workload}")
    print(f"Initial CPU utilization: {simulated_cpu_utilization}%")
    print("Dashboard:")
    print("  GET  / - Overview dashboard")
    print("  GET  /autoscaling-comparison")
    print("  GET  /energy-analysis")
    print("  GET  /performance-analysis")
    print("  GET  /experiment-explorer")
    print("  GET  /research-methodology")
    print("API:")
    print("  GET  /api/status | /health | /ready | /info")
    print("  GET  /workload/status | POST /workload/change")
    print("  GET  /cpu/light | /cpu/intensive | /metrics")
    print("  GET  /api/v1/experiments | /api/v1/research-papers")
    print("  GET  /status | /controller/status")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, threaded=True)

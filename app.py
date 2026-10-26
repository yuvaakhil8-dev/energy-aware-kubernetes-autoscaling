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
import csv
import hashlib
import json
from collections import Counter, defaultdict
import os
import sys
import threading

try:
    import yaml
except ImportError:  # pragma: no cover - requirements include PyYAML
    yaml = None

# ---------------------------------------------------------------------------
# Paths / imports
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Make sibling modules (controller.py) importable regardless of the CWD used
# to launch the process.
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

PROJECT_ROOT = os.path.dirname(BASE_DIR)
RESULTS_DIR = os.path.join(BASE_DIR, 'results')
CONFIG_DIR = os.path.join(BASE_DIR, 'configs')

RESEARCH_STRATEGIES = ['static', 'cpu_threshold', 'hpa_formula', 'eaes', 'forecasting_eaes']
RESEARCH_STRATEGY_LABELS = {
    'static': 'Static',
    'cpu_threshold': 'CPU threshold',
    'hpa_formula': 'HPA formula',
    'eaes': 'EAES',
    'forecasting_eaes': 'Forecasting EAES',
}
RESEARCH_METRIC_LABELS = {
    'energy_per_served_request_j': 'Energy / served request (J)',
    'sla_violation_rate': 'SLA violation rate',
    'replica_hours': 'Replica-hours',
    'drop_rate': 'Drop rate',
    'energy_per_offered_request_j': 'Energy / offered request (J)',
    'p95_latency_ms': 'P95 latency (ms)',
}
PRIMARY_RESEARCH_METRICS = [
    'energy_per_served_request_j', 'sla_violation_rate', 'replica_hours', 'drop_rate'
]

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

    # The originals live one directory above the app.  ``data/`` contains
    # byte-identical read-only copies so the Docker image and a fresh clone keep
    # the legacy endpoints working without reaching outside the build context.
    data_dirs = [PROJECT_ROOT, os.path.join(BASE_DIR, 'data')]
    for directory in data_dirs:
        v2_path = os.path.join(directory, 'experiment_results_v2.json')
        data = _load_json(v2_path)
        if isinstance(data, list) and data:
            EXPERIMENT_RESULTS = data
            DATASET_FILE = os.path.basename(v2_path)
            DATASET_IS_FALLBACK = False
            break
    else:
        for directory in data_dirs:
            legacy_path = os.path.join(directory, 'experiment_results.json')
            data = _load_json(legacy_path)
            if isinstance(data, list) and data:
                EXPERIMENT_RESULTS = data
                DATASET_FILE = os.path.basename(legacy_path)
                DATASET_IS_FALLBACK = True
                break

    log = None
    for directory in data_dirs:
        log = _load_json(os.path.join(directory, 'experiment_execution_log.json'))
        if log is not None:
            break
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
# Research data layer (generated files, read-only)
# ---------------------------------------------------------------------------
def _read_json_file(path, default=None):
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _read_csv_file(path, default=None):
    try:
        with open(path, 'r', encoding='utf-8', newline='') as fh:
            return list(csv.DictReader(fh))
    except (FileNotFoundError, OSError, csv.Error):
        return default if default is not None else []


def _as_float(value):
    if value is None or value == '' or value == 'null':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _research_run_dir():
    pointer = _read_json_file(os.path.join(RESULTS_DIR, 'latest_run.json'), {}) or {}
    rel = pointer.get('run_dir')
    if rel:
        candidate = rel if os.path.isabs(rel) else os.path.join(BASE_DIR, rel)
        if os.path.exists(os.path.join(candidate, 'manifest.json')):
            return candidate
    runs_root = os.path.join(RESULTS_DIR, 'runs')
    try:
        candidates = sorted(
            (os.path.join(runs_root, name) for name in os.listdir(runs_root)),
            key=lambda p: os.path.getmtime(p),
        )
    except OSError:
        candidates = []
    for candidate in reversed(candidates):
        if os.path.exists(os.path.join(candidate, 'manifest.json')):
            return candidate
    return None


def _normalise_row(row, numeric_fields):
    out = dict(row)
    for field in numeric_fields:
        if field in out:
            if field in {'n', 'n_pairs', 'n_blocks', 'n_seeds', 'ticks'}:
                out[field] = _as_int(out[field])
            else:
                out[field] = _as_float(out[field])
    return out


def _load_research_bundle():
    run_dir = _research_run_dir()
    bundle = {
        'run_dir': run_dir,
        'manifest': None,
        'summaries': [],
        'tables': {},
        'diagnostic': None,
        'cluster_rows': [],
        'cluster_manifest': None,
        'available': False,
        'error': None,
    }
    if not run_dir:
        bundle['error'] = 'No generated run found. Run python -m experiments.run_v3.'
        return bundle
    bundle['manifest'] = _read_json_file(os.path.join(run_dir, 'manifest.json'))
    bundle['summaries'] = _read_json_file(os.path.join(run_dir, 'summary.json'), []) or []
    numeric = {
        'energy_per_served_request_j', 'sla_violation_rate', 'replica_hours',
        'drop_rate', 'energy_per_offered_request_j', 'p95_latency_ms',
        'scaling_events', 'oscillations', 'mean', 'median', 'sd', 'ci_low',
        'ci_high', 'mean_diff', 'median_diff', 'p_value', 'p_holm',
        'cliffs_delta', 'Q',
    }
    for name in (
        'descriptive', 'paired', 'friedman', 'nemenyi', 'forecasting', 'sensitivity',
        'headline', 'paired_headline',
    ):
        rows = _read_csv_file(os.path.join(RESULTS_DIR, 'tables', f'{name}.csv'))
        bundle['tables'][name] = [_normalise_row(row, numeric) for row in rows]
    bundle['diagnostic'] = _read_json_file(os.path.join(RESULTS_DIR, 'diagnostic.json'))
    cluster_dir = os.path.join(RESULTS_DIR, 'cluster_validation')
    cluster_rows = _read_csv_file(os.path.join(cluster_dir, 'summary.csv'))
    cluster_numeric = {
        'repetition', 'seed', 'offered_requests', 'served_requests',
        'failed_requests', 'drop_rate', 'throughput_rps', 'avg_latency_ms',
        'p95_latency_ms', 'p99_latency_ms', 'avg_ready_replicas',
        'max_ready_replicas', 'avg_node_cpu_percent', 'max_node_cpu_percent',
        'modelled_energy_j', 'modelled_energy_per_served_request_j',
    }
    bundle['cluster_rows'] = [_normalise_row(row, cluster_numeric) for row in cluster_rows]
    bundle['cluster_manifest'] = _read_json_file(os.path.join(cluster_dir, 'manifest.json'))
    bundle['available'] = bool(bundle['manifest'] and bundle['summaries'])
    return bundle


def _table_lookup(rows, metric, workload, strategy):
    for row in rows:
        if row.get('metric') == metric and row.get('workload') == workload and row.get('strategy') == strategy:
            return row
    return None


def _cluster_aggregate(rows):
    aggregated = []
    for mode in ('static', 'hpa'):
        subset = [r for r in rows if r.get('mode') == mode]
        if not subset:
            continue
        def mean(field):
            vals = [r[field] for r in subset if isinstance(r.get(field), (int, float))]
            return sum(vals) / len(vals) if vals else None
        aggregated.append({
            'mode': mode,
            'replications': len(subset),
            'served_requests': mean('served_requests'),
            'offered_requests': mean('offered_requests'),
            'drop_rate': mean('drop_rate'),
            'throughput_rps': mean('throughput_rps'),
            'p95_latency_ms': mean('p95_latency_ms'),
            'avg_ready_replicas': mean('avg_ready_replicas'),
            'max_ready_replicas': max(
                [r['max_ready_replicas'] for r in subset if isinstance(r.get('max_ready_replicas'), (int, float))],
                default=None,
            ),
            'avg_node_cpu_percent': mean('avg_node_cpu_percent'),
            'modelled_energy_per_served_request_j': mean('modelled_energy_per_served_request_j'),
        })
    return aggregated


def _primary_descriptive(bundle):
    rows = bundle['tables'].get('descriptive', [])
    return [
        row for row in rows
        if row.get('metric') in PRIMARY_RESEARCH_METRICS
        and row.get('strategy') in RESEARCH_STRATEGIES
    ]


def _research_kpis(bundle):
    desc = bundle['tables'].get('descriptive', [])
    if not desc:
        return {}
    def mean_for(strategy, metric):
        values = [
            r['mean'] for r in desc
            if r.get('strategy') == strategy and r.get('metric') == metric
            and isinstance(r.get('mean'), (int, float))
        ]
        return sum(values) / len(values) if values else None
    eaes_energy = mean_for('eaes', 'energy_per_served_request_j')
    hpa_energy = mean_for('hpa_formula', 'energy_per_served_request_j')
    static_drop = mean_for('static', 'drop_rate')
    eaes_sla = mean_for('eaes', 'sla_violation_rate')
    hpa_sla = mean_for('hpa_formula', 'sla_violation_rate')
    eaes_rh = mean_for('eaes', 'replica_hours')
    hpa_rh = mean_for('hpa_formula', 'replica_hours')
    return {
        'runs': len(bundle['summaries']),
        'seeds': len(bundle['manifest'].get('seeds', [])) if bundle['manifest'] else 0,
        'workloads': len(bundle['manifest'].get('workloads', [])) if bundle['manifest'] else 0,
        'strategies': len(bundle['manifest'].get('strategies', [])) if bundle['manifest'] else 0,
        'eaes_energy_per_served_j': eaes_energy,
        'hpa_energy_per_served_j': hpa_energy,
        'energy_ratio_vs_hpa': (eaes_energy / hpa_energy) if eaes_energy and hpa_energy else None,
        'eaes_sla_violation_rate': eaes_sla,
        'hpa_sla_violation_rate': hpa_sla,
        'static_drop_rate': static_drop,
        'eaes_replica_hours': eaes_rh,
        'hpa_replica_hours': hpa_rh,
        'replica_ratio_vs_hpa': (eaes_rh / hpa_rh) if eaes_rh and hpa_rh else None,
    }


def _research_chart_data(bundle):
    desc = bundle['tables'].get('descriptive', [])
    workloads = bundle['manifest'].get('workloads', []) if bundle['manifest'] else []
    strategies = bundle['manifest'].get('strategies', RESEARCH_STRATEGIES) if bundle['manifest'] else RESEARCH_STRATEGIES
    metrics = {}
    for metric in (
        'energy_per_served_request_j', 'energy_per_offered_request_j',
        'sla_violation_rate', 'replica_hours', 'drop_rate',
        'p95_latency_ms', 'scaling_events', 'oscillations',
    ):
        metrics[metric] = {
            workload: [
                (_table_lookup(desc, metric, workload, strategy) or {}).get('mean')
                for strategy in strategies
            ]
            for workload in workloads
        }
    return {
        'labels': workloads,
        'strategies': strategies,
        'strategy_labels': [RESEARCH_STRATEGY_LABELS.get(s, s) for s in strategies],
        'metrics': metrics,
        'metric_labels': RESEARCH_METRIC_LABELS,
    }


def _research_choices(bundle):
    manifest = bundle['manifest'] or {}
    return {
        'workloads': manifest.get('workloads', []),
        'strategies': manifest.get('strategies', RESEARCH_STRATEGIES),
        'strategy_labels': {
            s: RESEARCH_STRATEGY_LABELS.get(s, s)
            for s in manifest.get('strategies', RESEARCH_STRATEGIES)
        },
        'seeds': manifest.get('seeds', []),
        'default_workload': (manifest.get('workloads') or ['steady'])[0],
        'default_strategy': 'eaes' if 'eaes' in manifest.get('strategies', []) else 'static',
    }


def _raw_run_file(workload, strategy, seed):
    run_dir = _research_run_dir()
    if not run_dir:
        return None
    return os.path.join(run_dir, f'{workload}_seed{int(seed)}_{strategy}.jsonl')


def _read_jsonl(path):
    rows = []
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except (FileNotFoundError, OSError):
        return []
    return rows


def _num(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _mean_or_none(values):
    vals = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return round(sum(vals) / len(vals), 6) if vals else None


def _summary_mean(bundle, workload, strategy, field):
    vals = [
        r.get(field) for r in bundle['summaries']
        if r.get('workload') == workload and r.get('strategy') == strategy
        and isinstance(r.get(field), (int, float)) and not isinstance(r.get(field), bool)
    ]
    return round(sum(vals) / len(vals), 6) if vals else None


def _selected_summary(bundle, workload, strategy):
    fields = [
        'energy_per_served_request_j', 'energy_per_offered_request_j',
        'drop_rate', 'sla_violation_rate', 'replica_hours',
        'p95_latency_ms', 'scaling_events', 'oscillations',
        'served_requests', 'offered_requests', 'avg_ready_replicas',
        'measurement_energy_j',
    ]
    out = {field: _summary_mean(bundle, workload, strategy, field) for field in fields}
    out['n_runs'] = len([
        r for r in bundle['summaries']
        if r.get('workload') == workload and r.get('strategy') == strategy
    ])
    return out


def _time_series_from_rows(rows_by_seed):
    if not rows_by_seed:
        return {}
    length = min(len(rows) for rows in rows_by_seed)
    if length == 0:
        return {}

    def avg(field):
        values = []
        for i in range(length):
            vals = [_num(rows[i].get(field)) for rows in rows_by_seed]
            vals = [v for v in vals if v is not None]
            values.append(round(sum(vals) / len(vals), 6) if vals else None)
        return values

    observed = avg('observed_rate_rps')
    forecast = avg('forecast_rps')
    actual_forward = [
        observed[i + 2] if i + 2 < len(observed) else None
        for i in range(length)
    ]
    return {
        'time_s': avg('time_s'),
        'offered_rps': observed,
        'observed_rps': observed,
        'forecast_rps': forecast,
        'actual_forward_rps': actual_forward,
        'cpu_percent': [
            (round(v * 100.0, 4) if v is not None else None)
            for v in avg('cpu_util')
        ],
        'ready_replicas': avg('ready_replicas'),
        'desired_replicas': avg('desired_replicas'),
        'pending_replicas': avg('pending_replicas'),
        'p95_latency_ms': avg('p95_latency_ms'),
        'backlog_requests': avg('backlog_requests'),
        'energy_per_tick_j': avg('node_energy_j'),
        'cumulative_energy_j': avg('cumulative_energy_j'),
        'sla_margin': avg('sla_margin'),
    }


def research_timeseries_payload(workload=None, strategy=None, seed=None):
    bundle = _load_research_bundle()
    choices = _research_choices(bundle)
    workload = workload or choices['default_workload']
    strategy = strategy or choices['default_strategy']
    payload = {
        'available': False,
        'error': None,
        'workload': workload,
        'strategy': strategy,
        'seed': seed,
        'choices': choices,
        'series': {},
        'summary': {},
    }
    if not bundle['available']:
        payload['error'] = bundle['error'] or 'No generated run is available.'
        return payload
    if workload not in choices['workloads']:
        payload['error'] = f'Unknown workload: {workload}'
        return payload
    if strategy not in choices['strategies']:
        payload['error'] = f'Unknown strategy: {strategy}'
        return payload
    seeds = choices['seeds']
    if seed in (None, '', 'all'):
        requested_seeds = list(seeds)
        payload['seed'] = 'all'
    else:
        try:
            seed_int = int(seed)
        except (TypeError, ValueError):
            payload['error'] = f'Invalid seed: {seed}'
            return payload
        if seed_int not in seeds:
            payload['error'] = f'Unknown seed: {seed_int}'
            return payload
        requested_seeds = [seed_int]
    rows_by_seed = []
    for s in requested_seeds:
        path = _raw_run_file(workload, strategy, s)
        rows = _read_jsonl(path) if path else []
        if rows:
            rows_by_seed.append(rows)
    if not rows_by_seed:
        payload['error'] = 'Raw per-tick logs are missing for this selection.'
        return payload
    payload['available'] = True
    payload['seeds_used'] = requested_seeds
    payload['series'] = _time_series_from_rows(rows_by_seed)
    payload['summary'] = _selected_summary(bundle, workload, strategy)
    payload['strategy_label'] = RESEARCH_STRATEGY_LABELS.get(strategy, strategy)
    payload['execution_mode'] = (bundle['manifest'] or {}).get('execution_mode')
    return payload


def research_controller_trace_payload(workload=None, strategy=None, seed=None):
    bundle = _load_research_bundle()
    choices = _research_choices(bundle)
    workload = workload or choices['default_workload']
    strategy = strategy or choices['default_strategy']
    payload = {
        'available': False,
        'error': None,
        'workload': workload,
        'strategy': strategy,
        'seed': seed or (choices['seeds'][0] if choices['seeds'] else None),
        'choices': choices,
        'latest': {},
        'history': [],
        'behavior': {},
        'series': {},
        'summary': {},
    }
    if not bundle['available']:
        payload['error'] = bundle['error'] or 'No generated run is available.'
        return payload
    if workload not in choices['workloads']:
        payload['error'] = f'Unknown workload: {workload}'
        return payload
    if strategy not in choices['strategies']:
        payload['error'] = f'Unknown strategy: {strategy}'
        return payload
    try:
        seed_int = int(payload['seed'])
    except (TypeError, ValueError):
        payload['error'] = f'Invalid seed: {payload["seed"]}'
        return payload
    if seed_int not in choices['seeds']:
        payload['error'] = f'Unknown seed: {seed_int}'
        return payload
    path = _raw_run_file(workload, strategy, seed_int)
    rows = _read_jsonl(path) if path else []
    if not rows:
        payload['error'] = 'Raw per-tick log is missing for this selection.'
        return payload

    latest = rows[-1]
    rule = str(latest.get('rule_fired') or '')
    blocking_tokens = (
        'cooldown', 'min_dwell', 'stabilization', 'warmup_no_scaledown',
    )
    if strategy == 'static':
        cooldown_status = 'Fixed replicas; no cooldown rule applies.'
    elif any(token in rule for token in blocking_tokens):
        cooldown_status = f'Blocking: {latest.get("decision_reason") or rule}'
    else:
        cooldown_status = 'Not blocking at the final tick.'
    history = []
    for row in reversed(rows):
        if row.get('scaling_action') in ('up', 'down'):
            history.append({
                'time_s': row.get('time_s'),
                'action': row.get('scaling_action'),
                'from_replicas': (row.get('decision_details') or {}).get('current_replicas'),
                'to_replicas': row.get('desired_replicas'),
                'rule': row.get('rule_fired'),
                'reason': row.get('decision_reason'),
                'observed_rps': row.get('observed_rate_rps'),
                'cpu_percent': round((_num(row.get('cpu_util')) or 0.0) * 100.0, 3),
            })
        if len(history) >= 20:
            break
    behavior_counts = Counter(str(r.get('rule_fired') or 'unknown') for r in rows)
    action_counts = Counter(str(r.get('scaling_action') or 'hold') for r in rows)
    payload.update({
        'available': True,
        'execution_mode': (bundle['manifest'] or {}).get('execution_mode'),
        'strategy_label': RESEARCH_STRATEGY_LABELS.get(strategy, strategy),
        'latest': {
            'time_s': latest.get('time_s'),
            'tick': latest.get('tick'),
            'warmup': latest.get('warmup'),
            'observed_rps': latest.get('observed_rate_rps'),
            'arrival_rate_rps': latest.get('arrival_rate_rps'),
            'cpu_percent': round((_num(latest.get('cpu_util')) or 0.0) * 100.0, 3),
            'ready_replicas': latest.get('ready_replicas'),
            'desired_replicas': latest.get('desired_replicas'),
            'pending_replicas': latest.get('pending_replicas'),
            'pending_after': latest.get('pending_replicas_after'),
            'backlog_requests': latest.get('backlog_requests'),
            'forecast_rps': latest.get('forecast_rps'),
            'sla_margin': latest.get('sla_margin'),
            'scaling_action': latest.get('scaling_action'),
            'rule_fired': latest.get('rule_fired'),
            'decision_reason': latest.get('decision_reason'),
            'decision_details': latest.get('decision_details') or {},
            'cooldown_status': cooldown_status,
            'energy_per_tick_j': latest.get('node_energy_j'),
        },
        'history': history,
        'behavior': {
            'action_counts': dict(action_counts),
            'rule_counts': dict(behavior_counts.most_common(8)),
            'scaling_events': sum(v for k, v in action_counts.items() if k in ('up', 'down')),
            'ticks': len(rows),
        },
        'series': _time_series_from_rows([rows]),
        'summary': _selected_summary(bundle, workload, strategy),
    })
    return payload


def research_results_payload():
    bundle = _load_research_bundle()
    payload = {
        'available': bundle['available'],
        'error': bundle['error'],
        'run': {
            'run_id': (bundle['manifest'] or {}).get('run_id'),
            'git_commit': (bundle['manifest'] or {}).get('git_commit'),
            'execution_mode': (bundle['manifest'] or {}).get('execution_mode'),
            'energy_scenario': (bundle['manifest'] or {}).get('energy_scenario'),
            'config_hash': (bundle['manifest'] or {}).get('config_hash'),
            'seeds': (bundle['manifest'] or {}).get('seeds', []),
            'workloads': (bundle['manifest'] or {}).get('workloads', []),
            'strategies': (bundle['manifest'] or {}).get('strategies', []),
            'n_runs': (bundle['manifest'] or {}).get('n_runs'),
            'started_at': (bundle['manifest'] or {}).get('started_at'),
            'ended_at': (bundle['manifest'] or {}).get('ended_at'),
        },
        'kpis': _research_kpis(bundle),
        'choices': _research_choices(bundle),
        'descriptive_primary': _primary_descriptive(bundle),
        'chart': _research_chart_data(bundle),
        'paired_primary': [
            row for row in bundle['tables'].get('paired', [])
            if row.get('metric') in PRIMARY_RESEARCH_METRICS
        ],
        'friedman_primary': [
            row for row in bundle['tables'].get('friedman', [])
            if row.get('metric') in PRIMARY_RESEARCH_METRICS
        ],
        'cluster': {
            'available': bool(bundle['cluster_rows']),
            'aggregate': _cluster_aggregate(bundle['cluster_rows']),
            'rows': bundle['cluster_rows'],
            'manifest': bundle['cluster_manifest'],
        },
        'diagnostic_findings': (bundle['diagnostic'] or {}).get('findings', []),
        'extensions': {
            'oracle': os.path.exists(os.path.join(RESULTS_DIR, 'extension', 'oracle', 'ORACLE.md')),
            'startup_sweep': os.path.exists(os.path.join(RESULTS_DIR, 'extension', 'startup_sweep', 'STARTUP_SWEEP.md')),
            'seed30': os.path.exists(os.path.join(RESULTS_DIR, 'extension', 'seed30', 'RESULTS_30SEED.md')),
            'energy_sensitivity': os.path.exists(os.path.join(RESULTS_DIR, 'extension', 'energy_sensitivity', 'ENERGY_SENSITIVITY.md')),
            'pareto': os.path.exists(os.path.join(RESULTS_DIR, 'extension', 'energy_vs_drop', 'README.md')),
            'hpa_replay': os.path.exists(os.path.join(RESULTS_DIR, 'extension', 'hpa_replay', 'HPA_REPLAY.md')),
            'forecast_accuracy': os.path.exists(os.path.join(RESULTS_DIR, 'tables', 'forecast_accuracy.md')),
        },
        'warnings': [
            'All energy is modelled, not measured.',
            'Static replicas can show low energy per served request while dropping traffic; read drop/SLA columns together.',
            'The HPA-formula baseline is a simulation of the replica formula, not the Kubernetes HPA controller.',
            'The real-cluster validation is separate from the paired simulation.',
            'Optimality and energy claims are restricted to the simulated design and modelled power assumptions.',
        ],
    }
    return payload


def research_diagnostic_payload():
    bundle = _load_research_bundle()
    diagnostic = bundle['diagnostic'] or {}
    return {
        'available': bool(diagnostic),
        'run': (bundle['manifest'] or {}).get('run_id'),
        'git_commit': (bundle['manifest'] or {}).get('git_commit'),
        'execution_mode': (bundle['manifest'] or {}).get('execution_mode'),
        'choices': _research_choices(bundle),
        'comparisons': diagnostic.get('comparisons', []),
        'forecast_comparison': diagnostic.get('forecast_comparison', []),
        'rule_rows': diagnostic.get('rule_rows', []),
        'findings': diagnostic.get('findings', []),
        'conservation_max_error_j': diagnostic.get('nominal_conservation_max_error_j'),
        'cluster': {
            'aggregate': _cluster_aggregate(bundle['cluster_rows']),
            'manifest': bundle['cluster_manifest'],
        },
        'forecasting_eval': bundle['tables'].get('forecasting', []),
        'limitations': [
            'Energy is modelled, never measured.',
            'EAES is EAES-inspired, not a reproduction of Li et al. (2025).',
            'Simulation findings do not establish production behaviour.',
        ],
    }


def research_methodology_payload():
    configs = {}
    for name in ('experiment', 'simulation', 'energy', 'sla', 'strategies', 'extensions'):
        path = os.path.join(CONFIG_DIR, f'{name}.yaml')
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                configs[name] = yaml.safe_load(fh) if yaml else {}
        except (FileNotFoundError, OSError):
            configs[name] = {}
    manifest = _load_research_bundle()['manifest'] or {}
    dataset_hashes = {
        'experiment_results_v2.json': '6279D01DC92D9C4FBE2EBB2C5BA0C12A7DA3EA7CA985E9FA762E88A11F34234E',
        'experiment_results.json': 'C4BF4BFFFA8D0242395D2A2FB966C16DBC4884078BE7E82395E778EF87968451',
    }
    return {
        'configs': configs,
        'config_hashes': manifest.get('config_hashes', {}),
        'combined_config_hash': manifest.get('config_hash'),
        'run_id': manifest.get('run_id'),
        'git_commit': manifest.get('git_commit'),
        'execution_mode': manifest.get('execution_mode'),
        'dataset_hashes': dataset_hashes,
        'strategy_distinctions': {
            'static': 'Fixed replicas; no feedback.',
            'cpu_threshold': 'Legacy 80/30 threshold with 5% hysteresis and cooldowns; not HPA.',
            'hpa_formula': 'Simulated Kubernetes HPA replica formula; not the cluster HPA controller.',
            'eaes': 'SLA-first lexicographic controller with a utilization margin, cooldown, and stabilization.',
            'forecasting_eaes': 'EAES with a Holt forecast over the startup horizon.',
        },
        'statistics': [
            'Paired by workload and seed.',
            '5,000-resample bootstrap 95% CIs.',
            'Wilcoxon signed-rank with Holm correction.',
            'Friedman test and Nemenyi critical difference.',
            "Cliff's delta effect size.",
        ],
        'limitations': [
            'Single-node simulation assumptions; no measured power.',
            'Kubernetes validation is a separate single-node Minikube run.',
            'No reproduction of Li et al. (2025); full text was unavailable.',
            'The original 27-row dataset is pseudo-replicated and is not used for inference.',
            'The HPA formula is not the native Kubernetes HPA controller.',
            'Only three repetitions per cluster mode were recorded.',
        ],
        'architecture': {
            'summary': 'A Flask service exposes the dashboard; a stdlib simulation engine generates paired runs; analysis scripts consume run summaries and raw ticks; Kubernetes validation is a separate recorded path.',
            'layers': [
                {
                    'name': 'Flask application',
                    'path': 'app.py',
                    'responsibility': 'Three-page dashboard, preserved legacy routes, research APIs, and demo workload endpoints.',
                },
                {
                    'name': 'Configuration and provenance',
                    'path': 'eaes/config.py; configs/*.yaml',
                    'responsibility': 'Validated YAML configuration, canonical hashes, git state, and atomic JSON writes.',
                },
                {
                    'name': 'Workload generation',
                    'path': 'eaes/workload.py',
                    'responsibility': 'Six deterministic workload traces per seed with SHA-256 trace hashes.',
                },
                {
                    'name': 'Simulation backend',
                    'path': 'eaes/backend.py',
                    'responsibility': 'Bounded queue, pod capacity, node placement, startup delay, and capacity accounting.',
                },
                {
                    'name': 'Autoscaling engine',
                    'path': 'eaes/strategies.py; eaes/forecast.py',
                    'responsibility': 'Five confirmatory controllers plus an extension-only oracle.',
                },
                {
                    'name': 'Energy estimator',
                    'path': 'eaes/energy.py',
                    'responsibility': 'Node-level P_idle/P_max/PUE model with pod attribution and conservation checks.',
                },
                {
                    'name': 'Experiment engine',
                    'path': 'eaes/engine.py; experiments/run_v3.py',
                    'responsibility': 'Paired workload x seed x strategy runs, raw tick logs, summaries, and manifests.',
                },
                {
                    'name': 'Analysis pipeline',
                    'path': 'analysis/',
                    'responsibility': 'Headline tables, paired tests, diagnostics, forecast accuracy, sensitivity, and extension reports.',
                },
                {
                    'name': 'Kubernetes validation',
                    'path': 'experiments/run_cluster_validation.py; kubernetes/',
                    'responsibility': 'Separate real Minikube observations with modelled energy from measured node CPU.',
                },
            ],
        },
        'execution_flow': [
            'Load and validate YAML configuration; record canonical config hashes and git state.',
            'Generate or load deterministic traces for each workload and seed; verify trace hashes.',
            'Run each strategy on the same trace and seed, recording every control interval as JSONL.',
            'Aggregate ticks to run-level metrics; never treat ticks as independent observations.',
            'Compute descriptive intervals, paired differences, Holm-adjusted Wilcoxon tests, Friedman/Nemenyi tests, and effect sizes.',
            'Render the confirmatory results and diagnostics from generated artifacts; label extensions separately.',
        ],
        'workload_generation': {
            'classes': ['steady', 'light', 'medium', 'heavy', 'variable', 'bursty'],
            'method': 'Seeded arrival counts per 5 s interval from documented class parameters; identical traces are reused across strategies.',
            'seeds_confirmatory': 10,
            'seeds_extension': 30,
            'trace_root': 'traces/',
        },
        'metrics_collection': [
            'Offered, served, and dropped requests per tick and cumulatively.',
            'CPU utilisation, ready/desired/pending replicas, backlog, and p95 latency.',
            'Estimated node and pod energy per tick, with conservation error.',
            'Scaling action, rule fired, reason, forecast, SLA margin, and decision details.',
            'Run-level aggregates: energy per served/offered request, drop rate, SLA violation rate, replica-hours, scaling events, oscillations.',
        ],
        'energy_estimator': {
            'formula': 'P_node = P_idle + (P_max - P_idle) * CPU_util; E_node = P_node * dt * PUE',
            'idle_w': 150.0,
            'max_w': 500.0,
            'pue': 1.2,
            'sensitivity': 'low/nominal/high power and PUE 1.0-1.6 under results/extension/energy_sensitivity/',
            'warning': 'All energy values are model estimates, not physical power measurements.',
        },
        'kubernetes_integration': {
            'backend': 'KubernetesCluster in eaes/backend.py uses kubectl; the installed Python kubernetes package is broken.',
            'manifests': ['kubernetes/deployment.yaml', 'kubernetes/service.yaml', 'kubernetes/hpa.yaml'],
            'validation_script': 'experiments/run_cluster_validation.py',
            'native_hpa': 'autoscaling/v2, CPU target 50%, min 1, max 10.',
            'recorded_results': 'results/cluster_validation/ (3 static and 3 native-HPA repetitions; energy modelled from node CPU).',
        },
        'api_endpoints': [
            {'path': '/', 'description': 'Results dashboard with filters, KPIs, time series, and energy-vs-drop comparison.'},
            {'path': '/eaes-diagnostics', 'description': 'EAES decomposition, controller trace, forecast error, and rule diagnostics.'},
            {'path': '/methodology', 'description': 'System overview, execution flow, configuration, statistics, and limitations.'},
            {'path': '/api/v1/research/results', 'description': 'Confirmatory results, KPIs, chart series, and cluster aggregate.'},
            {'path': '/api/v1/research/diagnostic', 'description': 'Diagnostic decomposition, rule evidence, and forecast ablation.'},
            {'path': '/api/v1/research/timeseries?workload=&strategy=&seed=', 'description': 'Backend series from raw confirmatory tick logs; seed=all averages runs.'},
            {'path': '/api/v1/research/controller-trace?workload=&strategy=&seed=', 'description': 'Latest controller state, decision, cooldown status, history, actual vs forecast.'},
            {'path': '/api/v1/research/methodology', 'description': 'Configuration, architecture, provenance, and limitations.'},
            {'path': '/api/v1/research/cluster', 'description': 'Separate Kubernetes validation records.'},
            {'path': '/api/v1/research/tables/<name>', 'description': 'Whitelisted generated CSV table.'},
        ],
        'execution_modes': {
            'simulation': 'Paired discrete-time simulation; every confirmatory result on the dashboard.',
            'kubernetes_validation': 'Separate single-node Minikube observations; replica counts and request outcomes are real, node energy is modelled.',
            'dashboard': 'Read-only views over committed/generated artifacts; no live cluster data is implied.',
        },
        'extension_artifacts': {
            'oracle': 'results/extension/oracle/ORACLE.md',
            'startup_sweep': 'results/extension/startup_sweep/STARTUP_SWEEP.md',
            'seed30': 'results/extension/seed30/RESULTS_30SEED.md',
            'energy_sensitivity': 'results/extension/energy_sensitivity/ENERGY_SENSITIVITY.md',
            'energy_vs_drop': 'results/extension/energy_vs_drop/README.md',
            'hpa_replay': 'results/extension/hpa_replay/HPA_REPLAY.md',
            'forecast_accuracy': 'results/tables/forecast_accuracy.md',
        },
        'reproduce_commands': [
            'python analysis/verify_dataset_hashes.py',
            'python -m analysis.analyze',
            'python -m analysis.make_headline_table',
            'python -m analysis.diagnose',
            'python -m analysis.forecast_accuracy',
            'python -m experiments.run_extensions',
            'python -m analysis.energy_sensitivity',
            'python -m analysis.energy_vs_drop',
            'python -m analysis.hpa_replay',
            'python -m pytest -q',
        ],
    }


# ---------------------------------------------------------------------------
# Dashboard routes (three main pages; legacy routes remain HTML 200)
# ---------------------------------------------------------------------------
@app.route("/")
def dashboard():
    """Main research results dashboard."""
    return render_template(
        'research/results.html',
        active='results',
        data=research_results_payload(),
        summary=dataset_summary(),
    )


@app.route("/eaes-diagnostics")
def eaes_diagnostics():
    return render_template(
        'research/diagnostics.html',
        active='diagnostics',
        data=research_diagnostic_payload(),
        summary=dataset_summary(),
    )


@app.route("/methodology")
def methodology():
    return render_template(
        'research/methodology.html',
        active='methodology',
        data=research_methodology_payload(),
        summary=dataset_summary(),
    )


def _compatibility_view(title, target, target_label):
    return render_template(
        'research/compatibility.html',
        active='legacy',
        title=title,
        target=target,
        target_label=target_label,
        summary=dataset_summary(),
    )


@app.route("/autoscaling-comparison")
def autoscaling_comparison():
    return _compatibility_view('Autoscaling comparison', '/', 'Results dashboard')


@app.route("/energy-analysis")
def energy_analysis():
    return _compatibility_view('Energy analysis', '/', 'Results dashboard')


@app.route("/performance-analysis")
def performance_analysis():
    return _compatibility_view('Performance analysis', '/', 'Results dashboard')


@app.route("/experiment-explorer")
def experiment_explorer():
    return _compatibility_view('Experiment explorer', '/', 'Results dashboard')


@app.route("/research-methodology")
def research_methodology():
    return render_template(
        'research/methodology.html',
        active='methodology',
        data=research_methodology_payload(),
        summary=dataset_summary(),
        legacy_notice=True,
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
        "replicas": 1,  # local demo process indicator, not a cluster reading
        "execution_mode": "simulation-dashboard",
        "dashboard_pages": ["/", "/eaes-diagnostics", "/methodology"],
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
        "application": "Energy-Aware Autoscaling Research Framework",
        "framework": "Discrete-time simulation; separate Minikube validation",
        "microservice": "Flask demo service and research dashboard",
        "workload": current_workload,
        "cpu_percent": round(simulated_cpu_utilization, 1),
        "memory_percent": round(random.uniform(40, 80), 1),
        "supported_algorithms": [
            "static: fixed replica provisioning",
            "cpu_threshold: legacy 80/30 controller with hysteresis and cooldowns",
            "hpa_formula: simulated Kubernetes HPA replica formula",
            "eaes: EAES-inspired SLA-first controller",
            "forecasting_eaes: EAES with a Holt forecast over startup delay",
        ],
        "energy_estimation": {
            "method": "Node-level CPU-utilization model with PUE (estimate, not measurement)",
            "formula": "P_node = P_idle + (P_max - P_idle) * u; E_node = P_node * dt * PUE",
            "parameters": {"P_idle_W": 150.0, "P_max_W": 500.0, "PUE": 1.2, "tick_s": 5},
            "note": "Energy values are modelled from CPU utilisation, not direct hardware power measurements",
        },
        "dataset": dataset_summary()['file'],
        "experiment_count": len(EXPERIMENT_RESULTS),
        "research_run": (_load_research_bundle()['manifest'] or {}).get('run_id'),
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


@app.route("/api/v1/research/results")
def research_results_api():
    return jsonify(research_results_payload())


@app.route("/api/v1/research/diagnostic")
def research_diagnostic_api():
    return jsonify(research_diagnostic_payload())


@app.route("/api/v1/research/timeseries")
def research_timeseries_api():
    payload = research_timeseries_payload(
        workload=request.args.get('workload'),
        strategy=request.args.get('strategy'),
        seed=request.args.get('seed', 'all'),
    )
    status = 200 if payload.get('available') else 400
    return jsonify(payload), status


@app.route("/api/v1/research/controller-trace")
def research_controller_trace_api():
    payload = research_controller_trace_payload(
        workload=request.args.get('workload'),
        strategy=request.args.get('strategy'),
        seed=request.args.get('seed'),
    )
    status = 200 if payload.get('available') else 400
    return jsonify(payload), status


@app.route("/api/v1/research/methodology")
def research_methodology_api():
    return jsonify(research_methodology_payload())


@app.route("/api/v1/research/cluster")
def research_cluster_api():
    bundle = _load_research_bundle()
    return jsonify({
        "execution_mode": "kubernetes_validation",
        "available": bool(bundle['cluster_rows']),
        "aggregate": _cluster_aggregate(bundle['cluster_rows']),
        "rows": bundle['cluster_rows'],
        "manifest": bundle['cluster_manifest'],
        "energy_note": "Modelled from measured node CPU; not measured power.",
    })


@app.route("/api/v1/research/tables/<name>")
def research_table_api(name):
    allowed = {
        'descriptive', 'paired', 'friedman', 'nemenyi', 'forecasting', 'sensitivity',
        'headline', 'paired_headline',
    }
    if name not in allowed:
        return jsonify({"error": "unknown table", "allowed": sorted(allowed)}), 404
    bundle = _load_research_bundle()
    rows = bundle['tables'].get(name, [])
    return jsonify({
        "table": name,
        "rows": rows,
        "columns": list(rows[0].keys()) if rows else [],
        "run_id": (bundle['manifest'] or {}).get('run_id'),
    })


@app.route("/status")
def status():
    """Service status endpoint."""
    return jsonify({
        "status": "operational",
        "workload": current_workload,
        "cpu_utilization": round(simulated_cpu_utilization, 1),
        "uptime_s": round(time.time() - app_start_time, 1),
        "flask_version": "3.x",
        "mode": "simulation for the confirmatory experiment; separate Minikube validation",
        "experiment_count": len(EXPERIMENT_RESULTS),
        "dataset": DATASET_FILE,
        "docker_status": "Docker Desktop Linux engine available (verified for validation)",
        "kubernetes_status": "Minikube single-node validation completed; not the confirmatory environment",
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
    print("  GET  /                  - paired results")
    print("  GET  /eaes-diagnostics  - EAES decomposition and ablation")
    print("  GET  /methodology       - assumptions and provenance")
    print("  Legacy HTML routes: /autoscaling-comparison, /energy-analysis,")
    print("                      /performance-analysis, /experiment-explorer,")
    print("                      /research-methodology")
    print("API:")
    print("  GET  /api/status | /health | /ready | /info")
    print("  GET  /workload/status | POST /workload/change")
    print("  GET  /cpu/light | /cpu/intensive | /metrics")
    print("  GET  /api/v1/experiments | /api/v1/research-papers")
    print("  GET  /api/v1/research/results | /diagnostic | /methodology | /cluster")
    print("  GET  /api/v1/research/timeseries | /controller-trace")
    print("  GET  /status | /controller/status")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, threaded=True)

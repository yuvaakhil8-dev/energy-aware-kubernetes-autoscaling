#!/usr/bin/env python3
"""Live demonstration of the Energy-Aware Autoscaling Framework."""
import json
import sys
import urllib.request
import subprocess
import time

PROJECT_ROOT = Path(__file__).resolve().parent

# Start Flask app in background
proc = subprocess.Popen(
    [sys.executable, 'app.py'],
    cwd=PROJECT_ROOT,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
time.sleep(3)

try:
    print('=== LIVE DEMONSTRATION OF FLASK MICROSERVICE ===')
    print()

    # Test all endpoints
    endpoints = [
        ('GET', '/', ''),
        ('GET', '/health', ''),
        ('GET', '/metrics', ''),
        ('GET', '/status', ''),
        ('GET', '/info', ''),
        ('GET', '/api/v1/experiments', ''),
        ('GET', '/api/v1/research-papers', ''),
        ('GET', '/workload/status', ''),
        ('GET', '/controller/status', ''),
    ]

    for method, path, _ in endpoints:
        try:
            url = f'http://localhost:5000{path}'
            req = urllib.request.Request(url, method=method)
            response = urllib.request.urlopen(url, timeout=5)
            data = response.read()
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type or data.startswith(b'{'):
                parsed = json.loads(data)
                keys = list(parsed.keys())[:3]
                print(f'{method} {path:30s} -> JSON keys: {keys}')
            else:
                text = data.decode('utf-8', errors='replace')[:120]
                print(f'{method} {path:30s} -> {text}')
        except Exception as e:
            print(f'{method} {path:30s} -> ERROR: {e}')

    print()
    print('=== EXPERIMENT DATA ===')
    with open(PROJECT_ROOT / 'experiment_results.json', 'r') as f:
        data = json.load(f)
    print(f'Total experiments: {len(data)}')
    modes = set(r.get('mode') for r in data)
    workloads = set(r.get('workload') for r in data)
    print(f'Modes: {sorted(modes)}')
    print(f'Workloads: {sorted(workloads)}')

    print()
    print('=== FIRST EXAMPLE EXPERIMENT ===')
    first = data[0]
    for k, v in first.items():
        if k != 'samples':
            print(f'  {k}: {v}')

    print()
    print('=== CONTROLLER STATUS ===')
    try:
        req = urllib.request.Request('http://localhost:5000/controller/status')
        response = urllib.request.urlopen(req, timeout=5)
        status = json.loads(response.read())
        cr = status.get('current_replicas')
        ac = status.get('avg_cpu')
        epe = status.get('energy_per_request_estimate')
        sc = status.get('sla_compliant')
        ds = status.get('docker_status')
        ks = status.get('kubernetes_status')
        print(f'Current replicas: {cr}')
        print(f'Avg CPU: {ac}%')
        print(f'Energy per request: {epe} J')
        print(f'SLA compliant: {sc}')
        print(f'Docker status: {ds}')
        print(f'K8s status: {ks}')
    except Exception as e:
        print(f'Controller status error: {e}')

finally:
    # Stop the Flask app
    proc.terminate()
    proc.wait()

print()
print('=== DEMONSTRATION COMPLETE ===')
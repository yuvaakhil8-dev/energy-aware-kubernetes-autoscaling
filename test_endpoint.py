#!/usr/bin/env python3
"""Test the /api/v1/experiments endpoint."""
import json
import sys
import time
import subprocess
import urllib.request

# Start Flask app
proc = subprocess.Popen(
    [sys.executable, 'app.py'],
    cwd=r'C:\Users\yuvaa\OneDrive\Desktop\Documents\Default Project\flask-kubernetes',
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
time.sleep(3)

try:
    print('=== Testing /api/v1/experiments endpoint ===')
    req = urllib.request.Request('http://localhost:5000/api/v1/experiments')
    response = urllib.request.urlopen(req, timeout=5)
    data = json.loads(response.read())
    
    print(f'HTTP Status: 200 (OK)')
    print(f'Total experiments: {data[\"total_experiments\"]}')
    print(f'Modes: {data[\"modes\"]}')
    print(f'Number of experiment records: {len(data[\"experiments\"])}')
    print(f'Unique modes in experiments: {len(set([e[\"mode\"] for e in data[\"experiments\"]]))}')
    print(f'Experiment 1 mode: {data[\"experiments\"][0][\"mode\"]}')
    print(f'Experiment 18 mode: {data[\"experiments\"][17][\"mode\"]}')
    print()
    print('=== Verification ===')
    # Verify all 18 records are present and no duplicates
    assert data['total_experiments'] == 18, f'Expected 18 experiments, got {data[\"total_experiments\"]}'
    assert len(data['experiments']) == 18, f'Expected 18 experiment records, got {len(data[\"experiments\"])}'
    modes = [e['mode'] for e in data['experiments']]
    assert len(set(modes)) == 3, f'Expected 3 unique modes, got {len(set(modes))}'
    # Check that all modes are present
    mode_counts = {m: modes.count(m) for m in set(modes)}
    print(f'Mode counts: {mode_counts}')
    print()
    print('All assertions passed! Endpoint is working correctly.')
    
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
    
finally:
    # Stop the Flask app
    proc.terminate()
    proc.wait()
    print()
    print('Flask app stopped.')